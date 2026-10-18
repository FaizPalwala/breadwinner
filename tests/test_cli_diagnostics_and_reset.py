"""Functional tests for Breadwinner CLI storage diagnostics, canonical resolution, and reset operations."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from breadwinner.cli import main
from breadwinner.config import get_breadwinner_home, settings
from breadwinner.core.models import CandidateProfile, WorkExperience
from breadwinner.core.pantry import PantryManager
from breadwinner.db.repository import JobRecord, JobRepository


def test_canonical_home_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that BREADWINNER_HOME environment variable takes absolute precedence."""
    custom_home = tmp_path / "custom_breadwinner_home"
    monkeypatch.setenv("BREADWINNER_HOME", str(custom_home))

    resolved = get_breadwinner_home()
    assert resolved == custom_home
    assert resolved.exists()


def test_cli_where_diagnostic(tmp_path: Path):
    """Verify that 'breadwinner where' outputs a diagnostic report of storage paths."""
    runner = CliRunner()
    result = runner.invoke(main, ["where"])
    assert result.exit_code == 0
    assert "Breadwinner Storage & Environment Map" in result.output
    assert "Breadwinner Home" in result.output
    assert "Career Pantry" in result.output
    assert "Tracking Database" in result.output


def test_cli_pantry_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that 'breadwinner pantry clear -y' wipes profile and context."""
    test_pantry = tmp_path / "pantry"
    test_pantry.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "pantry_dir", test_pantry)

    pantry = PantryManager(test_pantry)
    profile = CandidateProfile(
        full_name="Ada Lovelace",
        title="Mathematician",
        summary="Analytical Engine Programmer",
        experiences=[
            WorkExperience(company="Babbage Labs", role="Analyst", start_date="1842", bullets=["Drafted algorithm"])
        ]
    )
    pantry.save_pantry(profile, context="Must focus on analytical algorithms.")
    assert pantry.is_initialized()

    runner = CliRunner()
    result = runner.invoke(main, ["pantry", "clear", "-y"])
    assert result.exit_code == 0
    assert "cleared successfully" in result.output
    assert not pantry.is_initialized()


def test_cli_reset_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that 'breadwinner reset --all -y' wipes pantry, database, applications, and personas."""
    test_pantry = tmp_path / "pantry"
    test_apps = tmp_path / "applications"
    test_db = tmp_path / "data" / "tracker.db"
    test_pantry.mkdir(parents=True, exist_ok=True)
    test_apps.mkdir(parents=True, exist_ok=True)
    test_db.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "pantry_dir", test_pantry)
    monkeypatch.setattr(settings, "applications_dir", test_apps)
    monkeypatch.setattr(settings, "database_path", test_db)

    # 1. Populate pantry
    pantry = PantryManager(test_pantry)
    profile = CandidateProfile(full_name="Alan Turing", title="Cryptanalyst")
    pantry.save_pantry(profile)
    assert pantry.is_initialized()

    # 2. Populate db
    repo = JobRepository(test_db)
    repo.upsert_job(JobRecord(
        id="job-1",
        company="Bletchley Park",
        title="Crypto Analyst",
        date_added="1942-01-01"
    ))
    assert test_db.exists()

    # 3. Populate applications dir
    app_folder = test_apps / "2026-10-01_Bletchley"
    app_folder.mkdir(parents=True, exist_ok=True)
    (app_folder / "resume.html").write_text("dummy", encoding="utf-8")
    assert app_folder.exists()

    # Run reset
    runner = CliRunner()
    result = runner.invoke(main, ["reset", "--all", "-y"])
    assert result.exit_code == 0
    assert "Reset operation complete" in result.output

    # Verify everything was wiped
    assert not pantry.is_initialized()
    assert not test_db.exists()
    assert not app_folder.exists()


def test_cli_bake_dual_pdf(tmp_path: Path):
    """Verify that 'breadwinner bake <app_dir>' compiles dual PDFs and reports statuses."""
    from unittest.mock import patch, MagicMock

    app_folder = tmp_path / "2026-10-13_OpenAI_Research"
    app_folder.mkdir(parents=True, exist_ok=True)
    (app_folder / "resume.html").write_text("<html>Resume</html>", encoding="utf-8")
    (app_folder / "cover_letter.md").write_text("Dear OpenAI,\n\nI love AGI safety.", encoding="utf-8")

    resume_json = {"basics": {"name": "Ilya Sutskever", "email": "ilya@example.com"}, "work": []}
    import json
    (app_folder / "resume.json").write_text(json.dumps(resume_json), encoding="utf-8")

    def fake_subprocess_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                pdf_target = Path(arg.split("=", 1)[1])
                pdf_target.write_bytes(b"%PDF-1.4 Mock PDF bytes" * 100)
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock

    runner = CliRunner()
    with patch("breadwinner.core.pdf.find_browser_executable", return_value="/fake/chrome"):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            result = runner.invoke(main, ["bake", str(app_folder)])
            assert result.exit_code == 0
            assert "Fresh out of the oven" in result.output
            assert "Resume PDF" in result.output
            assert "Cover Letter PDF" in result.output
            assert (app_folder / "resume.pdf").exists()
            assert (app_folder / "cover_letter.pdf").exists()


def test_cli_version_flag():
    """Verify that 'breadwinner --version' and 'breadwinner -v' output the pinned version."""
    from breadwinner import __version__
    runner = CliRunner()
    result_long = runner.invoke(main, ["--version"])
    assert result_long.exit_code == 0
    assert f"breadwinner {__version__}" in result_long.output

    result_short = runner.invoke(main, ["-v"])
    assert result_short.exit_code == 0
    assert f"breadwinner {__version__}" in result_short.output
