import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.core.celery_app import celery_app
from app.db.session import engine
from app.controllers.upload_controller import UploadController
from app.utils.maintenance import run_vacuum_analyze

logger = logging.getLogger(__name__)


@celery_app.task(name="maintenance_tasks.daily_maintenance")
def daily_maintenance() -> None:
    """
    Scheduled daily maintenance task.
    1. Runs VACUUM ANALYZE on the whole database.
    2. Prunes partitions older than 18 months.
    """
    logger.info("Starting daily database maintenance...")

    # 1. Full Vacuum Analyze (Refreshes stats and reclaims space)
    try:
        run_vacuum_analyze()
    except Exception as e:
        logger.error(f"Daily vacuum failed: {e}")

    # 2. Partition Pruning
    try:
        _prune_old_partitions()
    except Exception as e:
        logger.error(f"Partition pruning failed: {e}")

    logger.info("Daily database maintenance completed.")


@celery_app.task(name="maintenance_tasks.cleanup_stale_uploads_task")
def cleanup_stale_uploads_task(max_age_hours: int = 24) -> int:
    """
    Identifies and removes temporary upload folders older than max_age_hours.
    """
    logger.info(f"Starting stale upload cleanup (max_age={max_age_hours}h)...")
    try:
        removed_count = UploadController.cleanup_stale_uploads(max_age_hours)
        logger.info(f"Cleanup completed. Removed {removed_count} stale folders.")
        return removed_count
    except Exception as e:
        logger.error(f"Stale upload cleanup failed: {e}", exc_info=True)
        return 0


def _prune_old_partitions(retention_months: int = 18) -> None:
    """
    Identifies and drops partitions older than the retention period.
    Names follow the pattern {table}_{year}_{month}.
    """
    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=retention_months * 30)

    tables = [
        "user_history",
        "group_history",
        "avatar_history",
        "group_membership_history",
        "user_timeline_ledger",
        "group_timeline_ledger",
    ]

    with engine.begin() as conn:
        for t_name in tables:
            # We look for partitions using a regex/pattern in information_schema or pg_class
            # Simpler: we iterate back from cutoff_date - 1 month to cutoff_date - 24 months
            # and try to drop if they exist.

            for i in range(1, 12):  # Look back further if needed
                target_date = cutoff_date - timedelta(days=i * 30)
                suffix = target_date.strftime("%Y_%m")
                part_name = f"{t_name}_{suffix}"

                # Check if exists and drop
                check_stmt = text(
                    f"SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = '{part_name}'"
                )
                result = conn.execute(check_stmt).scalar()

                if result:
                    logger.info(f"Pruning old partition: {part_name}")
                    conn.execute(text(f"DROP TABLE {part_name}"))


logger.info("Maintenance tasks registered.")
