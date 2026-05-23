import logging
from sqlalchemy import create_engine, text
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_groups_boolean():
    logger.info("Starting migration: groups.admin_approval_required -> BOOLEAN")

    engine = create_engine(settings.DATABASE_URL)

    with engine.begin() as conn:
        # Check current type (optional, but good for safety)
        # We'll just execute the ALTER command.

        sql = text(
            """
            ALTER TABLE groups 
            ALTER COLUMN admin_approval_required TYPE BOOLEAN 
            USING CASE 
                WHEN LOWER(admin_approval_required) = 'yes' THEN true 
                WHEN LOWER(admin_approval_required) = 'no' THEN false 
                ELSE null 
            END;
        """
        )

        logger.info("Executing ALTER TABLE command...")
        conn.execute(sql)
        logger.info("Migration successful.")


if __name__ == "__main__":
    try:
        migrate_groups_boolean()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        exit(1)
