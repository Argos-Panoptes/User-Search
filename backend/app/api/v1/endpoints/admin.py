from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.schemas.app_models import SystemSetting, AppUser
from app.api.deps import get_current_active_superuser
from app.controllers.deletion_controller import DeletionController
from app.schemas.api_models import (
    DeleteUserRequest,
    BulkDeleteRequest,
    DeleteUserResponse,
    BulkDeleteResponse,
    AuditLogResponse,
    UserDeletionPreview,
)
from app.core.logging import logger
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SystemSettingUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None


@router.get("/settings", response_model=list[SystemSettingUpdate])
def get_system_settings(db: Session = Depends(get_db)):
    """
    Get all system settings.
    """
    settings = db.query(SystemSetting).all()
    return [
        SystemSettingUpdate(key=s.key, value=s.value, description=s.description)
        for s in settings
    ]


@router.post("/settings", response_model=SystemSettingUpdate)
def update_system_setting(setting: SystemSettingUpdate, db: Session = Depends(get_db)):
    """
    Update or create a system setting.
    """
    db_setting = (
        db.query(SystemSetting).filter(SystemSetting.key == setting.key).first()
    )
    if db_setting:
        db_setting.value = setting.value
        if setting.description:
            db_setting.description = setting.description
    else:
        db_setting = SystemSetting(
            key=setting.key,
            value=setting.value,
            description=setting.description,
        )
        db.add(db_setting)

    db.commit()
    db.refresh(db_setting)
    return SystemSettingUpdate(
        key=db_setting.key,
        value=db_setting.value,
        description=db_setting.description,
    )


# --- User Deletion Endpoints ---


@router.get("/users/{service_id}/deletion-preview", response_model=UserDeletionPreview)
def preview_user_deletion(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    """Preview user info before deletion (confirmation step)."""
    try:
        return DeletionController.preview_user(db, service_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing user deletion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/delete", response_model=DeleteUserResponse)
def soft_delete_user(
    request: DeleteUserRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    """Soft-delete a single user by service_id."""
    try:
        return DeletionController.soft_delete_user(
            db,
            service_id=request.service_id,
            reason=request.reason,
            notes=request.notes,
            admin_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_users(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    """Bulk soft-delete multiple users."""
    try:
        return DeletionController.bulk_soft_delete(
            db,
            service_ids=request.service_ids,
            reason=request.reason,
            notes=request.notes,
            admin_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk deletion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/deletions/audit-log", response_model=AuditLogResponse)
def get_deletion_audit_log(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    reason: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    """View deletion audit log with filtering and pagination."""
    try:
        return DeletionController.get_audit_log(
            db,
            limit=limit,
            offset=offset,
            search=search,
            reason=reason,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as e:
        logger.error(f"Error fetching audit log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/deletions/audit-log/export")
def export_audit_log_csv(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    """Export deletion audit log as CSV."""
    try:
        return DeletionController.export_audit_log_csv(db)
    except Exception as e:
        logger.error(f"Error exporting audit log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
