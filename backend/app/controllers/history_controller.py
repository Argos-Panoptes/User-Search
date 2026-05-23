from sqlalchemy.orm import Session
from sqlalchemy.engine import CursorResult
from typing import Any, Callable


class HistoryController:

    @staticmethod
    def record_user_history_optimized(
        db: Session,
        job_id: int,
        batch_size: int = 10000,
        progress_callback: Callable[..., Any] | None = None,
    ) -> int:
        """
        Pure SQL optimized User History.
        Uses INSERT ... SELECT with snapshot_hash for maximum performance.
        Now integrates with UserTimelineLedger.
        """
        from sqlalchemy import text

        sql = text(
            """
            WITH latest_history AS (
                SELECT DISTINCT ON (service_id)
                    service_id,
                    snapshot_hash,
                    avatar_id
                FROM user_history
                ORDER BY service_id, history_date DESC
            ),
            candidates AS (
                SELECT
                    u.*,
                    l.snapshot_hash as old_hash,
                    CASE WHEN l.service_id IS NULL THEN 'INSERT' ELSE 'UPDATE' END as op_type
                FROM user_metadata u
                LEFT JOIN latest_history l ON l.service_id = u.service_id
                WHERE u.last_updated_job_id = :job_id
                AND (
                    l.snapshot_hash IS NULL 
                    OR l.snapshot_hash IS DISTINCT FROM u.snapshot_hash
                    OR l.avatar_id IS DISTINCT FROM u.avatar_id
                )
            ),
            ledger_upsert AS (
                INSERT INTO user_timeline_ledger (user_id, service_id, job_id, export_timestamp, has_profile_change, has_membership_change, has_avatar_change, created_at)
                SELECT DISTINCT c.id, c.service_id, :job_id, c.export_timestamp, TRUE, FALSE, FALSE, NOW()
                FROM candidates c
                ON CONFLICT (user_id, job_id, export_timestamp)
                DO UPDATE SET has_profile_change = TRUE
                RETURNING id as timeline_id, user_id
            )
            INSERT INTO user_history (
                service_id, history_operation, last_updated_job_id, snapshot_hash, history_date,
                e164, name, profile_name, profile_family_name, profile_full_name,
                active_at, profile_last_fetched_at, about, about_emoji, remote_avatar_url, 
                profile_key, profile_key_version, access_key, profile_key_credential, 
                profile_key_credential_expiration, sharing_phone_number, capabilities, 
                verified, color, storage_version, storage_id, conversation_id, is_admin,
                export_timestamp, avatar_id, timeline_id
            )
            SELECT
                c.service_id,
                c.op_type,
                :job_id,
                c.snapshot_hash,
                NOW(),
                c.e164, c.name, c.profile_name, c.profile_family_name, c.profile_full_name,
                c.active_at, c.profile_last_fetched_at, c.about, c.about_emoji, c.remote_avatar_url,
                c.profile_key, c.profile_key_version, c.access_key, c.profile_key_credential,
                c.profile_key_credential_expiration, c.sharing_phone_number, c.capabilities,
                c.verified, c.color, c.storage_version, c.storage_id, c.conversation_id, c.is_admin,
                c.export_timestamp, c.avatar_id, lu.timeline_id
            FROM candidates c
            JOIN ledger_upsert lu ON c.id = lu.user_id
        """
        )

        result = db.execute(sql, {"job_id": job_id})
        db.commit()
        if isinstance(result, CursorResult):
            return result.rowcount if result.rowcount is not None else 0
        return 0

    @staticmethod
    def record_group_history_optimized(
        db: Session,
        job_id: int,
    ) -> int:
        """
        Pure SQL optimized Group History with Ledger Integration.
        """
        from sqlalchemy import text

        sql = text(
            """
            WITH latest_history AS (
                SELECT DISTINCT ON (group_id)
                    group_id,
                    snapshot_hash,
                    number_of_members
                FROM group_history
                ORDER BY group_id, history_date DESC
            ),
            candidates AS (
                SELECT
                    g.*,
                    l.snapshot_hash as old_hash,
                    CASE WHEN l.group_id IS NULL THEN 'INSERT' ELSE 'UPDATE' END as op_type
                FROM groups g
                LEFT JOIN latest_history l ON l.group_id = g.group_id
                WHERE g.last_updated_job_id = :job_id
                AND (
                    l.snapshot_hash IS NULL 
                    OR l.snapshot_hash IS DISTINCT FROM g.snapshot_hash
                    OR l.number_of_members IS DISTINCT FROM g.number_of_members
                )
            ),
            ledger_upsert AS (
                INSERT INTO group_timeline_ledger (group_pk, group_id, job_id, export_timestamp, has_detail_change, has_membership_change, created_at)
                SELECT DISTINCT c.id, c.group_id, :job_id, COALESCE(c.export_timestamp, NOW()), TRUE, FALSE, NOW()
                FROM candidates c
                ON CONFLICT (group_pk, job_id, export_timestamp)
                DO UPDATE SET has_detail_change = TRUE
                RETURNING id as timeline_id, group_pk
            )
            INSERT INTO group_history (
                group_id, history_operation, last_updated_job_id, snapshot_hash, history_date,
                group_name, number_of_members, admin_approval_required, group_link,
                description, retention_period, master_key, invite_link_password, 
                secret_params, public_params, reconstructed_link, timeline_id
            )
            SELECT
                c.group_id,
                c.op_type,
                 :job_id,
                c.snapshot_hash,
                NOW(),
                c.group_name, c.number_of_members, c.admin_approval_required, c.group_link,
                c.description, c.retention_period, c.master_key, c.invite_link_password,
                c.secret_params, c.public_params, c.reconstructed_link, lu.timeline_id
            FROM candidates c
            JOIN ledger_upsert lu ON c.id = lu.group_pk
        """
        )

        result = db.execute(sql, {"job_id": job_id})
        db.commit()
        if isinstance(result, CursorResult):
            return result.rowcount if result.rowcount is not None else 0
        return 0

    @staticmethod
    def record_avatar_history_optimized(
        db: Session,
        job_id: int,
    ) -> int:
        """
        Pure SQL optimized Avatar History.
        """
        from sqlalchemy import text

        sql = text(
            """
            WITH latest_history AS (
                SELECT DISTINCT ON (service_id)
                    service_id,
                    snapshot_hash
                FROM avatar_history
                ORDER BY service_id, history_date DESC
            ),
            candidates AS (
                SELECT
                    a.*,
                    l.snapshot_hash as old_hash,
                    u.id as user_id,
                    CASE WHEN l.service_id IS NULL THEN 'INSERT' ELSE 'UPDATE' END as op_type
                FROM avatars a
                JOIN user_metadata u ON a.service_id = u.service_id
                LEFT JOIN latest_history l ON l.service_id = a.service_id
                WHERE a.snapshot_hash IS NOT NULL
                AND (l.snapshot_hash IS NULL OR l.snapshot_hash IS DISTINCT FROM a.snapshot_hash)
                AND (a.last_updated_job_id = :job_id OR :job_id IS NULL)
            ),
            ledger_upsert AS (
                INSERT INTO user_timeline_ledger (user_id, service_id, job_id, export_timestamp, has_avatar_change, has_profile_change, has_membership_change, created_at)
                SELECT DISTINCT c.user_id, c.service_id, :job_id, c.timestamp, TRUE, FALSE, FALSE, NOW()
                FROM candidates c
                ON CONFLICT (user_id, job_id, export_timestamp)
                DO UPDATE SET has_avatar_change = TRUE
                RETURNING id as timeline_id, user_id
            )
            INSERT INTO avatar_history (
                id, service_id, history_operation, last_updated_job_id, snapshot_hash, history_date,
                s3_key, s3_url, filename, file_size, timestamp
            )
            SELECT
                c.id, c.service_id,
                c.op_type,
                :job_id,
                c.snapshot_hash,
                NOW(),
                c.s3_key, c.s3_url, c.filename, c.file_size, c.timestamp
            FROM candidates c
            JOIN ledger_upsert lu ON c.user_id = lu.user_id
        """
        )

        result = db.execute(sql, {"job_id": job_id})
        db.commit()
        if isinstance(result, CursorResult):
            return result.rowcount if result.rowcount is not None else 0
        return 0

    @staticmethod
    def record_membership_history_optimized(
        db: Session,
        job_id: int,
    ) -> int:
        """
        SCD Type 2 History for Group Memberships with Ledger Integration.
        Tracks valid_from / valid_to for each user-group relationship.
        Uses u.export_timestamp for validity dates.
        """
        from sqlalchemy import text

        # 0. Upsert Group Timeline Ledgers for all affected groups
        # We identify groups that have either a Closure or an Insert pending.
        ledger_sql = text(
            """
            stable_ts AS (
                SELECT created_at FROM ingestion_jobs WHERE id = :job_id
            ),
            affected_groups AS (
                -- Identify groups with Closed Memberships
                SELECT h.group_id as group_pk
                FROM group_membership_history h
                JOIN user_metadata u ON h.user_id = u.id
                LEFT JOIN group_memberships_map m 
                    ON h.user_id = m.user_id 
                    AND h.group_id = m.group_id
                    AND h.role IS NOT DISTINCT FROM m.role
                WHERE h.valid_to IS NULL
                AND u.last_updated_job_id = :job_id
                AND m.id IS NULL

                UNION

                -- Identify groups with New Memberships
                SELECT m.group_id as group_pk
                FROM group_memberships_map m
                JOIN user_metadata u ON m.user_id = u.id
                LEFT JOIN group_membership_history h 
                    ON h.user_id = m.user_id 
                    AND h.group_id = m.group_id 
                    AND h.valid_to IS NULL
                    AND h.role IS NOT DISTINCT FROM m.role
                WHERE u.last_updated_job_id = :job_id
                AND h.id IS NULL
            )
            INSERT INTO group_timeline_ledger (group_pk, group_id, job_id, export_timestamp, has_membership_change, has_detail_change, created_at)
            SELECT DISTINCT ag.group_pk, g.group_id, :job_id, (SELECT created_at FROM stable_ts), TRUE, FALSE, NOW()
            FROM affected_groups ag
            JOIN groups g ON g.id = ag.group_pk
            ON CONFLICT (group_pk, job_id, export_timestamp)
            DO UPDATE SET has_membership_change = TRUE
        """
        )
        db.execute(ledger_sql, {"job_id": job_id})

        # 1. Close Removed Memberships (or Role Changes)
        # Link to the Group Timeline Ledger
        close_sql = text(
            """
            WITH updates_to_close AS (
                SELECT h.id, u.export_timestamp, l.id as timeline_id
                FROM group_membership_history h
                JOIN user_metadata u ON h.user_id = u.id
                LEFT JOIN group_memberships_map m 
                    ON h.user_id = m.user_id 
                    AND h.group_id = m.group_id
                    AND h.role IS NOT DISTINCT FROM m.role
                -- Join Ledger to link event
                JOIN group_timeline_ledger l
                    ON l.group_pk = h.group_id
                    AND l.job_id = :job_id
                WHERE h.valid_to IS NULL
                AND u.last_updated_job_id = :job_id
                AND m.id IS NULL
            )
            UPDATE group_membership_history h
            SET valid_to = u.export_timestamp,
                job_id = :job_id,
                exit_group_timeline_id = u.timeline_id
            FROM updates_to_close u
            WHERE h.id = u.id
        """
        )

        result_close = db.execute(close_sql, {"job_id": job_id})
        closed_count = result_close.rowcount if result_close.rowcount is not None else 0

        # 2. Insert New Memberships (or Role Changes)
        # Link to the Group Timeline Ledger
        insert_sql = text(
            """
            INSERT INTO group_membership_history (
                user_id, group_id, role, valid_from, valid_to, job_id, join_group_timeline_id
            )
            SELECT 
                m.user_id, m.group_id, m.role, u.export_timestamp, NULL, :job_id, l.id
            FROM group_memberships_map m
            JOIN user_metadata u ON m.user_id = u.id
            -- Join Ledger to link event
            JOIN group_timeline_ledger l
                ON l.group_pk = m.group_id
                AND l.job_id = :job_id
            LEFT JOIN group_membership_history h 
                ON h.user_id = m.user_id 
                AND h.group_id = m.group_id 
                AND h.valid_to IS NULL
                AND h.role IS NOT DISTINCT FROM m.role
            WHERE u.last_updated_job_id = :job_id
            AND h.id IS NULL
        """
        )

        result_insert = db.execute(insert_sql, {"job_id": job_id})
        inserted_count = (
            result_insert.rowcount if result_insert.rowcount is not None else 0
        )

        db.commit()
        return closed_count + inserted_count
