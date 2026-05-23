"""
Quick diagnostic script to test Signal CDN avatar fetch + decrypt on a few users.

Usage:
    cd backend
    python scripts/test_cdn_fetch.py          # test 3 users (default)
    python scripts/test_cdn_fetch.py 10       # test 10 users
"""

import sys
import os
import base64
import hashlib
import requests

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

CDN_BASE_URL = "https://cdn.signal.org/"
TIMEOUT = 15

# How many users to test
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def fetch_and_decrypt(service_id, remote_avatar_url, profile_key, access_key=None):
    """Test the full CDN fetch + decrypt pipeline for one user. Returns details."""
    print(f"\n{'='*70}")
    print(f"  User: {service_id}")
    print(f"  remote_avatar_url: {remote_avatar_url[:80]}{'...' if len(remote_avatar_url) > 80 else ''}")
    print(f"  profile_key: {profile_key[:20]}...")
    print(f"{'='*70}")

    # Step 1: Build URL
    if remote_avatar_url.startswith("profiles/"):
        path = remote_avatar_url
    else:
        path = f"profiles/{remote_avatar_url}"
    cdn_url = f"{CDN_BASE_URL.rstrip('/')}/{path}"
    print(f"\n  [1] CDN URL: {cdn_url}")

    # Step 2: Fetch
    print(f"  [2] Fetching...")
    try:
        resp = requests.get(cdn_url, timeout=TIMEOUT, verify=True)
    except requests.RequestException as e:
        print(f"  [2] FAILED - Network error: {e}")
        # Retry without SSL verify
        print(f"  [2] Retrying with verify=False...")
        try:
            resp = requests.get(cdn_url, timeout=TIMEOUT, verify=False)
        except requests.RequestException as e2:
            print(f"  [2] FAILED again: {e2}")
            return False

    print(f"  [2] HTTP {resp.status_code} — {len(resp.content)} bytes")
    print(f"  [2] Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    print(f"  [2] Headers: {dict(list(resp.headers.items())[:5])}")

    if resp.status_code != 200:
        print(f"  [2] FAILED - Non-200 status")
        return False

    encrypted_data = resp.content
    if len(encrypted_data) == 0:
        print(f"  [2] FAILED - Empty response body")
        return False

    print(f"  [2] First 32 bytes (hex): {encrypted_data[:32].hex()}")

    # Step 3: Check if already unencrypted
    magic_checks = {
        b'\xff\xd8\xff': 'JPEG',
        b'\x89PNG': 'PNG',
        b'RIFF': 'WEBP',
        b'GIF8': 'GIF',
    }
    for magic, fmt in magic_checks.items():
        if encrypted_data.startswith(magic):
            print(f"  [3] Data is ALREADY a {fmt} image (unencrypted)")
            sha = hashlib.sha256(encrypted_data).hexdigest()
            print(f"  [3] SHA-256: {sha[:32]}...")
            print(f"  [3] Size: {len(encrypted_data)} bytes")
            print(f"\n  ✓ SUCCESS (unencrypted {fmt})")
            return True

    # Step 4: Decrypt
    print(f"\n  [3] Attempting AES-256-GCM decryption...")
    PROFILE_IV_LENGTH = 12
    PROFILE_KEY_LENGTH = 32
    GCM_TAG_LENGTH = 16

    if len(encrypted_data) < PROFILE_IV_LENGTH + GCM_TAG_LENGTH:
        print(f"  [3] FAILED - Data too short ({len(encrypted_data)} bytes, need {PROFILE_IV_LENGTH + GCM_TAG_LENGTH}+)")
        return False

    # Decode profile key
    try:
        profile_key_bytes = base64.b64decode(profile_key)
        print(f"  [3] Profile key decoded: {len(profile_key_bytes)} bytes")
        if len(profile_key_bytes) != PROFILE_KEY_LENGTH:
            print(f"  [3] FAILED - Key length {len(profile_key_bytes)}, expected {PROFILE_KEY_LENGTH}")
            return False
    except Exception as e:
        print(f"  [3] FAILED - Cannot decode profile_key: {e}")
        return False

    iv = encrypted_data[:PROFILE_IV_LENGTH]
    ciphertext_with_tag = encrypted_data[PROFILE_IV_LENGTH:]

    print(f"  [3] IV (hex): {iv.hex()}")
    print(f"  [3] Ciphertext+tag length: {len(ciphertext_with_tag)} bytes")

    try:
        from Crypto.Cipher import AES
        cipher = AES.new(profile_key_bytes, AES.MODE_GCM, nonce=iv)
        decrypted = cipher.decrypt(ciphertext_with_tag)
    except Exception as e:
        print(f"  [3] FAILED - Decryption error: {e}")
        return False

    print(f"  [3] Decrypted: {len(decrypted)} bytes")
    print(f"  [3] First 32 bytes (hex): {decrypted[:32].hex()}")

    # Step 5: Validate image
    is_image = False
    img_type = "UNKNOWN"
    for magic, fmt in magic_checks.items():
        if decrypted.startswith(magic):
            is_image = True
            img_type = fmt
            break

    if is_image:
        sha = hashlib.sha256(decrypted).hexdigest()
        print(f"\n  ✓ SUCCESS — Valid {img_type} image, {len(decrypted)} bytes")
        print(f"  ✓ SHA-256: {sha[:32]}...")
        return True
    else:
        print(f"\n  ✗ FAILED — Decrypted data is not a recognized image format")
        print(f"  ✗ First bytes: {decrypted[:16].hex()}")
        return False


def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/user_search")
    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Find users with both remote_avatar_url and profile_key
        result = conn.execute(text("""
            SELECT service_id, remote_avatar_url, profile_key, access_key
            FROM user_metadata
            WHERE remote_avatar_url IS NOT NULL
              AND profile_key IS NOT NULL
              AND remote_avatar_url != ''
              AND profile_key != ''
            LIMIT :limit
        """), {"limit": LIMIT})

        rows = result.fetchall()

    if not rows:
        print("No users found with remote_avatar_url + profile_key in user_metadata!")
        print("Check that user data has been ingested and these columns are populated.")
        return

    print(f"\nFound {len(rows)} users to test\n")

    success = 0
    failed = 0

    for row in rows:
        service_id, remote_avatar_url, profile_key, access_key = row
        ok = fetch_and_decrypt(service_id, remote_avatar_url, profile_key, access_key)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"  RESULTS: {success} success, {failed} failed out of {len(rows)} tested")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
