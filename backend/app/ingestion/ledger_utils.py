from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_or_create_timeline_ledger(
    conn, user_id: int, service_id: str, job_id: int, timestamp: datetime
) -> int:
    """
    Ensures a UserTimelineLedger entry exists for the given user and job.
    Returns the ID of the ledger entry.
    """

    # 1. Try to fetch existing
    select_sql = text(
        """
        SELECT id FROM user_timeline_ledger 
        WHERE user_id = :user_id AND job_id = :job_id AND export_timestamp = :ts
    """
    )
    result = conn.execute(
        select_sql, {"user_id": user_id, "job_id": job_id, "ts": timestamp}
    ).fetchone()

    if result:
        return result[0]

    # 2. Insert new
    # Use ON CONFLICT DO NOTHING to handle race conditions if any (though usually strictly serial per user)
    insert_sql = text(
        """
        INSERT INTO user_timeline_ledger (user_id, service_id, job_id, export_timestamp, has_profile_change, has_membership_change, has_avatar_change, created_at)
        VALUES (:user_id, :service_id, :job_id, :ts, FALSE, FALSE, FALSE, NOW())
        ON CONFLICT (user_id, job_id, export_timestamp) DO NOTHING
        RETURNING id
    """
    )

    result = conn.execute(
        insert_sql,
        {
            "user_id": user_id,
            "service_id": service_id,
            "job_id": job_id,
            "ts": timestamp,
        },
    ).fetchone()

    if result:
        return result[0]

    # 3. If INSERT returned nothing (due to conflict race), fetch again
    result = conn.execute(select_sql, {"user_id": user_id, "job_id": job_id}).fetchone()
    if result:
        return result[0]

    raise Exception(
        f"Failed to get or create timeline ledger for user_id={user_id}, job_id={job_id}"
    )


def update_ledger_flags(
    conn,
    ledger_id: int,
    has_profile: bool = False,
    has_membership: bool = False,
    has_avatar: bool = False,
):
    """
    Updates the change flags for a ledger entry.
    """
    set_clauses = []
    params = {"id": ledger_id}

    if has_profile:
        set_clauses.append("has_profile_change = TRUE")
    if has_membership:
        set_clauses.append("has_membership_change = TRUE")
    if has_avatar:
        set_clauses.append("has_avatar_change = TRUE")

    if not set_clauses:
        return

    sql = text(
        f"""
        UPDATE user_timeline_ledger
        SET {', '.join(set_clauses)}
        WHERE id = :id
    """
    )
    conn.execute(sql, params)


def get_or_create_group_timeline_ledger(
    conn, group_pk: int, group_id: str, job_id: int, timestamp: datetime
) -> int:
    """
    Ensures a GroupTimelineLedger entry exists for the given group and job.
    Returns the ID of the ledger entry.
    """
    select_sql = text(
        """
        SELECT id FROM group_timeline_ledger 
        WHERE group_pk = :group_pk AND job_id = :job_id AND export_timestamp = :ts
    """
    )
    result = conn.execute(
        select_sql, {"group_pk": group_pk, "job_id": job_id, "ts": timestamp}
    ).fetchone()

    if result:
        return result[0]

    insert_sql = text(
        """
        INSERT INTO group_timeline_ledger (group_pk, group_id, job_id, export_timestamp, has_detail_change, has_membership_change, created_at)
        VALUES (:group_pk, :group_id, :job_id, :ts, FALSE, FALSE, NOW())
        ON CONFLICT (group_pk, job_id, export_timestamp) DO NOTHING
        RETURNING id
    """
    )

    result = conn.execute(
        insert_sql,
        {
            "group_pk": group_pk,
            "group_id": group_id,
            "job_id": job_id,
            "ts": timestamp,
        },
    ).fetchone()

    if result:
        return result[0]

    result = conn.execute(
        select_sql, {"group_pk": group_pk, "job_id": job_id, "ts": timestamp}
    ).fetchone()
    if result:
        return result[0]

    raise Exception(
        f"Failed to get or create group timeline ledger for group_pk={group_pk}, job_id={job_id}"
    )


def update_group_ledger_flags(
    conn,
    ledger_id: int,
    has_detail: bool = False,
    has_membership: bool = False,
):
    """
    Updates the change flags for a group ledger entry.
    """
    set_clauses = []
    params = {"id": ledger_id}

    if has_detail:
        set_clauses.append("has_detail_change = TRUE")
    if has_membership:
        set_clauses.append("has_membership_change = TRUE")

    if not set_clauses:
        return

    sql = text(
        f"""
        UPDATE group_timeline_ledger
        SET {', '.join(set_clauses)}
        WHERE id = :id
    """
    )
    conn.execute(sql, params)
