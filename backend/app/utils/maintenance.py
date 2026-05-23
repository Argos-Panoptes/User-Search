import logging
from sqlalchemy import text, create_engine
from app.core.config import settings

logger = logging.getLogger(__name__)


def run_vacuum_analyze(tables=None):
    """
    Runs VACUUM ANALYZE on the specified tables or the whole database.
    Note: VACUUM cannot be run inside a transaction.
    """
    # Use a dedicated engine and connection without autocommit=False (default is fine for raw)
    # Actually, SQLAlchemy's 'begin' or 'connect' usually manages transactions.
    # To run VACUUM, we need to be outside a transaction.
    engine = create_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"),
        isolation_level="AUTOCOMMIT",
    )

    if tables is None:
        logger.info("Running VACUUM ANALYZE on the entire database...")
        stmt = "VACUUM ANALYZE"
    else:
        logger.info(f"Running VACUUM ANALYZE on tables: {', '.join(tables)}")
        # For multiple tables, we run them sequentially or as one if PostgreSQL supports it (it does: VACUUM ANALYZE table1, table2)
        stmt = f"VACUUM ANALYZE {', '.join(tables)}"

    try:
        with engine.connect() as conn:
            conn.execute(text(stmt))
        logger.info("VACUUM ANALYZE completed successfully.")
    except Exception as e:
        logger.error(f"VACUUM ANALYZE failed: {e}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    run_vacuum_analyze(["user_metadata", "groups"])
