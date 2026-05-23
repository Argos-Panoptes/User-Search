import logging
import sys
import json
import traceback
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_record["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        return json.dumps(log_record)


class Logger(object):
    _instances = {}

    def __new__(cls, name="user_search", log_file="app.log"):
        if name not in cls._instances:
            instance = super(Logger, cls).__new__(cls)
            instance._initialize_logger(name, log_file)
            cls._instances[name] = instance
        return cls._instances[name]

    def _initialize_logger(self, name, log_filename):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Avoid adding handlers if they already exist
        if not self.logger.handlers:
            # Console Handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(JsonFormatter())
            self.logger.addHandler(console_handler)

            # File Handler (Daily Rotation)
            import os
            from logging.handlers import TimedRotatingFileHandler

            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)

            # Rotate daily at midnight, keep 30 days of logs
            file_handler = TimedRotatingFileHandler(
                os.path.join(log_dir, log_filename),
                when="midnight",
                interval=1,
                backupCount=30,
                encoding="utf-8",
            )
            file_handler.setFormatter(JsonFormatter())
            self.logger.addHandler(file_handler)

    def get_logger_instance(self) -> logging.Logger:
        return self.logger


# Factory functions
def get_logger() -> logging.Logger:
    return Logger(name="user_search", log_file="app.log").get_logger_instance()


def get_celery_logger() -> logging.Logger:
    return Logger(name="celery_worker", log_file="celery.log").get_logger_instance()


# Default logger
logger = get_logger()


# Global entry point
