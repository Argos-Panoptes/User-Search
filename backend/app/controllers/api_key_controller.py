"""
Business logic for API key management.
Shared between user self-service and admin endpoints.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.schemas.api_key_models import ApiKey


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns (key_id, raw_key, key_hash).
    Format: usk_{key_id}.{secret}
    """
    key_id = f"usk_{secrets.token_urlsafe(8)}"
    secret = secrets.token_urlsafe(32)
    raw_key = f"{key_id}.{secret}"
    key_hash = _bcrypt.hashpw(secret.encode(), _bcrypt.gensalt(rounds=12)).decode()
    return key_id, raw_key, key_hash


def create_key(
    db: Session,
    *,
    name: str,
    created_by_id: int,
    description: str | None = None,
    expires_in_days: int | None = None,
    quota_limit: int | None = None,
    allowed_endpoints: list[str] | None = None,
) -> tuple[ApiKey, str]:
    """
    Create a new API key. Returns (api_key_model, raw_key).
    The raw_key is returned only once and cannot be retrieved later.
    """
    key_id, raw_key, key_hash = generate_api_key()

    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days or 30)

    if quota_limit is None:
        quota_limit = settings.DEFAULT_API_KEY_QUOTA

    api_key = ApiKey(
        key_id=key_id,
        key_hash=key_hash,
        name=name,
        description=description,
        created_by_id=created_by_id,
        expires_at=expires_at,
        quota_limit=quota_limit,
        allowed_endpoints=allowed_endpoints,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(f"API key created: {key_id} by user {created_by_id}")
    return api_key, raw_key


def list_keys(
    db: Session,
    *,
    user_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ApiKey], int]:
    """
    List API keys. If user_id is provided, filter to that user only.
    Returns (keys, total_count).
    """
    query = db.query(ApiKey)

    if user_id is not None:
        query = query.filter(ApiKey.created_by_id == user_id)

    if not include_inactive:
        query = query.filter(ApiKey.is_active == True)

    total = query.count()
    keys = query.order_by(ApiKey.created_at.desc()).offset(offset).limit(limit).all()

    return keys, total


def get_key(
    db: Session,
    *,
    key_id: str,
    user_id: int | None = None,
) -> ApiKey | None:
    """
    Get a single API key by key_id.
    If user_id is provided, enforce ownership.
    """
    query = db.query(ApiKey).filter(ApiKey.key_id == key_id)

    if user_id is not None:
        query = query.filter(ApiKey.created_by_id == user_id)

    return query.first()


def update_key(
    db: Session,
    *,
    key_id: str,
    updates: dict[str, Any],
    user_id: int | None = None,
) -> ApiKey | None:
    """
    Update an API key. If user_id is provided, enforce ownership.
    User-level updates are restricted to name and description.
    Admin updates can include quota_limit, allowed_endpoints, is_active, expires_at.
    """
    api_key = get_key(db, key_id=key_id, user_id=user_id)
    if not api_key:
        return None

    for field, value in updates.items():
        if value is not None and hasattr(api_key, field):
            setattr(api_key, field, value)

    db.commit()
    db.refresh(api_key)

    logger.info(f"API key updated: {key_id}")
    return api_key


def revoke_key(
    db: Session,
    *,
    key_id: str,
    user_id: int | None = None,
) -> bool:
    """
    Soft-revoke an API key (set is_active=False).
    If user_id is provided, enforce ownership.
    Returns True if key was revoked, False if not found.
    """
    api_key = get_key(db, key_id=key_id, user_id=user_id)
    if not api_key:
        return False

    api_key.is_active = False
    db.commit()

    logger.info(f"API key revoked: {key_id}")
    return True


def count_user_keys(db: Session, user_id: int) -> int:
    """Count active API keys for a user."""
    return (
        db.query(ApiKey)
        .filter(ApiKey.created_by_id == user_id, ApiKey.is_active == True)
        .count()
    )


def validate_api_key(db: Session, raw_key: str) -> ApiKey | None:
    """
    Validate a raw API key string.
    Used by the auth dependency.
    """
    parts = raw_key.split(".", 1)
    if len(parts) != 2:
        return None

    key_id_part, secret = parts
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_id == key_id_part, ApiKey.is_active == True)
        .first()
    )
    if not api_key:
        return None

    if api_key.expires_at:
        now = datetime.now(timezone.utc)
        expires = api_key.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            return None

    if not _bcrypt.checkpw(secret.encode(), api_key.key_hash.encode()):
        return None

    return api_key
