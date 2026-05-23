from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.api import deps
from app.controllers.logs_controller import LogsController
from app.core.logging import logger

router = APIRouter()


@router.get("/", response_model=List[str])
def get_logs(
    log_type: str = Query(
        ..., pattern="^(app|celery)$", description="Log file type to fetch"
    ),
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to fetch"),
    current_user=Depends(deps.get_current_user),
):
    """
    Fetch the last N lines of logs.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        return LogsController.get_logs(log_type, lines)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
