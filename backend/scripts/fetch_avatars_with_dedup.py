#!/usr/bin/env python3
"""
Fetch avatar images from Signal's CDN with deduplication against S3 manifest.

This script:
1. Extracts remoteAvatarUrl and profileKey from user_metadata.sql
2. Checks S3 manifest (signal_avatars.json) against previous exports
3. Compares JPEG encoding similarity with existing avatars
4. Only keeps new/updated avatars (>10% different)
5. Deletes duplicate avatars

WARNING: This may violate Signal's Terms of Service. Use at your own risk.
"""

import re
import json
import sys
import os
import base64
import hashlib
import hmac
import csv
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from Crypto.Cipher import AES
import requests
from urllib.parse import urljoin
import urllib3
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

# Disable SSL warnings (for testing only)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Signal CDN base URL
CDN_BASE_URL = "https://cdn.signal.org/"

# Similarity threshold (10% difference = 0.9 similarity)
SIMILARITY_THRESHOLD = 0.9

def parse_sql_row(row_str):
    """Parse a single SQL row and extract fields."""
    fields = []
    current_field = ""
    in_quotes = False
    escape_next = False
    
    i = 0
    while i < len(row_str):
        char = row_str[i]
        
        if escape_next:
            current_field += char
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            escape_next = True
            current_field += char
            i += 1
            continue
        
        if char == "'":
            if not in_quotes:
                in_quotes = True
                current_field += char
            else:
                # Check if it's an escaped quote ('') or end of field
                if i + 1 < len(row_str) and row_str[i + 1] == "'":
                    # Escaped quote
                    current_field += "''"
                    i += 2
                    continue
                else:
                    # End of quoted field
                    in_quotes = False
                    current_field += char
            i += 1
            continue
        
        if not in_quotes:
            if char == ',':
                # End of field
                val = current_field.strip()
                # Remove surrounding quotes and unescape
                if val.startswith("'") and val.endswith("'"):
                    val = val[1:-1].replace("''", "'")
                if val.upper() == 'NULL':
                    fields.append(None)
                else:
                    fields.append(val)
                current_field = ""
                i += 1
                continue
            elif char in (' ', '\n', '\t'):
                # Skip whitespace outside quotes
                i += 1
                continue
        
        current_field += char
        i += 1
    
    # Add last field
    if current_field.strip():
        val = current_field.strip()
        if val.startswith("'") and val.endswith("'"):
            val = val[1:-1].replace("''", "'")
        if val.upper() == 'NULL':
            fields.append(None)
        else:
            fields.append(val)
    
    return fields

def load_s3_manifest(manifest_path):
    """Load S3 manifest JSON file. Returns dict mapping UUID to image path/URL."""
    if not os.path.exists(manifest_path):
        print(f"Warning: Manifest file not found: {manifest_path}")
        return {}
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        # Convert manifest to UUID -> image_path mapping
        manifest = {}
        
        # Handle array of objects (S3 manifest format)
        if isinstance(manifest_data, list):
            # Compile UUID pattern once (8-4-4-4-12 hex format)
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
            
            for item in manifest_data:
                if not isinstance(item, dict):
                    continue
                
                # Extract Key and URL from S3 manifest entry
                key = item.get('Key') or item.get('key')
                url = item.get('URL') or item.get('url')
                
                if not key:
                    continue
                
                # Extract UUID from filename (format: "01/UUID_name_timestamp.jpg" or "01/._UUID_name_timestamp.jpg")
                # Skip macOS metadata files (._ prefix)
                filename = os.path.basename(key)
                if filename.startswith('._') or not filename:
                    continue
                
                # Extract UUID from filename (first part before underscore)
                # Pattern: UUID_name_timestamp.jpg
                parts = filename.split('_')
                if len(parts) >= 1:
                    # Check if first part is a UUID (8-4-4-4-12 hex format)
                    potential_uuid = parts[0]
                    if uuid_pattern.match(potential_uuid):
                        uuid = potential_uuid
                        # Use URL if available, otherwise use Key as path
                        image_path = url if url else key
                        manifest[uuid] = image_path
        
        # Handle dictionary format (legacy support)
        elif isinstance(manifest_data, dict):
            for key, value in manifest_data.items():
                uuid = None
                image_path = None
                
                if isinstance(value, dict):
                    uuid = value.get('uuid') or value.get('serviceId') or value.get('id') or key
                    image_path = value.get('path') or value.get('url') or value.get('image') or value.get('file')
                else:
                    uuid = key
                    image_path = value
                
                if uuid:
                    manifest[uuid] = image_path
        
        print(f"Loaded manifest with {len(manifest)} entries")
        return manifest
    except Exception as e:
        print(f"Error loading manifest: {e}")
        import traceback
        traceback.print_exc()
        return {}

def find_existing_avatars(base_dir, uuid):
    """Find existing avatar files for a given UUID in previous export directories."""
    existing_files = []
    
    # Look for directories matching export pattern (NNN_YYYY-MM-DD)
    if not os.path.exists(base_dir):
        return existing_files
    
    # Search in base directory and subdirectories
    search_patterns = [
        os.path.join(base_dir, "[0-9][0-9][0-9]_*", f"{uuid}_*"),
        os.path.join(base_dir, f"{uuid}_*")
    ]
    
    for pattern in search_patterns:
        files = glob.glob(pattern)
        existing_files.extend(files)
    
    return existing_files

def compare_jpeg_similarity(img1_path, img2_data):
    """
    Compare JPEG similarity between existing file and new image data.
    Returns similarity score (0-1, where 1 is identical).
    """
    try:
        # Load existing image
        img1 = Image.open(img1_path)
        if img1.mode != 'RGB':
            img1 = img1.convert('RGB')
        
        # Convert new image data to PIL Image
        from io import BytesIO
        img2 = Image.open(BytesIO(img2_data))
        if img2.mode != 'RGB':
            img2 = img2.convert('RGB')
        
        # Resize to same dimensions for comparison (use smaller size for efficiency)
        max_size = 256
        img1 = img1.resize((max_size, max_size), Image.Resampling.LANCZOS)
        img2 = img2.resize((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert to numpy arrays
        img1_array = np.array(img1)
        img2_array = np.array(img2)
        
        # Calculate SSIM (Structural Similarity Index)
        # Use channel_axis for RGB images (newer scikit-image)
        try:
            similarity = ssim(img1_array, img2_array, channel_axis=2, data_range=255)
        except TypeError:
            # Fallback for older scikit-image versions
            similarity = ssim(img1_array, img2_array, multichannel=True, data_range=255)
        
        return similarity
    except Exception as e:
        print(f"    Error comparing images: {e}")
        return 0.0

def extract_avatar_info_from_sql(sql_file):
    """Extract remoteAvatarUrl and profileKey from user_metadata SQL export."""
    avatars = []
    
    # Statistics tracking
    stats = {
        'total_rows': 0,
        'empty_rows': 0,
        'parse_errors': 0,
        'insufficient_fields': 0,
        'missing_serviceid': 0,
        'missing_avatar_url_or_key': 0,
        'has_url_no_key': 0,
        'has_key_no_url': 0,
        'missing_both': 0,
    }
    
    print(f"Reading {sql_file}...")
    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all INSERT statements - use a simpler approach:
    # Split content by "INSERT INTO user_metadata" and process each section
    # Count INSERT statements first
    all_insert_markers = list(re.finditer(r'INSERT INTO user_metadata\s*\(', content, re.IGNORECASE))
    print(f"Found {len(all_insert_markers)} INSERT INTO user_metadata statement(s) in file")
    
    # Extract VALUES sections from each INSERT statement
    insert_statements = []
    for i, match in enumerate(all_insert_markers):
        start_pos = match.start()
        # Find the VALUES keyword after the column list
        # The column list ends with ), then we look for VALUES
        after_insert = content[start_pos:]
        values_match = re.search(r'\)\s*VALUES\s*\n', after_insert, re.IGNORECASE | re.DOTALL)
        
        if values_match:
            values_start = start_pos + values_match.end()
            # Find where this INSERT statement ends (next INSERT or end of content)
            if i + 1 < len(all_insert_markers):
                # Next INSERT starts here
                values_end = all_insert_markers[i + 1].start()
            else:
                # This is the last INSERT statement
                values_end = len(content)
            
            values_data = content[values_start:values_end]
            # Remove trailing semicolon and whitespace
            values_data = values_data.rstrip().rstrip(';').strip()
            if values_data:
                insert_statements.append(values_data)
    
    print(f"Extracted VALUES sections from {len(insert_statements)} INSERT statement(s)")
    
    if len(insert_statements) < len(all_insert_markers):
        print(f"WARNING: Only extracted {len(insert_statements)} VALUES sections but found {len(all_insert_markers)} INSERT statements!")
    
    matches = insert_statements
    
    row_count = 0
    for match_idx, match in enumerate(matches):
        if match_idx == 0:
            print(f"Processing first INSERT statement (showing first 200 chars): {match[:200]}...")
        
        # Remove trailing semicolon if present (from last row of INSERT statement)
        values_section = match.rstrip().rstrip(';')
        # Split rows by ),( but handle quoted strings carefully
        rows = []
        current_row = ""
        paren_depth = 0
        in_quotes = False
        i = 0
        
        while i < len(values_section):
            char = values_section[i]
            
            if char == "'" and (i == 0 or values_section[i-1] != '\\'):
                in_quotes = not in_quotes
                current_row += char
                i += 1
                continue
            
            if not in_quotes:
                if char == '(':
                    paren_depth += 1
                    if paren_depth == 1:
                        current_row = ""
                        i += 1
                        continue
                elif char == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        rows.append(current_row)
                        current_row = ""
                        i += 1
                        # Skip comma, semicolon, and whitespace after closing paren
                        while i < len(values_section) and values_section[i] in (',', ';', ' ', '\n', '\t'):
                            i += 1
                        continue
            
            current_row += char
            i += 1
        
        # Process each row
        for row_str in rows:
            row_count += 1
            stats['total_rows'] += 1
            if row_count % 10000 == 0:
                print(f"  Processed {row_count} rows...")
            
            if not row_str.strip():
                stats['empty_rows'] += 1
                continue
            
            try:
                fields = parse_sql_row(row_str)
            except Exception as e:
                stats['parse_errors'] += 1
                continue
            
            # Expected fields in user_metadata table:
            # 0: serviceId, 1: e164, 2: name, 3: profileName, 4: profileFamilyName,
            # 5: profileFullName, 6: active_at, 7: profileLastFetchedAt, 8: about,
            # 9: aboutEmoji, 10: remoteAvatarUrl, 11: profileKey, 12: profileKeyVersion,
            # 13: accessKey, ... (27 total fields)
            if len(fields) < 14:
                stats['insufficient_fields'] += 1
                continue
            
            # Extract fields directly (no JSON parsing needed)
            service_id = fields[0] if len(fields) > 0 else None
            profile_name = fields[3] if len(fields) > 3 and fields[3] else None
            profile_family_name = fields[4] if len(fields) > 4 and fields[4] else None
            profile_full_name = fields[5] if len(fields) > 5 and fields[5] else None
            profile_last_fetched = fields[7] if len(fields) > 7 and fields[7] else None
            remote_avatar_url = fields[10] if len(fields) > 10 and fields[10] else None
            profile_key = fields[11] if len(fields) > 11 and fields[11] else None
            access_key = fields[13] if len(fields) > 13 and fields[13] else None
            
            if not service_id:
                stats['missing_serviceid'] += 1
                continue
            
            # Use profileFullName if available, otherwise profileName, otherwise serviceId prefix
            display_name = profile_full_name or profile_name or service_id[:8]
            
            # Track detailed statistics about missing data
            has_url = bool(remote_avatar_url and remote_avatar_url.strip())
            has_key = bool(profile_key and profile_key.strip())
            
            if has_url and has_key:
                avatars.append({
                    'serviceId': service_id,
                    'remoteAvatarUrl': remote_avatar_url,
                    'profileKey': profile_key,
                    'accessKey': access_key,
                    'profileName': display_name,
                    'profileLastFetchedAt': profile_last_fetched,
                })
            else:
                stats['missing_avatar_url_or_key'] += 1
                if has_url and not has_key:
                    stats['has_url_no_key'] += 1
                elif has_key and not has_url:
                    stats['has_key_no_url'] += 1
                else:
                    stats['missing_both'] += 1
    
    # Print statistics
    print(f"\n{'='*60}")
    print(f"Processing Statistics:")
    print(f"{'='*60}")
    print(f"Total rows processed: {stats['total_rows']:,}")
    print(f"  - Empty rows: {stats['empty_rows']:,}")
    print(f"  - Parse errors: {stats['parse_errors']:,}")
    print(f"  - Insufficient fields (<14): {stats['insufficient_fields']:,}")
    print(f"  - Missing service_id: {stats['missing_serviceid']:,}")
    print(f"\nAvatar Data Breakdown:")
    print(f"  - Users with BOTH remoteAvatarUrl AND profileKey: {len(avatars):,}")
    print(f"  - Users missing avatar data: {stats['missing_avatar_url_or_key']:,}")
    print(f"    • Has remoteAvatarUrl but NO profileKey: {stats['has_url_no_key']:,}")
    print(f"    • Has profileKey but NO remoteAvatarUrl: {stats['has_key_no_url']:,}")
    print(f"    • Missing BOTH remoteAvatarUrl and profileKey: {stats['missing_both']:,}")
    
    # Calculate percentages
    valid_rows = stats['total_rows'] - stats['empty_rows'] - stats['parse_errors'] - stats['insufficient_fields'] - stats['missing_serviceid']
    if valid_rows > 0:
        pct_with_avatar = (len(avatars) / valid_rows) * 100
        pct_no_url = (stats['has_key_no_url'] / valid_rows) * 100
        pct_no_key = (stats['has_url_no_key'] / valid_rows) * 100
        pct_no_both = (stats['missing_both'] / valid_rows) * 100
        print(f"\nPercentages (of {valid_rows:,} valid rows):")
        print(f"  - {pct_with_avatar:.1f}% have both URL and key (can fetch avatar)")
        print(f"  - {pct_no_url:.1f}% have key but no URL (no avatar set)")
        print(f"  - {pct_no_key:.1f}% have URL but no key (cannot decrypt)")
        print(f"  - {pct_no_both:.1f}% missing both (no avatar data)")
    
    print(f"\n{'='*60}")
    print(f"Final result: {len(avatars):,} users with remoteAvatarUrl and profileKey")
    print(f"{'='*60}\n")
    return avatars

def check_if_unencrypted(data):
    """Check if data might be unencrypted (already an image)"""
    # Check for image magic bytes
    if data.startswith(b'\xff\xd8\xff'):  # JPEG
        return True, "JPEG"
    if data.startswith(b'\x89PNG'):
        return True, "PNG"
    if data.startswith(b'RIFF') and b'WEBP' in data[:12]:
        return True, "WEBP"
    if data.startswith(b'GIF8'):
        return True, "GIF"
    return False, None

def decrypt_avatar(encrypted_data, profile_key_b64, access_key_b64=None, debug=False):
    """
    Decrypt avatar using AES-GCM (as per Signal Desktop implementation).
    
    Signal uses AES-256-GCM for profile avatars:
    - IV: 12 bytes (not 16!)
    - Key: profileKey used directly (32 bytes, no derivation)
    - Format: IV (12 bytes) + ciphertext (includes 16-byte GCM tag at end)
    """
    PROFILE_IV_LENGTH = 12
    PROFILE_KEY_LENGTH = 32
    GCM_TAG_LENGTH = 16
    
    if len(encrypted_data) < PROFILE_IV_LENGTH + GCM_TAG_LENGTH:
        if debug:
            print(f"    Data too short: {len(encrypted_data)} bytes (need at least {PROFILE_IV_LENGTH + GCM_TAG_LENGTH})")
        return None
    
    # Extract components
    iv = encrypted_data[:PROFILE_IV_LENGTH]
    ciphertext_with_tag = encrypted_data[PROFILE_IV_LENGTH:]
    
    if debug:
        print(f"    Data length: {len(encrypted_data)} bytes")
        print(f"    IV length: {len(iv)} bytes (expected {PROFILE_IV_LENGTH})")
        print(f"    IV: {iv.hex()[:24]}...")
        print(f"    Ciphertext+tag length: {len(ciphertext_with_tag)} bytes")
        print(f"    Last 16 bytes (GCM tag): {encrypted_data[-16:].hex()}")
    
    # First, check if data is already unencrypted
    is_image, img_type = check_if_unencrypted(encrypted_data)
    if is_image:
        if debug:
            print(f"    ✓ Data appears to be unencrypted {img_type} image")
        return encrypted_data
    
    try:
        # Decode profile key from base64
        profile_key = base64.b64decode(profile_key_b64)
        
        if len(profile_key) != PROFILE_KEY_LENGTH:
            if debug:
                print(f"    ✗ Invalid profile key length: {len(profile_key)} (expected {PROFILE_KEY_LENGTH})")
            return None
        
        if debug:
            print(f"    Using profile key directly (no derivation needed)")
            print(f"    Profile key: {profile_key.hex()[:32]}...")
        
        # Decrypt using AES-GCM
        # The ciphertext_with_tag includes the GCM authentication tag at the end
        cipher = AES.new(profile_key, AES.MODE_GCM, nonce=iv)
        decrypted = cipher.decrypt(ciphertext_with_tag)
        
        if debug:
            print(f"    ✓ AES-GCM decryption successful")
            print(f"    Decrypted length: {len(decrypted)} bytes")
            print(f"    First 16 bytes: {decrypted[:16].hex()}")
        
        # Check if result looks like an image
        if len(decrypted) > 0 and (
            decrypted.startswith(b'\xff\xd8\xff') or  # JPEG
            decrypted.startswith(b'\x89PNG') or      # PNG
            decrypted.startswith(b'RIFF') or         # WEBP
            decrypted.startswith(b'GIF8')            # GIF
        ):
            if debug:
                img_type = "JPEG" if decrypted.startswith(b'\xff\xd8\xff') else \
                          "PNG" if decrypted.startswith(b'\x89PNG') else \
                          "WEBP" if decrypted.startswith(b'RIFF') else "GIF"
                print(f"    ✓ Decrypted data is valid {img_type} image")
            return decrypted
        else:
            if debug:
                print(f"    ✗ Decrypted data doesn't look like an image")
                print(f"    First bytes: {decrypted[:32].hex()}")
            return None
            
    except Exception as e:
        if debug:
            print(f"    ✗ Decryption error: {e}")
            import traceback
            traceback.print_exc()
        return None

def download_manifest_image(manifest_path, verbose=False):
    """Download image from manifest path (S3 or local)."""
    try:
        if manifest_path.startswith('http://') or manifest_path.startswith('https://'):
            # Download from URL
            if verbose:
                print(f"      Downloading manifest image from URL: {manifest_path}")
            response = requests.get(manifest_path, timeout=10, verify=False)
            if response.status_code == 200:
                return response.content
            else:
                if verbose:
                    print(f"      Failed to download: HTTP {response.status_code}")
                return None
        else:
            # Local file path
            if verbose:
                print(f"      Reading manifest image from local path: {manifest_path}")
            if os.path.exists(manifest_path):
                with open(manifest_path, 'rb') as f:
                    return f.read()
            else:
                if verbose:
                    print(f"      File not found: {manifest_path}")
                return None
    except Exception as e:
        if verbose:
            print(f"      Error downloading manifest image: {e}")
        return None

def fetch_avatar_from_cdn(remote_url, profile_key, output_dir, service_id, profile_name, access_key=None, verbose=False, existing_files=None, base_dir=None, manifest=None):
    """
    Fetch and decrypt avatar from Signal CDN.
    Compares with manifest images and existing avatars, only saves if significantly different.
    Returns (success, message, should_keep, manifest_file_deleted, details_dict)
    where details_dict contains: image_type, similarity_score, manifest_match, comparison_source, download_path
    """
    import time
    
    # Construct full CDN URL
    if remote_url.startswith("profiles/"):
        path = remote_url
    else:
        path = f"profiles/{remote_url}"
    
    cdn_url = urljoin(CDN_BASE_URL, path)
    
    # Generate safe filename: ACI_UserName_UnixTimestamp.ext
    safe_name = re.sub(r'[^\w\-_\.]', '_', profile_name)[:50]
    # Get current Unix timestamp
    unix_timestamp = int(time.time())
    # Use full serviceId (ACI) instead of truncated version
    filename_base = f"{service_id}_{safe_name}_{unix_timestamp}"
    
    manifest_file_deleted = None
    details = {
        'image_type': None,
        'similarity_score': None,
        'manifest_match': False,
        'comparison_source': None,
        'download_path': None,
        'error_type': None
    }
    
    try:
        # Step 1: Download avatar from CDN
        if verbose:
            print(f"    [DOWNLOAD] Fetching avatar from CDN: {cdn_url}")
        
        response = requests.get(cdn_url, timeout=10, verify=False)
        
        if response.status_code != 200:
            if verbose:
                print(f"    [DOWNLOAD] Failed: HTTP {response.status_code}")
            details['error_type'] = f"HTTP {response.status_code}"
            return False, f"HTTP {response.status_code}", False, None, details
        
        encrypted_data = response.content
        
        if len(encrypted_data) == 0:
            if verbose:
                print(f"    [DOWNLOAD] Failed: Empty response")
            details['error_type'] = "Empty response"
            return False, "Empty response", False, None, details
        
        if verbose:
            print(f"    [DOWNLOAD] Success: Downloaded {len(encrypted_data)} bytes")
        
        # Decrypt avatar
        if verbose:
            print(f"    [DECRYPT] Decrypting avatar...")
        decrypted_data = decrypt_avatar(encrypted_data, profile_key, access_key, debug=verbose)
        
        if not decrypted_data:
            if verbose:
                print(f"    [DECRYPT] Failed: Decryption failed")
            details['error_type'] = "Decryption failed"
            return False, "Decryption failed", False, None, details
        
        if verbose:
            print(f"    [DECRYPT] Success: Decrypted {len(decrypted_data)} bytes")
        
        # Determine file extension and image type
        ext = ".jpg"  # Default
        image_type = "JPG"
        if decrypted_data.startswith(b'\x89PNG'):
            ext = ".png"
            image_type = "PNG"
        elif decrypted_data.startswith(b'RIFF') and b'WEBP' in decrypted_data[:12]:
            ext = ".webp"
            image_type = "WEBP"
        elif decrypted_data.startswith(b'GIF8'):
            ext = ".gif"
            image_type = "GIF"
        elif decrypted_data.startswith(b'\xff\xd8\xff'):
            ext = ".jpg"
            image_type = "JPG"
        
        details['image_type'] = image_type
        
        # Step 2: Check manifest for UUID match
        manifest_image_data = None
        manifest_path = None
        if manifest and service_id in manifest:
            manifest_path = manifest[service_id]
            details['manifest_match'] = True
            if verbose:
                print(f"    [MANIFEST] UUID match: YES")
                print(f"    [MANIFEST] Manifest path: {manifest_path}")
            
            # Step 3: Download manifest image
            manifest_image_data = download_manifest_image(manifest_path, verbose=verbose)
            if manifest_image_data:
                if verbose:
                    print(f"    [MANIFEST] Downloaded manifest image: {len(manifest_image_data)} bytes")
            else:
                if verbose:
                    print(f"    [MANIFEST] Failed to download manifest image")
        else:
            details['manifest_match'] = False
            if verbose:
                print(f"    [MANIFEST] UUID match: NO")
        
        # Step 4: Compare images
        max_similarity = 0.0
        most_similar_file = None
        comparison_source = None
        details['similarity_score'] = 0.0
        
        # Compare with manifest image if available
        if manifest_image_data:
            if verbose:
                print(f"    [COMPARE] Comparing with manifest image...")
            try:
                similarity = compare_jpeg_similarity_bytes(manifest_image_data, decrypted_data)
                if similarity > max_similarity:
                    max_similarity = similarity
                    comparison_source = "manifest"
                    if verbose:
                        print(f"    [COMPARE] Manifest similarity: {similarity:.3f}")
            except Exception as e:
                if verbose:
                    print(f"    [COMPARE] Error comparing with manifest: {e}")
        
        # Compare with existing local files
        if existing_files:
            if verbose:
                print(f"    [COMPARE] Comparing with {len(existing_files)} existing local file(s)...")
            for existing_file in existing_files:
                try:
                    similarity = compare_jpeg_similarity(existing_file, decrypted_data)
                    if similarity > max_similarity:
                        max_similarity = similarity
                        most_similar_file = existing_file
                        comparison_source = "local"
                    if verbose:
                        print(f"    [COMPARE] Local file {os.path.basename(existing_file)} similarity: {similarity:.3f}")
                except Exception as e:
                    if verbose:
                        print(f"    [COMPARE] Error comparing with {existing_file}: {e}")
                    continue
        
        # Step 5: Determine if we should keep the new image
        if max_similarity >= SIMILARITY_THRESHOLD:
            # Images are too similar (>90% similar = <10% different)
            if verbose:
                print(f"    [RESULT] Same (similarity: {max_similarity:.3f} >= {SIMILARITY_THRESHOLD})")
                print(f"    [RESULT] Discarding new download (duplicate)")
            
            # Delete manifest version if we compared with it and it's the same
            if comparison_source == "manifest" and manifest_path:
                try:
                    if os.path.exists(manifest_path):
                        os.remove(manifest_path)
                        manifest_file_deleted = manifest_path
                        if verbose:
                            print(f"    [DELETE] Deleted manifest file: {manifest_path}")
                except Exception as e:
                    if verbose:
                        print(f"    [DELETE] Error deleting manifest file: {e}")
            
            source_info = f"manifest ({os.path.basename(manifest_path)})" if comparison_source == "manifest" else f"local ({os.path.basename(most_similar_file)})"
            details['similarity_score'] = max_similarity
            details['comparison_source'] = comparison_source
            return True, f"Duplicate (similarity: {max_similarity:.3f}, matches {source_info})", False, manifest_file_deleted, details
        else:
            # Images are different enough to keep
            if verbose:
                print(f"    [RESULT] Different (similarity: {max_similarity:.3f} < {SIMILARITY_THRESHOLD})")
                print(f"    [RESULT] Keeping new version (>10% different)")
            
            # Step 6: Save new image locally
            output_path = os.path.join(output_dir, f"{filename_base}{ext}")
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            
            if verbose:
                print(f"    [SAVE] Saved to: {output_path}")
            
            details['download_path'] = output_path
            details['similarity_score'] = max_similarity if max_similarity > 0 else None
            details['comparison_source'] = comparison_source if comparison_source else 'none'
            
            # Step 7: Delete manifest version if we compared with it
            if comparison_source == "manifest" and manifest_path:
                try:
                    if os.path.exists(manifest_path):
                        os.remove(manifest_path)
                        manifest_file_deleted = manifest_path
                        if verbose:
                            print(f"    [DELETE] Deleted manifest file (replaced with new version): {manifest_path}")
                except Exception as e:
                    if verbose:
                        print(f"    [DELETE] Error deleting manifest file: {e}")
            
            return True, output_path, True, manifest_file_deleted, details
        
    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"    [ERROR] Network error: {e}")
        details['error_type'] = f"Network error: {e}"
        return False, f"Network error: {e}", False, None, details
    except Exception as e:
        if verbose:
            print(f"    [ERROR] {e}")
        details['error_type'] = f"Error: {e}"
        return False, f"Error: {e}", False, None, details

def compare_jpeg_similarity_bytes(img1_data, img2_data):
    """Compare JPEG similarity between two image byte arrays."""
    try:
        from io import BytesIO
        
        # Convert image data to PIL Images
        img1 = Image.open(BytesIO(img1_data))
        if img1.mode != 'RGB':
            img1 = img1.convert('RGB')
        
        img2 = Image.open(BytesIO(img2_data))
        if img2.mode != 'RGB':
            img2 = img2.convert('RGB')
        
        # Resize to same dimensions for comparison (use smaller size for efficiency)
        max_size = 256
        img1 = img1.resize((max_size, max_size), Image.Resampling.LANCZOS)
        img2 = img2.resize((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert to numpy arrays
        img1_array = np.array(img1)
        img2_array = np.array(img2)
        
        # Calculate SSIM (Structural Similarity Index)
        try:
            similarity = ssim(img1_array, img2_array, channel_axis=2, data_range=255)
        except TypeError:
            # Fallback for older scikit-image versions
            similarity = ssim(img1_array, img2_array, multichannel=True, data_range=255)
        
        return similarity
    except Exception as e:
        raise Exception(f"Error comparing images: {e}")

def process_avatar_worker(avatar_data):
    """Worker function to process a single avatar. Returns result dict."""
    avatar, output_dir, base_dir, manifest, verbose, index, total = avatar_data
    
    service_id = avatar['serviceId']
    result = {
        'index': index,
        'service_id': service_id,
        'profile_name': avatar['profileName'],
        'success': False,
        'should_keep': False,
        'message': '',
        'manifest_deleted': None,
        'image_type': None,
        'similarity_score': None,
        'manifest_match': False,
        'comparison_source': None,
        'download_path': None,
        'error_type': None,
        'status': None
    }
    
    try:
        # Find existing avatars for this UUID
        existing_files = find_existing_avatars(base_dir, service_id)
        
        success_flag, message, should_keep, manifest_file_deleted, details = fetch_avatar_from_cdn(
            avatar['remoteAvatarUrl'],
            avatar['profileKey'],
            output_dir,
            service_id,
            avatar['profileName'],
            avatar.get('accessKey'),
            verbose=verbose,
            existing_files=existing_files,
            base_dir=base_dir,
            manifest=manifest
        )
        
        result['success'] = success_flag
        result['should_keep'] = should_keep
        result['message'] = message
        result['manifest_deleted'] = manifest_file_deleted
        result['image_type'] = details.get('image_type')
        result['similarity_score'] = details.get('similarity_score')
        result['manifest_match'] = details.get('manifest_match', False)
        result['comparison_source'] = details.get('comparison_source')
        result['download_path'] = details.get('download_path')
        result['error_type'] = details.get('error_type')
        
        # Determine status
        if not success_flag:
            result['status'] = 'Failed'
        elif should_keep:
            result['status'] = 'Downloaded New'
        else:
            if details.get('comparison_source') == 'manifest':
                result['status'] = 'Same as Manifest'
            elif details.get('comparison_source') == 'local':
                result['status'] = 'Same as Local'
            else:
                result['status'] = 'Duplicate'
        
    except Exception as e:
        result['message'] = f"Error: {e}"
        result['success'] = False
        result['error_type'] = f"Exception: {e}"
        result['status'] = 'Failed'
    
    return result

def main():
    if len(sys.argv) < 1:
        print("Usage: python3 fetch_avatars_with_dedup.py [manifest_file] [sql_file] [output_dir] [base_dir] [limit] [--threads N] [--debug]")
        print("\nArguments:")
        print("  manifest_file: Path to manifest JSON (default: signal_avatars_manifest_01.json)")
        print("  sql_file: Path to SQL file (default: user_metadata.sql)")
        print("  output_dir: Directory to save new avatars (default: ./004_dedup_test)")
        print("  base_dir: Base directory to search for existing avatars (default: current dir)")
        print("  limit: Optional limit on number of avatars to process")
        print("  --threads N: Number of parallel threads (default: 10, use 1 for sequential)")
        print("  --debug, --verbose, -v: Enable verbose output")
        print("\nWARNING: This may violate Signal's Terms of Service. Use at your own risk.")
        print("NOTE: SSL verification is disabled for testing.")
        sys.exit(1)
    
    # Default files
    default_manifest_file = "signal_avatars_manifest_01.json"
    default_sql_file = "user_metadata.sql"
    
    # Parse arguments
    manifest_file = default_manifest_file
    sql_file = default_sql_file
    output_dir = "./004_dedup_test"
    base_dir = "."
    limit = None
    debug = False
    num_threads = 10  # Default to 10 threads for parallel processing
    
    # Parse arguments
    verbose = False
    i = 0
    while i < len(sys.argv[1:]):
        arg = sys.argv[1:][i]
        if arg == '--debug' or arg == '--verbose' or arg == '-v':
            debug = True
            verbose = True
        elif arg == '--threads' and i + 1 < len(sys.argv[1:]):
            num_threads = int(sys.argv[1:][i + 1])
            i += 1  # Skip next argument as it's the thread count
        elif arg.isdigit() and limit is None:
            limit = int(arg)
        elif arg.endswith('.json'):
            manifest_file = arg
        elif arg.endswith('.sql'):
            sql_file = arg
        elif os.path.isdir(arg) or not arg.startswith('--'):
            # Could be output_dir or base_dir
            if output_dir == "./004_dedup_test":
                output_dir = arg
            else:
                base_dir = arg
        i += 1
    
    if not os.path.exists(sql_file):
        print(f"Error: File not found: {sql_file}")
        sys.exit(1)
    
    # Load S3 manifest
    manifest = load_s3_manifest(manifest_file)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract avatar info
    avatars = extract_avatar_info_from_sql(sql_file)
    
    if not avatars:
        print("No avatars found with remoteAvatarUrl and profileKey")
        return
    
    # Filter avatars based on manifest (if manifest is provided and not empty)
    if manifest:
        original_count = len(avatars)
        # Manifest should contain UUIDs (serviceIds) as keys or in a list
        # Try to extract UUIDs from manifest
        manifest_uuids = set()
        if isinstance(manifest, dict):
            # If manifest is a dict, keys might be UUIDs or we need to look in values
            for key, value in manifest.items():
                if isinstance(value, dict) and 'uuid' in value:
                    manifest_uuids.add(value['uuid'])
                elif isinstance(value, dict) and 'serviceId' in value:
                    manifest_uuids.add(value['serviceId'])
                else:
                    # Try key as UUID
                    manifest_uuids.add(key)
        elif isinstance(manifest, list):
            for item in manifest:
                if isinstance(item, dict):
                    manifest_uuids.add(item.get('uuid') or item.get('serviceId') or item.get('id'))
                else:
                    manifest_uuids.add(item)
        
        if manifest_uuids:
            avatars = [a for a in avatars if a['serviceId'] in manifest_uuids]
            print(f"Filtered to {len(avatars)} avatars matching manifest (from {original_count} total)")
        else:
            print("Warning: Could not extract UUIDs from manifest, processing all avatars")
    
    if limit:
        avatars = avatars[:limit]
        print(f"\nLimiting to first {limit} avatars for testing")
    
    print(f"\nAttempting to fetch {len(avatars)} avatars from CDN...")
    print(f"Checking against manifest: {manifest_file}")
    print(f"Checking against existing avatars in: {base_dir}")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD} (keep if >10% different)")
    print(f"Using {num_threads} thread(s) for parallel processing")
    print("NOTE: SSL verification is disabled for testing.\n")
    
    # Thread-safe counters and results collection
    stats_lock = threading.Lock()
    success = 0
    failed = 0
    duplicates = 0
    new_avatars = 0
    manifest_deleted = 0
    processed_count = 0
    all_results = []  # Collect all results for CSV output
    
    # Prepare avatar data for workers
    avatar_data_list = [
        (avatar, output_dir, base_dir, manifest, verbose, i + 1, len(avatars))
        for i, avatar in enumerate(avatars)
    ]
    
    # Process avatars with ThreadPoolExecutor
    if num_threads == 1:
        # Sequential processing (original behavior)
        print("Processing sequentially (single thread)...\n")
        for avatar_data in avatar_data_list:
            avatar, _, _, _, _, index, total = avatar_data
            service_id = avatar['serviceId']
            profile_name = avatar['profileName']
            
            # Show progress
            last_fetched = avatar.get('profileLastFetchedAt')
            if last_fetched:
                try:
                    ts = int(last_fetched) / 1000
                    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    print(f"[{index}/{total}] {profile_name} ({service_id[:8]}...) [Last fetched: {date_str}]")
                except:
                    print(f"[{index}/{total}] {profile_name} ({service_id[:8]}...)")
            else:
                print(f"[{index}/{total}] {profile_name} ({service_id[:8]}...)")
            
            result = process_avatar_worker(avatar_data)
            
            # Update statistics and collect results
            with stats_lock:
                processed_count += 1
                all_results.append(result)
                if result['success']:
                    if result['should_keep']:
                        print(f"  ✓ Saved: {result['message']}")
                        success += 1
                        new_avatars += 1
                        if result['manifest_deleted']:
                            manifest_deleted += 1
                    else:
                        print(f"  ⊘ Duplicate: {result['message']}")
                        duplicates += 1
                        if result['manifest_deleted']:
                            manifest_deleted += 1
                else:
                    print(f"  ❌ {result['message']}")
                    failed += 1
    else:
        # Parallel processing with ThreadPoolExecutor
        print(f"Processing in parallel with {num_threads} threads...\n")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit all tasks
            future_to_avatar = {
                executor.submit(process_avatar_worker, avatar_data): avatar_data
                for avatar_data in avatar_data_list
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_avatar):
                avatar_data = future_to_avatar[future]
                avatar, _, _, _, _, index, total = avatar_data
                
                try:
                    result = future.result()
                    service_id = result['service_id']
                    profile_name = result['profile_name']
                    
                    # Show progress (thread-safe printing)
                    with stats_lock:
                        processed_count += 1
                        last_fetched = avatar.get('profileLastFetchedAt')
                        if last_fetched:
                            try:
                                ts = int(last_fetched) / 1000
                                date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                                print(f"[{processed_count}/{total}] {profile_name} ({service_id[:8]}...) [Last fetched: {date_str}]")
                            except:
                                print(f"[{processed_count}/{total}] {profile_name} ({service_id[:8]}...)")
                        else:
                            print(f"[{processed_count}/{total}] {profile_name} ({service_id[:8]}...)")
                        
                        # Update statistics and collect results
                        all_results.append(result)
                        if result['success']:
                            if result['should_keep']:
                                print(f"  ✓ Saved: {result['message']}")
                                success += 1
                                new_avatars += 1
                                if result['manifest_deleted']:
                                    manifest_deleted += 1
                            else:
                                print(f"  ⊘ Duplicate: {result['message']}")
                                duplicates += 1
                                if result['manifest_deleted']:
                                    manifest_deleted += 1
                        else:
                            print(f"  ❌ {result['message']}")
                            failed += 1
                            
                except Exception as e:
                    with stats_lock:
                        processed_count += 1
                        failed += 1
                        error_result = {
                            'index': processed_count,
                            'service_id': avatar.get('serviceId', 'Unknown'),
                            'profile_name': avatar.get('profileName', 'Unknown'),
                            'success': False,
                            'should_keep': False,
                            'message': f"Error: {e}",
                            'manifest_deleted': None,
                            'image_type': None,
                            'similarity_score': None,
                            'manifest_match': False,
                            'comparison_source': None,
                            'download_path': None,
                            'error_type': f"Exception: {e}",
                            'status': 'Failed'
                        }
                        all_results.append(error_result)
                        print(f"[{processed_count}/{len(avatars)}] Error processing avatar: {e}")
    
    print(f"\nSummary:")
    print(f"  Success (new/updated): {new_avatars}")
    print(f"  Duplicates (discarded): {duplicates}")
    print(f"  Failed: {failed}")
    print(f"  Manifest files deleted: {manifest_deleted}")
    print(f"  Output directory: {output_dir}")
    if num_threads > 1:
        print(f"  Processed using {num_threads} parallel threads")
    
    # Write CSV summary
    csv_filename = os.path.join(output_dir, f"avatar_processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    print(f"\nWriting CSV summary to: {csv_filename}")
    
    # Sort results by index to maintain order
    all_results.sort(key=lambda x: x.get('index', 0))
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'UUID',
            'Profile Name',
            'Status',
            'Image Type',
            'Manifest Match',
            'Similarity Score',
            'Comparison Source',
            'Download Path',
            'Download Name',
            'Error Type',
            'Message'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in all_results:
            download_name = None
            if result.get('download_path'):
                download_name = os.path.basename(result['download_path'])
            
            similarity_str = None
            if result.get('similarity_score') is not None:
                similarity_str = f"{result['similarity_score']:.4f}"
            
            writer.writerow({
                'UUID': result.get('service_id', ''),
                'Profile Name': result.get('profile_name', ''),
                'Status': result.get('status', 'Unknown'),
                'Image Type': result.get('image_type', ''),
                'Manifest Match': 'Yes' if result.get('manifest_match') else 'No',
                'Similarity Score': similarity_str or '',
                'Comparison Source': result.get('comparison_source', ''),
                'Download Path': result.get('download_path', ''),
                'Download Name': download_name or '',
                'Error Type': result.get('error_type', ''),
                'Message': result.get('message', '')
            })
    
    print(f"CSV summary written with {len(all_results)} entries")

if __name__ == '__main__':
    main()

