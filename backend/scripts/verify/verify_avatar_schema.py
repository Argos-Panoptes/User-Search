import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.core.config import settings


def verify_and_fix_schema():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)

    # Check indexes on avatars table
    indexes = inspector.get_indexes("avatars")
    unique_constraints = inspector.get_unique_constraints("avatars")

    print("Current Indexes:", indexes)
    print("Current Unique Constraints:", unique_constraints)

    service_id_unique = False
    s3_key_unique = False

    for idx in indexes:
        # Check column names (list of strings)
        cols = idx.get("column_names", [])
        if "service_id" in cols and idx.get("unique", False):
            service_id_unique = True
        if "s3_key" in cols and idx.get("unique", False):
            s3_key_unique = True

    # Also check unique constraints explicitly
    for const in unique_constraints:
        cols = const.get("column_names", [])
        if "service_id" in cols:
            service_id_unique = True
        if "s3_key" in cols:
            # We treat constraint as proof of uniqueness too
            s3_key_unique = True

    print(f"Is service_id unique? {service_id_unique}")
    print(f"Is s3_key unique? {s3_key_unique}")

    if service_id_unique:
        print("FAIL: service_id is still unique. Attempting to fix...")
        with engine.begin() as conn:
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_avatars_service_id"))
                conn.execute(
                    text(
                        "ALTER TABLE avatars DROP CONSTRAINT IF EXISTS avatars_service_id_key"
                    )
                )
                print("Dropped service_id constraints.")
            except Exception as e:
                print(f"Error dropping service_id constraints: {e}")

    if not s3_key_unique:
        print("FAIL: s3_key is not unique. Attempting to fix...")
        with engine.begin() as conn:
            try:
                # Dedup first
                conn.execute(
                    text(
                        """
                    DELETE FROM avatars a
                    USING avatars b
                    WHERE a.id < b.id
                    AND a.s3_key = b.s3_key
                """
                    )
                )
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_avatars_s3_key ON avatars (s3_key)"
                    )
                )
                print("Created s3_key unique index.")
            except Exception as e:
                print(f"Error creating s3_key index: {e}")

    # Re-check
    inspector = inspect(engine)
    indexes = inspector.get_indexes("avatars")
    service_id_unique_now = any(
        "service_id" in i["column_names"] and i["unique"] for i in indexes
    )
    print(f"Final check - service_id unique: {service_id_unique_now}")


if __name__ == "__main__":
    verify_and_fix_schema()
