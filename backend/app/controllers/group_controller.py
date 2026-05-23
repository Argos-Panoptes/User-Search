from sqlalchemy.orm import Session

from typing import Any

# from typing import List, Optional  # Switched to modern | syntax

# actually, let's just stick to what's used.
from app.core.logging import logger
from typing import TypedDict


class RetentionCache(TypedDict):
    data: list[str] | None
    timestamp: float


_retention_periods_cache: RetentionCache = {"data": None, "timestamp": 0.0}


class GroupController:
    @staticmethod
    def search_groups(
        db: Session,
        q: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        description: str | None = None,
        min_members: int | None = None,
        max_members: int | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        retention_period: str | None = None,
        admin_approval_required: bool | None = None,
        has_link: bool | None = None,
    ) -> list[dict[str, Any]]:
        from app.core.search import get_opensearch_client, search_index

        client = get_opensearch_client()

        must_clauses = []
        filter_clauses = []

        if q:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": q,
                        "fields": ["group_name", "description", "group_id"],
                        "fuzziness": "AUTO",
                    }
                }
            )

        if group_id:
            if isinstance(group_id, int) or (
                isinstance(group_id, str) and group_id.isdigit()
            ):
                filter_clauses.append({"term": {"id": int(group_id)}})
            else:
                must_clauses.append({"wildcard": {"group_id": f"*{group_id}*"}})

        if group_name:
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "group_name": {
                                        "query": group_name,
                                        "fuzziness": "AUTO",
                                    }
                                }
                            },
                            {"wildcard": {"group_name": f"*{group_name}*"}},
                        ]
                    }
                }
            )

        if description:
            must_clauses.append(
                {"match": {"description": {"query": description, "fuzziness": "AUTO"}}}
            )

        if min_members is not None:
            filter_clauses.append(
                {"range": {"number_of_members": {"gte": min_members}}}
            )

        if max_members is not None:
            filter_clauses.append(
                {"range": {"number_of_members": {"lte": max_members}}}
            )

        if retention_period:
            if retention_period == "Off":
                filter_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"term": {"retention_period": "Off"}},
                                {"term": {"retention_period": "Never"}},
                                {
                                    "bool": {
                                        "must_not": {
                                            "exists": {"field": "retention_period"}
                                        }
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )
            else:
                filter_clauses.append(
                    {
                        "match": {
                            "retention_period": {
                                "query": retention_period,
                                "operator": "and",
                            }
                        }
                    }
                )

        if admin_approval_required is not None:
            # Handle boolean logic with legacy string support
            if admin_approval_required is False:
                # If False (Open), also include groups where field is missing (null)
                filter_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"term": {"admin_approval_required": False}},
                                {
                                    "bool": {
                                        "must_not": {
                                            "exists": {
                                                "field": "admin_approval_required"
                                            }
                                        }
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )
            else:
                # If True (Approval Required)
                filter_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"term": {"admin_approval_required": True}},
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )

        if has_link is not None:
            if has_link:
                must_clauses.append(
                    {
                        "bool": {
                            "should": [
                                {"exists": {"field": "group_link"}},
                                {"exists": {"field": "reconstructed_link"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                )
            else:
                filter_clauses.append(
                    {
                        "bool": {
                            "must_not": [
                                {"exists": {"field": "group_link"}},
                                {"exists": {"field": "reconstructed_link"}},
                            ]
                        }
                    }
                )

        sort_clause = []
        if sort_by == "members-desc":
            sort_clause = [{"number_of_members": "desc"}]
        elif sort_by == "members-asc":
            sort_clause = [{"number_of_members": "asc"}]
        elif sort_by == "name-asc":
            sort_clause = [{"group_name.keyword": "asc"}]
        elif sort_by == "name-desc":
            sort_clause = [{"group_name.keyword": "desc"}]
        elif sort_by == "link":
            # Priority to groups with links (either group_link or reconstructed_link)
            sort_clause = [
                {
                    "_script": {
                        "type": "number",
                        "script": {
                            "lang": "painless",
                            "source": "(doc['group_link'].size() > 0 || doc['reconstructed_link'].size() > 0) ? 1 : 0",
                        },
                        "order": "desc",
                    }
                },
                {"number_of_members": "desc"},
            ]
        else:
            # Default sort
            sort_clause = [{"number_of_members": "desc"}]

        if not must_clauses and not filter_clauses:
            must_clauses.append({"match_all": {}})

        query_body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "sort": sort_clause,
        }
        # Execute search
        hits: list[dict[str, Any]] = search_index(
            client, "groups", query_body, size=limit, from_=offset
        )

        results: list[dict[str, Any]] = []
        for source in hits:
            results.append(
                {
                    "id": source.get("id"),
                    "groupId": source.get("group_id"),
                    "groupName": source.get("group_name"),
                    "numberOfMembers": source.get("number_of_members"),
                    "description": source.get("description"),
                    "groupLink": source.get("group_link"),
                    "reconstructedLink": source.get("reconstructed_link"),
                    "adminApprovalRequired": source.get("admin_approval_required"),
                    "firstObserved": source.get("first_observed"),
                    "lastObserved": source.get("last_observed"),
                    "retentionPeriod": source.get("retention_period"),
                }
            )

        return results

    @staticmethod
    def search_groups_paginated(
        db: Session,
        q: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        description: str | None = None,
        min_members: int | None = None,
        max_members: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "desc",
        retention_period: str | None = None,
        admin_approval_required: bool | None = None,
        has_link: bool | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Search groups with total count for pagination meta.
        Returns (results, total_count).
        """
        from app.core.search import get_opensearch_client, search_index_with_total

        client = get_opensearch_client()

        must_clauses: list[dict] = []
        filter_clauses: list[dict] = []

        if q:
            must_clauses.append(
                {"multi_match": {"query": q, "fields": ["group_name", "description", "group_id"], "fuzziness": "AUTO"}}
            )
        if group_id:
            if isinstance(group_id, int) or (isinstance(group_id, str) and group_id.isdigit()):
                filter_clauses.append({"term": {"id": int(group_id)}})
            else:
                must_clauses.append({"wildcard": {"group_id": f"*{group_id}*"}})
        if group_name:
            must_clauses.append({"bool": {"should": [
                {"match": {"group_name": {"query": group_name, "fuzziness": "AUTO"}}},
                {"wildcard": {"group_name": f"*{group_name}*"}},
            ]}})
        if description:
            must_clauses.append({"match": {"description": {"query": description, "fuzziness": "AUTO"}}})
        if min_members is not None:
            filter_clauses.append({"range": {"number_of_members": {"gte": min_members}}})
        if max_members is not None:
            filter_clauses.append({"range": {"number_of_members": {"lte": max_members}}})
        if retention_period:
            if retention_period == "Off":
                filter_clauses.append({"bool": {"should": [
                    {"term": {"retention_period": "Off"}},
                    {"term": {"retention_period": "Never"}},
                    {"bool": {"must_not": {"exists": {"field": "retention_period"}}}},
                ], "minimum_should_match": 1}})
            else:
                filter_clauses.append({"match": {"retention_period": {"query": retention_period, "operator": "and"}}})
        if admin_approval_required is not None:
            if admin_approval_required:
                filter_clauses.append({"term": {"admin_approval_required": True}})
            else:
                filter_clauses.append({"bool": {"should": [
                    {"term": {"admin_approval_required": False}},
                    {"bool": {"must_not": {"exists": {"field": "admin_approval_required"}}}},
                ], "minimum_should_match": 1}})
        if has_link is not None:
            if has_link:
                must_clauses.append({"bool": {"should": [
                    {"exists": {"field": "group_link"}},
                    {"exists": {"field": "reconstructed_link"}},
                ], "minimum_should_match": 1}})
            else:
                filter_clauses.append({"bool": {"must_not": [
                    {"exists": {"field": "group_link"}},
                    {"exists": {"field": "reconstructed_link"}},
                ]}})

        if not must_clauses and not filter_clauses:
            must_clauses.append({"match_all": {}})

        # Sort
        sort_map = {
            "members": "number_of_members",
            "name": "group_name.keyword",
        }
        sort_field = sort_map.get(sort_by, "number_of_members")
        sort_clause = [{sort_field: {"order": sort_order}}]

        query_body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "sort": sort_clause,
        }

        hits, total = search_index_with_total(client, "groups", query_body, size=limit, from_=offset)

        results: list[dict[str, Any]] = []
        for source in hits:
            results.append({
                "id": source.get("id"),
                "groupId": source.get("group_id"),
                "groupName": source.get("group_name"),
                "numberOfMembers": source.get("number_of_members"),
                "description": source.get("description"),
                "groupLink": source.get("group_link"),
                "reconstructedLink": source.get("reconstructed_link"),
                "adminApprovalRequired": source.get("admin_approval_required"),
                "firstObserved": source.get("first_observed"),
                "lastObserved": source.get("last_observed"),
            })

        return results, total

    @staticmethod
    def get_group(db: Session, group_id: str) -> dict[str, Any] | None:
        from app.db.schemas.ingestion_models import (
            GroupMetadata,
            GroupMembershipMap,
            UserMetadata,
        )

        if not group_id:
            return None

        group_id = group_id.strip()
        group = None

        logger.info(f"get_group called with id: '{group_id}'")

        # 1. Try Lookup by Primary Key (if numeric)
        if group_id.isdigit():
            try:
                pk_id = int(group_id)
                logger.info(f"Attempting lookup by PK: {pk_id}")
                group = (
                    db.query(GroupMetadata).filter(GroupMetadata.id == pk_id).first()
                )
                if group:
                    logger.info(f"Found group by PK: {group.id}")
            except Exception as e:
                logger.error(f"Error looking up by PK: {e}")

        # 2. Fallback: Lookup by group_id string
        # We do this if NOT found by PK, OR if it wasn't numeric to begin with.
        if not group:
            logger.info(f"Attempting lookup by group_id string: '{group_id}'")
            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.group_id == group_id)
                .first()
            )
            if group:
                logger.info(
                    f"Found group by group_id string: {group.group_id} (PK: {group.id})"
                )

        # 3. Last Resort: Try URL decoding
        if not group:
            from urllib.parse import unquote

            decoded_id = unquote(group_id)
            if decoded_id != group_id:
                logger.info(f"Attempting lookup by decoded group_id: '{decoded_id}'")
                group = (
                    db.query(GroupMetadata)
                    .filter(GroupMetadata.group_id == decoded_id)
                    .first()
                )
                if group:
                    logger.info(f"Found group by decoded ID: {decoded_id}")

        if not group:
            logger.warning(f"Group not found for identifier: '{group_id}'")
            return None

        # Fetch members
        logger.info(f"Fetching members for group PK: {group.id}")
        # GroupMembershipMap.group_id is now INT FK. GroupMembershipMap.user_id is INT FK.
        members_query = (
            db.query(GroupMembershipMap, UserMetadata)
            .join(UserMetadata, GroupMembershipMap.user_id == UserMetadata.id)
            .filter(GroupMembershipMap.group_id == group.id)
            .filter(UserMetadata.is_active != False)  # noqa: E712 - exclude soft-deleted users
            .all()
        )

        members_list = []
        for membership, user in members_query:
            # Fallback name logic: name > profile_name > profile_full_name > profile_family_name > service_id
            display_name = (
                user.name
                or user.profile_name
                or user.profile_full_name
                or user.profile_family_name
            )
            if not display_name:
                display_name = (
                    f"User ({user.service_id[:8]}...)" if user.service_id else "Unknown"
                )
            members_list.append(
                {
                    "serviceId": user.service_id,
                    "name": display_name,
                    "role": membership.role,
                    "profileName": user.profile_name,
                    "profileFullName": user.profile_full_name,
                    "profileFamilyName": user.profile_family_name,
                    "avatarId": user.avatar_id,
                    "e164": user.e164,
                }
            )

        return {
            "id": group.id,  # DB PK
            "groupId": group.group_id,
            "groupName": group.group_name,
            "numberOfMembers": group.number_of_members,
            "description": group.description,
            "groupLink": group.group_link,
            "reconstructedLink": group.reconstructed_link,
            "adminApprovalRequired": group.admin_approval_required,
            "retentionPeriod": group.retention_period,
            "publicParams": group.public_params,
            "masterKey": group.master_key,
            "inviteLinkPassword": group.invite_link_password,
            "secretParams": group.secret_params,
            "reconstructedLink": group.reconstructed_link,
            "members": members_list,
        }

    @staticmethod
    def get_group_history(db: Session, group_identifier: str) -> list[dict[str, Any]]:
        from app.db.schemas.ingestion_models import GroupHistory, GroupMetadata

        # Resolve to group_id if int ID provided
        group_id_str = group_identifier
        if group_identifier and group_identifier.isdigit():
            g = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.id == int(group_identifier))
                .first()
            )
            if g:
                group_id_str = g.group_id

        history = (
            db.query(GroupHistory)
            .filter(GroupHistory.group_id == group_id_str)
            .order_by(GroupHistory.history_date.desc())
            .all()
        )

        results = []
        for h in history:
            results.append(
                {
                    "historyId": h.history_id,
                    "timelineId": h.timeline_id,
                    "historyDate": (
                        int(h.history_date.timestamp()) if h.history_date else None
                    ),
                    "operation": h.history_operation,
                    "previousData": None,
                    "currentData": {
                        "groupId": h.group_id,
                        "groupName": h.group_name,
                        "numberOfMembers": h.number_of_members,
                        "adminApprovalRequired": h.admin_approval_required,
                        "groupLink": h.group_link,
                        "reconstructedLink": h.reconstructed_link,
                        "description": h.description,
                        "retentionPeriod": h.retention_period,
                        "publicParams": h.public_params,
                        "masterKey": h.master_key,
                        "inviteLinkPassword": h.invite_link_password,
                        "secretParams": h.secret_params,
                    },
                }
            )
        return results

    @staticmethod
    def get_group_members_at_timestamp(
        db: Session, group_id_identifier: str, timestamp_s: float
    ) -> list[dict[str, Any]]:
        """
        Fetches the members of a group at a specific point in time.
        """
        from app.db.schemas.ingestion_models import (
            GroupMetadata,
            GroupMembershipHistory,
            UserMetadata,
        )
        from datetime import datetime, timezone

        # 1. Resolve Group PK
        group = None
        if group_id_identifier.isdigit():
            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.id == int(group_id_identifier))
                .first()
            )
        if not group:
            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.group_id == group_id_identifier)
                .first()
            )

        if not group:
            return []

        dt = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)
        logger.info(f"Fetching members for group PK: {group.id} at {dt}")

        # 2. Query Membership History
        # We look for all memberships in this group that were active at 'dt'
        # i.e., valid_from <= dt AND (valid_to is NULL OR valid_to > dt)
        memberships = (
            db.query(GroupMembershipHistory, UserMetadata)
            .join(UserMetadata, GroupMembershipHistory.user_id == UserMetadata.id)
            .filter(GroupMembershipHistory.group_id == group.id)
            .filter(GroupMembershipHistory.valid_from <= dt)
            .filter(
                (GroupMembershipHistory.valid_to.is_(None))
                | (GroupMembershipHistory.valid_to > dt)
            )
            .filter(UserMetadata.is_active != False)  # noqa: E712 - exclude soft-deleted users
            .all()
        )

        results = []
        for membership, user in memberships:
            # Fallback name logic: name > profile_name > profile_full_name > profile_family_name > service_id
            display_name = (
                user.name
                or user.profile_name
                or user.profile_full_name
                or user.profile_family_name
            )
            if not display_name:
                display_name = (
                    f"User ({user.service_id[:8]}...)"
                    if user.service_id
                    else "Unknown User"
                )

            results.append(
                {
                    "serviceId": user.service_id,
                    "name": display_name,
                    "role": membership.role,
                    "profileName": user.profile_name,
                    "avatarId": user.avatar_id,
                    "validFrom": int(membership.valid_from.timestamp()),
                    "validTo": (
                        int(membership.valid_to.timestamp())
                        if membership.valid_to
                        else None
                    ),
                }
            )

        return results

    @staticmethod
    def get_group_timeline(
        db: Session, group_identifier: str, limit: int = 10, offset: int = 0
    ) -> dict:
        """
        Fetches the 'Spine' of the group's history from the Ledger.
        Returns a lightweight list of events (timestamps and change flags) and total count.
        INCLUDES membership diffs (joined, left, role_changed) for each event.
        """
        from app.db.schemas.ingestion_models import (
            GroupMetadata,
            GroupTimelineLedger,
            GroupMembershipHistory,
            UserMetadata,
        )
        from sqlalchemy import or_

        # Resolve Group
        group = None
        if group_identifier.isdigit():
            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.id == int(group_identifier))
                .first()
            )

        if not group:
            group = (
                db.query(GroupMetadata)
                .filter(GroupMetadata.group_id == group_identifier)
                .first()
            )

        if not group:
            return {"items": [], "total": 0}

        # Count total
        total_count = (
            db.query(GroupTimelineLedger)
            .filter(GroupTimelineLedger.group_pk == group.id)
            .count()
        )

        # Fetch Ledger
        ledger = (
            db.query(GroupTimelineLedger)
            .filter(GroupTimelineLedger.group_pk == group.id)
            .order_by(
                GroupTimelineLedger.export_timestamp.desc(),
                GroupTimelineLedger.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        if not ledger:
            return {"items": [], "total": total_count}

        # --- Bulk Fetch Membership Changes ---
        timeline_ids = [entry.id for entry in ledger]

        # Find all membership history records linked to these timeline IDs (either as join or exit)
        membership_changes = (
            db.query(GroupMembershipHistory, UserMetadata)
            .join(UserMetadata, GroupMembershipHistory.user_id == UserMetadata.id)
            .filter(
                or_(
                    GroupMembershipHistory.join_group_timeline_id.in_(timeline_ids),
                    GroupMembershipHistory.exit_group_timeline_id.in_(timeline_ids),
                )
            )
            .all()
        )

        # Organize changes by timeline_id
        # Structure: { timeline_id: { joins: [record], leaves: [record] } }
        changes_map = {tid: {"joins": [], "leaves": []} for tid in timeline_ids}

        for mh, user in membership_changes:
            # Fallback name logic
            display_name = user.name or user.profile_name
            if not display_name:
                display_name = (
                    f"User ({user.service_id[:8]}...)"
                    if user.service_id
                    else "Unknown User"
                )

            # Map User DTO
            user_dto = {
                "serviceId": user.service_id,
                "name": display_name,
                "profileName": user.profile_name,
                "avatarId": user.avatar_id,
                "role": mh.role,
            }

            if mh.join_group_timeline_id in changes_map:
                changes_map[mh.join_group_timeline_id]["joins"].append(
                    {"record": mh, "user": user_dto}
                )

            if mh.exit_group_timeline_id in changes_map:
                changes_map[mh.exit_group_timeline_id]["leaves"].append(
                    {"record": mh, "user": user_dto}
                )

        results = []
        for entry in ledger:
            changes = []
            if entry.has_detail_change:
                changes.append("details")
            if entry.has_membership_change:
                changes.append("membership")

            # Process Membership Diffs for this entry
            entry_changes = changes_map.get(entry.id, {"joins": [], "leaves": []})
            raw_joins = entry_changes["joins"]
            raw_leaves = entry_changes["leaves"]

            final_joins = []
            final_leaves = []
            final_role_changes = []

            # Correlation for Role Changes
            # If a user is in both joins and leaves for this timeline_id, it's a role change.
            # We map leaves by user_id for quick lookup
            leaves_by_user = {item["record"].user_id: item for item in raw_leaves}
            processed_leave_user_ids = set()

            for join_item in raw_joins:
                uid = join_item["record"].user_id
                if uid in leaves_by_user:
                    # Found a role change
                    leave_item = leaves_by_user[uid]
                    final_role_changes.append(
                        {
                            "serviceId": join_item["user"]["serviceId"],
                            "name": join_item["user"]["name"],
                            "avatarId": join_item["user"]["avatarId"],
                            "fromRole": leave_item["record"].role,
                            "toRole": join_item["record"].role,
                        }
                    )
                    processed_leave_user_ids.add(uid)
                else:
                    # Pure Join
                    final_joins.append(join_item["user"])

            # Process remaining leaves
            for leave_item in raw_leaves:
                if leave_item["record"].user_id not in processed_leave_user_ids:
                    final_leaves.append(leave_item["user"])

            results.append(
                {
                    "timelineId": entry.id,
                    "jobId": entry.job_id,
                    "exportTimestamp": entry.export_timestamp.timestamp(),
                    "changes": changes,
                    "hasDetailChange": entry.has_detail_change,
                    "hasMembershipChange": entry.has_membership_change,
                    "membershipDiff": {
                        "joined": final_joins,
                        "left": final_leaves,
                        "roleChanged": final_role_changes,
                    },
                }
            )

        return {"items": results, "total": total_count}

    @staticmethod
    def get_membership_changes(db: Session, timeline_id: int) -> dict[str, Any]:
        from app.db.schemas.ingestion_models import GroupMembershipHistory, UserMetadata

        # 1. Fetch Joiners (where join_group_timeline_id = timeline_id)
        joiners = (
            db.query(GroupMembershipHistory, UserMetadata)
            .join(UserMetadata, GroupMembershipHistory.user_id == UserMetadata.id)
            .filter(GroupMembershipHistory.join_group_timeline_id == timeline_id)
            .all()
        )

        # 2. Fetch Leavers (where exit_group_timeline_id = timeline_id)
        leaver_records = (
            db.query(GroupMembershipHistory, UserMetadata)
            .join(UserMetadata, GroupMembershipHistory.user_id == UserMetadata.id)
            .filter(GroupMembershipHistory.exit_group_timeline_id == timeline_id)
            .all()
        )

        role_changes = []
        joined_list = []
        left_list = []

        processed_leaver_ids = set()
        processed_joiner_user_ids = set()

        # Check for Role Changes:
        for r_join in joiners:
            h_join = r_join.GroupMembershipHistory
            u = r_join.UserMetadata

            # Look for a leaver record for this user in this same timeline entry
            matching_leaver = None
            for r_leave in leaver_records:
                h_leave = r_leave.GroupMembershipHistory
                if h_leave.user_id == h_join.user_id:
                    matching_leaver = r_leave
                    break

            if matching_leaver:
                h_leave = matching_leaver.GroupMembershipHistory
                role_changes.append(
                    {
                        "serviceId": u.service_id,
                        "name": u.name or u.profile_name,
                        "fromRole": h_leave.role,
                        "toRole": h_join.role,
                        "avatarId": u.avatar_id,
                    }
                )
                processed_leaver_ids.add(h_leave.id)
                processed_joiner_user_ids.add(h_join.user_id)

        # Remaining joiners are pure Joins
        for r_join in joiners:
            h_join = r_join.GroupMembershipHistory
            u = r_join.UserMetadata
            if h_join.user_id not in processed_joiner_user_ids:
                display_name = u.name or u.profile_name
                if not display_name:
                    display_name = (
                        f"User ({u.service_id[:8]}...)"
                        if u.service_id
                        else "Unknown User"
                    )

                joined_list.append(
                    {
                        "serviceId": u.service_id,
                        "name": display_name,
                        "role": h_join.role,
                        "avatarId": u.avatar_id,
                    }
                )

        # Remaining leaver_records are pure Leaves
        for r_leave in leaver_records:
            h_leave = r_leave.GroupMembershipHistory
            u = r_leave.UserMetadata
            if h_leave.id not in processed_leaver_ids:
                display_name = u.name or u.profile_name
                if not display_name:
                    display_name = (
                        f"User ({u.service_id[:8]}...)"
                        if u.service_id
                        else "Unknown User"
                    )

                left_list.append(
                    {
                        "serviceId": u.service_id,
                        "name": display_name,
                        "role": h_leave.role,
                        "avatarId": u.avatar_id,
                    }
                )

        return {"joined": joined_list, "left": left_list, "roleChanged": role_changes}

    @staticmethod
    def export_groups_csv(
        db: Session,
        q: str | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        description: str | None = None,
        min_members: int | None = None,
        max_members: int | None = None,
        limit: int = 250,
        offset: int = 0,
        sort_by: str | None = None,
        retention_period: str | None = None,
        admin_approval_required: bool | None = None,
        has_link: bool | None = None,
    ):
        """
        Executes a search and returns a CSV stream of the results.
        """
        import csv
        import io

        # 1. Reuse search logic to get data
        results = GroupController.search_groups(
            db,
            q=q,
            group_id=group_id,
            group_name=group_name,
            description=description,
            min_members=min_members,
            max_members=max_members,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            retention_period=retention_period,
            admin_approval_required=admin_approval_required,
            has_link=has_link,
        )

        # 2. Define CSV Headers
        fieldnames = [
            "Group ID",
            "Group Name",
            "Member Count",
            "Description",
            "Access Type",
            "Has Link",
            "Link",
            "Retention Period",
        ]

        # 3. Create CSV Stream
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for group in results:
            writer.writerow(
                {
                    "Group ID": group.get("groupId", ""),
                    "Group Name": group.get("groupName", ""),
                    "Member Count": group.get("numberOfMembers", 0),
                    "Description": (group.get("description") or "").replace("\n", " ")[
                        :1000
                    ],
                    "Access Type": (
                        "Approval Required"
                        if group.get("adminApprovalRequired")
                        else "Open"
                    ),
                    "Has Link": "Yes" if group.get("groupLink") else "No",
                    "Link": group.get("groupLink", ""),
                    "Retention Period": group.get("retentionPeriod", ""),
                }
            )

        output.seek(0)
        return output

    @staticmethod
    def get_retention_periods(db: Session) -> list[str]:
        global _retention_periods_cache
        import time
        from app.db.schemas.ingestion_models import GroupMetadata

        now = time.time()
        # 1 hour cache = 3600 seconds
        if _retention_periods_cache["data"] and (
            now - _retention_periods_cache["timestamp"] < 3600
        ):
            return _retention_periods_cache["data"]

        logger.info("Fetching distinct retention periods from database")
        # Fetch distinct values from DB
        periods = db.query(GroupMetadata.retention_period).distinct().all()
        # Flatten and filter out None
        data = sorted(list(set(p[0] for p in periods if p[0])))

        _retention_periods_cache["data"] = data
        _retention_periods_cache["timestamp"] = now
        return data
