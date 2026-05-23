
import sys
import os
from sqlalchemy import text

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.db.session import SessionLocal

def optimize_tables():
    db = SessionLocal()
    try:
        print("Starting optimization of history tables...")

        # 1. User History
        print("Optimizing user_history...")
        user_cols = [
            "e164", "name", "profile_name", "profile_family_name", "profile_full_name",
            "active_at", "profile_last_fetched_at", "about", "about_emoji", "remote_avatar_url",
            "profile_key", "profile_key_version", "access_key", "profile_key_credential",
            "profile_key_credential_expiration", "sharing_phone_number", "capabilities",
            "verified", "color", "storage_version", "storage_id", "conversation_id",
            "group_memberships", "is_admin", "admin_groups", "avatar_id", "export_timestamp"
        ]
        stmt = f"ALTER TABLE user_history DROP COLUMN IF EXISTS {', DROP COLUMN IF EXISTS '.join(user_cols)};"
        db.execute(text(stmt))
        print("user_history optimized.")

        # 2. Group History
        print("Optimizing group_history...")
        group_cols = [
            "group_name", "number_of_members", "admin_approval_required", "group_link",
            "description", "retention_period", "master_key", "invite_link_password",
            "secret_params", "public_params"
        ]
        stmt = f"ALTER TABLE group_history DROP COLUMN IF EXISTS {', DROP COLUMN IF EXISTS '.join(group_cols)};"
        db.execute(text(stmt))
        print("group_history optimized.")

        # 3. Avatar History
        print("Optimizing avatar_history...")
        avatar_cols = [
            "s3_key", "s3_url", "filename", "file_size", "timestamp"
        ]
        # Keep 'id' (original PK), 'service_id'
        stmt = f"ALTER TABLE avatar_history DROP COLUMN IF EXISTS {', DROP COLUMN IF EXISTS '.join(avatar_cols)};"
        db.execute(text(stmt))
        print("avatar_history optimized.")

        db.commit()
        print("All tables optimized successfully.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    optimize_tables()
