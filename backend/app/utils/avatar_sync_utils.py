"""
Avatar Sync Part B: Utility functions for smart filtering, rate limiting,
and change frequency tracking.

Updated to query UserMetadata (CDN fetch source) instead of Avatar (S3 revalidation).
"""

import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import or_, and_, text
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.core.logging import logger
from app.db.schemas.ingestion_models import Avatar, UserMetadata


def _get_setting_int(db: Session, key: str, default: int) -> int:
    """Read an integer setting from SystemSetting table, falling back to default."""
    from app.db.schemas.app_models import SystemSetting

    row = db.query(SystemSetting).filter(SystemSetting.key == key).scalar()
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    return default


def _get_setting_float(db: Session, key: str, default: float) -> float:
    """Read a float setting from SystemSetting table, falling back to default."""
    from app.db.schemas.app_models import SystemSetting

    row = db.query(SystemSetting).filter(SystemSetting.key == key).scalar()
    if row and row.value:
        try:
            return float(row.value)
        except ValueError:
            pass
    return default


def build_smart_filter_query(db: Session, last_processed_id: int = 0, shard_end: int | None = None):
    """
    Build the smart filtering query that returns UserMetadata rows needing CDN sync.

    Queries UserMetadata rows that have both remote_avatar_url and profile_key,
    left-joining to Avatar via avatar_id to check verification status.

    Multi-layer filtering:
    1. Only include users with remote_avatar_url AND profile_key
    2. Skip users whose linked avatar was verified recently based on change_frequency:
       - HIGH: re-check every AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS (default 6h)
       - MEDIUM: re-check every AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS (default 72h / 3 days)
       - LOW: re-check every AVATAR_SYNC_CHECK_LOW_FREQ_HOURS (default 168h / 7 days)
       - No avatar / never verified: always check within AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS
    3. Order by change_frequency DESC (HIGH first), then last_verified_at ASC (oldest first)
    4. Keyset pagination via UserMetadata.id > last_processed_id

    Tier hours are read from SystemSetting (admin-editable) with env var fallback.

    Returns query of (UserMetadata, Avatar|None) tuples.
    """
    now = datetime.now(timezone.utc)

    # Read tier hours from SystemSetting (admin UI) with env var defaults
    high_hours = _get_setting_int(db, "AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS", settings.AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS)
    medium_hours = _get_setting_int(db, "AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS", settings.AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS)
    low_hours = _get_setting_int(db, "AVATAR_SYNC_CHECK_LOW_FREQ_HOURS", settings.AVATAR_SYNC_CHECK_LOW_FREQ_HOURS)
    never_hours = _get_setting_int(db, "AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS", settings.AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS)

    high_cutoff = now - timedelta(hours=high_hours)
    medium_cutoff = now - timedelta(hours=medium_hours)
    low_cutoff = now - timedelta(hours=low_hours)
    never_cutoff = now - timedelta(hours=never_hours)

    # Avatars that need re-checking based on their frequency tier
    needs_check = or_(
        # No linked avatar yet — always fetch
        UserMetadata.avatar_id.is_(None),
        # Avatar exists but never verified
        Avatar.last_verified_at.is_(None),
        # HIGH change frequency — check frequently
        and_(
            Avatar.change_frequency == "HIGH",
            Avatar.last_verified_at < high_cutoff,
        ),
        # MEDIUM change frequency — check moderately
        and_(
            Avatar.change_frequency == "MEDIUM",
            Avatar.last_verified_at < medium_cutoff,
        ),
        # LOW change frequency — check infrequently
        and_(
            Avatar.change_frequency == "LOW",
            Avatar.last_verified_at < low_cutoff,
        ),
        # No change_frequency assigned yet — treat as never-verified
        and_(
            Avatar.change_frequency.is_(None),
            or_(
                Avatar.last_verified_at.is_(None),
                Avatar.last_verified_at < never_cutoff,
            ),
        ),
    )

    query = (
        db.query(UserMetadata, Avatar)
        .outerjoin(Avatar, UserMetadata.avatar_id == Avatar.id)
        .filter(
            UserMetadata.id > last_processed_id,
            *(
                [UserMetadata.id <= shard_end] if shard_end is not None else []
            ),
            UserMetadata.remote_avatar_url.isnot(None),
            UserMetadata.profile_key.isnot(None),
            needs_check,
        )
        .order_by(
            # Prioritize: HIGH first, then MEDIUM, then LOW, then NULL/no avatar
            text(
                "CASE avatars.change_frequency "
                "WHEN 'HIGH' THEN 1 "
                "WHEN 'MEDIUM' THEN 2 "
                "WHEN 'LOW' THEN 3 "
                "ELSE 4 END"
            ),
            Avatar.last_verified_at.asc().nullsfirst(),
            UserMetadata.id.asc(),
        )
        .limit(_get_setting_int(db, "AVATAR_SYNC_BATCH_SIZE", settings.AVATAR_SYNC_BATCH_SIZE))
    )

    return query


def update_change_frequency(avatar: Avatar, changed: bool) -> None:
    """
    Auto-adjust change_frequency based on actual change patterns.

    Rules:
    - If avatar changed → promote toward HIGH
    - If avatar unchanged → demote toward LOW
    - New avatars start as MEDIUM

    Transition logic:
      changed=True:  LOW → MEDIUM, MEDIUM → HIGH, HIGH → HIGH
      changed=False: HIGH → MEDIUM, MEDIUM → LOW, LOW → LOW
    """
    current = avatar.change_frequency

    if changed:
        # Promote: avatar is actively changing
        if current is None or current == "LOW":
            avatar.change_frequency = "MEDIUM"
        elif current == "MEDIUM":
            avatar.change_frequency = "HIGH"
        # HIGH stays HIGH
    else:
        # Demote: avatar is stable
        if current is None:
            avatar.change_frequency = "LOW"
        elif current == "HIGH":
            avatar.change_frequency = "MEDIUM"
        elif current == "MEDIUM":
            avatar.change_frequency = "LOW"
        # LOW stays LOW


def rate_limit_sleep(requests_this_second: int) -> None:
    """
    Simple rate limiter: sleeps if we've exceeded the per-second CDN request limit.
    Called after each avatar sync within a batch.
    """
    max_per_sec = settings.AVATAR_SYNC_CDN_REQUESTS_PER_SEC
    if max_per_sec <= 0:
        return
    if requests_this_second >= max_per_sec:
        time.sleep(1.0 / max_per_sec)


def retry_with_backoff(attempt: int) -> float:
    """
    Calculate backoff delay for retry attempts.
    Uses configurable base with exponential growth: base * 2^attempt
    e.g. base=0.5: 0.5s, 1.0s, 2.0s...
    """
    base = settings.AVATAR_SYNC_RETRY_BACKOFF_BASE
    delay = base * (2 ** attempt)
    return min(delay, 30.0)  # Cap at 30 seconds


def check_timeout_exceeded(job_started_at: datetime | None) -> tuple[bool, float]:
    """
    Check if the sync job has exceeded the configured timeout.
    Returns (exceeded: bool, elapsed_seconds: float).
    """
    if job_started_at is None:
        return False, 0.0

    started = job_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    exceeded = elapsed > settings.AVATAR_SYNC_TIMEOUT_SECONDS
    return exceeded, elapsed


def check_alert_threshold(job_started_at: datetime | None) -> tuple[bool, float]:
    """
    Check if the sync job duration exceeds the alert threshold.
    Returns (should_alert: bool, elapsed_seconds: float).
    """
    if job_started_at is None:
        return False, 0.0

    started = job_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    should_alert = elapsed > settings.AVATAR_SYNC_ALERT_IF_EXCEEDS_SECONDS
    return should_alert, elapsed
