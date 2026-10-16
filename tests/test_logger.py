"""Tests for breadwinner rotating logger and crash dump recording."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from breadwinner.core.logger import (
    get_logger,
    record_crash,
    LOGS_DIR,
    LOG_FILE,
    LAST_CRASH_FILE,
    CRASH_LOG_HINT,
)


def test_crash_log_hint():
    assert "Crash dump logged to: ~/.breadwinner/logs/last_crash.log" in CRASH_LOG_HINT


def test_get_logger_creates_rotating_handler(tmp_path: Path):
    with patch("breadwinner.core.logger.LOGS_DIR", tmp_path):
        with patch("breadwinner.core.logger.LOG_FILE", tmp_path / "breadwinner.log"):
            logger = get_logger("test_breadwinner_unit")
            assert logger is not None
            logger.info("Test log entry")
            log_file = tmp_path / "breadwinner.log"
            assert log_file.exists()
            assert "Test log entry" in log_file.read_text(encoding="utf-8")


def test_record_crash(tmp_path: Path):
    fake_crash_file = tmp_path / "last_crash.log"
    fake_log_file = tmp_path / "breadwinner.log"

    with patch("breadwinner.core.logger.LOGS_DIR", tmp_path):
        with patch("breadwinner.core.logger.LOG_FILE", fake_log_file):
            with patch("breadwinner.core.logger.LAST_CRASH_FILE", fake_crash_file):
                logger = get_logger("test_crash_logger")
                try:
                    def broken_func():
                        raise ValueError("process() takes no keyword arguments")
                    broken_func()
                except Exception as e:
                    tb = record_crash(e, context="test_worker", logger=logger)

                assert fake_crash_file.exists()
                crash_content = fake_crash_file.read_text(encoding="utf-8")
                assert "ValueError: process() takes no keyword arguments" in crash_content
                assert "broken_func" in crash_content

                assert fake_log_file.exists()
                log_content = fake_log_file.read_text(encoding="utf-8")
                assert "Exception in test_worker" in log_content
                assert "ValueError: process() takes no keyword arguments" in log_content
