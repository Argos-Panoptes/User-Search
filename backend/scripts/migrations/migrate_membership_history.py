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


def migrate_membership_history():
    """
    Creates the group_membership_history table.
    """
    engine = create_engine(settings.DATABASE_URL)

    with engine.begin() as conn:
        logger.info("Checking/Creating group_membership_history table...")

        # Create Table SQL
        create_sql = text(
            """
        CREATE TABLE IF NOT EXISTS group_membership_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES user_metadata(id),
            group_id INTEGER NOT NULL REFERENCES groups(id),
            role VARCHAR,
            valid_from TIMESTAMPTZ DEFAULT NOW(),
            valid_to TIMESTAMPTZ,
            job_id INTEGER
        );
        """
        )
        conn.execute(create_sql)

        # Create Indexes for performance
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gmh_user_id ON group_membership_history (user_id);"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gmh_group_id ON group_membership_history (group_id);"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gmh_valid_range ON group_membership_history (valid_from, valid_to);"
            )
        )

        logger.info("Migration complete.")


if __name__ == "__main__":
    migrate_membership_history()
