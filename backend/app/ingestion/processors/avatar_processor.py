import logging
import uuid
from pyspark.sql.functions import (
    col,
    split,
    element_at,
    regexp_extract,
    to_timestamp,
    row_number,
    lit,
    when,
    concat,
    coalesce,
    sha2,
)
from pyspark.sql.window import Window
from app.ingestion.spark_session import get_spark_session
from app.core.config import settings
from sqlalchemy.engine.url import make_url
from typing import Optional, Callable
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def process_avatar_manifest_spark(
    file_path: str,
    job_id: int | None = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    status_callback: Optional[Callable[..., None]] = None,
):
    """
    Process Avatar Manifest (JSON) using Spark.
    Strategy: Spark Read -> Filter -> Parse -> Deduplicate -> JDBC Staging -> SQL Upsert -> Link to Users
    """
    if status_callback:
        status_callback("Initializing Spark Session", False)

    spark = get_spark_session()

    if progress_callback:
        progress_callback(5.0)

    logger.info(f"Processing Avatar Manifest: {file_path}")

    try:
        # 1. Read JSON
        if status_callback:
            status_callback("Reading Manifest", False)

        df = spark.read.option("multiline", "true").json(file_path)

        if progress_callback:
            progress_callback(15.0)

        if status_callback:
            status_callback("Reading Manifest", True)

        # 2. Extract Filename & Filter
        if status_callback:
            status_callback("Filtering & Parsing", False)

        df_clean = (
            df.withColumn("filename", element_at(split(col("Key"), "/"), -1))
            .filter(~col("filename").startswith("."))
            .filter(~col("filename").startswith("._"))
        )

        if progress_callback:
            progress_callback(30.0)

        # 3. Regex Parsing
        df_parsed = (
            df_clean.withColumn(
                "service_id", regexp_extract(col("filename"), "^([^_]+)_", 1)
            )
            .withColumn(
                "timestamp_str",
                regexp_extract(col("filename"), "_([0-9]+)\\.[^.]+$", 1),
            )
            .withColumn(
                "profile_name",
                regexp_extract(col("filename"), "^[^_]+_(.+)_[0-9]+\\.[^.]+$", 1),
            )
            .withColumn("s3_url", col("URL"))
            .withColumn("s3_key", col("Key"))
            .withColumn("file_size", col("Size"))
        )

        df_typed = df_parsed.withColumn(
            "timestamp",
            to_timestamp(
                when(col("timestamp_str") == "", None)
                .otherwise(col("timestamp_str"))
                .cast("long")
            ),
        )

        # 4. Deduplication
        windowSpec = Window.partitionBy("service_id").orderBy(col("timestamp").desc())

        df_dedup = (
            df_typed.withColumn("row_num", row_number().over(windowSpec))
            .filter(col("row_num") == 1)
            .drop("row_num")
        )

        # 5. Write to DB (Avatars Table)
        db_url = make_url(settings.DATABASE_URL)
        jdbc_url = f"jdbc:postgresql://{db_url.host}:{db_url.port}/{db_url.database}"
        properties = {
            "user": db_url.username,
            "password": db_url.password,
            "driver": "org.postgresql.Driver",
        }

        logger.info("Writing Avatars to DB...")

        if status_callback:
            status_callback("Filtering & Parsing", True)
            status_callback("Upserting Avatars", False)

        unique_suffix = str(uuid.uuid4()).replace("-", "")[:8]
        staging_table = f"staging_avatars_{unique_suffix}"

        df_final = df_dedup
        if job_id:
            df_final = df_final.withColumn("last_updated_job_id", lit(job_id))
        else:
            df_final = df_final.withColumn("last_updated_job_id", lit(None).cast("int"))

        # --- Pre-calculate snapshot_hash in Spark ---
        df_final = df_final.withColumn(
            "snapshot_hash",
            sha2(
                concat(
                    col("s3_key"),
                    lit("|"),
                    coalesce(col("filename"), lit("")),
                    lit("|"),
                    col("file_size").cast("string"),
                ),
                256,
            ),
        )

        df_final.select(
            "service_id",
            "s3_key",
            "s3_url",
            "filename",
            "file_size",
            "timestamp",
            "last_updated_job_id",
            "snapshot_hash",
        ).write.jdbc(
            url=jdbc_url, table=staging_table, mode="overwrite", properties=properties
        )

        if progress_callback:
            progress_callback(80.0)

        # 6. SQL Upsert & Link to Users
        engine = create_engine(settings.DATABASE_URL)

        with engine.begin() as conn:
            logger.info("Performing SQL Upsert for Avatars...")

            # Use pre-calculated snapshot_hash from Spark (hex string -> BYTEA)
            upsert_query = text(
                f"""
                INSERT INTO avatars (
                    service_id, s3_key, s3_url, filename, file_size, timestamp, last_updated_job_id, snapshot_hash
                )
                SELECT 
                    service_id, s3_key, s3_url, filename, file_size, timestamp, last_updated_job_id,
                    DECODE(snapshot_hash, 'hex')
                FROM {staging_table} s
                ON CONFLICT (s3_key) DO UPDATE SET
                    last_updated_job_id = EXCLUDED.last_updated_job_id,
                    snapshot_hash = EXCLUDED.snapshot_hash
            """
            )

            conn.execute(upsert_query)

            if status_callback:
                status_callback("Upserting Avatars", True)
                status_callback("Linking Users", False)

            logger.info("Updating UserMetadata with latest Avatar IDs...")

            update_users_query = text(
                """
                UPDATE user_metadata u
                SET avatar_id = a.id,
                    last_updated_job_id = :job_id
                FROM (
                    SELECT DISTINCT ON (service_id) id, service_id
                    FROM avatars
                    ORDER BY service_id, timestamp DESC
                ) a
                WHERE u.service_id = a.service_id
                AND (u.avatar_id IS DISTINCT FROM a.id) -- Only update if changed
            """
            )
            conn.execute(update_users_query, {"job_id": job_id})

            # Drop Staging
            conn.execute(text(f"DROP TABLE IF EXISTS {staging_table}"))

        logger.info("Avatar Processing Complete.")

        if progress_callback:
            progress_callback(100.0)

        if status_callback:
            status_callback("Linking Users", True)

        return df_dedup.count()

    finally:
        try:
            spark.stop()
            logger.info("Spark Session stopped.")
        except Exception as e:
            logger.warning(f"Failed to stop Spark Session: {e}")
