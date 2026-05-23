from app.core.logging import logger
from app.db.session import SessionLocal
from app.controllers.jobs_controller import JobsController
from app.db.schemas.ingestion_models import IngestionStep

# --- Helper Functions ---

SUBSTEP_DEFINITIONS = {
    "processing_users": [
        "Processing SQL Dump",
        "Content Hashing",
        "Executing Upsert",
    ],
    "processing_groups": [
        "Reading Excel",
        "Writing to Staging",
        "Upserting to DB",
    ],
    "extracting_groups": [
        "Scanning metadata",
        "Deduplicating groups",
        "Upserting to DB",
    ],
    "extracting_memberships": [
        "Reading User Metadata",
        "Upserting Membership Mappings",
        "Pruning Stale Memberships",
    ],
    "processing_avatars": [
        "Reading Manifest",
        "Filtering & Parsing",
        "Upserting Avatars",
        "Linking Users",
    ],
    "indexing_users": [
        "Preparing to Index Users",
        "Committing",
    ],
    "indexing_groups": [
        "Fetching groups",
        "Indexing groups",
    ],
    "cleanup_staging": [
        "Dropping staging schema",
        "Deleting temporary files",
    ],
    "revert_ingestion": [
        "Identifying affected records",
        "Reverting database changes",
        "Syncing OpenSearch indexes",
    ],
    "recording_history": [
        "Fetching updated users",
        "Recording History Batches",
    ],
    "avatar_sync": [],
}


def get_job_db_logger(job_id: int):
    """
    Returns a logging function that logs to both local logger and DB.
    """

    def log(message: str, level: str = "INFO", step: str | None = None) -> None:
        logger.info(f"[Job {job_id}] {message}")
        db = SessionLocal()
        try:
            JobsController.add_log(db, job_id, message, level, step)
        finally:
            db.close()

    return log


def _update_action(step_id: int, action: str):
    """
    Helper to update current_action for a step.
    LEGACY: Use _mark_substep if possible.
    """
    db = SessionLocal()
    try:
        JobsController.update_step_action(db, step_id, action)
    except Exception as e:
        logger.error(f"Failed to update step action: {e}")
    finally:
        db.close()


def _mark_substep(step_id: int, substep_name: str):
    """
    Mark a substep as completed.
    """
    db = SessionLocal()
    try:
        JobsController.complete_substep(db, step_id, substep_name)
    except Exception as e:
        logger.error(f"Failed to mark substep {substep_name}: {e}")
    finally:
        db.close()


def _ensure_steps_generic(job_id: int, required_steps: list):
    """
    Ensures specified steps exist for the job and initializes their substeps.
    """
    db = SessionLocal()
    try:
        # Check existing to avoid duplicates
        existing = db.query(IngestionStep).filter(IngestionStep.job_id == job_id).all()
        existing_names = {s.step_name for s in existing}

        for name in required_steps:
            if name not in existing_names:
                step = JobsController.create_step(db, job_id, name)
                # Initialize Substeps
                if name in SUBSTEP_DEFINITIONS:
                    JobsController.set_substeps(db, step.id, SUBSTEP_DEFINITIONS[name])
    finally:
        db.close()


def _ensure_all_steps_created(job_id: int):
    """
    Legacy: Ensures all 6 steps exist for User Ingestion.
    """
    REQUIRED_STEPS = [
        "processing_users",
        "extracting_groups",
        "extracting_memberships",
        "indexing_users",
        "indexing_groups",
        "recording_history",
        "cleanup_staging",
    ]
    _ensure_steps_generic(job_id, REQUIRED_STEPS)


def _get_step_id(job_id: int, step_name: str) -> int:
    db = SessionLocal()
    try:
        step = JobsController.get_job_step(db, job_id, step_name)
        if step:
            return step.id
        # Fallback create
        step = JobsController.create_step(db, job_id, step_name)
        return step.id
    finally:
        db.close()
