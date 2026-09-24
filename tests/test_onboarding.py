"""Unit tests for onboarding wizard and starter portfolio generator."""

import json
from pathlib import Path
from unittest.mock import patch

from breadwinner.onboarding import initialize_starter_portfolio, run_setup_wizard


def test_initialize_starter_portfolio(tmp_path: Path):
    target_dir = tmp_path / "portfolio"
    resume_file = initialize_starter_portfolio(target_dir)

    assert resume_file.exists()
    data = json.loads(resume_file.read_text(encoding="utf-8"))
    assert "basics" in data
    assert "work" in data
    assert len(data["work"]) > 0
    assert data["basics"]["name"] == "Alex Taylor"


def test_run_setup_wizard_mocked(tmp_path: Path):
    env_file = tmp_path / ".env"
    portfolio_dir = tmp_path / "my_portfolio"
    initialize_starter_portfolio(portfolio_dir)

    # Prompt sequence:
    # 1. portfolio_input -> str(portfolio_dir)
    # 2. engine choice -> "6" (offline mock)
    inputs = [str(portfolio_dir), "6"]

    with patch("rich.prompt.Confirm.ask", return_value=False):
        with patch("rich.prompt.Prompt.ask", side_effect=inputs):
            success = run_setup_wizard(env_file_path=env_file)
            assert success is True
            assert env_file.exists()

            content = env_file.read_text(encoding="utf-8")
            assert 'BREADWINNER_LLM_PROVIDER="mock"' in content
            assert f'PORTFOLIO_PATH="{portfolio_dir}"' in content
