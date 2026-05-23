import logging
from sqlalchemy import create_engine, text
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        try:
            # Check if column exists
            result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='ingestion_jobs' AND column_name='content_hash'"
                )
            )
            if result.fetchone():
                logger.info("Column 'content_hash' already exists.")
                return

            logger.info("Adding column 'content_hash' to ingestion_jobs...")
            conn.execute(
                text("ALTER TABLE ingestion_jobs ADD COLUMN content_hash VARCHAR")
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_ingestion_jobs_content_hash ON ingestion_jobs (content_hash)"
                )
            )
            logger.info("Migration successful.")
        except Exception as e:
            logger.error(f"Migration failed: {e}")


if __name__ == "__main__":
    migrate()
