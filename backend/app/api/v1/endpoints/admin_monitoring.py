"""
Admin monitoring and analytics endpoints.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.controllers import api_key_controller
from app.core.config import settings
from app.db.session import get_db
from app.db.schemas.api_key_models import ApiKey, ApiRequestLog
from app.db.schemas.app_models import AppUser
from app.schemas.api_response import (
    wrap_response,
    ApiObjectResponse,
    ApiListResponse,
)

router = APIRouter()


def _parse_time_range(time_range: str) -> datetime:
    now = datetime.now(timezone.utc)
    mapping = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    return now - mapping.get(time_range, timedelta(hours=24))


@router.get("/usage/stats", response_model=ApiObjectResponse)
def get_usage_stats(
    request: Request,
    db: Session = Depends(get_db),
):
    total_keys = db.query(ApiKey).count()
    active_keys = db.query(ApiKey).filter(ApiKey.is_active == True).count()
    total_requests = (
        db.query(func.sum(ApiKey.request_count)).scalar() or 0
    )
    total_users = db.query(AppUser).filter(AppUser.is_active == True).count()

    # Enhanced: today's stats from request logs
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_requests = (
        db.query(func.count(ApiRequestLog.id))
        .filter(ApiRequestLog.timestamp >= today_start)
        .scalar()
        or 0
    )
    avg_response_time = (
        db.query(func.avg(ApiRequestLog.response_time_ms))
        .filter(ApiRequestLog.timestamp >= today_start)
        .scalar()
    )
    error_count_today = (
        db.query(func.count(ApiRequestLog.id))
        .filter(
            ApiRequestLog.timestamp >= today_start,
            ApiRequestLog.status_code >= 400,
        )
        .scalar()
        or 0
    )

    return wrap_response(
        data={
            "total_api_keys": total_keys,
            "active_api_keys": active_keys,
            "total_api_requests": total_requests,
            "total_active_users": total_users,
            "today_requests": today_requests,
            "avg_response_time_ms": round(avg_response_time, 1) if avg_response_time else None,
            "today_errors": error_count_today,
        },
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/usage/by-key", response_model=ApiListResponse)
def get_usage_by_key(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 20,
):
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.is_active == True)
        .order_by(ApiKey.request_count.desc())
        .limit(limit)
        .all()
    )

    data = [
        {
            "key_id": k.key_id,
            "name": k.name,
            "created_by_id": k.created_by_id,
            "request_count": k.request_count or 0,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "quota_limit": k.quota_limit,
        }
        for k in keys
    ]

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/usage/endpoints", response_model=ApiListResponse)
def get_endpoint_usage(
    request: Request,
    db: Session = Depends(get_db),
    time_range: str = "24h",
    limit: int = 20,
    api_key_id: str | None = None,
):
    """Top endpoints by hit count within a time range."""
    since = _parse_time_range(time_range)

    query = db.query(
        ApiRequestLog.endpoint,
        ApiRequestLog.method,
        func.count(ApiRequestLog.id).label("hit_count"),
        func.avg(ApiRequestLog.response_time_ms).label("avg_response_ms"),
        func.count(
            case((ApiRequestLog.status_code >= 400, 1))
        ).label("error_count"),
    ).filter(ApiRequestLog.timestamp >= since)

    if api_key_id:
        query = query.filter(ApiRequestLog.api_key_id == api_key_id)

    results = (
        query.group_by(ApiRequestLog.endpoint, ApiRequestLog.method)
        .order_by(func.count(ApiRequestLog.id).desc())
        .limit(limit)
        .all()
    )

    data = [
        {
            "endpoint": r.endpoint,
            "method": r.method,
            "hit_count": r.hit_count,
            "avg_response_ms": round(r.avg_response_ms, 1) if r.avg_response_ms else None,
            "error_count": r.error_count,
        }
        for r in results
    ]

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/usage/timeline", response_model=ApiListResponse)
def get_usage_timeline(
    request: Request,
    db: Session = Depends(get_db),
    time_range: str = "24h",
    api_key_id: str | None = None,
):
    """Request count over time in hourly or daily buckets."""
    since = _parse_time_range(time_range)
    bucket = "hour" if time_range in ("1h", "24h") else "day"

    bucket_col = func.date_trunc(bucket, ApiRequestLog.timestamp).label("bucket")

    query = db.query(
        bucket_col,
        func.count(ApiRequestLog.id).label("request_count"),
        func.avg(ApiRequestLog.response_time_ms).label("avg_response_ms"),
        func.count(
            case((ApiRequestLog.status_code >= 400, 1))
        ).label("error_count"),
    ).filter(ApiRequestLog.timestamp >= since)

    if api_key_id:
        query = query.filter(ApiRequestLog.api_key_id == api_key_id)

    results = query.group_by(bucket_col).order_by(bucket_col).all()

    data = [
        {
            "bucket": r.bucket.isoformat() if r.bucket else None,
            "request_count": r.request_count,
            "avg_response_ms": round(r.avg_response_ms, 1) if r.avg_response_ms else None,
            "error_count": r.error_count,
        }
        for r in results
    ]

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/usage/by-key/{key_id}", response_model=ApiObjectResponse)
def get_key_detail_usage(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
    time_range: str = "7d",
):
    """Detailed usage stats for a specific API key."""
    api_key = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    since = _parse_time_range(time_range)

    base_q = db.query(ApiRequestLog).filter(
        ApiRequestLog.api_key_id == key_id,
        ApiRequestLog.timestamp >= since,
    )

    total_in_range = base_q.count()

    avg_response = (
        db.query(func.avg(ApiRequestLog.response_time_ms))
        .filter(
            ApiRequestLog.api_key_id == key_id,
            ApiRequestLog.timestamp >= since,
        )
        .scalar()
    )

    error_count = (
        db.query(func.count(ApiRequestLog.id))
        .filter(
            ApiRequestLog.api_key_id == key_id,
            ApiRequestLog.timestamp >= since,
            ApiRequestLog.status_code >= 400,
        )
        .scalar()
        or 0
    )

    # Top endpoints for this key
    top_endpoints = (
        db.query(
            ApiRequestLog.endpoint,
            func.count(ApiRequestLog.id).label("hit_count"),
        )
        .filter(
            ApiRequestLog.api_key_id == key_id,
            ApiRequestLog.timestamp >= since,
        )
        .group_by(ApiRequestLog.endpoint)
        .order_by(func.count(ApiRequestLog.id).desc())
        .limit(10)
        .all()
    )

    # Timeline for this key
    bucket = "hour" if time_range in ("1h", "24h") else "day"
    bucket_col = func.date_trunc(bucket, ApiRequestLog.timestamp).label("bucket")
    timeline = (
        db.query(
            bucket_col,
            func.count(ApiRequestLog.id).label("request_count"),
        )
        .filter(
            ApiRequestLog.api_key_id == key_id,
            ApiRequestLog.timestamp >= since,
        )
        .group_by(bucket_col)
        .order_by(bucket_col)
        .all()
    )

    data = {
        "key_id": api_key.key_id,
        "name": api_key.name,
        "total_requests_all_time": api_key.request_count or 0,
        "requests_in_range": total_in_range,
        "avg_response_ms": round(avg_response, 1) if avg_response else None,
        "error_count": error_count,
        "error_rate": round(error_count / total_in_range * 100, 1) if total_in_range > 0 else 0,
        "top_endpoints": [
            {"endpoint": ep.endpoint, "hit_count": ep.hit_count}
            for ep in top_endpoints
        ],
        "timeline": [
            {
                "bucket": t.bucket.isoformat() if t.bucket else None,
                "request_count": t.request_count,
            }
            for t in timeline
        ],
    }

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/health", response_model=ApiObjectResponse)
def get_extended_health(
    request: Request,
    db: Session = Depends(get_db),
):
    components = {}

    # Database
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception as e:
        components["database"] = f"error: {str(e)}"

    # OpenSearch
    try:
        import requests as http_requests
        from app.core.config import settings

        resp = http_requests.get(
            f"{settings.OPENSEARCH_URL}/_cluster/health", timeout=3
        )
        if resp.status_code == 200:
            health = resp.json()
            components["opensearch"] = {
                "status": health.get("status"),
                "number_of_nodes": health.get("number_of_nodes"),
                "active_shards": health.get("active_shards"),
            }
        else:
            components["opensearch"] = "error"
    except Exception:
        components["opensearch"] = "unreachable"

    # Redis
    try:
        import redis
        from app.core.config import settings

        r = redis.from_url(settings.REDIS_URL, socket_timeout=3)
        r.ping()
        components["redis"] = "ok"
    except Exception:
        components["redis"] = "unreachable"

    # S3
    try:
        from app.core.config import settings

        if settings.S3_BUCKET_NAME:
            from app.core.s3 import get_s3_client

            s3 = get_s3_client()
            if s3:
                s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
                components["s3"] = "ok"
            else:
                components["s3"] = "not configured"
        else:
            components["s3"] = "not configured"
    except Exception:
        components["s3"] = "error"

    all_ok = all(
        v == "ok" or (isinstance(v, dict) and v.get("status") in ("green", "yellow"))
        for v in components.values()
        if v != "not configured"
    )

    return wrap_response(
        data={
            "status": "healthy" if all_ok else "degraded",
            "components": components,
        },
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


# --- Per-User API Limits Management ---


class UserLimitsUpdate(BaseModel):
    rate_limit_per_minute: Optional[int] = Field(
        None, ge=1, le=10000, description="Custom rate limit (requests/minute). Set to null to use system default."
    )
    max_api_keys: Optional[int] = Field(
        None, ge=1, le=100, description="Max API keys this user can create. Set to null to use system default."
    )


class UserLimitsResetField(BaseModel):
    """Use this to explicitly reset a field back to system default."""
    reset_rate_limit: bool = Field(False, description="Reset rate limit to system default")
    reset_max_api_keys: bool = Field(False, description="Reset max API keys to system default")


@router.get("/users/limits", response_model=ApiListResponse)
def list_user_limits(
    request: Request,
    db: Session = Depends(get_db),
    search: str | None = None,
    has_custom_limits: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List users with their API limits. Filter to only users with custom limits."""
    query = db.query(AppUser).filter(AppUser.is_active == True)

    if search:
        query = query.filter(
            AppUser.email.ilike(f"%{search}%")
            | AppUser.full_name.ilike(f"%{search}%")
        )

    if has_custom_limits:
        query = query.filter(
            (AppUser.rate_limit_per_minute.isnot(None))
            | (AppUser.max_api_keys.isnot(None))
        )

    total = query.count()
    users = query.order_by(AppUser.id).offset(offset).limit(limit).all()

    data = []
    for u in users:
        active_keys = api_key_controller.count_user_keys(db, u.id)
        effective_max_keys = u.max_api_keys if u.max_api_keys is not None else settings.MAX_API_KEYS_PER_USER
        effective_rate_limit = u.rate_limit_per_minute if u.rate_limit_per_minute is not None else settings.DEFAULT_API_KEY_QUOTA

        data.append({
            "user_id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_superuser": u.is_superuser,
            "rate_limit_per_minute": u.rate_limit_per_minute,
            "max_api_keys": u.max_api_keys,
            "effective_rate_limit": effective_rate_limit,
            "effective_max_api_keys": effective_max_keys,
            "active_api_keys": active_keys,
            "system_defaults": {
                "rate_limit_per_minute": settings.DEFAULT_API_KEY_QUOTA,
                "max_api_keys": settings.MAX_API_KEYS_PER_USER,
            },
        })

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.get("/users/{user_id}/limits", response_model=ApiObjectResponse)
def get_user_limits(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific user's API limits and current usage."""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    active_keys = api_key_controller.count_user_keys(db, user.id)
    effective_max_keys = user.max_api_keys if user.max_api_keys is not None else settings.MAX_API_KEYS_PER_USER
    effective_rate_limit = user.rate_limit_per_minute if user.rate_limit_per_minute is not None else settings.DEFAULT_API_KEY_QUOTA

    # Get the user's API keys with their individual quotas
    keys, _ = api_key_controller.list_keys(db, user_id=user.id, include_inactive=False)
    key_summaries = [
        {
            "key_id": k.key_id,
            "name": k.name,
            "quota_limit": k.quota_limit,
            "request_count": k.request_count or 0,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]

    data = {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_superuser": user.is_superuser,
        "rate_limit_per_minute": user.rate_limit_per_minute,
        "max_api_keys": user.max_api_keys,
        "effective_rate_limit": effective_rate_limit,
        "effective_max_api_keys": effective_max_keys,
        "active_api_keys": active_keys,
        "keys": key_summaries,
        "system_defaults": {
            "rate_limit_per_minute": settings.DEFAULT_API_KEY_QUOTA,
            "max_api_keys": settings.MAX_API_KEYS_PER_USER,
        },
    }

    return wrap_response(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )


@router.patch("/users/{user_id}/limits", response_model=ApiObjectResponse)
def update_user_limits(
    request: Request,
    user_id: int,
    body: UserLimitsUpdate,
    reset: UserLimitsResetField = Depends(),
    db: Session = Depends(get_db),
):
    """
    Update a user's API rate limit and/or max API keys.

    - Pass a value to set a custom limit.
    - Use reset query params (?reset_rate_limit=true) to revert to system defaults.
    """
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_unset=True)

    if reset.reset_rate_limit:
        user.rate_limit_per_minute = None
    elif "rate_limit_per_minute" in updates:
        user.rate_limit_per_minute = updates["rate_limit_per_minute"]

    if reset.reset_max_api_keys:
        user.max_api_keys = None
    elif "max_api_keys" in updates:
        new_max = updates["max_api_keys"]
        # Warn if user already has more keys than the new limit
        if new_max is not None:
            active_keys = api_key_controller.count_user_keys(db, user.id)
            if active_keys > new_max:
                raise HTTPException(
                    status_code=400,
                    detail=f"User already has {active_keys} active keys, cannot set max to {new_max}. Revoke some keys first.",
                )
        user.max_api_keys = new_max

    db.commit()
    db.refresh(user)

    effective_max_keys = user.max_api_keys if user.max_api_keys is not None else settings.MAX_API_KEYS_PER_USER
    effective_rate_limit = user.rate_limit_per_minute if user.rate_limit_per_minute is not None else settings.DEFAULT_API_KEY_QUOTA

    return wrap_response(
        data={
            "user_id": user.id,
            "email": user.email,
            "rate_limit_per_minute": user.rate_limit_per_minute,
            "max_api_keys": user.max_api_keys,
            "effective_rate_limit": effective_rate_limit,
            "effective_max_api_keys": effective_max_keys,
            "updated": True,
        },
        request_id=getattr(request.state, "request_id", "unknown"),
        start_time=getattr(request.state, "start_time", None),
    )
