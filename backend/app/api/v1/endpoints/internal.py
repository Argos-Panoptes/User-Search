"""
Internal API endpoints for Telchines ingestion service.
Requires superuser/internal authentication. No rate limiting.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.controllers.internal_controller import InternalController
from app.schemas.api_response import wrap_response

router = APIRouter()


class BatchPullRequest(BaseModel):
    service_ids: list[str]
    include_history: bool = False
    include_avatars: bool = False
    fields: Optional[list[str]] = None


class ObservedDateUpdate(BaseModel):
    service_id: str
    first_observed: Optional[str] = None
    last_observed: Optional[str] = None


class GroupObservedDateUpdate(BaseModel):
    group_id: str
    first_observed: Optional[str] = None
    last_observed: Optional[str] = None


class BulkUpdateObservedRequest(BaseModel):
    updates: list[ObservedDateUpdate]


class BulkUpdateGroupObservedRequest(BaseModel):
    updates: list[GroupObservedDateUpdate]


@router.post("/telchines/batch-pull")
def batch_pull(
    request: Request,
    body: BatchPullRequest,
    db: Session = Depends(get_db),
):
    if len(body.service_ids) > 10000:
        from app.schemas.api_response import wrap_error

        return wrap_error(
            error_code="BATCH_TOO_LARGE",
            message="Maximum 10,000 service IDs per batch request",
            request_id=getattr(request.state, "request_id", "unknown"),
        )

    results = InternalController.batch_pull_users(
        db=db,
        service_ids=body.service_ids,
        include_history=body.include_history,
        include_avatars=body.include_avatars,
        fields=body.fields,
    )

    return wrap_response(
        data=results,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        auth_method=getattr(request.state, "auth_method", None),
    )


@router.get("/telchines/avatars/metadata")
def get_avatars_metadata(
    request: Request,
    db: Session = Depends(get_db),
    service_ids: str | None = Query(None, description="Comma-separated service IDs"),
    updated_since: str | None = Query(None, description="ISO 8601 timestamp"),
):
    sid_list = service_ids.split(",") if service_ids else None
    since = None
    if updated_since:
        try:
            since = datetime.fromisoformat(updated_since)
        except ValueError:
            pass

    results = InternalController.get_avatar_metadata(
        db=db,
        service_ids=sid_list,
        updated_since=since,
    )

    return wrap_response(
        data=results,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        auth_method=getattr(request.state, "auth_method", None),
    )


@router.post("/telchines/users/update-observed-dates")
def update_observed_dates(
    request: Request,
    body: BulkUpdateObservedRequest,
    db: Session = Depends(get_db),
):
    updates = [u.model_dump() for u in body.updates]
    result = InternalController.bulk_update_observed_dates(db=db, updates=updates)

    return wrap_response(
        data=result,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        auth_method=getattr(request.state, "auth_method", None),
    )


@router.post("/telchines/groups/update-observed-dates")
def update_group_observed_dates(
    request: Request,
    body: BulkUpdateGroupObservedRequest,
    db: Session = Depends(get_db),
):
    updates = [u.model_dump() for u in body.updates]
    result = InternalController.bulk_update_group_observed_dates(db=db, updates=updates)

    return wrap_response(
        data=result,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        auth_method=getattr(request.state, "auth_method", None),
    )


@router.get("/telchines/config")
def get_telchines_config(request: Request):
    config = InternalController.get_config()

    return wrap_response(
        data=config,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        auth_method=getattr(request.state, "auth_method", None),
    )
