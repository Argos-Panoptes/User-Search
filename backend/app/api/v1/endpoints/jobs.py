from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api import deps
from app.controllers.jobs_controller import JobsController
from app.schemas.job_models import (
    IngestionJobDTO,
    IngestionLogDTO,
    IngestionJobPaginationDTO,
)

router = APIRouter()


@router.get("/", response_model=IngestionJobPaginationDTO)
def list_jobs(
    ingestion_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    items, total = JobsController.list_jobs(db, ingestion_type, limit, offset)
    return {"items": items, "total": total}


@router.get("/{job_id}", response_model=IngestionJobDTO)
def get_job(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    job = JobsController.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/logs", response_model=List[IngestionLogDTO])
def get_job_logs(
    job_id: int,
    limit: int = 100,
    offset: int = 0,
    after_id: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return JobsController.get_job_logs(db, job_id, limit, offset, after_id)


# @router.post("/{job_id}/reprocess", response_model=dict)
# def reprocess_job(
#     job_id: int,
#     db: Session = Depends(deps.get_db),
#     current_user=Depends(deps.get_current_user),
# ):
#     """
#     Triggers reprocessing of a previous ingestion job using the same pipeline as initial ingestion.
#     """
#     from app.controllers.ingestion_controller import IngestionController
#     from app.schemas.api_models import IngestRequest
#
#     # Verify source job exists
#     source_job = JobsController.get_job(db, job_id)
#     if not source_job:
#         raise HTTPException(status_code=404, detail="Job not found")
#
#     if not source_job.source_file_path:
#         raise HTTPException(
#             status_code=400, detail="Job has no stored source file path."
#         )
#
#     # Convert source job details into an IngestRequest
#     request = IngestRequest(file_path=source_job.source_file_path)
#
#     # Dispatch to the central IngestionController for unified logic
#     if source_job.ingestion_type == "users":
#         return IngestionController.ingest_users(request, db, current_user)
#     elif source_job.ingestion_type == "groups":
#         return IngestionController.ingest_groups(request, db, current_user)
#     elif source_job.ingestion_type == "avatars":
#         return IngestionController.ingest_avatars(request, db, current_user)
#     else:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Unknown ingestion type: {source_job.ingestion_type}",
#         )


# @router.post("/{job_id}/rollback", response_model=dict)
# def rollback_job(
#     job_id: int,
#     db: Session = Depends(deps.get_db),
#     current_user=Depends(deps.get_current_user),
# ):
#     """
#     Initiates a rollback for the specified job.
#     """
#     from app.tasks.ingestion_tasks import rollback_job_task
#
#     # Verify job exists
#     target_job = JobsController.get_job(db, job_id)
#     if not target_job:
#         raise HTTPException(status_code=404, detail="Job not found")
#
#     if target_job.status == "rolled_back":
#         raise HTTPException(status_code=400, detail="Job is already rolled back.")
#
#     # Create Rollback Job Tracking synchronously
#     rollback_job = JobsController.create_rollback_job(db, job_id)
#     db.commit()  # Commit to get ID
#
#     # Trigger Celery Task with the new rollback job ID
#     task = rollback_job_task.delay(rollback_job.id, job_id)
#
#     return {
#         "message": "Rollback initiated",
#         "job_id": rollback_job.id,
#         "task_id": str(task.id),
#     }
