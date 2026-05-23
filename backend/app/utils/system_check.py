import shutil
import os
from app.core.logging import logger


def get_disk_usage_percent(path: str = "/") -> float:
    """
    Returns the disk usage percentage of the filesystem containing 'path' as a float between 0 and 1.
    On Windows, '/' will typically refer to the drive of the current working directory.
    """
    try:
        # On Windows, path should be a drive or root
        if os.name == "nt":
            # Use current drive if path is /
            if path == "/":
                path = os.path.abspath(os.sep)

        total, used, free = shutil.disk_usage(path)
        percent = used / total
        return percent
    except Exception as e:
        logger.error(f"Failed to get disk usage for {path}: {e}")
        # Default to 0.0 to avoid blocking ingestion if check fails,
        # but in production, one might prefer to fail closed.
        # However, for this requirement, we want to inform if > 90%.
        return 0.0


def is_storage_critical(threshold: float = 0.9, path: str = "/") -> bool:
    """
    Checks if disk usage exceeds the specified threshold.
    """
    return get_disk_usage_percent(path) > threshold
