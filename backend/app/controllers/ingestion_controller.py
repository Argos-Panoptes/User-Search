from fastapi import HTTPException
from app.tasks.ingestion_tasks import (
    process_avatars_step,
    process_users_step,
    process_groups_step,
    extract_groups_step,
    extract_memberships_step,
    index_users_step,
    index_groups_step,
    record_history_step,
    cleanup_staging_step,
)
from app.schemas.api_models import IngestRequest
from app.controllers.upload_controller import UploadController
from app.controllers.jobs_controller import JobsController
from app.core.logging import logger
from app.core.config import settings
from app.db.schemas.app_models import AppUser
from sqlalchemy.orm import Session
from celery import chain


class IngestionController:
    @staticmethod
    def resolve_file_path(request: IngestRequest) -> str:
        if request.file_path:
            return request.file_path

        if request.upload_id:
            path = UploadController.get_uploaded_file_path(request.upload_id)
            if not path:
                raise HTTPException(
                    status_code=404, detail="Upload ID not found or file missing"
                )
            return path

        raise HTTPException(
            status_code=400, detail="Either file_path or upload_id must be provided"
        )

    @staticmethod
    def ingest_users(request: IngestRequest, db: Session, user: AppUser):
        file_path = IngestionController.resolve_file_path(request)

        # Create Job
        job = JobsController.create_job(db, ingestion_type="users", user_id=user.id)
        JobsController.update_job_file_path(db, job.id, file_path)

        # Start Celery Chain: Process -> Extract Groups -> Extract Memberships -> Index Users -> Index Groups -> Cleanup
        pipeline = chain(
            process_users_step.s(file_path, job.id)
            | extract_groups_step.s()
            | extract_memberships_step.s()
            | index_users_step.s()
            | index_groups_step.s()
            | record_history_step.s()
            | cleanup_staging_step.s()
        )
        task = pipeline.apply_async()

        # Update Job with Task ID (store the chain's parent task ID)
        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Started user ingestion chain Job: {job.id} (Task: {task.id})")
        return {
            "message": "User ingestion pipeline started",
            "task_id": task.id,
            "job_id": job.id,
        }

    @staticmethod
    def ingest_groups(request: IngestRequest, db: Session, user: AppUser):
        file_path = IngestionController.resolve_file_path(request)

        job = JobsController.create_job(db, ingestion_type="groups", user_id=user.id)
        JobsController.update_job_file_path(db, job.id, file_path)

        # Start Celery Chain: Process -> Index Groups -> Cleanup
        pipeline = chain(
            process_groups_step.s(file_path, job.id)
            | index_groups_step.s()
            | record_history_step.s()
            | cleanup_staging_step.s()
        )
        task = pipeline.apply_async()

        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Started group ingestion chain Job: {job.id} (Task: {task.id})")
        return {
            "message": "Group ingestion pipeline started",
            "task_id": task.id,
            "job_id": job.id,
        }

    @staticmethod
    def ingest_avatars(request: IngestRequest, db: Session, user: AppUser):
        file_path = IngestionController.resolve_file_path(request)

        job = JobsController.create_job(db, ingestion_type="avatars", user_id=user.id)
        JobsController.update_job_file_path(db, job.id, file_path)

        # Start Celery Chain: Process Avatars -> Index Users -> Cleanup
        pipeline = chain(
            process_avatars_step.s(file_path, job.id)
            | index_users_step.s()
            | record_history_step.s()
            | cleanup_staging_step.s()
        )
        task = pipeline.apply_async()

        job.celery_task_id = task.id
        db.commit()

        logger.info(f"Started avatar ingestion chain Job: {job.id} (Task: {task.id})")
        return {
            "message": "Avatar ingestion pipeline started",
            "task_id": task.id,
            "job_id": job.id,
        }
