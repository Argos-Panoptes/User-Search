from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api import deps

from app.schemas.api_models import IngestRequest
from app.controllers.ingestion_controller import IngestionController
from app.core.logging import logger
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.tasks.reconstruction import reconstruct_group_links_task
from app.tasks.avatar_sync_tasks import run_avatar_sync_batch
from pydantic import BaseModel
from app.db.schemas.ingestion_models import IngestionJob, IngestionStep, AvatarSyncAuditLog

router = APIRouter()


@router.post("/ingest/users")
def ingest_users(
    request: IngestRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Trigger user ingestion from file (Upload ID or Path).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        return IngestionController.ingest_users(request, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger user ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/ingest/groups")
def ingest_groups(
    request: IngestRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        return IngestionController.ingest_groups(request, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger group ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/ingest/avatars")
def ingest_avatars(
    request: IngestRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        return IngestionController.ingest_avatars(request, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger avatar ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/ingest/reconstruct-links")
def trigger_link_reconstruction(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Manually trigger the background link reconstruction job.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        logger.info("Received request to trigger link reconstruction")
        # Create Job Record
        job = IngestionJob(
            ingestion_type="link_reconstruction",
            status="pending",
            created_by_id=current_user.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Trigger Task
        # Note: Ensure the worker is listening to the 'reconstruction' queue if configured!
        task = reconstruct_group_links_task.delay(job_id=job.id, batch_size=100)

        # Update with Task ID
        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Link reconstruction triggered: job_id={job.id} task_id={task.id}")
        return {"status": "success", "job_id": job.id, "task_id": task.id}

    except Exception as e:
        logger.error(f"Failed to trigger link reconstruction: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/avatar-sync")
def trigger_avatar_sync(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Manually trigger the avatar sync revalidation job (Part B).
    Checks known avatars against S3 for freshness.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        # Check for already running sync job
        existing = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.ingestion_type == "avatar_sync",
                IngestionJob.status.in_(["running", "queued", "pending"]),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Avatar sync job {existing.id} is already {existing.status}."
            )

        # Create Job Record
        job = IngestionJob(
            ingestion_type="avatar_sync",
            status="pending",
            created_by_id=current_user.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Dispatch first batch to avatars queue
        task = run_avatar_sync_batch.apply_async(
            args=[job.id, 0],
            queue="avatars",
        )

        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Avatar sync triggered manually: job_id={job.id} task_id={task.id}")
        return {"status": "success", "job_id": job.id, "task_id": task.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger avatar sync: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/avatar-sync/{job_id}/stop")
def stop_avatar_sync(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Stop a running avatar sync job. Marks it as failed so the next
    self-re-queued batch will see the status and stop processing.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    from datetime import datetime, timezone

    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.ingestion_type != "avatar_sync":
        raise HTTPException(status_code=400, detail="This endpoint only stops avatar_sync jobs")

    if job.status not in ("running", "queued", "pending"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is already {job.status}, cannot stop."
        )

    job.status = "failed"
    job.error_message = f"Stopped manually by {current_user.email}"
    job.completed_at = datetime.now(timezone.utc)

    # Calculate duration in metrics so the UI can display progress made
    if job.started_at and job.metrics is not None:
        started = job.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        job.metrics["duration_seconds"] = round(
            (job.completed_at - started).total_seconds(), 1
        )

    # Mark any running/pending steps as failed so the UI shows a cross
    running_steps = (
        db.query(IngestionStep)
        .filter(
            IngestionStep.job_id == job_id,
            IngestionStep.status.in_(["running", "pending"]),
        )
        .all()
    )
    for step in running_steps:
        step.status = "failed"
        step.completed_at = datetime.now(timezone.utc)

    db.commit()

    # Also try to revoke the Celery task if we have a task ID
    if job.celery_task_id:
        try:
            from app.core.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=False)
        except Exception as e:
            logger.warning(f"Could not revoke celery task {job.celery_task_id}: {e}")

    logger.info(f"Avatar sync job {job_id} stopped by {current_user.email}")
    return {"status": "stopped", "job_id": job_id}


@router.get("/ingest/avatar-sync/{job_id}/failures")
def get_avatar_sync_failures(
    job_id: int,
    action: Optional[str] = Query(None, description="Filter by action: error, missing, or all"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Returns per-user failure details from the avatar_sync_audit_log for a given job.
    Includes service_id, action (error/missing), failure detail, and timestamp.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.ingestion_type != "avatar_sync":
        raise HTTPException(status_code=400, detail="Not an avatar_sync job")

    # Build query
    query = db.query(AvatarSyncAuditLog).filter(AvatarSyncAuditLog.job_id == job_id)

    if action and action != "all":
        query = query.filter(AvatarSyncAuditLog.action == action)
    else:
        # Default: only errors and missing (not changed/new which are successes)
        query = query.filter(AvatarSyncAuditLog.action.in_(["error", "missing"]))

    total = query.count()

    records = (
        query
        .order_by(AvatarSyncAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Summary counts by action
    summary = dict(
        db.query(AvatarSyncAuditLog.action, func.count(AvatarSyncAuditLog.id))
        .filter(
            AvatarSyncAuditLog.job_id == job_id,
            AvatarSyncAuditLog.action.in_(["error", "missing"]),
        )
        .group_by(AvatarSyncAuditLog.action)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "summary": summary,
        "items": [
            {
                "id": r.id,
                "service_id": r.service_id,
                "action": r.action,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
