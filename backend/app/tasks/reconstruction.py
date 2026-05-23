from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.schemas.ingestion_models import GroupMetadata, IngestionJob
from app.utils.reconstruct_utils import generate_signal_group_url
from app.ingestion import search_indexer
from app.core.logging import logger
from sqlalchemy import or_
from datetime import datetime, timedelta, timezone


@celery_app.task(bind=True, name="reconstruction_tasks.reconstruct_group_links_task")
def reconstruct_group_links_task(self, job_id: int, batch_size: int = 100):
    """
    Background task to reconstruct Signal group links.

    1. Checks for active ingestion jobs (Collision Detection).
    2. Fetches groups with missing/invalid links but valid keys.
    3. Reconstructs links.
    4. Updates DB and OpenSearch.
    """
    from app.controllers.jobs_controller import JobsController

    db = SessionLocal()
    job = JobsController.get_job(db, job_id)
    if not job:
        logger.error(f"Job {job_id} not found.")
        return

    try:
        # Update Job Status to Running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        JobsController.add_log(
            db, job_id, "Starting Link Reconstruction Task", level="INFO"
        )

        # 0. Auto-fail stale link_reconstruction jobs (stuck > 1 hour)
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stale_jobs = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.ingestion_type == "link_reconstruction",
                IngestionJob.status == "running",
                IngestionJob.id != job_id,
                IngestionJob.started_at < stale_cutoff,
            )
            .all()
        )
        for stale in stale_jobs:
            stale.status = "failed"
            stale.error_message = "Auto-failed: exceeded 1 hour timeout"
            stale.completed_at = datetime.now(timezone.utc)
            JobsController.add_log(
                db, stale.id,
                f"Job auto-failed: running for over 1 hour (likely worker crash)",
                level="ERROR",
            )
        if stale_jobs:
            db.commit()

        # 1. Collision Detection
        active_ingestion = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "running", IngestionJob.id != job_id)
            .first()
        )

        if active_ingestion:
            msg = f"Skipping Link Reconstruction: Another Ingestion Job {active_ingestion.id} is running."
            JobsController.add_log(db, job_id, msg, level="WARNING")
            job.status = "failed"
            job.error_message = msg
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "skipped", "reason": "ingestion_running"}

        # Create Step and Substeps
        step = JobsController.create_step(db, job_id, "Reconstruct Links")
        substeps = ["Fetch Candidates", "Process Groups", "Update Search Index"]
        JobsController.set_substeps(db, step.id, substeps)
        JobsController.update_step_progress(db, step.id, 0, status="running")

        # --- Substep 1: Fetch Candidates ---
        # Fetching is now done in batches within the processing loop
        JobsController.update_step_action(db, step.id, "Starting batch processing...")
        JobsController.complete_substep(db, step.id, "Fetch Candidates")

        # --- Substep 2: Process Groups ---
        JobsController.update_step_action(db, step.id, "Processing groups...")

        total_processed = 0
        total_updated = 0
        all_updated_ids = []

        # Start from ID 0 for keyset pagination
        last_processed_id = 0

        while True:
            # Query next batch of groups with IDs strictly greater than the last processed ID
            # Ordered by ID ASC for stable pagination
            groups_to_process = (
                db.query(GroupMetadata)
                .filter(
                    GroupMetadata.master_key.isnot(None),
                    GroupMetadata.invite_link_password.isnot(None),
                    GroupMetadata.id > last_processed_id,
                )
                .order_by(GroupMetadata.id.asc())
                .limit(batch_size)
                .all()
            )

            if not groups_to_process:
                break

            # Update cursor for next iteration (the last item in the current batch)
            last_processed_id = groups_to_process[-1].id

            current_batch_size = len(groups_to_process)
            JobsController.add_log(
                db,
                job_id,
                f"Processing batch of {current_batch_size} groups (IDs > {last_processed_id - current_batch_size})...",
                level="INFO",
            )

            batch_updated_count = 0
            batch_updated_ids = []

            for idx, group in enumerate(groups_to_process):
                try:
                    new_link = generate_signal_group_url(
                        str(group.master_key), str(group.invite_link_password)
                    )

                    # Debug log for the very first item processed
                    if total_processed == 0 and idx == 0:
                        JobsController.add_log(
                            db,
                            job_id,
                            f"Sample Check - ID: {group.id}, Generated: {new_link}",
                            level="INFO",
                        )

                    if new_link and new_link != group.reconstructed_link:
                        group.reconstructed_link = str(new_link)
                        batch_updated_count += 1
                        batch_updated_ids.append(group.id)
                except Exception as e:
                    JobsController.add_log(
                        db,
                        job_id,
                        f"Error processing group {group.id}: {e}",
                        level="ERROR",
                    )

            # Commit batch updates to DB so they don't show up in next query
            if batch_updated_count > 0:
                db.commit()
                total_updated += batch_updated_count
                all_updated_ids.extend(batch_updated_ids)

            total_processed += current_batch_size

            # Update Progress (Generic estimate, since we don't know total upfront easily without count query)
            # We'll just show processed count in action
            JobsController.update_step_action(
                db, step.id, f"Processed {total_processed} groups so far..."
            )

        JobsController.complete_substep(db, step.id, "Process Groups")

        # --- Substep 3: Update Search Index ---
        if total_updated > 0:
            JobsController.update_step_action(db, step.id, "Updating search index...")
            JobsController.add_log(
                db,
                job_id,
                f"Reconstructed {total_updated} links in total. Updating index...",
                level="INFO",
            )

            try:
                search_indexer.index_groups_by_ids(all_updated_ids)
            except Exception as e:
                JobsController.add_log(
                    db, job_id, f"Failed to update index: {e}", level="ERROR"
                )
        else:
            JobsController.add_log(
                db, job_id, "No links changed, skipping index update.", level="INFO"
            )

        JobsController.complete_substep(db, step.id, "Update Search Index")

        # Finish Job
        JobsController.update_step_progress(db, step.id, 100, status="completed")

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.metrics = {
            "processed": total_processed,
            "groups_updated": total_updated,
            "groups_inserted": 0,
            "users_inserted": 0,
            "users_updated": 0,
        }
        db.commit()

        JobsController.add_log(
            db,
            job_id,
            f"Task completed. Processed {total_processed}, Updated {total_updated} links.",
            level="INFO",
        )

        return {
            "status": "success",
            "processed": total_processed,
            "updated": total_updated,
            "updated_ids": all_updated_ids,
        }

    except Exception as e:
        logger.error(f"Link Reconstruction Task Failed: {e}")
        JobsController.add_log(db, job_id, f"Task Failed: {e}", level="ERROR")
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise e
    finally:
        db.close()


@celery_app.task(name="reconstruction_tasks.trigger_scheduled_link_reconstruction")
def trigger_scheduled_link_reconstruction():
    """
    Scheduled task to trigger the link reconstruction process.
    Checks SystemSetting for interval, and only runs if enough time has passed since last job.
    """
    from app.controllers.jobs_controller import JobsController
    from app.core.config import settings
    from app.db.schemas.app_models import SystemSetting

    db = SessionLocal()
    try:
        # 1. Get Configured Interval
        interval_setting = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == "LINK_RECONSTRUCTION_INTERVAL_MINUTES")
            .scalar()
        )

        interval_minutes = settings.LINK_RECONSTRUCTION_INTERVAL_MINUTES
        if interval_setting and interval_setting.value:
            try:
                interval_minutes = int(interval_setting.value)
            except ValueError:
                logger.error(
                    f"Invalid interval setting value: {interval_setting.value}. Using default."
                )

        # 2. Check for existing running job
        existing_job = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.ingestion_type == "link_reconstruction",
                IngestionJob.status == "running",
            )
            .first()
        )

        if existing_job:
            # If running, we obviously skip
            logger.warning(
                f"Skipping scheduled reconstruction: Job {existing_job.id} is already running."
            )
            return

        # 3. Check Last Job Time (Throttle)
        last_job = (
            db.query(IngestionJob)
            .filter(IngestionJob.ingestion_type == "link_reconstruction")
            .order_by(IngestionJob.created_at.desc())
            .first()
        )

        if last_job and last_job.created_at:
            # Calculate elapsed time
            # Ensure timezone awareness. created_at should be UTC.
            now = datetime.now(timezone.utc)
            # last_job.created_at might be offset-naive if not configured right in SA, but typically IS naive in UTC or aware.
            # safe approach:
            last_run = last_job.created_at
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)

            elapsed = (now - last_run).total_seconds() / 60

            if elapsed < interval_minutes:
                logger.info(
                    f"Skipping scheduled link reconstruction: Last run was {elapsed:.1f}m ago, "
                    f"which is less than the configured interval of {interval_minutes}m."
                )
                return

        # 4. Create new job
        job = JobsController.create_job(
            db=db,
            ingestion_type="link_reconstruction",
            celery_task_id=None,
        )

        logger.info(
            f"Triggering scheduled link reconstruction job {job.id} (Interval: {interval_minutes}m)"
        )

        # Call the actual worker task
        reconstruct_group_links_task.delay(job.id)

    except Exception as e:
        logger.error(f"Failed to trigger scheduled link reconstruction: {e}")
    finally:
        db.close()
