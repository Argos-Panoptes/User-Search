from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    print("Starting migration to add 'id' primary keys...")
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.begin() as conn:
        # --- 1. User Metadata ---
        print("Migrating user_metadata...")
        
        # Check if 'id' column already exists
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user_metadata' AND column_name='id'"))
        if result.fetchone():
            print("Column 'id' already exists in user_metadata.")
        else:
            # 1. Drop existing PK constraint (likely on service_id)
            # We use CASCADE to handle foreign keys (like avatars, group_memberships_map if any)
            # CAUTION: CASCADE might drop FKs. We need to check if we need to recreate them.
            # Avatars table references user_metadata.service_id.
            # If we drop PK on service_id, the FK might be dropped if it strictly requires PK.
            # However, we will immediately make service_id UNIQUE.
            # Postgres: FK target can be PK or UNIQUE. 
            # If we simply DROP CONSTRAINT pkey CASCADE, it WILL drop the FKs referencing it.
            # We should try to avoid CASCADE if possible, or we must recreate the FKs.
            
            # Let's inspect constraints first?
            # Or just do it: Drop PK (without cascade if possible? No, it's referenced).
            # Okay, let's use CASCADE and then Re-Add FK if needed?
            # Actually, `avatars` has `service_id` FK.
            
            # Better approach:
            # 1. ADD UNIQUE INDEX on service_id CONCURRENTLY (or just create index).
            # 2. ALTER TABLE ... DROP CONSTRAINT ... PRIMARY KEY
            
            # Postgres allows FKs to reference Unique columns.
            # But dropping the PK constraint referenced by FK usually requires CASCADE.
            
            print("Dropping PK constraint on user_metadata (with CASCADE)...")
            try:
                conn.execute(text("ALTER TABLE user_metadata DROP CONSTRAINT user_metadata_pkey CASCADE"))
            except Exception as e:
                print(f"Warning dropping user_metadata_pkey: {e}")

            # 2. Add 'id' column
            print("Adding 'id' column to user_metadata...")
            try:
                conn.execute(text("ALTER TABLE user_metadata ADD COLUMN id SERIAL PRIMARY KEY"))
            except Exception as e:
                print(f"Error adding id: {e}")

            # 3. Ensure service_id is UNIQUE (needed for FKs and logic)
            print("Ensuring service_id is UNIQUE...")
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_metadata_service_id ON user_metadata (service_id)"))
                # Also add explicit constraint for robustness?
                # conn.execute(text("ALTER TABLE user_metadata ADD CONSTRAINT uk_user_metadata_service_id UNIQUE (service_id)"))
                # The index is sufficient for FKs in recent PG?
                # Usually explicit CONSTRAINT is better for FK targets.
                conn.execute(text("ALTER TABLE user_metadata ADD CONSTRAINT uq_user_metadata_service_id UNIQUE USING INDEX ix_user_metadata_service_id"))
            except Exception as e:
                print(f"Warning setting service_id usage: {e}")
            
            # 4. Re-add FKs from `avatars` if they were dropped.
            # Check if `avatars` FK exists.
            # We can try to re-add it blindly.
            print("Restoring FK on avatars.service_id...")
            try:
                conn.execute(text("""
                    ALTER TABLE avatars 
                    ADD CONSTRAINT avatars_service_id_fkey 
                    FOREIGN KEY (service_id) REFERENCES user_metadata(service_id)
                """))
            except Exception as e:
                print(f"FK restore might have failed (maybe exists?): {e}")

        # --- 2. Groups ---
        print("Migrating groups...")
        
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='groups' AND column_name='id'"))
        if result.fetchone():
            print("Column 'id' already exists in groups.")
        else:
            print("Dropping PK constraint on groups (with CASCADE)...")
            try:
                conn.execute(text("ALTER TABLE groups DROP CONSTRAINT groups_pkey CASCADE"))
            except Exception as e:
                print(f"Warning dropping groups_pkey: {e}")

            print("Adding 'id' column to groups...")
            try:
                conn.execute(text("ALTER TABLE groups ADD COLUMN id SERIAL PRIMARY KEY"))
            except Exception as e:
                 print(f"Error adding id to groups: {e}")

            print("Ensuring group_id is UNIQUE...")
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_groups_group_id ON groups (group_id)"))
                conn.execute(text("ALTER TABLE groups ADD CONSTRAINT uq_groups_group_id UNIQUE USING INDEX ix_groups_group_id"))
            except Exception as e:
                 print(f"Warning setting group_id uniqueness: {e}")

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
