import logging
import os
import sys
from sqlalchemy import create_engine, text

# Add parent directory to path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_avatars_schema():
    engine = create_engine(settings.DATABASE_URL)

    with engine.begin() as conn:
        logger.info("Migrating avatars table schema...")

        # 1. Check existing constraints
        # We expect a unique constraint on service_id.
        # It's likely an index named 'ix_avatars_service_id' or a unique constraint 'avatars_service_id_key'.

        # Drop unique constraint/index on service_id
        try:
            conn.execute(text("DROP INDEX IF EXISTS ix_avatars_service_id"))
            logger.info("Dropped index ix_avatars_service_id")
        except Exception as e:
            logger.warning(f"Could not drop index: {e}")

        try:
            conn.execute(
                text(
                    "ALTER TABLE avatars DROP CONSTRAINT IF EXISTS avatars_service_id_key"
                )
            )
            logger.info("Dropped constraint avatars_service_id_key")
        except Exception as e:
            logger.warning(f"Could not drop constraint: {e}")

        # 2. Create standard (non-unique) index on service_id for performance
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_avatars_service_id_nonunique ON avatars (service_id)"
            )
        )
        logger.info("Created non-unique index on service_id")

        # 3. Create unique constraint/index on s3_key (to identify unique files)
        # We need to handle potential duplicates before adding unique constraint?
        # If multiple users point to same s3_key? Unlikely.
        # If the same s3_key is in the table twice? (Different IDs, same content).
        # We should deduplicate first if needed.

        # Dedup: Delete duplicate s3_keys, keeping the latest ID?
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
        logger.info("Deduplicated avatars by s3_key")

        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_avatars_s3_key ON avatars (s3_key)"
            )
        )
        logger.info("Created unique index on s3_key")

    logger.info("Migration complete.")


if __name__ == "__main__":
    migrate_avatars_schema()
