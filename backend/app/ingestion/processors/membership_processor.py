from typing import Any, Callable
from app.core.config import settings
from app.core.logging import logger
from sqlalchemy import create_engine, text


def process_memberships_sql(
    job_id: int | None = None,
    staging_schema: str | None = None,
    step_id: int | None = None,
    _update_action: Callable[..., Any] | None = None,
    _mark_substep: Callable[..., Any] | None = None,
    log_func: Callable[..., Any] | None = None,
) -> None:
    """
    Process Group Memberships from UserMetadata using PURE SQL.
    Source: {staging_schema}.user_metadata.group_memberships (JSON String)
    Target: group_memberships_map (user_id [INT], group_id [INT], role)

    Optimized for performance:
    - Avoids Spark overhead.
    - Uses Postgres JSONB expansion.
    - Single transaction for cleanup and upsert.
    """
    logger.info(f"Processing Group Memberships (SQL). Job ID: {job_id}")
    if log_func:
        log_func(f"Processing Group Memberships (SQL). Job ID: {job_id}")

    # 1. Database Connection
    engine = create_engine(settings.DATABASE_URL)

    # 2. Identify Staging Table
    schema_prefix = f"{staging_schema}." if staging_schema else ""
    staging_table = f"{schema_prefix}user_metadata"

    try:
        with engine.begin() as conn:
            # 3. Upsert Memberships (Insert New + Update Changed)
            if _update_action:
                _update_action(step_id, "Upserting Membership Mappings")

            logger.info("Upserting memberships directly from SQL (Diff-based)...")

            # Logic:
            # - Join Staging -> UserMetadata to get user_id (PK)
            # - Expand groupMemberships JSON array
            # - Join Groups table to get group_id (PK)
            # - Determine Role by checking adminGroups JSON array
            # - ON CONFLICT DO UPDATE ... WHERE role IS DISTINCT FROM (Avoids null writes)

            # We capture affected user_ids to force-update their metadata for indexing

            upsert_sql = text(
                f"""
                WITH raw_staging AS (
                    SELECT 
                        s.*,
                        CASE 
                            WHEN s."exportTimestamp"::double precision > 100000000000 THEN to_timestamp(s."exportTimestamp"::double precision / 1000.0)
                            ELSE to_timestamp(s."exportTimestamp"::double precision)
                        END as export_ts
                    FROM {staging_table} s
                ),
                staging_data AS (
                    SELECT DISTINCT
                        u.id as user_id,
                        u.service_id,
                        g.id as group_id,
                        CASE
                            WHEN EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    CASE 
                                        WHEN jsonb_typeof(rs."adminGroups"::jsonb) = 'array' THEN rs."adminGroups"::jsonb 
                                        ELSE '[]'::jsonb 
                                    END
                                ) ag
                                WHERE COALESCE(ag->>'id', ag->>'groupId') = COALESCE(gm->>'id', gm->>'groupId')
                            ) THEN 'admin'
                            ELSE 'member'
                        END as role,
                        rs.export_ts
                    FROM raw_staging rs
                    JOIN user_metadata u ON rs."serviceId" = u.service_id
                    CROSS JOIN LATERAL jsonb_array_elements(
                        CASE 
                            WHEN jsonb_typeof(rs."groupMemberships"::jsonb) = 'array' THEN rs."groupMemberships"::jsonb 
                            ELSE '[]'::jsonb 
                        END
                    ) gm
                    JOIN groups g ON g.group_id = COALESCE(gm->>'id', gm->>'groupId')
                    WHERE rs.export_ts >= u.export_timestamp
                ),
                affected_upsert AS (
                    INSERT INTO group_memberships_map (user_id, group_id, role)
                    SELECT user_id, group_id, role FROM staging_data
                    ON CONFLICT (user_id, group_id) 
                    DO UPDATE SET role = EXCLUDED.role
                    WHERE group_memberships_map.role IS DISTINCT FROM EXCLUDED.role
                    RETURNING user_id, group_id, role
                ),
                -- LEDGER (User): Upsert and get Timeline ID
                user_ledger_upsert AS (
                    INSERT INTO user_timeline_ledger (user_id, service_id, job_id, export_timestamp, has_membership_change, has_profile_change, has_avatar_change, created_at)
                    SELECT DISTINCT s.user_id, s.service_id, :job_id, s.export_ts, TRUE, FALSE, FALSE, NOW()
                    FROM affected_upsert a
                    JOIN staging_data s ON a.user_id = s.user_id
                    ON CONFLICT (user_id, job_id, export_timestamp)
                    DO UPDATE SET has_membership_change = TRUE
                    RETURNING id as timeline_id, user_id
                ),
                -- LEDGER (Group): Upsert and get Timeline ID for Affected Groups
                group_ledger_upsert AS (
                    INSERT INTO group_timeline_ledger (group_pk, group_id, job_id, export_timestamp, has_membership_change, has_detail_change, created_at)
                    SELECT g.id, g.group_id, :job_id, MAX(s.export_ts), TRUE, FALSE, NOW()
                    FROM affected_upsert a
                    JOIN groups g ON a.group_id = g.id
                    JOIN staging_data s ON a.user_id = s.user_id AND a.group_id = s.group_id
                    GROUP BY g.id, g.group_id
                    ON CONFLICT (group_pk, job_id, export_timestamp)
                    DO UPDATE SET has_membership_change = TRUE
                    RETURNING id as timeline_id, group_pk
                ),
                -- HISTORY LOGIC: Handle New or Changed Memberships
                -- 1. Close old history records for users whose role changed
                close_history AS (
                    UPDATE group_membership_history h
                    SET valid_to = s.export_ts,
                        exit_timeline_id = ul.timeline_id,
                        exit_group_timeline_id = gl.timeline_id -- Link closing event to group timeline
                    FROM affected_upsert a
                    JOIN staging_data s ON a.user_id = s.user_id AND a.group_id = s.group_id
                    JOIN user_ledger_upsert ul ON a.user_id = ul.user_id
                    JOIN group_ledger_upsert gl ON a.group_id = gl.group_pk
                    WHERE h.user_id = a.user_id 
                    AND h.group_id = a.group_id 
                    AND h.valid_to IS NULL
                    AND h.role IS DISTINCT FROM a.role
                    RETURNING h.user_id
                ),
                -- 2. Insert new history records for Upserts (New or Changed)
                insert_history AS (
                    INSERT INTO group_membership_history (user_id, group_id, role, valid_from, job_id, join_timeline_id, join_group_timeline_id)
                    SELECT a.user_id, a.group_id, a.role, s.export_ts, :job_id, ul.timeline_id, gl.timeline_id
                    FROM affected_upsert a
                    JOIN staging_data s ON a.user_id = s.user_id AND a.group_id = s.group_id
                    JOIN user_ledger_upsert ul ON a.user_id = ul.user_id
                    JOIN group_ledger_upsert gl ON a.group_id = gl.group_pk
                    WHERE NOT EXISTS (
                        SELECT 1 FROM group_membership_history h
                        WHERE h.user_id = a.user_id 
                        AND h.group_id = a.group_id
                        AND h.valid_to IS NULL
                        AND h.role = a.role
                    )
                    RETURNING user_id
                )
                SELECT user_id FROM affected_upsert
                UNION
                SELECT user_id FROM insert_history
                UNION
                SELECT user_id FROM close_history;
                """
            )
            result_upsert = conn.execute(upsert_sql, {"job_id": job_id}).fetchall()
            upsert_affected_ids: set[int] = {r.user_id for r in result_upsert}
            msg = f"Upserted Memberships & Recorded History for {len(upsert_affected_ids)} users."
            logger.info(msg)
            if log_func:
                log_func(msg)

            if _mark_substep:
                _mark_substep(step_id, "Upserting Membership Mappings")

            # 4. Delete Stale Memberships (Diff-based Removal)
            if _update_action:
                _update_action(step_id, "Pruning Stale Memberships")

            logger.info("Pruning stale memberships...")

            # Logic:
            # Delete from map WHERE user is in staging batch BUT group is NOT in the new list
            delete_sql = text(
                f"""
                WITH staging_users AS (
                    SELECT u.id as user_id, u.service_id, s."groupMemberships", 
                    CASE 
                        WHEN s."exportTimestamp"::double precision > 100000000000 THEN to_timestamp(s."exportTimestamp"::double precision / 1000.0)
                        ELSE to_timestamp(s."exportTimestamp"::double precision)
                    END as export_ts
                    FROM {staging_table} s
                    JOIN user_metadata u ON s."serviceId" = u.service_id
                ),
                targets_to_delete AS (
                    SELECT target.user_id, target.group_id
                    FROM group_memberships_map target
                    JOIN staging_users s ON target.user_id = s.user_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            CASE 
                                WHEN jsonb_typeof(s."groupMemberships"::jsonb) = 'array' THEN s."groupMemberships"::jsonb 
                                ELSE '[]'::jsonb 
                            END
                        ) gm
                        JOIN groups g ON g.group_id = COALESCE(gm->>'id', gm->>'groupId')
                        WHERE g.id = target.group_id
                    )
                ),
                affected_delete AS (
                    DELETE FROM group_memberships_map
                    USING targets_to_delete t
                    WHERE group_memberships_map.user_id = t.user_id AND group_memberships_map.group_id = t.group_id
                    RETURNING group_memberships_map.user_id, group_memberships_map.group_id
                ),
                -- LEDGER (User): Upsert and get Timeline ID for Deleted Memberships
                user_ledger_upsert_del AS (
                    INSERT INTO user_timeline_ledger (user_id, service_id, job_id, export_timestamp, has_membership_change, has_profile_change, has_avatar_change, created_at)
                    SELECT DISTINCT d.user_id, s.service_id, :job_id, s.export_ts, TRUE, FALSE, FALSE, NOW()
                    FROM affected_delete d
                    JOIN staging_users s ON d.user_id = s.user_id
                    ON CONFLICT (user_id, job_id, export_timestamp)
                    DO UPDATE SET has_membership_change = TRUE
                    RETURNING id as timeline_id, user_id
                ),
                -- LEDGER (Group): Upsert Timeline for affected groups
                group_ledger_upsert_del AS (
                    INSERT INTO group_timeline_ledger (group_pk, group_id, job_id, export_timestamp, has_membership_change, has_detail_change, created_at)
                    SELECT d.group_id, g.group_id, :job_id, MAX(s.export_ts), TRUE, FALSE, NOW()
                    FROM affected_delete d
                    JOIN groups g ON d.group_id = g.id
                    JOIN staging_users s ON d.user_id = s.user_id
                    GROUP BY d.group_id, g.group_id
                    ON CONFLICT (group_pk, job_id, export_timestamp)
                    DO UPDATE SET has_membership_change = TRUE
                    RETURNING id as timeline_id, group_pk
                ),
                -- HISTORY LOGIC: Close history for deleted memberships
                close_deleted_history AS (
                    UPDATE group_membership_history h
                    SET valid_to = s.export_ts,
                        exit_timeline_id = ul.timeline_id, 
                        exit_group_timeline_id = gl.timeline_id -- Link closing event to group timeline
                    -- Note: We do NOT update timeline_id here because that belongs to creation.
                    -- linking to ledger_upsert_del is done via JOIN to ensure the ledger entry is created.
                    FROM affected_delete d
                    JOIN staging_users s ON d.user_id = s.user_id
                    JOIN user_ledger_upsert_del ul ON d.user_id = ul.user_id -- Force dependency so ledger Insert runs
                    JOIN group_ledger_upsert_del gl ON d.group_id = gl.group_pk -- Force dependency so group ledger Insert runs
                    WHERE h.user_id = d.user_id 
                    AND h.group_id = d.group_id 
                    AND h.valid_to IS NULL
                    RETURNING h.user_id
                )
                SELECT user_id FROM affected_delete
                UNION
                SELECT user_id FROM close_deleted_history;
                """
            )
            result_del = conn.execute(delete_sql, {"job_id": job_id}).fetchall()
            delete_affected_ids: set[int] = {r.user_id for r in result_del}
            msg = f"Pruned Memberships & Recorded History for {len(delete_affected_ids)} users."
            logger.info(msg)
            if log_func:
                log_func(msg)
            if _mark_substep:
                _mark_substep(step_id, "Pruning Stale Memberships")

            # 5. Propagate Changes to UserMetadata
            # Update last_updated_job_id for ALL users who had membership changes
            # This ensures the Indexer (which queries user_metadata) picks them up.

            all_affected_ids = upsert_affected_ids.union(delete_affected_ids)

            if all_affected_ids and job_id:
                msg = f"Propagating membership updates to {len(all_affected_ids)} users..."
                logger.info(msg)
                if _update_action:
                    _update_action(step_id, msg)

                if log_func:
                    log_func(msg)

                # If single item tuple, python adds trailing comma which SQL handles, but empty tuple crashes
                update_meta_sql = text(
                    """
                    UPDATE user_metadata
                    SET last_updated_job_id = :job_id
                    WHERE id IN :ids
                    """
                )
                # execute accepts tuple/list for IN binding if using proper driver, but SQLAlchemy with Text can be tricky.
                # Safer to use bindparams or just :ids with the list
                conn.execute(
                    update_meta_sql, {"job_id": job_id, "ids": tuple(all_affected_ids)}
                )
                logger.info("Propagation complete.")
                if log_func:
                    log_func("Propagation complete.")
                if _mark_substep:
                    _mark_substep(step_id, "Propagation complete.")

    except Exception as e:
        logger.error(f"Membership SQL processing failed: {e}")
        raise e

    logger.info("Membership Mapping Complete (SQL).")


def compute_member_counts_sql(
    job_id: int | None = None,
    step_id: int | None = None,
    _update_action: Callable[..., Any] | None = None,
) -> None:
    """
    Computes the member count for each group based on the group_memberships_map
    and updates the groups.number_of_members column.
    """
    logger.info("Computing group member counts...")
    if _update_action:
        _update_action(step_id, "Computing Member Counts")

    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        # Use CTE to aggregate and UPDATE to set the count
        # Optimized to only update if changed
        sql = text(
            """
            WITH counts AS (
                SELECT group_id, COUNT(*) as m_count
                FROM group_memberships_map
                GROUP BY group_id
            )
            UPDATE groups g
            SET number_of_members = c.m_count,
                last_updated_job_id = :job_id
            FROM counts c
            WHERE g.id = c.group_id
            AND g.number_of_members IS DISTINCT FROM c.m_count;
            """
        )
        result = conn.execute(sql, {"job_id": job_id})
        logger.info(f"Updated member counts for {result.rowcount} groups.")
