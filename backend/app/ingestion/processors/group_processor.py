import json
import uuid
import pandas as pd
import os
import shutil
from typing import Callable, Any


import pyspark.sql.functions as F

from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.ingestion.spark_session import get_spark_session
from app.core.logging import logger


def process_group_data(
    file_path: str,
    job_id: int | None = None,
    progress_callback: Callable[[float], None] | None = None,
    status_callback: Callable[[str, bool], None] | None = None,
) -> int:
    """
    Process Group Data (CSV or Excel .xlsx).
    Strategy: Pandas Read -> Spark Normalize -> Postgres Staging Table -> SQL Upsert -> Drop Staging
    """
    if status_callback:
        status_callback("Initializing Spark Session", False)

    spark = get_spark_session()

    if progress_callback:
        progress_callback(5.0)

    logger.info(f"Reading group data from {file_path}")
    if status_callback:
        status_callback("Reading Source File", True)  # Mark previous step as completed
        status_callback("Loading Data", False)

    # --- Support CSV or XLSX ---
    if file_path.lower().endswith(".csv"):
        pdf = pd.read_csv(file_path)
    else:
        pdf = pd.read_excel(file_path, engine="openpyxl")

    if progress_callback:
        progress_callback(15.0)

    # 1.5 Sanitize Data for Parquet/Arrow compatibility
    for col_name in pdf.columns:
        if pdf[col_name].dtype == "object":
            pdf[col_name] = pdf[col_name].apply(
                lambda x: str(x) if pd.notnull(x) else None
            )

    # 2. Convert to Parquet (Intermediate)
    parquet_path = file_path + ".temp.parquet"
    pdf.to_parquet(parquet_path, engine="pyarrow", index=False)

    if status_callback:
        status_callback("Reading Source File", True)
        status_callback("Data Normalization", False)

    try:
        # 3. Read Parquet with Spark
        df = spark.read.parquet(parquet_path)
        if progress_callback:
            progress_callback(25.0)

        # 1. Normalize Columns with Case-Insensitivity
        # We normalize columns (lowercase, remove spaces/underscores) to match target internal names
        target_mappings = {
            "group_id": ["groupid", "group_id", "group id"],
            "group_name": ["groupname", "group_name", "group name"],
            "number_of_members": [
                "numberofmembers",
                "number_of_members",
                "number of members",
                "membercount",
            ],
            "admin_approval_required": [
                "adminapprovalrequired",
                "admin_approval_required",
                "admin approval required",
                "accesstype",
            ],
            "group_link": ["grouplink", "group_link", "group link"],
            "reconstructed_link": [
                "reconstructedlink",
                "reconstructed_link",
                "reconstructed link",
            ],
            "description": ["description"],
            "retention_period": [
                "retentionperiod",
                "retention_period",
                "retention period",
            ],
            "master_key": ["masterkey", "master_key", "master key"],
            "invite_link_password": [
                "invitelinkpassword",
                "invite_link_password",
                "invite link password",
            ],
            "secret_params": ["secretparams", "secret_params", "secret params"],
            "public_params": ["publicparams", "public_params", "public params"],
            "export_timestamp": [
                "exporttimestamp",
                "export_timestamp",
                "export timestamp",
            ],
        }

        # Helper to normalize for fuzzy matching
        def normalize_col(c: str) -> str:
            return c.lower().replace(" ", "").replace("_", "")

        found_columns = {}
        for actual_col in df.columns:
            norm_actual = normalize_col(actual_col)
            for internal_name, variations in target_mappings.items():
                # Check if normalized actual matches normalized variations
                if any(normalize_col(v) == norm_actual for v in variations):
                    found_columns[internal_name] = actual_col
                    break

        # Check for Mandatory Columns
        mandatory = ["group_id", "group_name"]
        missing_mandatory = [m for m in mandatory if m not in found_columns]

        if missing_mandatory:
            error_msg = f"Missing mandatory columns: {', '.join(missing_mandatory)}. Please ensure the file contains valid group data."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Rename columns to internal names
        for internal_name, actual_col in found_columns.items():
            if internal_name != actual_col:
                df = df.withColumnRenamed(actual_col, internal_name)

        # Ensure all required columns exist before processing with correct types
        column_types = {
            "group_id": "string",
            "group_name": "string",
            "number_of_members": "integer",
            "admin_approval_required": "string",
            "group_link": "string",
            "reconstructed_link": "string",
            "description": "string",
            "retention_period": "string",
            "master_key": "string",
            "invite_link_password": "string",
            "secret_params": "string",
            "public_params": "string",
            "export_timestamp": "timestamp",
            "last_updated_job_id": "integer",
        }

        for col_name, col_type in column_types.items():
            if col_name not in df.columns:
                df = df.withColumn(col_name, F.lit(None).cast(col_type))
            else:
                # Always cast to intended type to avoid inference issues (like string "10" for integer)
                df = df.withColumn(col_name, F.col(col_name).cast(col_type))

        # 1.5 Convert admin_approval_required to Boolean
        # Cast to string first to handle mixed types (e.g. excel boolean vs string) safely
        df_clean = df.withColumn(
            "admin_approval_required_str",
            F.col("admin_approval_required").cast("string"),
        )

        df = (
            df_clean.withColumn(
                "admin_approval_required_val",
                F.when(
                    F.lower(F.trim(F.col("admin_approval_required_str"))) == "yes",
                    F.lit(True),
                )
                .when(
                    F.lower(F.trim(F.col("admin_approval_required_str"))) == "no",
                    F.lit(False),
                )
                .when(
                    F.lower(F.trim(F.col("admin_approval_required_str"))) == "true",
                    F.lit(True),
                )
                .when(
                    F.lower(F.trim(F.col("admin_approval_required_str"))) == "false",
                    F.lit(False),
                )
                .when(
                    F.lower(F.trim(F.col("admin_approval_required_str"))) == "open",
                    F.lit(False),
                )  # "Open" -> No approval needed
                .when(
                    F.lower(F.trim(F.col("admin_approval_required_str")))
                    == "approval required",
                    F.lit(True),
                )  # "Approval Required" -> Yes
                .otherwise(None),
            )
            .drop("admin_approval_required", "admin_approval_required_str")
            .withColumnRenamed("admin_approval_required_val", "admin_approval_required")
        )

        # 1.6 Link Validation using native Spark functions
        # Check if link starts with http:// or https:// (case-insensitive rlike)
        link_pattern = r"^(?i)https?://.+"

        # Trim important fields to avoid regex mismatch or dirty data
        df = (
            df.withColumn("group_link", F.trim(F.col("group_link")))
            .withColumn("reconstructed_link", F.trim(F.col("reconstructed_link")))
            .withColumn("group_id", F.trim(F.col("group_id")))
            .withColumn("group_name", F.trim(F.col("group_name")))
        )

        # 1.6.1 Filter out rows with null or empty group_id to prevent NotNullViolation
        df = df.filter(
            (F.col("group_id").isNotNull()) & (F.trim(F.col("group_id")) != "")
        )

        df = df.withColumn(
            "group_link",
            F.when(
                F.col("group_link").rlike(link_pattern), F.col("group_link")
            ).otherwise(None),
        ).withColumn(
            "reconstructed_link",
            F.when(
                F.col("reconstructed_link").rlike(link_pattern),
                F.col("reconstructed_link"),
            ).otherwise(None),
        )

        # 1.6.2 Convert export_timestamp (similar to user processor)
        df = df.withColumn(
            "export_timestamp",
            F.when(
                F.col("export_timestamp").cast("double") > 100000000000,
                F.to_timestamp(F.col("export_timestamp").cast("double") / 1000.0),
            ).otherwise(F.to_timestamp(F.col("export_timestamp").cast("double"))),
        )

        if job_id:
            df = df.withColumn("last_updated_job_id", F.lit(job_id))

        # Select final columns to ensure order/existence
        sel_cols = [
            "group_id",
            "group_name",
            "number_of_members",
            "admin_approval_required",
            "group_link",
            "reconstructed_link",
            "description",
            "retention_period",
            "master_key",
            "invite_link_password",
            "secret_params",
            "public_params",
            "export_timestamp",
        ]

        if job_id:
            sel_cols.append("last_updated_job_id")

        final_df = df.select(*sel_cols)

        # --- Pre-calculate snapshot_hash in Spark ---
        # This offloads CPU from Postgres and allows workers to do it in parallel.
        hash_cols = [
            F.coalesce(F.col(c).cast("string"), F.lit(""))
            for c in sel_cols
            if c not in ["last_updated_job_id", "snapshot_hash"]
        ]

        # Create a piped string for hashing
        hash_expr = hash_cols[0]
        for c_expr in hash_cols[1:]:
            hash_expr = F.concat(hash_expr, F.lit("|"), c_expr)

        final_df = final_df.withColumn("snapshot_hash", F.sha2(hash_expr, 256))

        if status_callback:
            status_callback("Data Normalization", True)
            status_callback("Writing to Staging", False)

        count = final_df.count()
        logger.info(f"Processed {count} groups. Writing to Staging DB...")

        # 2. Write to Staging Table
        unique_suffix = str(uuid.uuid4()).replace("-", "")[:8]
        staging_table = f"staging_groups_{unique_suffix}"

        from sqlalchemy.engine.url import make_url

        db_url = make_url(settings.DATABASE_URL)
        jdbc_url = f"jdbc:postgresql://{db_url.host}:{db_url.port}/{db_url.database}"

        properties = {
            "user": db_url.username,
            "password": db_url.password,
            "driver": "org.postgresql.Driver",
        }

        final_df.write.jdbc(
            url=jdbc_url, table=staging_table, mode="overwrite", properties=properties
        )

        if progress_callback:
            progress_callback(80.0)

        if status_callback:
            status_callback("Writing to Staging", True)
            status_callback("Upserting to DB", False)

        # 3. SQL Upsert
        logger.info(f"Performing Upsert from {staging_table} to groups...")
        engine = create_engine(settings.DATABASE_URL)

        try:
            with engine.begin() as conn:
                # Construct standard INSERT ... ON CONFLICT ... DO UPDATE
                # Update set: All columns except PK (group_id)
                update_assignments = []
                for c in sel_cols:
                    if c == "group_id":
                        continue
                    update_assignments.append(f'"{c}" = EXCLUDED."{c}"')

                update_clause = ", ".join(update_assignments)

                # Use the pre-calculated snapshot_hash from Spark
                # Note: Spark's sha2 returns a hex string, but Postgres expects BYTEA.
                # We decode the hex string in the SELECT part so that EXCLUDED has BYTEA type.
                columns_to_insert = sel_cols + ["snapshot_hash"]
                cols_csv = ", ".join([f'"{c}"' for c in columns_to_insert])

                # Manual construction of vals_csv to handle the casting
                val_expressions = []
                for c in columns_to_insert:
                    if c == "snapshot_hash":
                        val_expressions.append(f"DECODE(S.\"{c}\", 'hex')")
                    else:
                        val_expressions.append(f'S."{c}"')
                vals_csv = ", ".join(val_expressions)

                upsert_sql = text(
                    f"""
                INSERT INTO public.groups ({cols_csv})
                SELECT {vals_csv}
                FROM public.{staging_table} S
                ON CONFLICT ("group_id") DO UPDATE SET
                {update_clause},
                snapshot_hash = EXCLUDED.snapshot_hash
                WHERE (public.groups.snapshot_hash IS NULL OR public.groups.snapshot_hash IS DISTINCT FROM EXCLUDED.snapshot_hash)
                """
                )

                result = conn.execute(upsert_sql)
                logger.info(f"Upsert complete. Affected rows: {result.rowcount}")

                if progress_callback:
                    progress_callback(95.0)

                if status_callback:
                    status_callback("Upserting to DB", True)

                # 4. Drop Staging
                conn.execute(text(f"DROP TABLE IF EXISTS public.{staging_table}"))

        except Exception as outer_e:
            logger.error(f"Group Upsert failed: {outer_e}")
            # Try to drop staging in case of error
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"DROP TABLE IF EXISTS public.{staging_table}"))
            except Exception as inner_e:
                logger.warning(
                    f"Failed to drop staging table {staging_table}: {inner_e}"
                )
            raise outer_e

        if progress_callback:
            progress_callback(100.0)

        logger.info("Group data ingestion finished successfully.")
        return count

    except Exception as e:
        logger.error(f"Error processing group data: {e}")
        # Re-raise to ensure the job is marked as failed
        raise e

    finally:
        # 5. Stop Spark Session to release resources
        try:
            spark.stop()
            logger.info("Spark Session stopped.")
        except Exception as e:
            logger.warning(f"Failed to stop Spark Session: {e}")

        # Cleanup temporary parquet file
        if os.path.exists(parquet_path):
            try:
                if os.path.isdir(parquet_path):
                    shutil.rmtree(parquet_path)
                else:
                    os.remove(parquet_path)
                logger.info(f"Cleaned up temporary file: {parquet_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {parquet_path}: {e}")


# --- SQL-based Extraction for User Ingestion ---


def extract_groups_from_staging(
    staging_schema: str,
    job_id: int | None = None,
    logger_func: Callable[..., Any] | None = None,
) -> int:
    """
    Extracts group information from user_metadata.groupMemberships column in the staging schema.
    """

    def _default_log(msg, level="INFO", **kwargs):
        if level == "ERROR":
            logger.error(msg)
        elif level == "WARNING":
            logger.warning(msg)
        else:
            logger.info(msg)

    log: Callable[..., Any] = logger_func if logger_func else _default_log
    log("Starting group extraction from staging tables.")

    engine = create_engine(settings.DATABASE_URL)

    groups_map = {}  # groupId -> {name, etc}

    with engine.begin() as conn:
        # Check and Add 'last_updated_job_id' column if missing
        try:
            inspector = inspect(conn)
            columns = [
                c["name"] for c in inspector.get_columns("groups", schema="public")
            ]
            if "last_updated_job_id" not in columns:
                log("Adding missing column 'last_updated_job_id' to groups table.")
                conn.execute(
                    text(
                        'ALTER TABLE public.groups ADD COLUMN "last_updated_job_id" INTEGER'
                    )
                )
        except Exception as e:
            log(f"Column check/add failed: {e}", level="WARNING")

        # 1. Fetch groupMemberships and export_timestamp
        # Assuming table name is known or we inspect. process_sql_dump uses "user_metadata".
        query = text(
            f"""
            SELECT 
                "groupMemberships", 
                CASE 
                    WHEN "exportTimestamp"::double precision > 100000000000 THEN to_timestamp("exportTimestamp"::double precision / 1000.0)
                    ELSE to_timestamp("exportTimestamp"::double precision)
                END as export_timestamp
            FROM {staging_schema}.user_metadata 
            WHERE "groupMemberships" IS NOT NULL
            """
        )
        result = conn.execute(query)

        row_count = 0
        for row in result:
            raw_json = row[0]
            if not raw_json:
                continue

            try:
                # It is stored as a JSON string
                memberships = json.loads(raw_json)
                if memberships:
                    for m in memberships:
                        gid = m.get("groupId")
                        gname = m.get("groupName")
                        # Try to find member count with common keys
                        member_count = (
                            m.get("memberCount")
                            or m.get("numberOfMembers")
                            or m.get("number_of_members")
                        )

                        # Parse Admin Approval
                        # Signal usually sends valid boolean in JSON, but sometimes strings if legacy?
                        # Let's handle both.
                        admin_approval = m.get("adminApprovalRequired")
                        if admin_approval is None:
                            admin_approval = m.get("admin_approval_required")

                        # Convert to strict boolean
                        is_approval_req = None
                        if isinstance(admin_approval, bool):
                            is_approval_req = admin_approval
                        elif isinstance(admin_approval, str):
                            if (
                                admin_approval.lower() == "yes"
                                or admin_approval.lower() == "true"
                            ):
                                is_approval_req = True
                            elif (
                                admin_approval.lower() == "no"
                                or admin_approval.lower() == "false"
                            ):
                                is_approval_req = False

                        if gid:
                            # Deduplicate: Last one wins or first?
                            # Let's just store the name and member count.
                            if gid not in groups_map:
                                groups_map[gid] = {
                                    "group_id": gid,
                                    "group_name": gname,
                                    "number_of_members": member_count,
                                    "admin_approval_required": is_approval_req,
                                    "export_timestamp": row[
                                        1
                                    ],  # row[1] is export_timestamp
                                }
                            else:
                                # Update if we have better data (optional)
                                pass
            except json.JSONDecodeError:
                pass  # Skip bad json

            row_count += 1

        log(f"Scanned {row_count} users. Found {len(groups_map)} unique groups.")

        if not groups_map:
            return 0

        # 2. Upsert into groups table

        metadata = MetaData()
        # Reflect groups table to be sure
        metadata.reflect(bind=conn, schema="public", only=["groups"])
        groups_tbl = metadata.tables.get("public.groups")

        if groups_tbl is None:
            log("Groups table not found. Skipping group insertion.", level="ERROR")
            return 0

        # Check actual column names in DB to handle potential camelCase from Spark
        db_cols = groups_tbl.c.keys()

        # Mappings
        pk_col = "group_id"
        name_col = "group_name"
        members_col = "number_of_members"

        # If DB has camelCase, adjust key mapping for insert
        if "groupId" in db_cols:
            pk_col = "groupId"

        if "groupName" in db_cols:
            name_col = "groupName"

        if "numberOfMembers" in db_cols:
            members_col = "numberOfMembers"
        elif "memberCount" in db_cols:
            members_col = "memberCount"

        approval_col = "admin_approval_required"
        if "adminApprovalRequired" in db_cols:
            approval_col = "adminApprovalRequired"

        # Remap data keys if needed
        # Our groups_map has 'group_id', 'group_name', 'number_of_members'
        final_insert_data = []
        for v in groups_map.values():
            item = {}
            item[pk_col] = v["group_id"]
            item[name_col] = v["group_name"]

            # Only add if not None to avoid overwriting existing data with Nulls?
            # Or always write? Let's write what we have.
            item[members_col] = v["number_of_members"]
            item[approval_col] = v.get("admin_approval_required")

            if job_id is not None and "last_updated_job_id" in db_cols:
                item["last_updated_job_id"] = job_id

            if "export_timestamp" in db_cols:
                item["export_timestamp"] = v.get("export_timestamp")

            final_insert_data.append(item)

        # Calculate snapshot_hash for groups
        hash_keys = [pk_col, name_col, members_col, approval_col]

        # We'll do this in a single query by using a temp table or CTE if it were complex,
        # but for this manual extraction, we can just add the hash to the dict before insert.
        import hashlib

        for item in final_insert_data:
            hash_parts = []
            for k in hash_keys:
                val = item.get(k)
                hash_parts.append(str(val) if val is not None else "")
            combined = "|".join(hash_parts)
            item["snapshot_hash"] = hashlib.sha256(combined.encode("utf-8")).digest()

        stmt = pg_insert(groups_tbl).values(final_insert_data)

        # ON CONFLICT UPDATE
        conflict_set = {name_col: getattr(stmt.excluded, name_col)}
        if members_col in db_cols:
            conflict_set[members_col] = getattr(stmt.excluded, members_col)
        if approval_col in db_cols:
            conflict_set[approval_col] = getattr(stmt.excluded, approval_col)

        if "export_timestamp" in db_cols:
            conflict_set["export_timestamp"] = getattr(
                stmt.excluded, "export_timestamp"
            )

        conflict_set["snapshot_hash"] = stmt.excluded.snapshot_hash

        if (
            job_id is not None
            and "last_updated_job_id" in db_cols
            and "last_updated_job_id" in stmt.excluded
        ):
            conflict_set["last_updated_job_id"] = getattr(
                stmt.excluded, "last_updated_job_id"
            )

        do_update_stmt = stmt.on_conflict_do_update(
            index_elements=[pk_col],
            set_=conflict_set,
            where=(
                groups_tbl.c.snapshot_hash.is_distinct_from(stmt.excluded.snapshot_hash)
            ),
        )

        result = conn.execute(do_update_stmt)
        log(f"Upserted {result.rowcount} groups.")
        return result.rowcount
