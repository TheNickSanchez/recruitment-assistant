"""Stdlib logging for the FastAPI + CrewAI process (stdout + optional file).

Does not change agent/task behavior. Log messages are secret-redacted.
File output shares the adapter log directory with per-run JSONL traces.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.trace_log import LOG_DIR

LOGGER_NAME = "recruitment"
APP_LOG_FILE = LOG_DIR / "app.log"

_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|(?i:api[_-]?key)\s*[=:]\s*\S+)",
)

_configured = False


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def log_level() -> int:
    name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, name, logging.INFO)


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_PATTERN.sub("[REDACTED]", str(record.msg))
        if record.args:
            record.args = tuple(
                _SECRET_PATTERN.sub("[REDACTED]", str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def configure_logging() -> logging.Logger:
    """Idempotent: stdout always; rotating app.log when LOG_TO_FILE is not false."""
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(log_level())
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    redact = _RedactFilter()

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    stdout.addFilter(redact)
    logger.addHandler(stdout)

    if env_flag("LOG_TO_FILE", default=True):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            APP_LOG_FILE,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redact)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(suffix: str = "") -> logging.Logger:
    name = LOGGER_NAME if not suffix else f"{LOGGER_NAME}.{suffix}"
    return logging.getLogger(name)
