from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class IngestionLogDTO(BaseModel):
    id: int
    timestamp: datetime
    log_level: str
    message: str
    step_name: Optional[str]

    class Config:
        from_attributes = True


class IngestionSubstepDTO(BaseModel):
    id: int
    name: str
    status: str
    created_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class IngestionStepDTO(BaseModel):
    id: int
    step_name: str
    status: str
    progress_percentage: float
    current_action: Optional[str]
    substeps: List[IngestionSubstepDTO] = []
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


from app.schemas.auth_models import UserSummary


class IngestionJobSummaryDTO(BaseModel):
    id: int
    celery_task_id: Optional[str] = None
    status: str
    ingestion_type: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metrics: Optional[dict] = None
    source_file_path: Optional[str] = None
    created_by_user: Optional[UserSummary] = None

    class Config:
        from_attributes = True


class IngestionJobDTO(IngestionJobSummaryDTO):
    steps: List[IngestionStepDTO] = []


class IngestionJobPaginationDTO(BaseModel):
    items: List[IngestionJobSummaryDTO]
    total: int
