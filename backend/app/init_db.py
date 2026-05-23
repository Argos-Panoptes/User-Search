import time
import logging
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.engine import Engine
from sqlalchemy import inspect as sa_inspect
from app.db.base import Base
from app.db.session import engine
from app.db.triggers import init_db_triggers

# Support modern type hints
from typing import Optional

# Import all models to ensure they are registered with Base.metadata
from app.db.schemas.auth_tables import *
from app.db.schemas.app_models import *
from app.db.schemas.ingestion_models import *
from app.db.schemas.stripe_models import *
from app.db.schemas.api_key_models import *
from datetime import datetime, timezone
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wait_for_db(db_engine: Engine, timeout: int = 60) -> bool:
    """
    Loops until a connection to the database is established or timeout is reached.
    """
    logger.info("Waiting for database connection...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection established.")
                return True
        except OperationalError:
            logger.info("Database not ready yet, retrying in 2 seconds...")
            time.sleep(2)

    logger.error(f"Could not connect to database within {timeout} seconds.")
    return False


def ensure_unique_constraints(db_engine: Engine) -> None:
    """
    Ensures that the necessary unique constraints exist for ON CONFLICT operations.
    Handles existing constraints and unique indices, and uses separate transactions
    to avoid 'InFailedSqlTransaction' errors.
    """
    constraints = [
        {
            "table": "group_memberships_map",
            "name": "uq_user_group_membership",
            "definition": "UNIQUE (user_id, group_id)",
        },
        {
            "table": "user_timeline_ledger",
            "name": "uq_user_timeline_job",
            "definition": "UNIQUE (user_id, job_id, export_timestamp)",
        },
        {
            "table": "group_timeline_ledger",
            "name": "uq_group_timeline_job",
            "definition": "UNIQUE (group_pk, job_id, export_timestamp)",
        },
    ]

    for c in constraints:
        table = c["table"]
        name = c["name"]
        definition = c["definition"]

        # Use a fresh connection/transaction for each constraint
        with db_engine.begin() as conn:
            # 1. Check if constraint or unique index exists with this name
            # pg_constraint covers constraints, pg_class covers indices (relkind='i')
            check_sql = text(
                """
                SELECT 1 FROM pg_constraint WHERE conname = :name
                UNION ALL
                SELECT 1 FROM pg_class WHERE relname = :name AND relkind = 'i'
            """
            )
            exists = conn.execute(check_sql, {"name": name}).fetchone()

            if not exists:
                logger.info(f"Adding missing constraint {name} to {table}...")
                try:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition}")
                    )
                    logger.info(f"Successfully added constraint {name}.")
                except (ProgrammingError, OperationalError) as e:
                    logger.warning(f"Could not add constraint {name} to {table}: {e}")
            else:
                logger.info(
                    f"Unique constraint/index {name} already exists on {table}."
                )


def init_db() -> None:
    logger.info("Standalone DB Initialization started...")

    # 1. Wait for DB
    logger.info("Step 1: Waiting for database connection...")
    if not wait_for_db(engine):
        logger.error("Step 1 Failed: Database connection timeout.")
        raise Exception("Database connection timeout.")
    logger.info("Step 1 Success: Database connection established.")

    try:
        # 2. Create tables
        logger.info("Step 2: Creating database tables using SQLAlchemy create_all...")
        Base.metadata.create_all(bind=engine)
        logger.info("Step 2 Success: Tables created.")

        # 3. Ensure constraints (Important for ON CONFLICT logic)
        logger.info("Step 3: Verifying and adding unique constraints...")
        ensure_unique_constraints(engine)
        logger.info("Step 3 Success: Constraints verified.")

        # 3b. Ensure soft-delete columns exist (for existing databases)
        logger.info("Step 3b: Ensuring soft-delete columns exist...")
        _ensure_soft_delete_columns(engine)
        logger.info("Step 3b Success: Soft-delete columns verified.")

        # 3c. Ensure avatar sync columns exist (for existing databases)
        logger.info("Step 3c: Ensuring avatar sync columns exist...")
        _ensure_avatar_sync_columns(engine)
        logger.info("Step 3c Success: Avatar sync columns verified.")

        # 3d. Ensure per-user API limit columns exist (for existing databases)
        logger.info("Step 3d: Ensuring user API limit columns exist...")
        _ensure_user_limit_columns(engine)
        logger.info("Step 3d Success: User API limit columns verified.")

        # 4. Initialize triggers
        logger.info("Step 4: Initializing database triggers...")
        init_db_triggers(engine)
        logger.info("Step 4 Success: Triggers initialized.")

        # 5. Initialize partitions for history tables
        logger.info("Step 5: Initializing partitions for history tables...")
        _init_partitions(engine)
        logger.info("Step 5 Success: Partitions initialized.")

        # 6. Tune autovacuum for high-upsert tables
        logger.info("Step 6: Tuning autovacuum parameters...")
        _tune_autovacuum(engine)
        logger.info("Step 6 Success: Autovacuum tuned.")

        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.error(
            f"Database initialization failed during Step {getattr(e, 'step', 'unknown') if hasattr(e, 'step') else 'processing'}: {e}"
        )
        import traceback

        logger.error(traceback.format_exc())
        raise e


def _ensure_soft_delete_columns(db_engine: Engine) -> None:
    """
    Adds is_active columns to existing tables if they don't exist.
    Required for databases created before the soft-delete feature.
    """
    migrations = [
        ("user_metadata", "is_active", "BOOLEAN DEFAULT TRUE NOT NULL"),
        ("user_history", "is_active", "BOOLEAN"),
        ("group_membership_history", "is_active", "BOOLEAN DEFAULT TRUE"),
    ]
    with db_engine.begin() as conn:
        inspector = sa_inspect(conn)
        for table_name, column_name, col_type in migrations:
            try:
                columns = [c["name"] for c in inspector.get_columns(table_name, schema="public")]
                if column_name not in columns:
                    logger.info(f"Adding column {column_name} to {table_name}")
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {col_type}'))
                    if "NOT NULL" in col_type:
                        conn.execute(text(f"UPDATE {table_name} SET {column_name} = TRUE WHERE {column_name} IS NULL"))
            except Exception as e:
                logger.warning(f"Could not add column {column_name} to {table_name}: {e}")

        # Create index on user_metadata.is_active if not exists
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_user_metadata_is_active ON user_metadata (is_active)"
            ))
        except Exception as e:
            logger.warning(f"Could not create is_active index: {e}")


def _ensure_avatar_sync_columns(db_engine: Engine) -> None:
    """
    Adds avatar sync (Part B) columns to existing avatars table if they don't exist.
    Required for databases created before the scheduled revalidation feature.
    """
    migrations = [
        ("avatars", "last_verified_at", "TIMESTAMPTZ"),
        ("avatars", "stored_etag", "VARCHAR"),
        ("avatars", "verification_status", "VARCHAR(20)"),
        ("avatars", "change_frequency", "VARCHAR(10)"),
        ("avatars", "failure_reason", "VARCHAR(100)"),
    ]
    with db_engine.begin() as conn:
        inspector = sa_inspect(conn)
        try:
            columns = [
                c["name"]
                for c in inspector.get_columns("avatars", schema="public")
            ]
            for table_name, column_name, col_type in migrations:
                if column_name not in columns:
                    logger.info(f"Adding column {column_name} to {table_name}")
                    conn.execute(
                        text(
                            f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {col_type}'
                        )
                    )
        except Exception as e:
            logger.warning(f"Could not ensure avatar sync columns: {e}")

        # Smart filtering indexes for scheduled sync
        indexes = [
            # Index 1: last_verified_at for finding stale avatars
            (
                "idx_avatars_last_verified",
                "ON avatars (last_verified_at) WHERE s3_key IS NOT NULL",
            ),
            # Index 2: Compound index for smart filtering by change_frequency + age
            (
                "idx_avatars_change_freq_verified",
                "ON avatars (change_frequency, last_verified_at) WHERE s3_key IS NOT NULL",
            ),
            # Index 3: verification_status for finding failed/changed avatars
            (
                "idx_avatars_verification_status",
                "ON avatars (verification_status) WHERE s3_key IS NOT NULL",
            ),
        ]
        for idx_name, idx_def in indexes:
            try:
                conn.execute(
                    text(f"CREATE INDEX IF NOT EXISTS {idx_name} {idx_def}")
                )
            except Exception as e:
                logger.warning(f"Could not create index {idx_name}: {e}")


def _ensure_user_limit_columns(db_engine: Engine) -> None:
    """
    Adds per-user API limit columns to app_users if they don't exist.
    Required for databases created before the per-user limit feature.
    """
    migrations = [
        ("app_users", "rate_limit_per_minute", "INTEGER"),
        ("app_users", "max_api_keys", "INTEGER"),
        ("app_users", "api_password_hash", "TEXT"),
    ]
    with db_engine.begin() as conn:
        inspector = sa_inspect(conn)
        try:
            columns = [
                c["name"]
                for c in inspector.get_columns("app_users", schema="public")
            ]
            for table_name, column_name, col_type in migrations:
                if column_name not in columns:
                    logger.info(f"Adding column {column_name} to {table_name}")
                    conn.execute(
                        text(
                            f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {col_type}'
                        )
                    )
        except Exception as e:
            logger.warning(f"Could not ensure user limit columns: {e}")


def _init_partitions(db_engine: Engine) -> None:
    """
    Creates the initial partitions for history and ledger tables.
    """
    now = datetime.now(timezone.utc)
    partitions = []

    # Generate partitions for the last 12 months + current + next month
    for i in range(-12, 2):
        year = now.year
        month = now.month + i
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1

        month_start = datetime(year, month, 1, tzinfo=timezone.utc)

        next_m = month + 1
        next_y = year
        if next_m > 12:
            next_m = 1
            next_y += 1
        month_end = datetime(next_y, next_m, 1, tzinfo=timezone.utc)

        partitions.append(
            {
                "suffix": f"{year}_{month:02d}",
                "start": month_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": month_end.strftime("%Y-%m-%d %H:%M:%S"),
                "is_default": False,
            }
        )

    partitions.append({"suffix": "default", "is_default": True})

    tables = [
        {"name": "user_history", "id_col": "service_id", "part_col": "history_date"},
        {"name": "group_history", "id_col": "group_id", "part_col": "history_date"},
        {"name": "avatar_history", "id_col": "service_id", "part_col": "history_date"},
        {
            "name": "user_timeline_ledger",
            "id_col": "user_id",
            "part_col": "export_timestamp",
        },
        {
            "name": "group_timeline_ledger",
            "id_col": "group_pk",
            "part_col": "export_timestamp",
        },
        {
            "name": "group_membership_history",
            "id_col": "user_id",
            "part_col": "valid_from",
        },
    ]

    with db_engine.begin() as conn:
        for table in tables:
            t_name = table["name"]
            id_col = table["id_col"]
            part_col = table["part_col"]
            for p in partitions:
                part_name = f"{t_name}_{p['suffix']}"
                check_stmt = text(f"SELECT to_regclass('public.{part_name}')")
                if not conn.execute(check_stmt).scalar():
                    if p["is_default"]:
                        create_part_stmt = text(
                            f"CREATE TABLE {part_name} PARTITION OF {t_name} DEFAULT"
                        )
                    else:
                        create_part_stmt = text(
                            f"CREATE TABLE {part_name} PARTITION OF {t_name} "
                            f"FOR VALUES FROM ('{p['start']}') TO ('{p['end']}')"
                        )
                    conn.execute(create_part_stmt)

                    # Create indexes on the new partition
                    idx_composite = f"idx_{part_name}_{id_col}_date"
                    conn.execute(
                        text(
                            f"CREATE INDEX IF NOT EXISTS {idx_composite} ON {part_name} ({id_col}, {part_col} DESC)"
                        )
                    )

                    idx_brin = f"idx_{part_name}_brin_date"
                    conn.execute(
                        text(
                            f"CREATE INDEX IF NOT EXISTS {idx_brin} ON {part_name} USING brin ({part_col})"
                        )
                    )


def _tune_autovacuum(db_engine: Engine) -> None:
    """
    Tunes autovacuum parameters for specific tables.
    """
    tables_to_tune = ["user_metadata", "groups", "group_memberships_map"]
    with db_engine.begin() as conn:
        for table in tables_to_tune:
            tune_stmt = text(
                f"""
                ALTER TABLE {table} SET (
                    autovacuum_vacuum_scale_factor = 0.05,
                    autovacuum_analyze_scale_factor = 0.02,
                    autovacuum_vacuum_cost_limit = 1000
                )
            """
            )
            try:
                conn.execute(tune_stmt)
            except Exception as e:
                logger.warning(f"Could not tune autovacuum for {table}: {e}")


if __name__ == "__main__":
    init_db()
