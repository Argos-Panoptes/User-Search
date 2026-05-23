from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional


class UserController:
    @staticmethod
    def search_users(
        db: Session,
        q: Optional[str] = None,
        service_id: Optional[str] = None,
        name: Optional[str] = None,
        group_name: Optional[str] = None,
        group_id: str | int | None = None,
        username: Optional[str] = None,
        min_group_count: Optional[int] = None,
        max_group_count: Optional[int] = None,
        e164: Optional[str] = None,
        about: Optional[str] = None,
        is_admin: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        has_avatar: Optional[bool] = None,
        sort_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        from app.core.search import get_opensearch_client, search_index
        from dateutil import parser
        import json

        client = get_opensearch_client()

        must_clauses = []
        filter_clauses = []

        if q:
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": q,
                                    "fields": [
                                        "name",
                                        "profile_name",
                                        "about",
                                        "e164",
                                        # "service_id", # Removed from strict text match, moved to wildcard below
                                    ],
                                    "fuzziness": "AUTO",
                                }
                            },
                            {"wildcard": {"service_id": f"*{q}*"}},
                            {"wildcard": {"name": f"*{q}*"}},
                            {"wildcard": {"profile_name": f"*{q}*"}},
                        ]
                    }
                }
            )
        else:
            must_clauses.append({"match_all": {}})

        if service_id:
            must_clauses.append({"wildcard": {"service_id": f"*{service_id}*"}})

        if name:
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"match": {"name": {"query": name, "fuzziness": "AUTO"}}},
                            {"wildcard": {"name": f"*{name}*"}},
                            {
                                "match": {
                                    "profile_name": {"query": name, "fuzziness": "AUTO"}
                                }
                            },
                            {"wildcard": {"profile_name": f"*{name}*"}},
                        ]
                    }
                }
            )

        if group_id:
            # Check if it's already an integer ID (database PK)
            is_numeric = isinstance(group_id, int) or (
                isinstance(group_id, str) and group_id.isdigit()
            )

            if is_numeric:
                resolved_id = int(group_id)
                must_clauses.append({"term": {"group_ids": resolved_id}})
            else:
                # 2-step lookup: Resolve string group_id to integer db id
                group_query = {
                    "query": {"term": {"group_id": group_id}},
                    "_source": ["id"],
                }
                group_hits = search_index(client, "groups", group_query, size=1)

                if group_hits and group_hits[0].get("id"):
                    resolved_id = group_hits[0]["id"]
                    must_clauses.append({"term": {"group_ids": resolved_id}})
                else:
                    # Group not found, so no users can match
                    must_clauses.append({"term": {"group_ids": "__NO_MATCH__"}})

        if about:
            must_clauses.append(
                {"match": {"about": {"query": about, "fuzziness": "AUTO"}}}
            )

        if e164:
            must_clauses.append({"wildcard": {"e164": f"*{e164}*"}})

        if group_name:
            # Optimization: 2-step search (Adult Fix)
            # 1. Find relevant group IDs
            group_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match_phrase_prefix": {"group_name": group_name}},
                            {
                                "match": {
                                    "group_name": {
                                        "query": group_name,
                                        "fuzziness": "AUTO",
                                    }
                                }
                            },
                        ]
                    }
                },
                "_source": ["id"],
            }
            # Search a max of 200 relevant groups to be inclusive
            group_hits_raw = search_index(client, "groups", group_query, size=200)

            # Extract integer IDs (filtering out Nones)
            found_ids = [h["id"] for h in group_hits_raw if h.get("id")]

            if found_ids:
                must_clauses.append({"terms": {"group_ids": found_ids}})
            else:
                # No groups matched, so no users can match
                must_clauses.append({"term": {"group_ids": "__NO_MATCH__"}})

        if username:
            must_clauses.append({"wildcard": {"username": f"*{username}*"}})

        if min_group_count is not None:
            filter_clauses.append({"range": {"group_count": {"gte": min_group_count}}})

        if max_group_count is not None:
            filter_clauses.append({"range": {"group_count": {"lte": max_group_count}}})

        if is_admin is not None:
            filter_clauses.append({"term": {"is_admin": is_admin}})

        if has_phone is not None:
            if has_phone:
                filter_clauses.append({"exists": {"field": "e164"}})
            else:
                filter_clauses.append(
                    {"bool": {"must_not": {"exists": {"field": "e164"}}}}
                )

        if has_avatar is not None:
            filter_clauses.append({"term": {"has_avatar": has_avatar}})

        # Exclude soft-deleted users (must_not handles docs missing the field)
        filter_clauses.append({"bool": {"must_not": {"term": {"is_active": False}}}})

        sort_map = {
            "name_asc":    [{"name.keyword": {"order": "asc",  "missing": "_last"}}, {"profile_name.keyword": {"order": "asc",  "missing": "_last"}}],
            "name_desc":   [{"name.keyword": {"order": "desc", "missing": "_last"}}, {"profile_name.keyword": {"order": "desc", "missing": "_last"}}],
            "newest":      [{"last_observed": {"order": "desc", "missing": "_last"}}],
            "oldest":      [{"last_observed": {"order": "asc",  "missing": "_last"}}],
            "most_groups": [{"group_count": {"order": "desc"}}],
        }
        resolved_sort = sort_map.get(sort_by) if sort_by else None
        default_sort = [
            {"group_count": {"order": "desc"}},
            {"admin_group_count": {"order": "desc"}},
            {"has_avatar": {"order": "desc"}},
            {"has_description": {"order": "desc"}},
            "_score",
        ]

        query_body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "sort": resolved_sort if resolved_sort else default_sort,
        }

        # Execute search
        hits = search_index(client, "users", query_body, size=limit, from_=offset)

        # Map to DTO structure
        results = []
        for source in hits:
            # Handle export_timestamp conversion (ISO string -> int timestamp)
            ts_val = source.get("export_timestamp")
            timestamp_int = 0
            if ts_val:
                try:
                    if isinstance(ts_val, (int, float)):
                        timestamp_int = int(ts_val)
                    else:
                        dt = parser.parse(str(ts_val))
                        timestamp_int = int(dt.timestamp())
                except Exception:
                    pass

            # Helper to safely serialize groups if they are objects (which they should be now)
            # Frontend expects strings (JSON.parse), or we can update frontend to expect objects.
            # Plan said "Remove JSON.parse for groupMemberships (as it will be an object)".
            # So here we should return the list of objects directly.

            group_memberships = source.get("group_memberships", [])
            # If for some reason it's still a string (old data?), parse it.
            if isinstance(group_memberships, str):
                try:
                    group_memberships = json.loads(group_memberships)
                except Exception:
                    group_memberships = []

            results.append(
                {
                    "serviceId": source.get("service_id"),
                    "e164": source.get("e164"),
                    "profileName": (
                        source.get("name")
                        or source.get("profile_name")
                        or source.get("profile_full_name")
                        or source.get("profile_family_name")
                    ),
                    "name": source.get("name"),
                    "profileFullName": source.get("profile_full_name"),
                    "profileFamilyName": source.get("profile_family_name"),
                    "username": source.get("username"),
                    "about": source.get("about"),
                    "isAdmin": source.get("is_admin"),
                    "exportTimestamp": timestamp_int,
                    "remoteAvatarUrl": source.get("remote_avatar_url"),
                    "avatarId": source.get("avatar_id"),
                    "groupMemberships": group_memberships,
                    "groupCount": source.get("group_count", 0),
                    "adminGroupCount": source.get("admin_group_count", 0),
                    "id": source.get("user_id"),  # DB ID for key lookups
                    "firstObserved": source.get("first_observed"),
                    "lastObserved": source.get("last_observed"),
                }
            )

        return results

    @staticmethod
    def get_user(db: Session, service_id: str) -> Optional[dict]:
        from app.db.schemas.ingestion_models import (
            UserMetadata,
            GroupMembershipMap,
            GroupMetadata,
        )

        user = None
        # Check if identifier is an integer ID or UUID string
        print("service_id, service_id.isdigit():", service_id, service_id.isdigit())
        if service_id and service_id.isdigit():
            user = db.query(UserMetadata).filter(UserMetadata.id == service_id).first()
            print("user by id:", user)

        # Fallback: try searching by service_id if not found by ID (or wasn't digits)
        if not user:
            user = (
                db.query(UserMetadata)
                .filter(UserMetadata.service_id == service_id)
                .first()
            )

        if not user:
            return None

        # Check if user is soft-deleted
        if hasattr(user, "is_active") and user.is_active is False:
            return None

        # Manually map to DTO structure
        # Convert timestamp
        ts_val = user.export_timestamp
        timestamp_int = 0
        if ts_val:
            try:
                timestamp_int = int(ts_val.timestamp())
            except Exception:
                pass

        # Fetch detailed group memberships from DB join
        # Join GroupMembershipMap -> GroupMetadata (via ids now)
        memberships_db = (
            db.query(
                GroupMetadata.id,
                GroupMetadata.group_id,
                GroupMetadata.group_name,
                GroupMetadata.description,
                GroupMetadata.number_of_members,
                GroupMembershipMap.role,
            )
            .join(GroupMembershipMap, GroupMetadata.id == GroupMembershipMap.group_id)
            .filter(GroupMembershipMap.user_id == user.id)
            .all()
        )

        group_memberships = []
        if memberships_db:
            for grp in memberships_db:
                group_memberships.append(
                    {
                        "id": grp.id,
                        "groupId": grp.group_id,
                        "groupName": grp.group_name,
                        "title": grp.group_name,  # Fallback/Duplicate for UI
                        "description": grp.description,
                        "memberCount": grp.number_of_members,
                        "role": grp.role,
                    }
                )
        else:
            # Fallback to JSON column if DB map is empty/not synced
            # Handle compressed binary or text JSON
            raw_memberships = user.group_memberships
            if raw_memberships:
                import zlib
                import json

                try:
                    if isinstance(raw_memberships, (bytes, memoryview)):
                        decompressed = zlib.decompress(raw_memberships)
                        group_memberships = json.loads(decompressed)
                    elif isinstance(raw_memberships, str):
                        group_memberships = json.loads(raw_memberships)
                except Exception:
                    pass

        return {
            "id": user.id,  # Include PK
            "serviceId": user.service_id,
            "e164": user.e164,
            "profileName": (
                user.name
                or user.profile_name
                or user.profile_full_name
                or user.profile_family_name
            ),
            "name": user.name,
            "profileFamilyName": user.profile_family_name,
            "profileFullName": user.profile_full_name,
            "about": user.about,
            "isAdmin": user.is_admin,
            "avatarId": user.avatar_id,
            "remoteAvatarUrl": user.remote_avatar_url,
            "exportTimestamp": timestamp_int,
            "activeAt": user.active_at,
            "groupMemberships": group_memberships,
            "capabilities": user.capabilities,
            # Technical Details
            "lastUpdatedJobId": (
                str(user.last_updated_job_id)
                if user.last_updated_job_id is not None
                else None
            ),
            "snapshotHash": (
                user.snapshot_hash.hex()
                if user.snapshot_hash and isinstance(user.snapshot_hash, bytes)
                else str(user.snapshot_hash) if user.snapshot_hash else None
            ),
            "profileLastFetchedAt": user.profile_last_fetched_at,
        }

    @staticmethod
    def get_user_timeline(
        db: Session, user_identifier: str, limit: int = 10, offset: int = 0
    ) -> dict:
        """
        Fetches the 'Spine' of the user's history from the Ledger.
        Returns a lightweight list of events (timestamps and change flags) and total count.
        """
        from app.db.schemas.ingestion_models import UserMetadata, UserTimelineLedger
        from sqlalchemy import String

        # Resolve User
        user = (
            db.query(UserMetadata)
            .filter(
                or_(
                    UserMetadata.id.cast(String) == user_identifier,
                    UserMetadata.service_id == user_identifier,
                )
            )
            .first()
        )
        if not user:
            return {"items": [], "total": 0}

        # Count total
        total_count = (
            db.query(UserTimelineLedger)
            .filter(UserTimelineLedger.service_id == user.service_id)
            .count()
        )

        # Fetch Ledger
        ledger = (
            db.query(UserTimelineLedger)
            .filter(UserTimelineLedger.service_id == user.service_id)
            .order_by(
                UserTimelineLedger.export_timestamp.desc(), UserTimelineLedger.id.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        results = []
        for entry in ledger:
            changes = []
            if entry.has_profile_change:
                changes.append("profile")
            if entry.has_membership_change:
                changes.append("membership")
            if entry.has_avatar_change:
                changes.append("avatar")

            results.append(
                {
                    "timelineId": entry.id,
                    "jobId": entry.job_id,
                    "exportTimestamp": int(entry.export_timestamp.timestamp()),
                    "changes": changes,
                    "hasProfileChange": entry.has_profile_change,
                    "hasMembershipChange": entry.has_membership_change,
                    "hasAvatarChange": entry.has_avatar_change,
                }
            )

        return {"items": results, "total": total_count}

    @staticmethod
    def get_profile_history(db: Session, user_identifier: str) -> List[dict]:
        """
        Fetches all Profile History snapshots for the user.
        """
        from app.db.schemas.ingestion_models import UserMetadata, UserHistory
        from sqlalchemy import String

        user = (
            db.query(UserMetadata)
            .filter(
                or_(
                    UserMetadata.id.cast(String) == user_identifier,
                    UserMetadata.service_id == user_identifier,
                )
            )
            .first()
        )
        if not user:
            return []

        history = (
            db.query(UserHistory)
            .filter(UserHistory.service_id == user.service_id)
            .order_by(UserHistory.history_date.desc())
            .all()
        )

        results = []
        # Reuse helper columns logic if dynamic, but manual mapping is explicit/safe
        for h in history:
            results.append(
                {
                    "historyId": h.history_id,
                    "timelineId": h.timeline_id,
                    "historyDate": int(h.history_date.timestamp()),
                    "exportTimestamp": (
                        int(h.export_timestamp.timestamp())
                        if h.export_timestamp
                        else None
                    ),
                    "serviceId": h.service_id,
                    "profileName": h.profile_name,
                    "name": h.name,
                    "profileFamilyName": h.profile_family_name,
                    "profileFullName": h.profile_full_name,
                    "e164": h.e164,
                    "about": h.about,
                    "aboutEmoji": h.about_emoji,
                    "remoteAvatarUrl": h.remote_avatar_url,
                    "isAdmin": h.is_admin,
                    "capabilities": h.capabilities,
                    "activeAt": h.active_at,
                    "avatarId": h.avatar_id,
                    "snapshotHash": h.snapshot_hash.hex() if h.snapshot_hash else None,
                    # Technical / Extra Details
                    "profileLastFetchedAt": h.profile_last_fetched_at,
                    "lastUpdatedJobId": h.last_updated_job_id,
                }
            )
        return results

    @staticmethod
    def get_membership_history(db: Session, user_identifier: str) -> List[dict]:
        """
        Fetches the raw SCD2 Membership History intervals.
        """
        from app.db.schemas.ingestion_models import (
            UserMetadata,
            GroupMembershipHistory,
            GroupMetadata,
        )
        from sqlalchemy import String

        user = (
            db.query(UserMetadata)
            .filter(
                or_(
                    UserMetadata.id.cast(String) == user_identifier,
                    UserMetadata.service_id == user_identifier,
                )
            )
            .first()
        )
        if not user:
            return []

        # Join with Group for names
        history = (
            db.query(
                GroupMembershipHistory,
                GroupMetadata.group_name,
                GroupMetadata.group_id.label("external_group_id"),
            )
            .join(GroupMetadata, GroupMembershipHistory.group_id == GroupMetadata.id)
            .filter(GroupMembershipHistory.user_id == user.id)
            .order_by(GroupMembershipHistory.valid_from.desc())
            .all()
        )

        results = []
        for mh, g_name, g_ext_id in history:
            results.append(
                {
                    "id": mh.id,
                    "groupId": g_ext_id,
                    "groupName": g_name,
                    "role": mh.role,
                    "validFrom": (
                        int(mh.valid_from.timestamp()) if mh.valid_from else None
                    ),
                    "validTo": int(mh.valid_to.timestamp()) if mh.valid_to else None,
                    "timelineId": mh.join_timeline_id,
                    "jobId": mh.job_id,
                }
            )
        return results

    @staticmethod
    def get_user_memberships_at_timestamp(
        db: Session, service_id: str, timestamp_s: float
    ) -> dict:
        """
        Fetches memberships active at a specific unix timestamp (seconds).
        Used to augment historical snapshots on request.
        """
        from app.db.schemas.ingestion_models import (
            UserMetadata,
            GroupMembershipHistory,
            GroupMetadata,
        )
        from datetime import datetime, timezone

        user = (
            db.query(UserMetadata).filter(UserMetadata.service_id == service_id).first()
        )
        if not user:
            return {"groupMemberships": [], "adminGroups": []}

        ts = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)

        # Fetch membership spells active at this time
        spells = (
            db.query(
                GroupMembershipHistory.role,
                GroupMetadata.group_name,
                GroupMetadata.group_id.label("external_group_id"),
            )
            .join(GroupMetadata, GroupMembershipHistory.group_id == GroupMetadata.id)
            .filter(
                GroupMembershipHistory.user_id == user.id,
                GroupMembershipHistory.valid_from <= ts,
                or_(
                    GroupMembershipHistory.valid_to == None,
                    GroupMembershipHistory.valid_to > ts,
                ),
            )
            .all()
        )

        memberships = []
        admin_groups = []
        for s in spells:
            memberships.append(
                {
                    "groupId": s.external_group_id,
                    "groupName": s.group_name,
                    "role": s.role,
                }
            )
            if s.role == "admin":
                admin_groups.append(s.group_name)

        return {
            "groupMemberships": sorted(memberships, key=lambda x: x["groupId"]),
            "adminGroups": admin_groups,
        }

    @staticmethod
    def get_membership_changes(db: Session, timeline_id: int) -> dict:
        from app.db.schemas.ingestion_models import (
            GroupMembershipHistory,
            GroupMetadata,
        )

        # 1. Fetch Joins (where join_timeline_id = timeline_id)
        joins = (
            db.query(GroupMembershipHistory, GroupMetadata)
            .join(GroupMetadata, GroupMembershipHistory.group_id == GroupMetadata.id)
            .filter(GroupMembershipHistory.join_timeline_id == timeline_id)
            .all()
        )

        # 2. Fetch Leaves (where exit_timeline_id = timeline_id)
        leaves = (
            db.query(GroupMembershipHistory, GroupMetadata)
            .join(GroupMetadata, GroupMembershipHistory.group_id == GroupMetadata.id)
            .filter(GroupMembershipHistory.exit_timeline_id == timeline_id)
            .all()
        )

        role_changes = []
        pure_joins = []
        pure_leaves = []

        processed_leave_ids = set()
        processed_join_group_ids = set()

        # Correlation logic
        for j_rec in joins:
            h_join = j_rec.GroupMembershipHistory
            g = j_rec.GroupMetadata

            matching_leave = None
            for l_rec in leaves:
                h_leave = l_rec.GroupMembershipHistory
                if h_leave.group_id == h_join.group_id:
                    matching_leave = l_rec
                    break

            if matching_leave:
                h_leave = matching_leave.GroupMembershipHistory
                role_changes.append(
                    {
                        "groupId": g.group_id,
                        "groupName": g.group_name,
                        "fromRole": h_leave.role,
                        "toRole": h_join.role,
                    }
                )
                processed_leave_ids.add(h_leave.id)
                processed_join_group_ids.add(h_join.group_id)

        for j_rec in joins:
            h_join = j_rec.GroupMembershipHistory
            if h_join.group_id not in processed_join_group_ids:
                pure_joins.append(
                    {
                        "groupId": j_rec.GroupMetadata.group_id,
                        "groupName": j_rec.GroupMetadata.group_name,
                        "role": h_join.role,
                    }
                )

        for l_rec in leaves:
            h_leave = l_rec.GroupMembershipHistory
            if h_leave.id not in processed_leave_ids:
                pure_leaves.append(
                    {
                        "groupId": l_rec.GroupMetadata.group_id,
                        "groupName": l_rec.GroupMetadata.group_name,
                        "role": h_leave.role,
                    }
                )

        return {"joined": pure_joins, "left": pure_leaves, "roleChanged": role_changes}

    @staticmethod
    def search_users_paginated(
        db: Session,
        q: Optional[str] = None,
        service_id: Optional[str] = None,
        name: Optional[str] = None,
        group_name: Optional[str] = None,
        group_id: str | int | None = None,
        username: Optional[str] = None,
        min_group_count: Optional[int] = None,
        max_group_count: Optional[int] = None,
        e164: Optional[str] = None,
        about: Optional[str] = None,
        is_admin: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        has_avatar: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> tuple[List[dict], int]:
        """
        Search users with total count for pagination meta.
        Returns (results, total_count).
        """
        from app.core.search import get_opensearch_client, search_index_with_total
        from dateutil import parser
        import json

        client = get_opensearch_client()

        must_clauses = []
        filter_clauses = []

        if q:
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": q,
                                    "fields": ["name", "profile_name", "about", "e164"],
                                    "fuzziness": "AUTO",
                                }
                            },
                            {"wildcard": {"service_id": f"*{q}*"}},
                            {"wildcard": {"name": f"*{q}*"}},
                            {"wildcard": {"profile_name": f"*{q}*"}},
                        ]
                    }
                }
            )
        else:
            must_clauses.append({"match_all": {}})

        if service_id:
            must_clauses.append({"wildcard": {"service_id": f"*{service_id}*"}})
        if name:
            must_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"match": {"name": {"query": name, "fuzziness": "AUTO"}}},
                            {"wildcard": {"name": f"*{name}*"}},
                            {"match": {"profile_name": {"query": name, "fuzziness": "AUTO"}}},
                            {"wildcard": {"profile_name": f"*{name}*"}},
                        ]
                    }
                }
            )
        if e164:
            must_clauses.append({"wildcard": {"e164": f"*{e164}*"}})
        if about:
            must_clauses.append({"match": {"about": {"query": about, "fuzziness": "AUTO"}}})
        if group_id:
            from app.core.search import search_index
            is_numeric = isinstance(group_id, int) or (isinstance(group_id, str) and group_id.isdigit())
            if is_numeric:
                must_clauses.append({"term": {"group_ids": int(group_id)}})
            else:
                group_query = {"query": {"term": {"group_id": group_id}}, "_source": ["id"]}
                group_hits = search_index(client, "groups", group_query, size=1)
                resolved = group_hits[0].get("id") if group_hits else None
                must_clauses.append({"term": {"group_ids": resolved or "__NO_MATCH__"}})
        if group_name:
            from app.core.search import search_index
            gq = {"query": {"bool": {"should": [
                {"match_phrase_prefix": {"group_name": group_name}},
                {"match": {"group_name": {"query": group_name, "fuzziness": "AUTO"}}},
            ]}}, "_source": ["id"]}
            ghr = search_index(client, "groups", gq, size=200)
            found = [h["id"] for h in ghr if h.get("id")]
            must_clauses.append({"terms": {"group_ids": found}} if found else {"term": {"group_ids": "__NO_MATCH__"}})
        if is_admin is not None:
            filter_clauses.append({"term": {"is_admin": is_admin}})
        if has_phone is not None:
            if has_phone:
                filter_clauses.append({"exists": {"field": "e164"}})
            else:
                filter_clauses.append({"bool": {"must_not": {"exists": {"field": "e164"}}}})
        if has_avatar is not None:
            filter_clauses.append({"term": {"has_avatar": has_avatar}})
        if min_group_count is not None:
            filter_clauses.append({"range": {"group_count": {"gte": min_group_count}}})
        if max_group_count is not None:
            filter_clauses.append({"range": {"group_count": {"lte": max_group_count}}})

        # Exclude soft-deleted users
        filter_clauses.append({"bool": {"must_not": {"term": {"is_active": False}}}})

        # Sort
        sort_mapping = {
            "name": "name.keyword" if sort_by == "name" else "name",
            "last_observed": "last_observed",
            "first_observed": "first_observed",
            "group_count": "group_count",
        }
        sort_field = sort_mapping.get(sort_by, "group_count")
        sort_clause = [{sort_field: {"order": sort_order}}, "_score"]

        query_body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "sort": sort_clause,
        }

        hits, total = search_index_with_total(client, "users", query_body, size=limit, from_=offset)

        results = []
        for source in hits:
            ts_val = source.get("export_timestamp")
            timestamp_int = 0
            if ts_val:
                try:
                    if isinstance(ts_val, (int, float)):
                        timestamp_int = int(ts_val)
                    else:
                        dt = parser.parse(str(ts_val))
                        timestamp_int = int(dt.timestamp())
                except Exception:
                    pass

            group_memberships = source.get("group_memberships", [])
            if isinstance(group_memberships, str):
                try:
                    group_memberships = json.loads(group_memberships)
                except Exception:
                    group_memberships = []

            results.append({
                "serviceId": source.get("service_id"),
                "e164": source.get("e164"),
                "profileName": (
                    source.get("name") or source.get("profile_name")
                    or source.get("profile_full_name") or source.get("profile_family_name")
                ),
                "name": source.get("name"),
                "profileFullName": source.get("profile_full_name"),
                "profileFamilyName": source.get("profile_family_name"),
                "username": source.get("username"),
                "about": source.get("about"),
                "isAdmin": source.get("is_admin"),
                "exportTimestamp": timestamp_int,
                "remoteAvatarUrl": source.get("remote_avatar_url"),
                "avatarId": source.get("avatar_id"),
                "groupMemberships": group_memberships,
                "groupCount": source.get("group_count", 0),
                "adminGroupCount": source.get("admin_group_count", 0),
                "id": source.get("user_id"),
                "firstObserved": source.get("first_observed"),
                "lastObserved": source.get("last_observed"),
            })

        return results, total

    @staticmethod
    def export_users_csv(
        db: Session,
        q: Optional[str] = None,
        service_id: Optional[str] = None,
        name: Optional[str] = None,
        group_name: Optional[str] = None,
        username: Optional[str] = None,
        min_group_count: Optional[int] = None,
        max_group_count: Optional[int] = None,
        e164: Optional[str] = None,
        about: Optional[str] = None,
        is_admin: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        has_avatar: Optional[bool] = None,
        limit: int = 250,
        offset: int = 0,
    ):
        """
        Executes a search and returns a CSV stream of the results.
        """
        import csv
        import io

        # 1. Reuse search logic to get data
        results = UserController.search_users(
            db=db,
            q=q,
            service_id=service_id,
            name=name,
            group_name=group_name,
            username=username,
            min_group_count=min_group_count,
            max_group_count=max_group_count,
            e164=e164,
            about=about,
            is_admin=is_admin,
            has_phone=has_phone,
            has_avatar=has_avatar,
            limit=limit,
            offset=offset,
        )

        # 2. Define CSV Headers
        fieldnames = [
            "Service ID",
            "Profile Name",
            "Name",
            "Profile Full Name",
            "Username",
            "Phone",
            "Is Admin",
            "Group Count",
            "Admin Group Count",
            "About",
            "Groups",
            "Export Timestamp",
            "Avatar URL",
        ]

        # 3. Create CSV Stream
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for user in results:
            # Format Groups: "Group A (Member); Group B (Admin)"
            groups_str = ""
            if user.get("groupMemberships"):
                groups_formatted = []
                for g in user.get("groupMemberships"):
                    g_name = (
                        g.get("groupName")
                        or g.get("title")
                        or g.get("name")
                        or "Unknown"
                    )
                    role = g.get("role") or "Member"
                    groups_formatted.append(f"{g_name} ({role})")
                groups_str = "; ".join(groups_formatted)

            writer.writerow(
                {
                    "Service ID": user.get("serviceId", ""),
                    "Profile Name": user.get("profileName", ""),
                    "Name": user.get("name", ""),
                    "Profile Full Name": user.get("profileFullName", ""),
                    "Username": user.get("username", ""),
                    "Phone": user.get("e164", ""),
                    "Is Admin": "Yes" if user.get("isAdmin") else "No",
                    "Group Count": user.get("groupCount", 0),
                    "Admin Group Count": user.get("adminGroupCount", 0),
                    "About": (user.get("about") or "").replace("\n", " ")[:1000],
                    "Groups": groups_str,
                    "Export Timestamp": user.get("exportTimestamp", ""),
                    "Avatar URL": user.get("remoteAvatarUrl", ""),
                }
            )

        output.seek(0)
        return output
