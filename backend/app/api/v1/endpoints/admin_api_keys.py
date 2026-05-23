"""
Admin API key management endpoints.
Superuser can manage all API keys across all users.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_superuser
from app.controllers import api_key_controller
from app.db.schemas.app_models import AppUser
from app.db.session import get_db
from app.schemas.api_key_schemas import (
    ApiKeyAdminCreate,
    ApiKeyAdminUpdate,
    ApiKeyCreatedResponse,
    ApiKeyDetail,
    ApiKeyListItem,
)
from app.schemas.api_response import wrap_response, build_pagination_meta, ApiObjectResponse, ApiListResponse

router = APIRouter()


@router.post("", response_model=ApiObjectResponse)
def admin_create_api_key(
    request: Request,
    body: ApiKeyAdminCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_superuser),
):
    created_by_id = body.user_id or current_user.id

    api_key, raw_key = api_key_controller.create_key(
        db,
        name=body.name,
        created_by_id=created_by_id,
        description=body.description,
        expires_in_days=body.expires_in_days,
        quota_limit=body.quota_limit,
        allowed_endpoints=body.allowed_endpoints,
    )

    data = ApiKeyCreatedResponse(
        key_id=api_key.key_id,
        raw_key=raw_key,
        name=api_key.name,
        description=api_key.description,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        quota_limit=api_key.quota_limit,
    ).model_dump(mode="json")

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("", response_model=ApiListResponse)
def admin_list_api_keys(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    keys, total = api_key_controller.list_keys(
        db,
        user_id=user_id,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )

    data = [
        ApiKeyListItem(
            key_id=k.key_id,
            name=k.name,
            description=k.description,
            created_by_id=k.created_by_id,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
            is_active=k.is_active,
            quota_limit=k.quota_limit,
            request_count=k.request_count or 0,
        ).model_dump(mode="json")
        for k in keys
    ]

    page = (offset // limit) + 1 if limit > 0 else 1
    pagination = build_pagination_meta(page=page, per_page=limit, total=total)

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
        pagination=pagination,
    )


@router.get("/{key_id}", response_model=ApiObjectResponse)
def admin_get_api_key(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
):
    api_key = api_key_controller.get_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    data = ApiKeyDetail(
        key_id=api_key.key_id,
        name=api_key.name,
        description=api_key.description,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        quota_limit=api_key.quota_limit,
        request_count=api_key.request_count or 0,
        allowed_endpoints=api_key.allowed_endpoints,
        metadata_json=api_key.metadata_json,
        created_by_id=api_key.created_by_id,
    ).model_dump(mode="json")

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.patch("/{key_id}", response_model=ApiObjectResponse)
def admin_update_api_key(
    request: Request,
    key_id: str,
    body: ApiKeyAdminUpdate,
    db: Session = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)

    # Handle expires_in_days -> expires_at conversion
    if "expires_in_days" in updates:
        days = updates.pop("expires_in_days")
        if days:
            updates["expires_at"] = datetime.now(timezone.utc) + timedelta(days=days)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    api_key = api_key_controller.update_key(db, key_id=key_id, updates=updates)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return wrap_response(
        data={"key_id": api_key.key_id, "updated": True},
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.delete("/{key_id}", response_model=ApiObjectResponse)
def admin_revoke_api_key(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
):
    revoked = api_key_controller.revoke_key(db, key_id=key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    return wrap_response(
        data={"key_id": key_id, "revoked": True},
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )
