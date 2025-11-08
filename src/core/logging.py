"""Logging configuration and setup."""

import logging
import json
import os
import warnings
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.config import config


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        base = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        # Include selected extras if present
        extra_fields = (
            "req_id", "endpoint", "src", "tgt", "items", "beam",
            "duration_ms", "queue_wait_ms", "retry_after_sec"
        )
        for field in extra_fields:
            if hasattr(record, field):
                base[field] = getattr(record, field)

        return json.dumps(base, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """Configure logging based on config settings.

    Returns:
        Logger instance for the application
    """
    # Set up base logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    logger = logging.getLogger("app")

    # Optional file logging with rotation
    if config.LOG_TO_FILE:
        try:
            os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
            file_handler = RotatingFileHandler(
                config.LOG_FILE_PATH,
                maxBytes=config.LOG_FILE_MAX_BYTES,
                backupCount=config.LOG_FILE_BACKUP_COUNT
            )

            if config.LOG_FORMAT == "json":
                file_handler.setFormatter(JsonFormatter())
            else:
                file_handler.setFormatter(
                    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
                )

            file_handler.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
            logging.getLogger().addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to set up file logging: {e}")

    # If JSON format requested, set all existing handlers to JSON formatter
    if config.LOG_FORMAT == "json":
        jf = JsonFormatter()
        for handler in logging.getLogger().handlers:
            try:
                handler.setFormatter(jf)
            except Exception:
                pass

    # Silence specific UserWarning about sacremoses
    warnings.filterwarnings("ignore", message=".*sacremoses.*", category=UserWarning)

    return logger


# Global logger instance
logger = setup_logging()
