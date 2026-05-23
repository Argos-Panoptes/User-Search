import os
import socket
import subprocess
from pathlib import Path
from pyspark.sql import SparkSession
from app.core.config import settings
from app.core.logging import logger


def _maybe_use_compatible_java_for_spark() -> None:
    """
    Spark/Hadoop compatibility can break on very new JVMs (e.g. Java 25).
    If SDKMAN has Java 21 installed, prefer it for Spark startup.
    """
    candidates_root = Path("/usr/local/sdkman/candidates/java")
    if not candidates_root.exists():
        _raise_if_incompatible_java_detected()
        return

    java21_candidates = sorted(
        [
            path
            for path in candidates_root.iterdir()
            if path.is_dir() and path.name.startswith("21.")
        ],
        key=lambda p: p.name,
    )
    if not java21_candidates:
        _raise_if_incompatible_java_detected()
        return

    selected_java_home = str(java21_candidates[-1])
    if os.environ.get("JAVA_HOME") == selected_java_home:
        return

    os.environ["JAVA_HOME"] = selected_java_home
    os.environ["SPARK_JAVA_HOME"] = selected_java_home

    java_bin = f"{selected_java_home}/bin"
    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(":") if current_path else []
    if java_bin not in path_entries:
        os.environ["PATH"] = f"{java_bin}:{current_path}" if current_path else java_bin

    logger.info(f"Using Java runtime for Spark: {selected_java_home}")


def _raise_if_incompatible_java_detected() -> None:
    try:
        version_output = subprocess.check_output(
            ["java", "-version"], stderr=subprocess.STDOUT, text=True
        )
    except Exception:
        return

    if 'version "25' in version_output or 'version "24' in version_output:
        raise RuntimeError(
            "Detected Java 24/25 for Spark. Configure JAVA_HOME to Java 21 "
            "(or Java 17) before starting workers."
        )


def get_spark_session(app_name: str = "UserSearchIngestion") -> SparkSession:
    """
    Creates or retrieves a SparkSession configured for local execution.
    Includes dependencies for Postgres and Excel processing if needed.
    """
    # In Docker, Spark workers need to connect back to the driver (this container).
    # We use the container's hostname or IP for spark.driver.host.
    try:
        driver_host = socket.gethostname()
        logger.info(f"Spark Driver Host resolved to: {driver_host}")
    except Exception as e:
        driver_host = "127.0.0.1"
        logger.warning(f"Failed to resolve hostname, falling back to 127.0.0.1: {e}")

    logger.info(
        f"Initializing Spark Session '{app_name}' with master: {settings.SPARK_MASTER_URL}"
    )
    _maybe_use_compatible_java_for_spark()

    builder = (
        SparkSession.builder.appName(app_name)
        .master(settings.SPARK_MASTER_URL)
        .config("spark.driver.host", driver_host)
        .config("spark.driver.bindAddress", "0.0.0.0")
        .config("spark.driver.memory", "1g")
        .config("spark.executor.memory", "1g")
        .config("spark.sql.shuffle.partitions", "4")
        .config(
            "spark.jars.packages",
            "org.postgresql:postgresql:42.7.8",
        )
    )

    try:
        session = builder.getOrCreate()
        logger.info("Spark Session successfully created.")
        return session
    except Exception as e:
        logger.error(f"Failed to create Spark Session: {e}")
        raise
