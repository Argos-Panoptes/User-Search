"""
Business logic for internal/Telchines API endpoints.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger


class InternalController:
    @staticmethod
    def batch_pull_users(
        db: Session,
        service_ids: list[str],
        include_history: bool = False,
        include_avatars: bool = False,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        from app.db.schemas.ingestion_models import (
            UserMetadata,
            Avatar,
            GroupMembershipMap,
            GroupMetadata,
        )

        if not service_ids:
            return []

        # Chunk large lists to avoid SQL IN clause limits
        chunk_size = 500
        all_results = []

        for i in range(0, len(service_ids), chunk_size):
            chunk = service_ids[i : i + chunk_size]
            users = (
                db.query(UserMetadata)
                .filter(
                    UserMetadata.service_id.in_(chunk),
                    UserMetadata.is_active == True,
                )
                .all()
            )

            for user in users:
                user_data: dict[str, Any] = {
                    "id": user.id,
                    "service_id": user.service_id,
                    "e164": user.e164,
                    "name": user.name,
                    "profile_name": user.profile_name,
                    "profile_full_name": user.profile_full_name,
                    "profile_family_name": user.profile_family_name,
                    "about": user.about,
                    "is_admin": user.is_admin,
                    "export_timestamp": (
                        user.export_timestamp.isoformat()
                        if user.export_timestamp
                        else None
                    ),
                    "snapshot_hash": (
                        user.snapshot_hash.hex()
                        if user.snapshot_hash and isinstance(user.snapshot_hash, bytes)
                        else str(user.snapshot_hash) if user.snapshot_hash else None
                    ),
                }

                if include_avatars and user.avatar_id:
                    avatar = db.query(Avatar).filter(Avatar.id == user.avatar_id).first()
                    if avatar:
                        user_data["avatar"] = {
                            "avatar_id": avatar.id,
                            "s3_key": avatar.s3_key,
                            "s3_url": avatar.s3_url,
                            "filename": avatar.filename,
                            "file_size": avatar.file_size,
                        }

                # Get group memberships
                memberships = (
                    db.query(GroupMembershipMap, GroupMetadata.group_id, GroupMetadata.group_name)
                    .join(GroupMetadata, GroupMembershipMap.group_id == GroupMetadata.id)
                    .filter(GroupMembershipMap.user_id == user.id)
                    .all()
                )
                user_data["group_memberships"] = [
                    {"group_id": gid, "group_name": gname, "role": m.role}
                    for m, gid, gname in memberships
                ]

                if fields:
                    user_data = {k: v for k, v in user_data.items() if k in fields}

                all_results.append(user_data)

        return all_results

    @staticmethod
    def get_avatar_metadata(
        db: Session,
        service_ids: list[str] | None = None,
        updated_since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        from app.db.schemas.ingestion_models import Avatar

        query = db.query(Avatar)

        if service_ids:
            query = query.filter(Avatar.service_id.in_(service_ids))

        if updated_since:
            query = query.filter(Avatar.timestamp >= updated_since)

        avatars = query.all()

        return [
            {
                "avatar_id": a.id,
                "service_id": a.service_id,
                "s3_key": a.s3_key,
                "s3_url": a.s3_url,
                "filename": a.filename,
                "file_size": a.file_size,
                "hash": (
                    a.snapshot_hash.hex()
                    if a.snapshot_hash and isinstance(a.snapshot_hash, bytes)
                    else str(a.snapshot_hash) if a.snapshot_hash else None
                ),
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in avatars
        ]

    @staticmethod
    def bulk_update_observed_dates(
        db: Session,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from app.db.schemas.ingestion_models import UserMetadata

        updated = 0
        errors = []
        affected_service_ids = []

        for item in updates:
            sid = item.get("service_id")
            if not sid:
                errors.append({"service_id": sid, "error": "Missing service_id"})
                continue

            user = (
                db.query(UserMetadata)
                .filter(UserMetadata.service_id == sid)
                .first()
            )
            if not user:
                errors.append({"service_id": sid, "error": "User not found"})
                continue

            # Parse and validate dates
            changed = False
            for field in ("first_observed", "last_observed"):
                raw = item.get(field)
                if raw is None:
                    continue
                try:
                    parsed = datetime.fromisoformat(raw)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    setattr(user, field, parsed)
                    changed = True
                except (ValueError, TypeError):
                    errors.append({
                        "service_id": sid,
                        "error": f"Invalid date format for {field}: {raw}",
                    })

            if changed:
                updated += 1
                affected_service_ids.append(sid)

        if updated > 0:
            db.commit()

        # Re-index affected users in OpenSearch
        if affected_service_ids:
            try:
                from app.ingestion.search_indexer import index_users_by_ids

                index_users_by_ids(affected_service_ids)
                logger.info(
                    f"Bulk observed date update: {updated} users updated, "
                    f"{len(errors)} errors. Re-indexed {len(affected_service_ids)} users."
                )
            except Exception as e:
                logger.warning(f"Could not trigger re-index: {e}")

        return {
            "updated": updated,
            "errors": errors,
        }

    @staticmethod
    def bulk_update_group_observed_dates(
        db: Session,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from app.db.schemas.ingestion_models import GroupMetadata

        updated = 0
        errors = []
        affected_group_ids = []

        for item in updates:
            gid = item.get("group_id")
            if not gid:
                errors.append({"group_id": gid, "error": "Missing group_id"})
                continue

            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.group_id == gid)
                .first()
            )
            if not group:
                errors.append({"group_id": gid, "error": "Group not found"})
                continue

            changed = False
            for field in ("first_observed", "last_observed"):
                raw = item.get(field)
                if raw is None:
                    continue
                try:
                    parsed = datetime.fromisoformat(raw)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    setattr(group, field, parsed)
                    changed = True
                except (ValueError, TypeError):
                    errors.append({
                        "group_id": gid,
                        "error": f"Invalid date format for {field}: {raw}",
                    })

            if changed:
                updated += 1
                affected_group_ids.append(gid)

        if updated > 0:
            db.commit()

        # Re-index affected groups in OpenSearch
        if affected_group_ids:
            try:
                from app.ingestion.search_indexer import index_groups_by_ids

                index_groups_by_ids(affected_group_ids)
                logger.info(
                    f"Bulk group observed date update: {updated} groups updated, "
                    f"{len(errors)} errors. Re-indexed {len(affected_group_ids)} groups."
                )
            except Exception as e:
                logger.warning(f"Could not trigger re-index: {e}")

        return {
            "updated": updated,
            "errors": errors,
        }

    @staticmethod
    def get_config() -> dict[str, Any]:
        return {
            "api_version": settings.API_VERSION,
            "data_version": settings.DATA_VERSION,
            "batch_pull_max_items": 10000,
            "supported_fields": [
                "id", "service_id", "e164", "name", "profile_name",
                "profile_full_name", "profile_family_name", "about",
                "is_admin", "export_timestamp", "snapshot_hash",
                "avatar", "group_memberships",
            ],
        }
