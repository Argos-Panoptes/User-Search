import logging
import sys
import os

# Ensure backend root is in sys.path
sys.path.append(os.getcwd())

from sqlalchemy import text, inspect
from app.db.session import engine
from app.db.base import Base
from app.db.triggers import init_db_triggers

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def update_database_schema():
    logger.info("Checking and updating database schema...")

    # Force connection check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    inspector = inspect(engine)

    tables_to_update = [
        "user_history",
        "group_history",
        "avatar_history",
        "group_membership_history",
    ]

    with engine.connect() as conn:
        for table in tables_to_update:
            logger.info(f"Checking table: {table}")
            try:
                columns = [col["name"] for col in inspector.get_columns(table)]

                if "previous_data" not in columns:
                    logger.info(f"Adding previous_data column to {table}")
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN previous_data JSONB")
                    )

                if "current_data" not in columns:
                    logger.info(f"Adding current_data column to {table}")
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN current_data JSONB")
                    )

                # Add timeline_id to avatar_history if missing
                if table == "avatar_history" and "timeline_id" not in columns:
                    logger.info(f"Adding timeline_id column to {table}")
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN timeline_id INTEGER REFERENCES user_timeline_ledger(id)"
                        )
                    )

                # Specific columns for group_membership_history
                if table == "group_membership_history":
                    if "timeline_id" in columns and "join_timeline_id" not in columns:
                        logger.info(
                            f"Renaming timeline_id to join_timeline_id in {table}"
                        )
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} RENAME COLUMN timeline_id TO join_timeline_id"
                            )
                        )
                    elif "join_timeline_id" not in columns:
                        logger.info(f"Adding join_timeline_id column to {table}")
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN join_timeline_id INTEGER REFERENCES user_timeline_ledger(id)"
                            )
                        )

                    if (
                        "group_timeline_id" in columns
                        and "join_group_timeline_id" not in columns
                    ):
                        logger.info(
                            f"Renaming group_timeline_id to join_group_timeline_id in {table}"
                        )
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} RENAME COLUMN group_timeline_id TO join_group_timeline_id"
                            )
                        )
                    elif "join_group_timeline_id" not in columns:
                        logger.info(f"Adding join_group_timeline_id column to {table}")
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN join_group_timeline_id INTEGER REFERENCES group_timeline_ledger(id)"
                            )
                        )

                    if "exit_timeline_id" not in columns:
                        logger.info(f"Adding exit_timeline_id column to {table}")
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN exit_timeline_id INTEGER REFERENCES user_timeline_ledger(id)"
                            )
                        )

                    if "exit_group_timeline_id" not in columns:
                        logger.info(f"Adding exit_group_timeline_id column to {table}")
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN exit_group_timeline_id INTEGER REFERENCES group_timeline_ledger(id)"
                            )
                        )

            except Exception as e:
                logger.error(f"Error checking/updating table {table}: {e}")

        # 2. Update 'groups' and 'group_history' with new columns if missing
        for table in ["groups", "group_history"]:
            try:
                logger.info(f"Ensuring extended columns in {table}")
                columns = [col["name"] for col in inspector.get_columns(table)]

                new_cols = {
                    "master_key": "TEXT",
                    "invite_link_password": "TEXT",
                    "secret_params": "TEXT",
                    "public_params": "TEXT",
                    "reconstructed_link": "TEXT",
                    "retention_period": "TEXT",
                    "description": "TEXT",
                }

                for col_name, col_type in new_cols.items():
                    if col_name not in columns:
                        logger.info(f"Adding {col_name} to {table}")
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                            )
                        )
            except Exception as e:
                logger.error(f"Error ensuring columns in {table}: {e}")

        # 3. Create 'subscriptions' and 'payment_transactions' tables if they don't exist
        for model in ["subscriptions", "payment_transactions"]:
            if not inspector.has_table(model):
                logger.info(f"Creating table {model}")
                try:
                    # We import here to ensure they are registered with Base
                    from app.db.schemas.stripe_models import (
                        Subscription,
                        PaymentTransaction,
                    )

                    # Create the tables using SQLAlchemy's metadata
                    Base.metadata.create_all(bind=engine)
                    logger.info(f"Table {model} created successfully.")
                except Exception as e:
                    logger.error(f"Error creating table {model}: {e}")

        conn.commit()

        # 4. Check 'ingestion_jobs' for 'created_by_id'
        try:
            if inspector.has_table("ingestion_jobs"):
                columns = [
                    col["name"] for col in inspector.get_columns("ingestion_jobs")
                ]
                if "created_by_id" not in columns:
                    logger.info("Adding created_by_id column to ingestion_jobs")
                    conn.execute(
                        text(
                            "ALTER TABLE ingestion_jobs ADD COLUMN created_by_id INTEGER REFERENCES app_users(id)"
                        )
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Error checking ingestion_jobs: {e}")

        # 5. Add first_observed/last_observed to user_metadata and groups
        for table in ["user_metadata", "groups"]:
            try:
                if inspector.has_table(table):
                    columns = [
                        col["name"] for col in inspector.get_columns(table)
                    ]
                    for col_name in ["first_observed", "last_observed"]:
                        if col_name not in columns:
                            logger.info(f"Adding {col_name} column to {table}")
                            conn.execute(
                                text(
                                    f"ALTER TABLE {table} ADD COLUMN {col_name} TIMESTAMP"
                                )
                            )
                    conn.commit()
            except Exception as e:
                logger.error(f"Error adding observed columns to {table}: {e}")

    logger.info("Schema update complete.")


def update_triggers():
    logger.info("Updating database triggers...")
    try:
        init_db_triggers(engine)
        logger.info("Triggers updated.")
    except Exception as e:
        logger.error(f"Failed to update triggers: {e}")


if __name__ == "__main__":
    try:
        update_database_schema()
        update_triggers()
        logger.info("Database verification and update successful.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
