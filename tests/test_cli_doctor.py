"""Tests for breadwinner doctor CLI command."""

from pathlib import Path
from click.testing import CliRunner
import pytest

from breadwinner.cli import main
from breadwinner.core.logger import LAST_CRASH_FILE


def test_cli_doctor_clean_run():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "BREADWINNER SYSTEM DOCTOR" in result.output
    assert "Platform & Python Environment" in result.output
    assert "Terminal Capabilities & Display" in result.output
    assert "Directory Ledgers & Permissions" in result.output
    assert "Active LLM Provider & Credentials" in result.output
    assert "Crash Diagnostics & Logs" in result.output


def test_cli_doctor_with_crash_log(tmp_path: Path, monkeypatch):
    fake_crash = tmp_path / "last_crash.log"
    fake_crash.write_text("Traceback (most recent call last):\n  File 'test.py', line 1, in <module>\n    raise RuntimeError('Baking failed')", encoding="utf-8")

    monkeypatch.setattr("breadwinner.core.logger.LAST_CRASH_FILE", fake_crash)

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Recent Crash Traceback" in result.output
    assert "RuntimeError('Baking failed')" in result.output


def test_cli_doctor_with_masked_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyDummySecretKey123456")
    monkeypatch.setattr("breadwinner.config.settings.breadwinner_llm_provider", "gemini")

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "AIza...3456" in result.output
    assert "Configured" in result.output
