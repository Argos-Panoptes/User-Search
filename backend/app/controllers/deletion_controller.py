import logging
import io
import csv
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.db.schemas.ingestion_models import (
    UserMetadata,
    UserExclusionList,
    GroupMembershipMap,
    GroupMembershipHistory,
    Avatar,
)
from app.db.schemas.app_models import AppUser
from app.core.search import get_opensearch_client
from app.core.s3 import delete_s3_object

logger = logging.getLogger(__name__)

INDEX_USERS = "users"


class DeletionController:

    @staticmethod
    def preview_user(db: Session, service_id: str) -> dict:
        """Returns user info for the confirmation step before deletion."""
        user = (
            db.query(UserMetadata)
            .filter(UserMetadata.service_id == service_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        group_count = (
            db.query(GroupMembershipMap)
            .filter(GroupMembershipMap.user_id == user.id)
            .count()
        )

        already_excluded = (
            db.query(UserExclusionList)
            .filter(UserExclusionList.service_id == service_id)
            .first()
            is not None
        )

        return {
            "service_id": user.service_id,
            "name": user.name or user.profile_name or user.profile_full_name,
            "e164": user.e164,
            "group_count": group_count,
            "has_avatar": user.avatar_id is not None,
            "is_active": user.is_active,
            "already_excluded": already_excluded,
        }

    @staticmethod
    def soft_delete_user(
        db: Session,
        service_id: str,
        reason: str,
        notes: str | None,
        admin_user: AppUser,
    ) -> dict:
        """
        Full soft-delete pipeline for a single user.
        Steps: Validate → DB Transaction → OpenSearch → S3 → Return audit record
        """
        # --- Step 1: Validate ---
        user = (
            db.query(UserMetadata)
            .filter(UserMetadata.service_id == service_id)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail=f"User with service_id '{service_id}' not found")

        if not user.is_active:
            raise HTTPException(status_code=409, detail=f"User '{service_id}' is already deleted")

        existing_exclusion = (
            db.query(UserExclusionList)
            .filter(UserExclusionList.service_id == service_id)
            .first()
        )
        if existing_exclusion:
            raise HTTPException(status_code=409, detail=f"User '{service_id}' is already in the exclusion list")

        # --- Step 2: DB Transaction ---
        try:
            # Mark user as inactive
            user.is_active = False

            # Create exclusion list record with user info snapshot
            exclusion_record = UserExclusionList(
                service_id=service_id,
                reason=reason,
                notes=notes,
                deleted_by=admin_user.email,
                deleted_by_id=admin_user.id,
                user_name=user.name or user.profile_name or user.profile_full_name,
                user_e164=user.e164,
            )
            db.add(exclusion_record)

            # Cascade: Mark group membership history as inactive
            db.query(GroupMembershipHistory).filter(
                GroupMembershipHistory.user_id == user.id,
                GroupMembershipHistory.is_active != False,  # noqa: E712
            ).update({"is_active": False}, synchronize_session=False)

            db.commit()
            db.refresh(exclusion_record)

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"User '{service_id}' is already in the exclusion list (concurrent deletion)",
            )
        except Exception:
            db.rollback()
            raise

        # --- Step 3: Remove from OpenSearch ---
        try:
            client = get_opensearch_client()
            client.delete(index=INDEX_USERS, id=service_id, ignore=[404])
            logger.info(f"Removed user '{service_id}' from OpenSearch index")
        except Exception as e:
            logger.warning(f"Failed to remove user '{service_id}' from OpenSearch: {e}")

        # --- Step 4: Delete avatar from S3 ---
        try:
            avatar = (
                db.query(Avatar)
                .filter(Avatar.service_id == service_id)
                .first()
            )
            if avatar and avatar.s3_key:
                deleted = delete_s3_object(avatar.s3_key)
                if deleted:
                    logger.info(f"Deleted avatar S3 object for user '{service_id}'")
        except Exception as e:
            logger.warning(f"Failed to delete avatar for user '{service_id}': {e}")

        # --- Step 5: Return audit record ---
        return {
            "audit_id": exclusion_record.id,
            "service_id": service_id,
            "deleted_by": admin_user.email,
            "deleted_at": exclusion_record.deleted_at.isoformat(),
            "status": "success",
        }

    @staticmethod
    def bulk_soft_delete(
        db: Session,
        service_ids: list[str],
        reason: str,
        notes: str | None,
        admin_user: AppUser,
    ) -> dict:
        """Bulk soft-delete users. Processes each user individually to collect per-user results."""
        results = []
        errors = []

        for service_id in service_ids:
            try:
                result = DeletionController.soft_delete_user(
                    db, service_id, reason, notes, admin_user
                )
                results.append(result)
            except HTTPException as e:
                errors.append({
                    "service_id": service_id,
                    "error": e.detail,
                    "status_code": e.status_code,
                })
            except Exception as e:
                errors.append({
                    "service_id": service_id,
                    "error": str(e),
                    "status_code": 500,
                })

        return {
            "total": len(service_ids),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    @staticmethod
    def get_audit_log(
        db: Session,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        reason: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """Paginated query of UserExclusionList for audit log display."""
        query = db.query(UserExclusionList)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (UserExclusionList.service_id.ilike(search_term))
                | (UserExclusionList.user_name.ilike(search_term))
                | (UserExclusionList.user_e164.ilike(search_term))
                | (UserExclusionList.deleted_by.ilike(search_term))
            )

        if reason:
            query = query.filter(UserExclusionList.reason == reason)

        if date_from:
            query = query.filter(UserExclusionList.deleted_at >= date_from)

        if date_to:
            query = query.filter(UserExclusionList.deleted_at <= date_to)

        total = query.count()

        items = (
            query.order_by(UserExclusionList.deleted_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": [
                {
                    "id": item.id,
                    "service_id": item.service_id,
                    "reason": item.reason,
                    "notes": item.notes,
                    "deleted_by": item.deleted_by,
                    "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
                    "user_name": item.user_name,
                    "user_e164": item.user_e164,
                }
                for item in items
            ],
            "total": total,
        }

    @staticmethod
    def export_audit_log_csv(db: Session) -> StreamingResponse:
        """Export the full audit log as a CSV file."""
        items = (
            db.query(UserExclusionList)
            .order_by(UserExclusionList.deleted_at.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Service ID", "User Name", "Phone", "Reason",
            "Notes", "Deleted By", "Deleted At",
        ])
        for item in items:
            writer.writerow([
                item.id,
                item.service_id,
                item.user_name,
                item.user_e164,
                item.reason,
                item.notes,
                item.deleted_by,
                item.deleted_at.isoformat() if item.deleted_at else "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=deletion_audit_log.csv"},
        )

    @staticmethod
    def check_exclusion(db: Session, service_id: str) -> bool:
        """Returns True if service_id is in the exclusion list."""
        return (
            db.query(UserExclusionList)
            .filter(UserExclusionList.service_id == service_id)
            .first()
            is not None
        )
