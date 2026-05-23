from app.core.celery_app import celery_app
from celery import Task
from celery.exceptions import Retry
from app.ingestion.processors.user_processor import process_user_data
from app.ingestion.processors.group_processor import (
    process_group_data,
    extract_groups_from_staging,
)
from app.ingestion.processors.avatar_processor import process_avatar_manifest_spark
from app.ingestion.processors.membership_processor import (
    process_memberships_sql,
    compute_member_counts_sql,
)
from app.ingestion.search_indexer import index_users_from_db, index_groups_from_db
from app.core.logging import logger
from app.db.session import SessionLocal
from app.controllers.jobs_controller import JobsController
from datetime import datetime, timezone
from app.controllers.history_controller import HistoryController
from app.utils.ingestion_helpers import (
    SUBSTEP_DEFINITIONS,
    _mark_substep,
    _update_action,
    _ensure_all_steps_created,
    _get_step_id,
    get_job_db_logger,
    _ensure_steps_generic,
)
from app.db.schemas.ingestion_models import IngestionJob
from app.utils.maintenance import run_vacuum_analyze
from app.utils.system_check import is_storage_critical, get_disk_usage_percent
from sqlalchemy.orm import Session
from typing import Callable, Any, TYPE_CHECKING, Protocol, cast


class JobLogger(Protocol):
    def __call__(
        self, message: str, level: str = "INFO", step: str | None = None
    ) -> None: ...


def _check_and_queue_if_blocked(
    db: Session,
    job_id: int,
    ingestion_type: str,
    db_log: JobLogger,
    retry_exc: Callable[..., Any],
) -> None:
    """
    Checks for older active jobs (running, queued, pending) of the same type.
    If found, sets current job to 'queued' and raises Retry.
    If not, sets current job to 'running' and proceeds.
    """

    # 1. Check for older active jobs (FIFO enforcement)
    # Active = running, queued, pending
    # Older = id < job_id
    older_active_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.ingestion_type == ingestion_type,
            IngestionJob.id < job_id,
            IngestionJob.status.in_(["running", "queued", "pending", "initializing"]),
        )
        .first()
    )

    if older_active_job:
        # We are blocked -> Queue ourselves
        current_job = JobsController.get_job(db, job_id)
        if current_job:
            # Update status to 'queued' if not already
            if current_job.status != "queued":
                current_job.status = "queued"
                db.commit()
                db_log(
                    f"Job queued. Waiting for Job #{older_active_job.id} (Status: {older_active_job.status}) to finish...",
                    level="INFO",
                )
            else:
                # Already queued, just log debug or nothing to reduce noise?
                # db_log(f"Still waiting for Job #{older_active_job.id}...", level="DEBUG")
                pass

        # Raise Retry to check again later
        raise retry_exc(countdown=10)  # Check every 10s for responsiveness

    # 2. If we are here, we are the oldest active job.
    # We should mark ourselves as running.
    JobsController.mark_job_running(db, job_id)


def _enforce_storage_limit(db: Session, job_id: int, db_log: JobLogger) -> None:
    """
    Checks if system storage is critical (>90%) and raises an exception if it is.
    """
    if is_storage_critical(threshold=0.9):
        usage = get_disk_usage_percent() * 100
        error_msg = (
            f"Ingestion aborted: System storage usage is at {usage:.1f}%. "
            "Please increase storage capacity to proceed with ingestion."
        )
        db_log(error_msg, level="ERROR")
        _fail_job(db, job_id, error_msg)
        raise Exception(error_msg)


@celery_app.task(bind=True)
def rollback_job_task(self: Task, rollback_job_id: int, target_job_id: int) -> None:
    """
    Rolls back a specific ingestion job by reverting DB changes and syncing OpenSearch.
    """
    from app.db.session import SessionLocal
    from app.controllers.jobs_controller import JobsController
    from app.ingestion import search_indexer

    db = SessionLocal()
    rollback_job = None

    try:
        # Get the pre-created rollback job
        rollback_job = JobsController.get_job(db, rollback_job_id)
        if not rollback_job:
            logger.error(f"Rollback job {rollback_job_id} not found")
            return

        job_id = rollback_job.id

        # Initialize Steps for Rollback
        step_name = "revert_ingestion"
        step = JobsController.create_step(db, job_id, step_name)
        JobsController.set_substeps(db, step.id, SUBSTEP_DEFINITIONS[step_name])
        step_id = step.id

        def job_log(msg: str, level: str = "INFO") -> None:
            JobsController.add_log(db, job_id, msg, level)

        job_log(f"Starting rollback for Job {target_job_id}")
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        # 2. Identify Affected Records
        _update_action(step_id, "Identifying affected records...")
        _mark_substep(step_id, "Identifying affected records")
        job_log("Identifying affected records...")
        affected = JobsController.get_job_affected_ids(db, target_job_id)

        # 3. Perform DB Rollback
        _update_action(step_id, "Reverting database changes...")
        _mark_substep(step_id, "Reverting database changes")
        job_log("Reverting database changes...")
        JobsController.perform_db_rollback(db, target_job_id, log_func=job_log)

        # 4. Sync OpenSearch
        _update_action(step_id, "Syncing OpenSearch indexes...")
        _mark_substep(step_id, "Syncing OpenSearch indexes")
        job_log("Syncing OpenSearch indexes...")

        # 4a. Delete documents inserted by the target job
        search_indexer.delete_documents_by_job_id(target_job_id, log_func=job_log)

        # 4b. Re-index documents that were updated by the target job
        users_to_reindex = affected["users"]["updated"]
        if users_to_reindex:
            job_log(f"Re-indexing {len(users_to_reindex)} reverted users...")
            search_indexer.index_users_by_ids(users_to_reindex, log_func=job_log)

        groups_to_reindex = affected["groups"]["updated"]
        if groups_to_reindex:
            job_log(f"Re-indexing {len(groups_to_reindex)} reverted groups...")
            search_indexer.index_groups_by_ids(groups_to_reindex, log_func=job_log)

        # 5. Mark Complete
        JobsController.mark_job_rolled_back(db, target_job_id)

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Rollback Complete")

        rollback_job.status = "completed"
        # rollback_job.progress_percentage = 100
        rollback_job.completed_at = datetime.now(timezone.utc)
        db.commit()

        job_log("Rollback completed successfully.")

    except Exception as e:
        if rollback_job:
            rollback_job.status = "failed"
            rollback_job.error_message = str(e)
            db.commit()
            JobsController.add_log(
                db, rollback_job.id, f"Rollback failed: {str(e)}", "ERROR"
            )
        logger.error(f"Rollback task failed: {e}")
        raise e
    finally:
        db.close()


# --- Core Pipeline Tasks ---


@celery_app.task(bind=True, max_retries=None, name="ingestion_tasks.process_users_step")
def process_users_step(self: Task, file_path: str, job_id: int) -> dict[str, Any]:
    db_log: JobLogger = get_job_db_logger(job_id)
    db = SessionLocal()
    try:
        # Serial Execution Enforcement (FIFO)
        _check_and_queue_if_blocked(db, job_id, "users", db_log, self.retry)

        # Storage Limit Check
        _enforce_storage_limit(db, job_id, db_log)

        db_log(f"Starting Pipeline. File: {file_path}", step="processing_users")

        # 1. Pre-create all steps for UI visibility
        _ensure_all_steps_created(job_id)

        step_name = "processing_users"
        step_id = _get_step_id(job_id, step_name)

        JobsController.update_step_progress(db, step_id, 0.0, "running")

        # Substep 1: Unzipping
        # We manually set current action to 1st pending substep if we want
        # _mark_substep(step_id, "Unzipping file")  # Just marking as running/done?
        # Wait, complete_substep marks as COMPLETED.
        # So we should probably 'Complete' them as they happen.
        # But for 'current action', we want to show it BEFORE it completes?
        # Let's trust _update_action for 'current status' and _mark_substep for 'checklist check'.

        # _update_action(step_id, "Processing SQL dump")
        # (Assuming process_user_data does unzipping internally early on)

        def progress_callback(percentage: float) -> None:
            try:
                db_prog = SessionLocal()
                JobsController.update_step_progress(
                    db_prog, step_id, percentage, "running"
                )
                db_prog.close()
            except:
                pass

        def status_callback(action: str, completed: bool = False) -> None:
            if completed:
                _mark_substep(step_id, action)
            else:
                _update_action(step_id, action)

        # Call Processor
        # We might need to split this processor to granularly mark substeps?
        # For now, we will mark them as we guess/approximate or if we can hook into callbacks.

        _update_action(step_id, "Processing SQL Dump")
        # _mark_substep(step_id, "Unzipping file")  # Assuming it's done or happening

        result = process_user_data(
            file_path,
            progress_callback=progress_callback,
            status_callback=status_callback,
            cleanup=False,
            job_id=job_id,
        )
        _mark_substep(step_id, "Processing SQL Dump")
        _mark_substep(step_id, "Cleaning SQL Syntax")
        _mark_substep(step_id, "Running psql Import")

        stats = result.stats()

        _update_action(step_id, "Finalizing...")
        db_log(
            f"Processed {stats['total']} records into {stats['staging_schema']}.",
            step=step_name,
        )

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        return {
            "job_id": job_id,
            "file_path": file_path,
            "staging_schema": stats["staging_schema"],
            "stats": stats,
            "skipped_upsert": stats.get("skipped", False),
        }

    except Retry:
        # Let Celery handle the retry; do not log as error or fail job
        raise
    except Exception as e:
        db_log(f"User Processing failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.extract_groups_step")
def extract_groups_step(self: Task, prev_result: dict[str, Any]) -> dict[str, Any]:
    job_id: int = cast(int, prev_result["job_id"])
    staging_schema: str = cast(str, prev_result["staging_schema"])

    step_name: str = "extracting_groups"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        _update_action(step_id, "Scanning metadata...")

        def step_log(msg: str, level: str = "INFO") -> None:
            db_log(msg, level=level, step=step_name)

        # Mark substeps roughly
        _mark_substep(step_id, "Scanning metadata")

        count = extract_groups_from_staging(
            staging_schema, job_id, logger_func=step_log
        )

        _mark_substep(step_id, "Deduplicating groups")
        _mark_substep(step_id, "Upserting to DB")

        _update_action(step_id, f"Extracted {count} groups")
        JobsController.update_step_progress(db, step_id, 100.0, "completed")

        prev_result["group_stats"] = {"extracted": count}
        return prev_result

    except Exception as e:
        db_log(f"Group Extraction failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.extract_memberships_step")
def extract_memberships_step(
    _self: Task, prev_result: dict[str, Any]
) -> dict[str, Any]:
    """
    Step 3: Extract Group Memberships from UserMetadata -> GroupMembershipMap
    """
    job_id: int = cast(int, prev_result["job_id"])
    staging_schema: str | None = cast(str | None, prev_result.get("staging_schema"))

    step_name: str = "extracting_memberships"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        _update_action(step_id, "Reading User Metadata...")
        _mark_substep(step_id, "Reading User Metadata")

        _mark_substep(step_id, "Reading User Metadata")

        def sub_log(msg: str) -> None:
            db_log(msg, step=step_name)

        process_memberships_sql(
            job_id=job_id,
            staging_schema=staging_schema,
            step_id=step_id,
            _update_action=_update_action,
            _mark_substep=_mark_substep,
            log_func=sub_log,
        )

        compute_member_counts_sql(
            job_id=job_id,
            step_id=step_id,
            _update_action=_update_action,
        )

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        return prev_result

    except Exception as e:
        db_log(f"Membership Extraction failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.index_users_step")
def index_users_step(self: Task, prev_result: dict[str, Any]) -> dict[str, Any]:
    job_id: int = cast(int, prev_result["job_id"])
    step_name: str = "indexing_users"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        def index_log(msg: str) -> None:
            # Parse msg for "Indexed X/Y" to update progress/action
            db_log(msg, step=step_name)
            if "Indexed" in msg:
                _update_action(step_id, msg)

        def update_progress(percentage: float) -> None:
            JobsController.update_step_progress(db, step_id, percentage, "running")

        _mark_substep(step_id, "Preparing to Index Users")

        count = index_users_from_db(
            job_id, log_func=index_log, update_progress=update_progress
        )

        _mark_substep(step_id, "Committing")

        _update_action(step_id, "Complete")
        JobsController.update_step_progress(db, step_id, 100.0, "completed")

        prev_result["index_users_count"] = count
        return prev_result

    except Exception as e:
        db_log(f"User Indexing failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.index_groups_step")
def index_groups_step(self: Task, prev_result: dict[str, Any]) -> dict[str, Any]:
    job_id: int = cast(int, prev_result["job_id"])
    step_name: str = "indexing_groups"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        _update_action(step_id, "Fetching groups...")
        _mark_substep(step_id, "Fetching groups")

        def index_log(msg: str) -> None:
            db_log(msg, step=step_name)
            if "Indexed" in msg:
                _update_action(step_id, msg)

        count = index_groups_from_db(job_id, log_func=index_log)
        _mark_substep(step_id, "Indexing groups")

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        prev_result["index_groups_count"] = count
        return prev_result

    except Exception as e:
        db_log(f"Group Indexing failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.record_history_step")
def record_history_step(_self: Task, prev_result: dict[str, Any]) -> dict[str, Any]:
    """
    Step 6: Record History (Optimized SQL-First Approach)
    """
    job_id: int = cast(int, prev_result["job_id"])
    step_name: str = "recording_history"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        _update_action(step_id, "Recording User History (SQL-Optimized)...")
        _mark_substep(step_id, "Fetching updated users")

        # 1. Record User History
        def progress_clbk(pct, total_processed):
            try:
                JobsController.update_step_progress(db, step_id, pct, "running")
                db_log(
                    f"Recording History Batches: {total_processed} processed",
                    step=step_name,
                )
                _update_action(
                    step_id, f"Recording History Batches: {total_processed} processed"
                )
            except:
                pass

        _update_action(step_id, "Recording History Batches")
        user_count = HistoryController.record_user_history_optimized(
            db,
            job_id=job_id,
            progress_callback=progress_clbk,
        )
        db_log(f"Recorded History for {user_count} users.", step=step_name)

        _mark_substep(step_id, "Recording History Batches")

        # 2. Record Group History
        _update_action(step_id, "Recording Group History...")
        group_count = HistoryController.record_group_history_optimized(
            db, job_id=job_id
        )
        db_log(f"Recorded History for {group_count} groups.", step=step_name)

        # 3. Record Avatar History
        _update_action(step_id, "Recording Avatar History...")
        avatar_count = HistoryController.record_avatar_history_optimized(
            db, job_id=job_id
        )
        db_log(f"Recorded History for {avatar_count} avatars.", step=step_name)

        # 4. Record Membership History
        _update_action(
            step_id, "Recording Membership History (Skipped - Handled in Extraction)..."
        )
        # membership_count = HistoryController.record_membership_history_optimized(
        #     db, job_id=job_id
        # )
        # db_log(f"Recorded History for {membership_count} memberships.", step=step_name)
        db_log("Membership history handled during extraction.", step=step_name)

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        return prev_result

    except Exception as e:
        db_log(f"History Recording failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.calculate_job_metrics_step")
def calculate_job_metrics_step(
    _self: Task, prev_result: dict[str, Any]
) -> dict[str, Any]:
    job_id: int = cast(int, prev_result["job_id"])
    # Gracefully handle missing staging_schema
    staging_schema: str | None = cast(str | None, prev_result.get("staging_schema"))
    file_path: str | None = cast(str | None, prev_result.get("file_path"))

    step_name: str = "calculate_metrics"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        if prev_result.get("skipped_upsert"):
            _update_action(step_id, "Skipped (Content Unchanged)")
            JobsController.update_step_progress(db, step_id, 100.0, "completed")
            return prev_result

        _update_action(step_id, "Calculating Metrics...")
        metrics = JobsController.calculate_job_metrics(db, job_id)
        JobsController.update_job_metrics(db, job_id, metrics)
        db_log(f"Job Metrics Calculated: {metrics}", step=step_name)

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Metrics Calculation Complete")

        return prev_result

    except Exception as e:
        db_log(f"Metrics Calculation failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="ingestion_tasks.cleanup_staging_step")
def cleanup_staging_step(_self: Task, prev_result: dict[str, Any]) -> dict[str, Any]:
    job_id: int = cast(int, prev_result["job_id"])
    # Gracefully handle missing staging_schema
    staging_schema: str | None = cast(str | None, prev_result.get("staging_schema"))
    file_path: str | None = cast(str | None, prev_result.get("file_path"))

    step_name: str = "cleanup_staging"
    step_id: int = _get_step_id(job_id, step_name)
    db_log: JobLogger = get_job_db_logger(job_id)

    db = SessionLocal()
    try:
        JobsController.update_step_progress(db, step_id, 0.0, "running")

        # 1. Drop Schema (Only if it exists)
        if staging_schema:
            _update_action(step_id, "Dropping Schema...")
            from sqlalchemy import create_engine, text
            from app.core.config import settings

            engine = create_engine(settings.DATABASE_URL)
            with engine.begin() as conn:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {staging_schema} CASCADE"))
                db_log(f"Dropped staging schema {staging_schema}.", step=step_name)
        else:
            db_log("No staging schema to drop.", step=step_name)

        _mark_substep(step_id, "Dropping staging schema")

        _mark_substep(step_id, "Dropping staging schema")

        # 2. Skip File Deletion (To allow re-ingestion/rollback)
        # _update_action(step_id, "Persisting File...")
        # We now keep the file. We might want to move it to a 'processed' folder?
        # For now, just leaving it in place as per requirements.
        db_log(f"File persisted at {file_path}", step=step_name)

        _mark_substep(step_id, "Deleting temporary files")

        # 3. Calculate Job Metrics
        _update_action(step_id, "Calculating Metrics...")
        metrics = JobsController.calculate_job_metrics(db, job_id)
        JobsController.update_job_metrics(db, job_id, metrics)
        db_log(f"Job Metrics Calculated: {metrics}", step=step_name)

        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Cleanup & Metrics Complete")

        # 4. Trigger Explicit VACUUM ANALYZE to refresh statistics and reclaim space
        db_log(
            "Triggering explicit VACUUM ANALYZE for high-churn tables...",
            step=step_name,
        )
        run_vacuum_analyze(["user_metadata", "groups", "group_memberships_map"])

        # Mark Job as Completed
        job = JobsController.get_job(db, job_id)
        if job:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

        return {"status": "success", "job_id": job_id}

    except Exception as e:
        db_log(f"Cleanup failed: {str(e)}", level="ERROR")
        # Fail the job even if partial success, to warn user.
        _fail_job(db, job_id, f"Cleanup failed: {str(e)}")
        raise e
    finally:
        db.close()


def _fail_job(db: Session, job_id: int, error_msg: str) -> None:
    job = JobsController.get_job(db, job_id)
    if job:
        job.status = "failed"
        job.error_message = error_msg
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


# --- Legacy Tasks ---
@celery_app.task(bind=True, name="ingestion_tasks.process_user_data_task")
def process_user_data_task(_self: Task, file_path: str) -> dict[str, Any]:
    return process_user_data(file_path).stats()


@celery_app.task(bind=True, name="ingestion_tasks.process_group_data_task")
def process_group_data_task(_self: Task, file_path: str) -> int:
    return process_group_data(file_path)


@celery_app.task(bind=True, name="ingestion_tasks.process_avatar_data_task")
def process_avatar_data_task(_self: Task, file_path: str) -> int:
    # Backward compatibility wrapper if needed, but we prefer the job one below
    return process_avatar_manifest_spark(file_path)


@celery_app.task(
    bind=True, max_retries=None, name="ingestion_tasks.process_groups_step"
)
def process_groups_step(self: Task, file_path: str, job_id: int) -> dict[str, Any]:
    """
    Step 1 for Groups: Read Excel -> Upsert to DB.
    """
    db_log: JobLogger = get_job_db_logger(job_id)
    db = SessionLocal()
    try:
        # Serial Execution Enforcement (FIFO)
        _check_and_queue_if_blocked(db, job_id, "groups", db_log, self.retry)

        # Storage Limit Check
        _enforce_storage_limit(db, job_id, db_log)

        db_log(f"Starting Group Pipeline. File: {file_path}", step="processing_groups")

        # Pre-create steps for Groups Job
        REQUIRED_STEPS = [
            "processing_groups",
            "indexing_groups",
            "recording_history",
            "cleanup_staging",
        ]
        _ensure_steps_generic(job_id, REQUIRED_STEPS)

        step_name = "processing_groups"
        step_id = _get_step_id(job_id, step_name)

        JobsController.update_step_progress(db, step_id, 0.0, "running")

        def progress_callback(percentage: float) -> None:
            try:
                db_prog = SessionLocal()
                JobsController.update_step_progress(
                    db_prog, step_id, percentage, "running"
                )
                db_prog.close()
            except:
                pass

        def status_callback(action: str, completed: bool = False) -> None:
            if completed:
                _mark_substep(step_id, action)
            else:
                _update_action(step_id, action)

        # process_group_data now handles internal reporting via callbacks
        count = process_group_data(
            file_path,
            job_id=job_id,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

        db_log(f"Processed {count} groups.", step=step_name)
        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        return {
            "job_id": job_id,
            "file_path": file_path,
            "group_stats": {"processed": count},
        }

    except Retry:
        # Let Celery handle the retry; do not log as error or fail job
        raise
    except Exception as e:
        db_log(f"Group Processing failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()


@celery_app.task(
    bind=True, max_retries=None, name="ingestion_tasks.process_avatars_step"
)
def process_avatars_step(self: Task, file_path: str, job_id: int) -> dict[str, Any]:
    db_log: JobLogger = get_job_db_logger(job_id)
    db = SessionLocal()
    try:
        # Serial Execution Enforcement (FIFO)
        _check_and_queue_if_blocked(db, job_id, "avatars", db_log, self.retry)

        # Storage Limit Check
        _enforce_storage_limit(db, job_id, db_log)

        db_log("Starting Avatar Ingestion Job", level="INFO")

        # Ensure steps exist
        REQUIRED_STEPS = [
            "processing_avatars",
            "indexing_users",
            "recording_history",
            "cleanup_staging",
        ]
        _ensure_steps_generic(job_id, REQUIRED_STEPS)

        step_name = "processing_avatars"
        step_id = _get_step_id(job_id, step_name)

        JobsController.update_step_progress(db, step_id, 0.0, "running")

        _update_action(step_id, "Reading Manifest...")
        # _mark_substep(step_id, "Reading Manifest")  # Handled by callback now

        db_log(f"Processing file: {file_path}", step=step_name)

        def progress_callback(percentage: float) -> None:
            try:
                db_prog = SessionLocal()
                JobsController.update_step_progress(
                    db_prog, step_id, percentage, "running"
                )
                db_prog.close()
            except:
                pass

        def status_callback(action: str, completed: bool = False) -> None:
            if completed:
                _mark_substep(step_id, action)
            else:
                _update_action(step_id, action)

        # Call Processor
        count = process_avatar_manifest_spark(
            file_path,
            job_id=job_id,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

        db_log(f"Processed {count} avatar records.", step="processing_avatars")
        JobsController.update_step_progress(db, step_id, 100.0, "completed")
        _update_action(step_id, "Complete")

        return {
            "status": "success",
            "count": count,
            "job_id": job_id,
            "file_path": file_path,  # Needed for cleanup
        }

    except Retry:
        # Let Celery handle the retry; do not log as error or fail job
        raise
    except Exception as e:
        db_log(f"Job failed: {str(e)}", level="ERROR")
        _fail_job(db, job_id, str(e))
        raise e
    finally:
        db.close()
