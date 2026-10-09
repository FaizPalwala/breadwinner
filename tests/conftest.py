"""Global PyTest fixtures and hermetic environment isolation for Breadwinner."""

import os
import pytest
from pathlib import Path
from breadwinner.config import settings


@pytest.fixture(autouse=True)
def isolate_breadwinner_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Hermetically isolate Breadwinner storage for each test.

    Ensures tests never read or write to ~/.breadwinner, stray CWD pantries, or pollute
    the user's canonical storage.
    """
    test_home = tmp_path / ".breadwinner"
    test_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BREADWINNER_HOME", str(test_home))
    monkeypatch.setattr(settings, "portfolio_path", test_home / "portfolio")
    monkeypatch.setattr(settings, "pantry_dir", test_home / "pantry")
    monkeypatch.setattr(settings, "applications_dir", test_home / "applications")
    monkeypatch.setattr(settings, "database_path", test_home / "tracker.db")
    monkeypatch.setattr(settings, "csv_tracker_path", test_home / "job_tracker.csv")
    monkeypatch.setattr(settings, "user_personas_dir", test_home / "user_personas")
    monkeypatch.setattr(settings, "breadwinner_llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "deepseek_api_key", None)
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "mistral_api_key", None)
    yield test_home
