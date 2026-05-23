"""
Avatar Sync Part B: Audit logging utilities.
Handles individual and batch audit record creation.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.schemas.ingestion_models import Avatar, AvatarSyncAuditLog
from app.core.logging import logger


def log_avatar_sync_audit(
    db: Session,
    avatar: Avatar,
    action: str,
    detail: str,
    job_id: int,
    old_hash: bytes | None = None,
    new_hash: bytes | None = None,
    old_file_size: int | None = None,
    new_file_size: int | None = None,
    old_s3_url: str | None = None,
    new_s3_url: str | None = None,
) -> None:
    """Create a single AvatarSyncAuditLog entry."""
    entry = AvatarSyncAuditLog(
        avatar_id=avatar.id,
        service_id=avatar.service_id,
        s3_key=avatar.s3_key,
        action=action,
        detail=detail,
        old_hash=old_hash,
        new_hash=new_hash,
        old_file_size=old_file_size,
        new_file_size=new_file_size,
        old_s3_url=old_s3_url,
        new_s3_url=new_s3_url,
        job_id=job_id,
    )
    db.add(entry)


def batch_log_avatar_sync_audits(
    db: Session,
    audit_records: list[dict],
) -> int:
    """
    Batch insert multiple audit records for performance.
    Each dict should have keys matching AvatarSyncAuditLog columns.
    Returns the number of records inserted.
    """
    if not audit_records:
        return 0

    try:
        db.bulk_insert_mappings(AvatarSyncAuditLog, audit_records)
        return len(audit_records)
    except Exception as e:
        logger.error(f"Failed to batch insert audit records: {e}")
        # Fall back to individual inserts
        inserted = 0
        for record in audit_records:
            try:
                entry = AvatarSyncAuditLog(**record)
                db.add(entry)
                inserted += 1
            except Exception as inner_e:
                logger.warning(f"Failed to insert audit record: {inner_e}")
        return inserted


def get_avatar_change_summary(
    db: Session,
    job_id: int,
) -> dict:
    """
    Query audit table for a summary of changes from a specific sync job.
    Returns dict with counts per action type.
    """
    from sqlalchemy import func

    results = (
        db.query(
            AvatarSyncAuditLog.action,
            func.count(AvatarSyncAuditLog.id).label("count"),
        )
        .filter(AvatarSyncAuditLog.job_id == job_id)
        .group_by(AvatarSyncAuditLog.action)
        .all()
    )

    summary = {row.action: row.count for row in results}
    return summary
