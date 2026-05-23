from sqlalchemy.orm import Session, joinedload
from app.db.schemas.ingestion_models import (
    IngestionJob,
    IngestionLog,
    IngestionStep,
    IngestionSubstep,
)
from datetime import datetime, timezone
from typing import List, Optional


class JobsController:
    @staticmethod
    def create_job(
        db: Session,
        ingestion_type: str,
        celery_task_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> IngestionJob:
        job = IngestionJob(
            ingestion_type=ingestion_type,
            celery_task_id=celery_task_id,
            status="pending",
            created_by_id=user_id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_job_running(db: Session, job_id: int):
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job and job.status != "running":
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def get_running_jobs(
        db: Session, ingestion_type: str, exclude_job_id: Optional[int] = None
    ) -> List[IngestionJob]:
        query = db.query(IngestionJob).filter(
            IngestionJob.ingestion_type == ingestion_type,
            IngestionJob.status == "running",
        )
        if exclude_job_id:
            query = query.filter(IngestionJob.id != exclude_job_id)
        return query.all()

    @staticmethod
    def get_job(db: Session, job_id: int) -> Optional[IngestionJob]:
        return db.query(IngestionJob).filter(IngestionJob.id == job_id).first()

    @staticmethod
    def create_step(db: Session, job_id: int, step_name: str) -> IngestionStep:
        step = IngestionStep(job_id=job_id, step_name=step_name, status="pending")
        db.add(step)
        db.commit()
        db.refresh(step)
        return step

    @staticmethod
    def update_step_progress(
        db: Session, step_id: int, progress: float, status: str = "running"
    ):
        step = db.query(IngestionStep).filter(IngestionStep.id == step_id).first()
        if step:
            step.progress_percentage = progress
            step.status = status
            if status == "running" and not step.started_at:
                step.started_at = datetime.now(timezone.utc)
            if status in ["completed", "failed"]:
                step.completed_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def get_job_step(
        db: Session, job_id: int, step_name: str
    ) -> Optional[IngestionStep]:
        return (
            db.query(IngestionStep)
            .filter(
                IngestionStep.job_id == job_id, IngestionStep.step_name == step_name
            )
            .first()
        )

    @staticmethod
    def update_step_action(db: Session, step_id: int, action: str):
        step = db.query(IngestionStep).filter(IngestionStep.id == step_id).first()
        if step:
            step.current_action = action
            db.commit()
            db.refresh(step)
        return step

    @staticmethod
    def set_substeps(db: Session, step_id: int, substep_names: List[str]) -> None:
        """
        Initializes the substeps list for a given step in the database.
        Deletes existing substeps if any, and creates new ones.
        """
        step = db.query(IngestionStep).filter(IngestionStep.id == step_id).first()
        if not step:
            return

        # Clear existing substeps for clean state (optional safety)
        db.query(IngestionSubstep).filter(IngestionSubstep.step_id == step_id).delete()

        new_substeps = []
        for name in substep_names:
            sub = IngestionSubstep(step_id=step_id, name=name, status="pending")
            db.add(sub)
            new_substeps.append(sub)

        db.commit()

    @staticmethod
    def complete_substep(db: Session, step_id: int, substep_name: str) -> None:
        """
        Marks a specific substep as completed and updates the step's current action.
        """
        # Find the specific substep
        substep = (
            db.query(IngestionSubstep)
            .filter(
                IngestionSubstep.step_id == step_id,
                IngestionSubstep.name == substep_name,
            )
            .first()
        )

        if substep:
            substep.status = "completed"
            substep.completed_at = datetime.now(timezone.utc)
            db.add(substep)  # Mark for update

        # Update parent step's current action to reflect this completion
        step = db.query(IngestionStep).filter(IngestionStep.id == step_id).first()
        if step:
            step.current_action = f"Completed: {substep_name}"
            db.add(step)

        db.commit()

    @staticmethod
    def add_log(
        db: Session,
        job_id: int,
        message: str,
        level: str = "INFO",
        step_name: Optional[str] = None,
    ):
        log_entry = IngestionLog(
            job_id=job_id,
            message=message,
            log_level=level,
            step_name=step_name,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()

    @staticmethod
    def get_job_logs(
        db: Session,
        job_id: int,
        limit: int = 100,
        offset: int = 0,
        after_id: Optional[int] = None,
    ) -> List[IngestionLog]:
        query = db.query(IngestionLog).filter(IngestionLog.job_id == job_id)

        if after_id is not None:
            query = query.filter(IngestionLog.id > after_id)

        return (
            query.order_by(IngestionLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def list_jobs(
        db: Session,
        ingestion_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[IngestionJob], int]:
        query = db.query(IngestionJob)
        if ingestion_type:
            if "," in ingestion_type:
                types = [t.strip() for t in ingestion_type.split(",")]
                query = query.filter(IngestionJob.ingestion_type.in_(types))
            else:
                query = query.filter(IngestionJob.ingestion_type == ingestion_type)

        total = query.count()

        jobs = (
            query.order_by(IngestionJob.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return jobs, total

    @staticmethod
    def update_job_metrics(db: Session, job_id: int, metrics: dict):
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.metrics = metrics
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def update_job_file_path(db: Session, job_id: int, file_path: str):
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.source_file_path = file_path
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def create_rollback_job(db: Session, target_job_id: int) -> IngestionJob:
        # Check if target job exists
        target_job = (
            db.query(IngestionJob).filter(IngestionJob.id == target_job_id).first()
        )
        if not target_job:
            raise ValueError(f"Job {target_job_id} not found")

        # Create rollback job
        rollback_job = IngestionJob(
            ingestion_type="rollback",
            status="pending",
            source_file_path=target_job.source_file_path,  # Optional: keep linked file
        )
        db.add(rollback_job)
        db.commit()
        db.refresh(rollback_job)
        return rollback_job

    @staticmethod
    def mark_job_rolled_back(db: Session, job_id: int):
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "rolled_back"
            db.commit()

    @staticmethod
    def perform_db_rollback(db: Session, target_job_id: int, log_func=None):
        from sqlalchemy import text

        # Tables configuration: (main_table, history_table, id_column)
        tables = [
            ("user_metadata", "user_history", "service_id"),
            ("groups", "group_history", "group_id"),
            ("avatars", "avatar_history", "id"),
        ]

        # Use connection for raw SQL to ensure efficiency
        for main_tbl, hist_tbl, id_col in tables:
            if log_func:
                log_func(f"Reverting {main_tbl}...")

            # Special handling for user_metadata dependencies
            if main_tbl == "user_metadata":
                # Delete referencing group memberships first to avoid FK violation
                delete_memberships_sql = """
                 DELETE FROM group_memberships_map
                 WHERE user_id IN (
                     SELECT id FROM user_metadata
                     WHERE service_id IN (
                        SELECT service_id FROM user_history
                        WHERE last_updated_job_id = :job_id AND history_operation = 'INSERT'
                     )
                 );
                 """
                db.execute(text(delete_memberships_sql), {"job_id": target_job_id})

            # Special handling for groups dependencies
            if main_tbl == "groups":
                # Delete referencing group memberships first to avoid FK violation
                delete_grp_memberships_sql = """
                 DELETE FROM group_memberships_map
                 WHERE group_id IN (
                     SELECT id FROM groups
                     WHERE group_id IN (
                        SELECT group_id FROM group_history
                        WHERE last_updated_job_id = :job_id AND history_operation = 'INSERT'
                     )
                 );
                 """
                db.execute(text(delete_grp_memberships_sql), {"job_id": target_job_id})

            # 1. DELETE records that were INSERTED by this job
            # Logic: Delete from main table where service_id is in history with op='INSERT' and job_id=target
            delete_sql = f"""
            DELETE FROM {main_tbl}
            WHERE {id_col} IN (
                SELECT {id_col} FROM {hist_tbl}
                WHERE last_updated_job_id = :job_id AND history_operation = 'INSERT'
            );
            """
            db.execute(text(delete_sql), {"job_id": target_job_id})

            # 2. REVERT records that were UPDATED by this job
            # Logic: Update main table with values from the *latest* history record *before* the target job
            # We use a FROM clause to join with the target history state

            # Construct column list for update (excluding specific history columns)
            # Since we can't dynamic columns safely without metadata reflection in raw sql easily,
            # we will assume we can update all columns present in history that match main table.
            # However, simpler approach:
            # Join main table with the "previous state" subquery.

            # Subquery: Get the latest history record for each ID *excluding* the target job.
            # This represents the state we want to roll back TO.
            # We filter for IDs that were actually modified (UPDATE) by the target job.

            # Define columns to restore for each table (excluding primary key if needed, coverage of all tracked fields)
            columns_map = {
                "user_metadata": [
                    "e164",
                    "name",
                    "profile_name",
                    "profile_family_name",
                    "profile_full_name",
                    "active_at",
                    "profile_last_fetched_at",
                    "about",
                    "about_emoji",
                    "remote_avatar_url",
                    "profile_key",
                    "profile_key_version",
                    "access_key",
                    "profile_key_credential",
                    "profile_key_credential_expiration",
                    "sharing_phone_number",
                    "capabilities",
                    "verified",
                    "color",
                    "storage_version",
                    "storage_id",
                    "conversation_id",
                    "group_memberships",
                    "is_admin",
                    "admin_groups",
                    "avatar_id",
                    "export_timestamp",
                    "last_updated_job_id",
                ],
                "groups": [
                    "group_id",
                    "group_name",
                    "number_of_members",
                    "admin_approval_required",
                    "group_link",
                    "description",
                    "retention_period",
                    "master_key",
                    "invite_link_password",
                    "secret_params",
                    "public_params",
                    "last_updated_job_id",
                ],
                "avatars": [
                    "s3_key",
                    "s3_url",
                    "filename",
                    "file_size",
                    "timestamp",
                    "last_updated_job_id",
                ],
            }

            if main_tbl not in columns_map:
                continue

            cols_list = columns_map[main_tbl]
            cols_str = ", ".join(cols_list)  # e.g. "name, e164, ..."
            rec_cols_str = ", ".join(
                [f"rec.{c}" for c in cols_list]
            )  # e.g. "rec.name, rec.e164"

            # We use LATERAL to expand the previous_data JSON into a record 'rec' typed as the main table.
            # Then we update the main table columns from 'rec'.
            revert_sql = f"""
            UPDATE {main_tbl}
            SET ({cols_str}) = ({rec_cols_str})
            FROM {hist_tbl} h,
                 LATERAL jsonb_populate_record(NULL::{main_tbl}, h.previous_data::jsonb) rec
            WHERE {main_tbl}.{id_col} = h.{id_col}
              AND h.last_updated_job_id = :job_id
              AND h.history_operation = 'UPDATE';
            """

            db.execute(text(revert_sql), {"job_id": target_job_id})

            # 3. Post-Revert: Re-sync group_memberships_map for Users
            # If we rolled back an UPDATE on user_metadata, the 'group_memberships' JSON column
            # has been reverted to the old state. We must now sync the mapping table to match.
            if main_tbl == "user_metadata":
                # 3a. Delete existing map entries for these users
                delete_map_sql = """
                 DELETE FROM group_memberships_map
                 WHERE user_id IN (
                     SELECT id FROM user_metadata
                     WHERE service_id IN (
                        SELECT service_id FROM user_history
                        WHERE last_updated_job_id = :job_id AND history_operation = 'UPDATE'
                     )
                 );
                 """
                db.execute(text(delete_map_sql), {"job_id": target_job_id})

                # 3b. Re-insert map entries from the reverted JSON
                # We join with 'groups' table to resolve group_id (string) -> id (int)
                insert_map_sql = """
                 INSERT INTO group_memberships_map (user_id, group_id, role)
                 SELECT
                     u.id,
                     g.id,
                     COALESCE(elem->>'role', 'member')
                 FROM
                     user_metadata u,
                     LATERAL jsonb_array_elements(u.group_memberships::jsonb) elem,
                     groups g
                 WHERE
                     u.service_id IN (
                        SELECT service_id FROM user_history
                        WHERE last_updated_job_id = :job_id AND history_operation = 'UPDATE'
                     )
                     AND g.group_id = (elem->>'group_id')
                 ON CONFLICT (user_id, group_id) DO UPDATE SET role = EXCLUDED.role;
                 """
                # Note: ON CONFLICT just in case, though we deleted first.
                db.execute(text(insert_map_sql), {"job_id": target_job_id})

        db.commit()

    @staticmethod
    def calculate_job_metrics(db: Session, job_id: int) -> dict:
        """
        Calculates insertion and update counts from history tables for the given job.
        """
        from app.core.logging import logger
        from sqlalchemy import text

        logger.info(f"CALCULATING METRICS FOR JOB ID: {job_id}")

        metrics = {}
        tables = [
            ("user_history", "users"),
            ("group_history", "groups"),
            ("avatar_history", "avatars"),
        ]

        total_inserts = 0
        total_updates = 0

        for hist_tbl, key_prefix in tables:
            # Count Inserts
            sql_insert = text(
                f"SELECT COUNT(*) FROM {hist_tbl} WHERE last_updated_job_id = :job_id AND history_operation = 'INSERT'"
            )
            inserts = db.execute(sql_insert, {"job_id": job_id}).scalar() or 0

            # Count Updates
            sql_update = text(
                f"SELECT COUNT(*) FROM {hist_tbl} WHERE last_updated_job_id = :job_id AND history_operation = 'UPDATE'"
            )
            updates = db.execute(sql_update, {"job_id": job_id}).scalar() or 0

            logger.info(f"Table {hist_tbl}: Inserted={inserts}, Updated={updates}")

            metrics[f"{key_prefix}_inserted"] = inserts
            metrics[f"{key_prefix}_updated"] = updates

            total_inserts += inserts
            total_updates += updates

        metrics["total_records_affected"] = total_inserts + total_updates
        logger.info(f"Final Metrics: {metrics}")
        return metrics

    @staticmethod
    def get_job_affected_ids(db: Session, job_id: int) -> dict:
        """
        Returns a dictionary of affected IDs by table and operation type.
        Structure:
        {
            "users": {"inserted": [...], "updated": [...]},
            "groups": {"inserted": [...], "updated": [...]},
        }
        """
        from sqlalchemy import text

        result = {
            "users": {"inserted": [], "updated": []},
            "groups": {"inserted": [], "updated": []},
        }

        # 1. Users
        logs = db.execute(
            text(
                "SELECT service_id, history_operation FROM user_history WHERE last_updated_job_id = :job_id"
            ),
            {"job_id": job_id},
        ).fetchall()

        for row in logs:
            op = "inserted" if row.history_operation == "INSERT" else "updated"
            if op in result["users"]:
                result["users"][op].append(str(row.service_id))

        # 2. Groups
        grps = db.execute(
            text(
                "SELECT group_id, history_operation FROM group_history WHERE last_updated_job_id = :job_id"
            ),
            {"job_id": job_id},
        ).fetchall()

        for row in grps:
            op = "inserted" if row.history_operation == "INSERT" else "updated"
            if op in result["groups"]:
                result["groups"][op].append(str(row.group_id))

        return result
