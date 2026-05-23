import os
from typing import List
from fastapi import HTTPException
from app.core.logging import logger


class LogsController:
    LOG_DIR = "logs"

    @classmethod
    def get_logs(cls, log_type: str, lines: int = 100) -> List[str]:
        """
        Reads the last N lines from the specified log file.
        log_type: "app" or "celery"
        """
        if log_type == "app":
            filename = "app.log"
        elif log_type == "celery":
            filename = "celery.log"
        else:
            raise HTTPException(status_code=400, detail="Invalid log type")

        file_path = os.path.join(cls.LOG_DIR, filename)

        if not os.path.exists(file_path):
            logger.warning(f"Log file not found: {file_path}")
            return []

        try:
            # Efficiently read last N lines
            # For simplicity, reading all and slicing. For huge logs, 'seek' is better.
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            logger.error(f"Error reading log file {filename}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to read logs")
