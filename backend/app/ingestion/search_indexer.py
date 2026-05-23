from sqlalchemy import text
from app.db.session import engine
from app.core.search import get_opensearch_client, create_index_if_not_exists
from app.core.logging import logger
from app.controllers.jobs_controller import JobsController
from typing import Callable, Any, Sequence
from opensearchpy import helpers, OpenSearch

# Index Names
INDEX_USERS = "users"
INDEX_GROUPS = "groups"


def index_users_from_db(
    job_id: int,
    log_func: Callable[[str], None] | None = None,
    update_progress: Callable[[float], None] | None = None,
) -> int:
    """
    Fetches users from the DB and indexes them into OpenSearch.
    """
    log = log_func if log_func else logger.info
    client = get_opensearch_client()

    # Ensure index exists with updated mapping
    mapping = {
        "properties": {
            "name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "profile_full_name": {"type": "text"},
            "about": {"type": "text"},
            "e164": {"type": "keyword"},
            "service_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "group_ids": {"type": "integer"},
            "last_updated_job_id": {"type": "integer"},
            "group_memberships": {
                "type": "object",
                "enabled": False,
            },
            "group_count": {"type": "integer"},
            "admin_group_count": {"type": "integer"},
            "has_avatar": {"type": "boolean"},
            "avatar_id": {"type": "integer", "index": False, "doc_values": False},
            "has_description": {"type": "boolean"},
            "is_admin": {"type": "boolean"},
            "is_active": {"type": "boolean"},
            # New metadata fields (index: false)
            "profile_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "profile_family_name": {
                "type": "keyword",
                "index": False,
                "doc_values": False,
            },
            "active_at": {"type": "long", "index": False, "doc_values": False},
            "profile_last_fetched_at": {
                "type": "long",
                "index": False,
                "doc_values": False,
            },
            "about_emoji": {"type": "keyword", "index": False, "doc_values": False},
            "remote_avatar_url": {
                "type": "keyword",
                "index": False,
                "doc_values": False,
            },
            "sharing_phone_number": {
                "type": "boolean",
                "index": False,
                "doc_values": False,
            },
            "verified": {"type": "keyword", "index": False, "doc_values": False},
            "color": {"type": "keyword", "index": False, "doc_values": False},
            "export_timestamp": {"type": "date", "index": False, "doc_values": False},
            "snapshot_hash": {"type": "keyword", "index": False, "doc_values": False},
            "first_observed": {"type": "date", "index": False},
            "last_observed": {"type": "date", "index": False},
        }
    }

    if not client.indices.exists(index=INDEX_USERS):
        create_index_if_not_exists(client, INDEX_USERS, mapping)
    else:
        # Push any mapping additions (adding keyword sub-fields, etc.)
        # Note: doc_values changes require a full index recreation
        try:
            client.indices.put_mapping(index=INDEX_USERS, body={"properties": mapping["properties"]})
        except Exception as e:
            log(f"Warning: could not update mapping: {e}")

    # optimization: set refresh_interval to -1
    client.indices.put_settings(
        index=INDEX_USERS, body={"index": {"refresh_interval": "-1"}}
    )

    # Simple offset-based pagination
    # Keyset pagination optimized
    BATCH_SIZE = 5000
    last_id = 0
    total_indexed = 0

    # Fetch group mapping logic removed...

    try:
        with engine.connect() as conn:
            # Get total count for progress (exclude soft-deleted users)
            count_query = "SELECT COUNT(*) FROM user_metadata WHERE (is_active IS NULL OR is_active = TRUE)"
            if job_id:
                count_query = f"SELECT COUNT(*) FROM user_metadata WHERE last_updated_job_id = {job_id} AND (is_active IS NULL OR is_active = TRUE)"

            count_res = conn.execute(text(count_query))
            total_count = int(count_res.scalar() or 0)
            log(f"Found {total_count} users to index (Job {job_id}).")

            while True:
                # We use a subquery for the base user selection to handle pagination efficiently,
                # then join with memberships for the current batch.
                # Keyset pagination requires ORDER BY id
                base_where = (
                    f"WHERE last_updated_job_id = {job_id} AND (is_active IS NULL OR is_active = TRUE)"
                    if job_id
                    else "WHERE (is_active IS NULL OR is_active = TRUE)"
                )
                where_clause = base_where
                sql_str = text(
                    f"""
                    WITH batch AS (
                        SELECT * FROM user_metadata
                        {where_clause}
                        AND id > {last_id}
                        ORDER BY id ASC
                        LIMIT {BATCH_SIZE}
                    )
                    SELECT
                        u.*,
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'id', g.id,
                                    'group_id', g.group_id,
                                    'groupName', g.group_name,
                                    'role', m.role
                                )
                            )
                            FROM group_memberships_map m
                            JOIN groups g ON m.group_id = g.id
                            WHERE m.user_id = u.id
                        ) as memberships_json,
                        tl.first_observed,
                        tl.last_observed
                    FROM batch u
                    LEFT JOIN LATERAL (
                        SELECT MIN(export_timestamp) as first_observed,
                               MAX(export_timestamp) as last_observed
                        FROM user_timeline_ledger
                        WHERE service_id = u.service_id
                    ) tl ON true
                """
                )

                result = conn.execute(sql_str)
                rows = result.mappings().all()

                if not rows:
                    break

                _bulk_index_users(client, rows, log)
                total_indexed += len(rows)

                # Sync first_observed/last_observed back to user_metadata
                _sync_user_observed_dates(conn, rows)

                # Update cursor
                last_id = rows[-1]["id"]
                log(f"Indexed {total_indexed}/{total_count} users...")
                if update_progress:
                    update_progress(total_indexed / (total_count or 0) * 100)
                if total_indexed >= total_count and total_count > 0:
                    break
                if len(rows) < BATCH_SIZE:
                    break
    finally:
        # Restore refresh_interval
        client.indices.put_settings(
            index=INDEX_USERS, body={"index": {"refresh_interval": "1s"}}
        )
        client.indices.refresh(index=INDEX_USERS)

    return total_indexed


def _sync_user_observed_dates(conn: Any, rows: Sequence[Any]) -> None:
    """Sync computed first_observed/last_observed from timeline ledger back to user_metadata."""
    updates = []
    for row in rows:
        row_dict = dict(row)
        first_obs = row_dict.get("first_observed")
        last_obs = row_dict.get("last_observed")
        uid = row_dict.get("id")
        if uid and (first_obs or last_obs):
            updates.append({"uid": uid, "first_obs": first_obs, "last_obs": last_obs})

    if not updates:
        return

    # Batch update using a single statement with CASE expressions
    ids = [u["uid"] for u in updates]
    id_list = ",".join(str(i) for i in ids)

    first_cases = []
    last_cases = []
    for u in updates:
        if u["first_obs"]:
            first_cases.append(f"WHEN {u['uid']} THEN '{u['first_obs'].isoformat()}'::timestamptz")
        if u["last_obs"]:
            last_cases.append(f"WHEN {u['uid']} THEN '{u['last_obs'].isoformat()}'::timestamptz")

    set_clauses = []
    if first_cases:
        set_clauses.append(f"first_observed = CASE id {' '.join(first_cases)} ELSE first_observed END")
    if last_cases:
        set_clauses.append(f"last_observed = CASE id {' '.join(last_cases)} ELSE last_observed END")

    if set_clauses:
        sql = text(f"UPDATE user_metadata SET {', '.join(set_clauses)} WHERE id IN ({id_list})")
        conn.execute(sql)
        conn.commit()


def _bulk_index_users(
    client: OpenSearch, rows: Sequence[Any], log: Callable[[str], None]
) -> None:
    actions = []
    for row in rows:
        row_dict = dict(row)

        # --- Transform Fields for Search (Explicit Selection) ---

        # 1. Memberships from JSON aggregation
        all_memberships = row_dict.get("memberships_json") or []

        # Populate group_ids (DB IDs for filtering)
        group_ids = [g["id"] for g in all_memberships if g.get("id")]

        # Re-derive admin count from ALL memberships
        admin_count = sum(1 for g in all_memberships if g.get("role") == "admin")

        export_ts = row_dict.get("export_timestamp")
        snapshot_h = row_dict.get("snapshot_hash")
        first_obs = row_dict.get("first_observed")
        last_obs = row_dict.get("last_observed")

        # Explicitly select fields matching the mapping
        doc = {
            "name": row_dict.get("name"),
            "profile_full_name": row_dict.get("profile_full_name"),
            "about": row_dict.get("about"),
            "e164": row_dict.get("e164"),
            "service_id": row_dict.get("service_id"),
            "user_id": row_dict.get("id"),
            "group_ids": group_ids,
            "last_updated_job_id": row_dict.get("last_updated_job_id"),
            "group_memberships": all_memberships[:5],
            "group_count": len(all_memberships),
            "admin_group_count": admin_count,
            "has_avatar": bool(row_dict.get("avatar_id")),
            "avatar_id": row_dict.get("avatar_id"),
            "has_description": bool(row_dict.get("about")),
            "is_admin": row_dict.get("is_admin"),
            "is_active": row_dict.get("is_active", True),
            # New metadata fields
            "profile_name": row_dict.get("profile_name"),
            "profile_family_name": row_dict.get("profile_family_name"),
            "active_at": row_dict.get("active_at"),
            "profile_last_fetched_at": row_dict.get("profile_last_fetched_at"),
            "about_emoji": row_dict.get("about_emoji"),
            "remote_avatar_url": row_dict.get("remote_avatar_url"),
            "sharing_phone_number": row_dict.get("sharing_phone_number"),
            "verified": row_dict.get("verified"),
            "color": row_dict.get("color"),
            "export_timestamp": export_ts.isoformat() if export_ts else None,
            "snapshot_hash": snapshot_h.hex() if snapshot_h else None,
            "first_observed": first_obs.isoformat() if first_obs else None,
            "last_observed": last_obs.isoformat() if last_obs else None,
        }

        action = {
            "_index": INDEX_USERS,
            "_id": str(doc.get("service_id")),
            "_source": doc,
        }
        actions.append(action)

    if actions:
        try:
            helpers.bulk(client, actions)
        except Exception as e:
            log(f"Bulk indexing failed: {e}")


def index_users_by_ids(
    ids: list[str], log_func: Callable[[str], None] | None = None
) -> int:
    """
    Re-indexes specific users by service_id.
    """
    if not ids:
        return 0

    log = log_func if log_func else logger.info
    client = get_opensearch_client()
    # Fetch group mapping logic removed...

    # Chunk IDs to avoid query limit
    chunk_size = 500
    total_indexed = 0

    with engine.connect() as conn:
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]

            sql = text(
                """
                SELECT
                    u.*,
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', g.id,
                                'group_id', g.group_id,
                                'groupName', g.group_name,
                                'role', m.role
                            )
                        )
                        FROM group_memberships_map m
                        JOIN groups g ON m.group_id = g.id
                        WHERE m.user_id = u.id
                    ) as memberships_json,
                    tl.first_observed,
                    tl.last_observed
                FROM user_metadata u
                LEFT JOIN LATERAL (
                    SELECT MIN(export_timestamp) as first_observed,
                           MAX(export_timestamp) as last_observed
                    FROM user_timeline_ledger
                    WHERE service_id = u.service_id
                ) tl ON true
                WHERE u.service_id ANY(:ids)
                AND (u.is_active IS NULL OR u.is_active = TRUE)
            """
            )

            # Note: ANY(:ids) is better than IN (...) for bulk params
            result = conn.execute(sql, {"ids": chunk})
            rows = result.mappings().all()

            if rows:
                _bulk_index_users(client, rows, log)
                total_indexed += len(rows)

    return total_indexed


def index_groups_from_db(
    job_id: int, log_func: Callable[[str], None] | None = None
) -> int:
    """
    Fetches groups from the DB and indexes them.
    """
    log = log_func if log_func else logger.info
    client = get_opensearch_client()

    # Define explicit mapping for groups
    mapping = {
        "properties": {
            "group_id": {"type": "keyword"},
            "group_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "description": {"type": "text"},
            "number_of_members": {"type": "integer"},
            "admin_approval_required": {
                "type": "boolean",
                "index": True,
                "doc_values": True,
            },
            "retention_period": {
                "type": "keyword",
                "index": True,
                "doc_values": True,
            },
            # enabled=False only for objects.
            "group_link": {"type": "keyword", "index": False, "doc_values": True},
            "reconstructed_link": {
                "type": "keyword",
                "index": False,
                "doc_values": True,
            },
            "public_params": {"type": "text", "index": False},
            "last_updated_job_id": {"type": "integer"},
            "id": {"type": "integer"},
            "first_observed": {"type": "date", "index": False, "doc_values": False},
            "last_observed": {"type": "date", "index": False, "doc_values": False},
        }
    }

    create_index_if_not_exists(client, INDEX_GROUPS, mapping)

    # Fetch group mapping logic removed...

    with engine.connect() as conn:
        where_clause = f"WHERE g.last_updated_job_id = {job_id}" if job_id else "WHERE 1=1"
        query = text(f"""
            SELECT g.*,
                   tl.first_observed,
                   tl.last_observed
            FROM groups g
            LEFT JOIN LATERAL (
                SELECT MIN(export_timestamp) as first_observed,
                       MAX(export_timestamp) as last_observed
                FROM group_timeline_ledger
                WHERE group_pk = g.id
            ) tl ON true
            {where_clause}
        """)

        result = conn.execute(query)
        rows = result.mappings().all()

        _bulk_index_groups(client, rows, log)

        # Sync first_observed/last_observed back to groups table
        _sync_group_observed_dates(conn, rows)

    return len(rows)


def _sync_group_observed_dates(conn: Any, rows: Sequence[Any]) -> None:
    """Sync computed first_observed/last_observed from timeline ledger back to groups table."""
    updates = []
    for row in rows:
        row_dict = dict(row)
        first_obs = row_dict.get("first_observed")
        last_obs = row_dict.get("last_observed")
        gid = row_dict.get("id")
        if gid and (first_obs or last_obs):
            updates.append({"gid": gid, "first_obs": first_obs, "last_obs": last_obs})

    if not updates:
        return

    ids = [u["gid"] for u in updates]
    id_list = ",".join(str(i) for i in ids)

    first_cases = []
    last_cases = []
    for u in updates:
        if u["first_obs"]:
            first_cases.append(f"WHEN {u['gid']} THEN '{u['first_obs'].isoformat()}'::timestamptz")
        if u["last_obs"]:
            last_cases.append(f"WHEN {u['gid']} THEN '{u['last_obs'].isoformat()}'::timestamptz")

    set_clauses = []
    if first_cases:
        set_clauses.append(f"first_observed = CASE id {' '.join(first_cases)} ELSE first_observed END")
    if last_cases:
        set_clauses.append(f"last_observed = CASE id {' '.join(last_cases)} ELSE last_observed END")

    if set_clauses:
        sql = text(f"UPDATE groups SET {', '.join(set_clauses)} WHERE id IN ({id_list})")
        conn.execute(sql)
        conn.commit()


def _bulk_index_groups(
    client: OpenSearch, rows: Sequence[Any], log: Callable[[str], None]
) -> None:
    actions = []
    for row in rows:
        row_dict = dict(row)

        first_obs = row_dict.get("first_observed")
        last_obs = row_dict.get("last_observed")

        # Explicit selection based on mapping
        doc = {
            "group_id": row_dict.get("group_id"),
            "group_name": row_dict.get("group_name"),
            "description": row_dict.get("description"),
            "number_of_members": row_dict.get("number_of_members"),
            "admin_approval_required": row_dict.get("admin_approval_required"),
            "retention_period": row_dict.get("retention_period"),
            "group_link": row_dict.get("group_link"),
            "reconstructed_link": row_dict.get("reconstructed_link"),
            "public_params": row_dict.get("public_params"),
            "last_updated_job_id": row_dict.get("last_updated_job_id"),
            "id": row_dict.get("id"),
            "first_observed": first_obs.isoformat() if first_obs else None,
            "last_observed": last_obs.isoformat() if last_obs else None,
        }

        action = {
            "_index": INDEX_GROUPS,
            "_id": str(doc.get("group_id")),
            "_source": doc,
        }
        actions.append(action)

    if actions:
        helpers.bulk(client, actions)
        log(f"Indexed {len(actions)} groups.")
    else:
        log("No groups found to index.")


def index_groups_by_ids(
    ids: list[str], log_func: Callable[[str], None] | None = None
) -> int:
    if not ids:
        return 0
    log = log_func if log_func else logger.info
    client = get_opensearch_client()
    # Fetch group mapping logic removed...

    chunk_size = 500
    total_indexed = 0

    with engine.connect() as conn:
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            id_list_str = ",".join([f"'{str(x)}'" for x in chunk])

            sql = f"""
                SELECT g.*,
                       tl.first_observed,
                       tl.last_observed
                FROM groups g
                LEFT JOIN LATERAL (
                    SELECT MIN(export_timestamp) as first_observed,
                           MAX(export_timestamp) as last_observed
                    FROM group_timeline_ledger
                    WHERE group_pk = g.id
                ) tl ON true
                WHERE g.group_id IN ({id_list_str})
            """
            result = conn.execute(text(sql))
            rows = result.mappings().all()

            if rows:
                _bulk_index_groups(client, rows, log)
                total_indexed += len(rows)

    return total_indexed


def delete_documents_by_job_id(
    job_id: int, log_func: Callable[[str], None] | None = None
) -> None:
    """
    Deletes documents from both indices where last_updated_job_id matches.
    """
    log = log_func if log_func else logger.info
    client = get_opensearch_client()

    query = {"query": {"term": {"last_updated_job_id": job_id}}}

    for idx in [INDEX_USERS, INDEX_GROUPS]:
        if client.indices.exists(index=idx):
            try:
                resp = client.delete_by_query(
                    index=idx, body=query, params={"conflicts": "proceed"}
                )
                deleted = resp.get("deleted", 0)
                log(f"Deleted {deleted} docs from {idx} for job {job_id}")
            except Exception as e:
                log(f"Error deleting from {idx}: {e}")
