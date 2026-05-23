import uuid
import re
import os
from typing import Optional, Callable
from sqlalchemy import (
    create_engine,
    text,
    inspect,
    MetaData,
    select,
    or_,
    and_,
    func,
    literal,
    case,
    Text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.logging import logger
from app.core.config import settings
from app.utils.ingestion_helpers import get_job_db_logger


def camel_to_snake(name: str) -> str:
    """
    Converts CamelCase to snake_case.
    e.g., serviceId -> service_id
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class IngestionResult:
    def __init__(self, t: int, p: int, d: int, s: str = "", skipped: bool = False):
        self.t = t
        self.p = p
        self.d = d
        self.schema = s
        self.skipped = skipped

    def count(self):
        return self.t

    def stats(self):
        return {
            "total": self.t,
            "processed": self.p,
            "duplicates": self.d,
            "staging_schema": self.schema,
            "skipped": self.skipped,
        }


def process_user_data(
    file_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    status_callback: Optional[Callable[..., None]] = None,
    cleanup: bool = True,
    job_id: Optional[int] = None,
) -> IngestionResult:
    """
    Process User Data.
    - SQL: Ingests via streaming to staging table -> Upsert to user_metadata using DB reflection.
    """
    if file_path.endswith(".sql"):
        return process_sql_dump(
            file_path, progress_callback, status_callback, cleanup, job_id
        )

    raise NotImplementedError(
        "TSV ingestion is currently disabled. Please upload a SQL snapshot."
    )


def process_sql_dump(
    file_path: str,
    progress_callback: Callable[[float], None] | None = None,
    status_callback: Callable[[str, bool | None], None] | None = None,
    cleanup: bool = True,
    job_id: int | None = None,
) -> IngestionResult:
    db_log = get_job_db_logger(job_id)

    """
    SQL Dump Ingestion using Schema Isolation & Adaptive Merge.
    Returns Result object containing stats and staging schema name.
    """
    # 1. Prepare Staging Schema Name
    unique_id = str(uuid.uuid4()).replace("-", "")[:8]
    staging_schema = f"staging_{unique_id}"
    dump_table_name = "user_metadata"

    logger.info(f"Starting SQL ingestion. Schema: {staging_schema}")

    engine = create_engine(settings.DATABASE_URL)

    # Track inserted records
    total_records = 0
    inserted_or_updated = 0
    duplicates = 0

    # --- BLOCK 1: Import SQL Dump ---
    with engine.begin() as conn:
        # Check and Add 'last_updated_job_id' column if missing
        try:
            inspector = inspect(conn)
            columns = [
                c["name"]
                for c in inspector.get_columns("user_metadata", schema="public")
            ]
            if "last_updated_job_id" not in columns:
                logger.info(
                    "Adding missing column 'last_updated_job_id' to user_metadata"
                )
                if status_callback:
                    status_callback(
                        "Adding missing column 'last_updated_job_id' to user_metadata",
                        False,
                    )
                conn.execute(
                    text(
                        'ALTER TABLE public.user_metadata ADD COLUMN "last_updated_job_id" INTEGER'
                    )
                )
        except Exception as e:
            logger.warning(
                f"Column check/add failed (might already exist or permission issue): {e}"
            )

        # A. Create Schema & Set Path
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {staging_schema}"))
        conn.execute(text(f"SET search_path TO {staging_schema}"))

        # B. Execute SQL File (Buffered)
        raw_conn = conn.connection
        if progress_callback:
            progress_callback(10.0)

        cursor = raw_conn.cursor()

        try:
            BATCH_SIZE = 5 * 1024 * 1024  # 5MB
            buffer = []
            current_size = 0

            total_size = os.path.getsize(file_path)
            processed_bytes = 0
            last_reported_pct = 0.0
            if total_size == 0:
                total_size = 1

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    line_len = len(line.encode("utf-8"))

                    if not stripped or stripped.startswith("--"):
                        processed_bytes += line_len
                        continue

                    buffer.append(line)
                    current_size += len(line)
                    processed_bytes += line_len
                    total_records += 1  # Count lines as records

                    if stripped.endswith(";") and current_size >= BATCH_SIZE:
                        statement = "".join(buffer)
                        cursor.execute(statement)
                        logger.info(f"Executed SQL batch (~{current_size} bytes)")
                        buffer = []
                        current_size = 0

                    if progress_callback:
                        pct = (processed_bytes / total_size) * 100.0
                        if pct - last_reported_pct >= 1.0:
                            progress_callback(pct)
                            last_reported_pct = pct

            if buffer:
                cursor.execute("".join(buffer))
                logger.info("Executed final SQL batch.")

            logger.info("SQL dump executed in staging schema.")
            if status_callback:
                status_callback("Processing SQL Dump", True)
        except Exception as e:
            logger.error(f"Failed to execute SQL dump: {e}")
            raise e

        # Reset search path
        conn.execute(text("SET search_path TO public"))

    # --- BLOCK 2: Verify & Content Hashing ---
    should_skip = False
    metadata = MetaData()
    if status_callback:
        status_callback("Verifying SQL dump", False)
    with engine.connect() as conn:
        with conn.begin():  # Ensure transaction for server-side cursor
            try:
                metadata.reflect(
                    bind=conn, schema=staging_schema, only=[dump_table_name]
                )
                metadata.reflect(bind=conn, schema="public", only=["user_metadata"])
            except Exception as e:
                logger.error(f"Reflection failed: {e}")
                raise RuntimeError("Could not reflect tables.")

            staging_tbl = metadata.tables.get(f"{staging_schema}.{dump_table_name}")
            target_tbl = metadata.tables.get("public.user_metadata")

            if staging_tbl is None or target_tbl is None:
                raise RuntimeError("Staging or Target table not found.")

            # Prepare Mapping for Hashing
            staging_columns = [c.name for c in staging_tbl.columns]
            column_mapping = {}
            for col_name in staging_columns:
                snake_name = camel_to_snake(col_name)
                if snake_name in target_tbl.columns:
                    column_mapping[col_name] = snake_name
                elif col_name in target_tbl.columns:
                    column_mapping[col_name] = col_name

            # --- OPTIMIZATION: Content Hashing ---
            if status_callback:
                status_callback("Content Hashing", completed=False)
            hash_exclude_cols = [
                "exportTimestamp",
                "export_timestamp",
                "timestamp",
                "last_updated_job_id",
            ]
            hash_check_columns = []
            sorted_col_keys = sorted(column_mapping.keys())

            for col_name in sorted_col_keys:
                target_name = column_mapping[col_name]
                if any(ex in col_name for ex in hash_exclude_cols) or any(
                    ex in target_name for ex in hash_exclude_cols
                ):
                    continue
                hash_check_columns.append(staging_tbl.c[col_name])

            if not hash_check_columns:
                hash_check_columns = [c for c in staging_tbl.c]

            # Compute Hash
            import hashlib

            staging_pk = "service_id" if "service_id" in staging_tbl.c else "serviceId"
            hash_query = select(*hash_check_columns).order_by(staging_tbl.c[staging_pk])

            logger.info("Computing Content Hash (excluding timestamps)...")
            content_hash = hashlib.sha256()

            # Run in stream (Transaction active)
            hash_proxy = conn.execution_options(stream_results=True).execute(hash_query)

            for row in hash_proxy:
                row_str = "".join([str(val) for val in row])
                content_hash.update(row_str.encode("utf-8"))

            current_hash_hex = content_hash.hexdigest()
            logger.info(f"Computed Hash: {current_hash_hex}")

            # Compare
            if job_id:
                from app.db.schemas.ingestion_models import IngestionJob

                prev_job_query = text(
                    """
                    SELECT content_hash FROM ingestion_jobs 
                    WHERE ingestion_type = 'users' 
                    AND status = 'completed' 
                    AND id < :jid 
                    AND content_hash IS NOT NULL 
                    ORDER BY id DESC LIMIT 1
                """
                )
                prev_hash_res = conn.execute(prev_job_query, {"jid": job_id}).fetchone()

                if prev_hash_res and prev_hash_res[0] == current_hash_hex:
                    logger.info("Content Hash matches previous job. Data unchanged.")
                    should_skip = True
            if status_callback:
                status_callback("Content Hashing", completed=True)

    # 4. Update Job Hash (Separate Transaction)
    if status_callback:
        status_callback("Updating Job Hash", False)
    if job_id:
        with engine.begin() as update_conn:
            update_conn.execute(
                text("UPDATE ingestion_jobs SET content_hash = :h WHERE id = :jid"),
                {"h": current_hash_hex, "jid": job_id},
            )
    if status_callback:
        status_callback("Updating Job Hash", True)
    if status_callback:
        status_callback("Checking if data is unchanged", False)
    if should_skip:
        logger.info("Skipping Upsert and subsequent steps.")
        return IngestionResult(total_records, 0, 0, staging_schema, skipped=True)

    # --- BLOCK 3: Upsert ---
    inserted_or_updated = 0
    with engine.begin() as conn:
        # C. Reflection (Re-reflect for Block 3 context)
        metadata = MetaData()
        metadata.reflect(bind=conn, schema=staging_schema, only=[dump_table_name])
        metadata.reflect(bind=conn, schema="public", only=["user_metadata"])

        staging_tbl = metadata.tables.get(f"{staging_schema}.{dump_table_name}")
        target_tbl = metadata.tables.get(f"public.user_metadata")

        if staging_tbl is None or target_tbl is None:
            raise RuntimeError("Staging or Target table not found during Upsert phase.")

        # D. Map Columns
        staging_columns = [c.name for c in staging_tbl.columns]
        column_mapping = {}
        for col_name in staging_columns:
            snake_name = camel_to_snake(col_name)
            if snake_name in target_tbl.columns:
                column_mapping[col_name] = snake_name
            elif col_name in target_tbl.columns:
                column_mapping[col_name] = col_name

        pk_camel = "serviceId"
        if pk_camel not in staging_columns and "service_id" in staging_columns:
            pk_camel = "service_id"

        if pk_camel not in column_mapping:
            raise ValueError(
                f"Primary Key ({pk_camel}) could not be mapped to target table."
            )

        pk_target_name = column_mapping[pk_camel]

        sel_columns = []
        target_column_names = []
        for col_name, target_name in column_mapping.items():
            col_obj = staging_tbl.c[col_name]
            target_col = target_tbl.columns[target_name]

            # Check for casting (BigInt -> DateTime)
            if str(target_col.type).startswith("DATETIME") or str(
                target_col.type
            ).startswith("TIMESTAMP"):
                sel_columns.append(
                    case(
                        (col_obj > 100000000000, func.to_timestamp(col_obj / 1000.0)),
                        else_=func.to_timestamp(col_obj),
                    ).label(target_name)
                )
            else:
                sel_columns.append(col_obj.label(target_name))

            target_column_names.append(target_name)

        # Inject job_id and snapshot_hash
        if job_id is not None and "last_updated_job_id" in target_tbl.columns:
            sel_columns.append(literal(job_id).label("last_updated_job_id"))
            target_column_names.append("last_updated_job_id")

        # Re-derive hash_check_columns for Block 3 context to avoid Alias duplication
        # We must use the 'staging_tbl' from THIS block, not the previous one.
        hash_check_columns_b3 = []
        hash_exclude_cols = [
            "exportTimestamp",
            "export_timestamp",
            "timestamp",
            "last_updated_job_id",
        ]
        sorted_col_keys = sorted(column_mapping.keys())

        for col_name in sorted_col_keys:
            target_name = column_mapping[col_name]
            if any(ex in col_name for ex in hash_exclude_cols) or any(
                ex in target_name for ex in hash_exclude_cols
            ):
                continue
            hash_check_columns_b3.append(staging_tbl.c[col_name])

        if not hash_check_columns_b3:
            hash_check_columns_b3 = [c for c in staging_tbl.c]

        # Calculate snapshot_hash for persistent change detection
        # We use the same columns as the previous manual diff logic
        hash_exprs = []
        for col_obj in hash_check_columns_b3:
            hash_exprs.append(func.coalesce(col_obj.cast(Text), literal("")))
            hash_exprs.append(literal("|"))

        # Combine and hash using pgcrypto digest
        if hash_exprs:
            # Remove last separator
            hash_exprs.pop()
            combined_text = hash_exprs[0]
            for i in range(1, len(hash_exprs)):
                combined_text = combined_text + hash_exprs[i]

            sel_columns.append(
                func.digest(combined_text, "sha256").label("snapshot_hash")
            )
            target_column_names.append("snapshot_hash")

        # Ensure pgcrypto extension is available for digest()
        if status_callback:
            status_callback("Ensuring hashing extension is available", False)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

        sel_stmt = select(*sel_columns)

        # Filter out users in the exclusion list (prevents re-ingestion of deleted users)
        try:
            exclusion_check = text(
                f"SELECT service_id FROM user_exclusion_list"
            )
            exclusion_result = conn.execute(exclusion_check)
            excluded_ids = [row[0] for row in exclusion_result]
            if excluded_ids and pk_camel in [c.name for c in staging_tbl.columns]:
                sel_stmt = sel_stmt.where(
                    ~staging_tbl.c[pk_camel].in_(excluded_ids)
                )
                if db_log:
                    db_log(f"Excluding {len(excluded_ids)} users from ingestion (exclusion list)")
                logger.info(f"Excluding {len(excluded_ids)} users from ingestion (exclusion list)")
        except Exception as e:
            # Table may not exist yet on first run
            logger.warning(f"Could not check exclusion list (may not exist yet): {e}")

        # E. Adaptive Merge Strategy
        # Check for Unique Constraint on PK
        if status_callback:
            status_callback("Checking for unique constraints", False)
        inspector = inspect(conn)
        unique_constraints = inspector.get_unique_constraints(
            "user_metadata", schema="public"
        )
        pk_constraint = inspector.get_pk_constraint("user_metadata", schema="public")

        has_unique_index = False
        if pk_constraint and pk_constraint.get("constrained_columns") == [
            pk_target_name
        ]:
            has_unique_index = True
        if not has_unique_index:
            for uc in unique_constraints:
                if uc.get("column_names") == [pk_target_name]:
                    has_unique_index = True
                    break

        # Force assumption for service_id if not detected (common introspection issue)
        if not has_unique_index and pk_target_name == "service_id":
            logger.info("Forcing Unique Constraint check for service_id.")
            has_unique_index = True

        if has_unique_index:
            # OPTION A: ON CONFLICT
            logger.info(
                f"Unique constraint found on {pk_target_name}. Using ON CONFLICT Upsert."
            )
            insert_stmt = pg_insert(target_tbl).from_select(
                target_column_names, sel_stmt
            )

            update_set = {}
            for col_name in target_column_names:
                if col_name == pk_target_name:
                    continue
                if col_name == "is_active":
                    continue  # Never overwrite is_active during ingestion
                update_set[col_name] = insert_stmt.excluded[col_name]

            # 2. Timestamp Condition (REMOVED for Incremental Indexing efficiency)
            # We do NOT want to update the row if only the 'export_timestamp' changed.
            # This would trigger re-indexing of all users every run.
            # Only update if meaningful content changed.

            # 3. Content Change Detection
            # Update ONLY if at least one column (excluding metadata/timestamps) has changed
            logger.info("Using Content-Diff optimization (ignoring timestamp changes).")

            # Columns to exclude from triggering an update
            # 'last_updated_job_id' is handled separately but good to include for safety
            trigger_exclude_cols = [
                "last_updated_job_id",
                "export_timestamp",
                "exportTimestamp",
                "timestamp",
            ]

            change_checks = []
            for split_col in update_set.keys():
                # Skip excluded columns
                if split_col in trigger_exclude_cols:
                    continue

                # Double check mapping to avoid edge case names
                if any(ex == split_col for ex in trigger_exclude_cols):
                    continue

                # IS DISTINCT FROM handles NULL vs Value comparisons correctly
                # FIX: We want to treat NULL and "" as identical to match snapshot_hash logic.
                # If we don't, we update metadata (and index) for no "real" change.
                val_excluded = func.coalesce(
                    insert_stmt.excluded[split_col].cast(Text), literal("")
                )
                val_existing = func.coalesce(
                    target_tbl.c[split_col].cast(Text), literal("")
                )

                change_checks.append(val_excluded != val_existing)

            if change_checks:
                update_condition = or_(*change_checks)
            else:
                # No columns to update? (Only PK and JobID?)
                # Prevent update of JobID alone
                update_condition = text("false")

            # Stale Data Protection: Only update if incoming export_timestamp is >= existing
            update_condition = and_(
                update_condition,
                insert_stmt.excluded.export_timestamp >= target_tbl.c.export_timestamp,
            )

            if status_callback:
                status_callback("Executing Upsert", False)
            if update_set:
                final_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[pk_target_name],
                    set_=update_set,
                    where=update_condition,
                ).returning(target_tbl.c.id)
            else:
                final_stmt = insert_stmt.on_conflict_do_nothing(
                    index_elements=[pk_target_name]
                ).returning(target_tbl.c.id)
            result = conn.execute(final_stmt)
            rows = result.fetchall()
            inserted_or_updated = len(rows)
            # upserted_ids = [r.id for r in rows]
            if status_callback:
                status_callback("Executing Upsert", True)
                status_callback(
                    f"Upsert complete. Rowcount: {inserted_or_updated}", True
                )
                db_log(f"Upsert complete. Rowcount: {inserted_or_updated}")
            logger.info(f"Upsert complete. Rowcount: {inserted_or_updated}")

        else:
            # FATAL ERROR: No Unique Constraint
            msg = (
                f"CRITICAL: No unique constraint found on '{pk_target_name}' in table 'user_metadata'. "
                "Cannot perform safe Upsert. Aborting to prevent data corruption. "
                "Please run 'scripts/fix_constraints.py' to fix the database schema."
            )
            db_log(msg, level="ERROR")
            logger.error(msg)
            raise RuntimeError(msg)

        # Cleanup
        # if cleanup:
        #    if status_callback:
        #        status_callback("cleanup")
        #    conn.execute(text(f"DROP SCHEMA {staging_schema} CASCADE"))
        #    logger.info(f"Schema {staging_schema} dropped.")

    duplicates = max(0, total_records - inserted_or_updated)
    db_log(f"Duplicates: {duplicates}", level="INFO")
    logger.info(f"Duplicates: {duplicates}")
    return IngestionResult(
        total_records, inserted_or_updated, duplicates, staging_schema, skipped=False
    )
