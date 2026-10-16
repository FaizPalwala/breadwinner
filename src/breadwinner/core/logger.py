"""Breadwinner structured file logging and crash dump recording."""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import traceback
from typing import Optional, Union


LOGS_DIR = Path.home() / ".breadwinner" / "logs"
LOG_FILE = LOGS_DIR / "breadwinner.log"
LAST_CRASH_FILE = LOGS_DIR / "last_crash.log"
CRASH_LOG_HINT = "Crash dump logged to: ~/.breadwinner/logs/last_crash.log"

_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_MAX_BYTES = 2 * 1024 * 1024  # 2MB
_BACKUP_COUNT = 3


def ensure_logs_dir() -> Path:
    """Ensure ~/.breadwinner/logs exists and return its path."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def get_logger(name: str = "breadwinner") -> logging.Logger:
    """Return a configured logger with a rotating file handler."""
    logger = logging.getLogger(name)

    # Avoid adding multiple handlers if already configured
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return logger

    logger.setLevel(logging.DEBUG)

    try:
        ensure_logs_dir()
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    except Exception:
        # Graceful fallback to null handler if filesystem is restricted
        logger.addHandler(logging.NullHandler())

    return logger


def record_crash(
    exc: Union[Exception, str],
    context: str = "",
    logger: Optional[logging.Logger] = None
) -> str:
    """Record an unhandled exception or crash to breadwinner.log and last_crash.log.

    Returns the formatted traceback string.
    """
    active_logger = logger or get_logger("breadwinner.crash")
    formatted_tb = traceback.format_exc()
    if not formatted_tb or formatted_tb.strip() == "NoneType: None":
        formatted_tb = str(exc)

    log_entry = f"Exception in {context}: {exc}\n{formatted_tb}" if context else f"Exception: {exc}\n{formatted_tb}"
    active_logger.error(log_entry)

    try:
        ensure_logs_dir()
        LAST_CRASH_FILE.write_text(formatted_tb, encoding="utf-8")
    except Exception:
        pass

    return formatted_tb
