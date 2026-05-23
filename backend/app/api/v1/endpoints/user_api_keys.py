"""
User self-service API key management endpoints.
Users can create and manage their own API keys.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_subscribed_user
from app.controllers import api_key_controller
from app.core.config import settings
from app.db.schemas.app_models import AppUser
from app.db.session import get_db
from app.schemas.api_key_schemas import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyDetail,
    ApiKeyListItem,
    ApiKeyUpdate,
)
from app.schemas.api_response import wrap_response, wrap_error, build_pagination_meta, ApiObjectResponse, ApiListResponse

router = APIRouter()


@router.post("", response_model=ApiObjectResponse)
def create_api_key(
    request: Request,
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_subscribed_user),
):
    # Check user hasn't exceeded key limit (per-user override or system default)
    max_keys = current_user.max_api_keys if current_user.max_api_keys is not None else settings.MAX_API_KEYS_PER_USER
    count = api_key_controller.count_user_keys(db, current_user.id)
    if count >= max_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_keys} API keys allowed. You currently have {count} active keys.",
        )

    api_key, raw_key = api_key_controller.create_key(
        db,
        name=body.name,
        created_by_id=current_user.id,
        description=body.description,
        expires_in_days=body.expires_in_days,
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
def list_api_keys(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_subscribed_user),
    limit: int = 50,
    offset: int = 0,
):
    keys, total = api_key_controller.list_keys(
        db, user_id=current_user.id, limit=limit, offset=offset
    )

    data = [
        ApiKeyListItem(
            key_id=k.key_id,
            name=k.name,
            description=k.description,
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
def get_api_key(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_subscribed_user),
):
    api_key = api_key_controller.get_key(db, key_id=key_id, user_id=current_user.id)
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
def update_api_key(
    request: Request,
    key_id: str,
    body: ApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_subscribed_user),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    api_key = api_key_controller.update_key(
        db, key_id=key_id, updates=updates, user_id=current_user.id
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return wrap_response(
        data={"key_id": api_key.key_id, "updated": True},
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.delete("/{key_id}", response_model=ApiObjectResponse)
def revoke_api_key(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_subscribed_user),
):
    revoked = api_key_controller.revoke_key(db, key_id=key_id, user_id=current_user.id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    return wrap_response(
        data={"key_id": key_id, "revoked": True},
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )
