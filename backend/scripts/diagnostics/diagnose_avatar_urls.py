"""
Quick diagnostic script to inspect avatar URLs and CDN fetch attempts.
Shows why avatars are returning 404.
Uses raw SQL to avoid model dependency issues.
"""

import requests
from app.core.config import settings
from app.db.session import SessionLocal
from sqlalchemy import text


def diagnose_avatar_urls():
    """Sample first 10 users with avatars and check CDN URLs."""
    db = SessionLocal()

    try:
        # Get sample users with remote_avatar_url set (raw SQL)
        result = db.execute(
            text("""
                SELECT service_id, remote_avatar_url, LENGTH(profile_key) as key_len
                FROM user_metadata
                WHERE remote_avatar_url IS NOT NULL
                AND profile_key IS NOT NULL
                LIMIT 10
            """)
        )
        
        sample_users = result.fetchall()

        if not sample_users:
            print("❌ NO USERS FOUND with remote_avatar_url and profile_key set!")
            print("   → This is why missing=100%")
            print("\n   Checking what data EXISTS...")
            
            # Check what's actually in the DB
            result = db.execute(text("""
                SELECT 
                  COUNT(*) as total,
                  SUM(CASE WHEN remote_avatar_url IS NOT NULL THEN 1 ELSE 0 END) as has_url,
                  SUM(CASE WHEN profile_key IS NOT NULL THEN 1 ELSE 0 END) as has_key
                FROM user_metadata
            """))
            counts = result.fetchone()
            print(f"   Total users: {counts[0]}")
            print(f"   With remote_avatar_url: {counts[1]}")
            print(f"   With profile_key: {counts[2]}")
            return

        print(f"\n✅ Found {len(sample_users)} sample users with avatar URLs\n")

        for i, row in enumerate(sample_users, 1):
            service_id, remote_url, key_len = row
            print(f"--- User {i}: {service_id} ---")
            print(f"   remote_avatar_url: {remote_url}")
            print(f"   profile_key length: {key_len}")

            # Build CDN URL (same logic as avatar_sync_tasks.py)
            if remote_url.startswith("profiles/"):
                path = remote_url
            else:
                path = f"profiles/{remote_url}"

            cdn_url = f"{settings.AVATAR_SYNC_CDN_BASE_URL.rstrip('/')}/{path}"
            print(f"   CDN URL: {cdn_url}")

            # Try to fetch (no decrypt, just check if 404)
            try:
                resp = requests.get(
                    cdn_url,
                    timeout=settings.AVATAR_SYNC_CDN_TIMEOUT,
                    verify=settings.AVATAR_SYNC_CDN_VERIFY_SSL,
                )
                print(f"   HTTP Status: {resp.status_code}")
                if resp.status_code == 200:
                    print(f"   ✅ Response size: {len(resp.content)} bytes")
                else:
                    print(f"   ❌ Status: {resp.status_code}")
            except Exception as e:
                print(f"   ❌ Request error: {str(e)[:80]}")

            print()

        # Summary stats
        print("--- OVERALL STATS ---")
        result = db.execute(text("""
            SELECT 
              COUNT(*) as total,
              SUM(CASE WHEN remote_avatar_url IS NOT NULL THEN 1 ELSE 0 END) as with_url,
              SUM(CASE WHEN profile_key IS NOT NULL THEN 1 ELSE 0 END) as with_key,
              SUM(CASE WHEN remote_avatar_url IS NOT NULL AND profile_key IS NOT NULL THEN 1 ELSE 0 END) as eligible
            FROM user_metadata
        """))
        stats = result.fetchone()
        print(f"Total users: {stats[0]}")
        print(f"With remote_avatar_url: {stats[1]}")
        print(f"With profile_key: {stats[2]}")
        print(f"With BOTH (eligible for sync): {stats[3]}")

    finally:
        db.close()


if __name__ == "__main__":
    diagnose_avatar_urls()
