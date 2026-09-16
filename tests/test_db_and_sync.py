"""Unit tests for SQLite database and CSV sync operations."""

from pathlib import Path
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.db.sync import CsvSync


def test_db_upsert_and_status(tmp_path: Path):
    db_file = tmp_path / "test.db"
    repo = JobRepository(db_file)

    rec = JobRecord(
        id="monzo-mle",
        company="Monzo",
        title="Machine Learning Engineer",
        url="https://monzo.com/careers/1",
        status="target",
        match_score=85,
        date_added="2026-09-14"
    )
    repo.upsert_job(rec)

    fetched = repo.get_job("monzo-mle")
    assert fetched is not None
    assert fetched.company == "Monzo"
    assert fetched.status == "target"

    # Update status
    repo.update_status("monzo-mle", "applied", notes="First round recruiter screen")
    updated = repo.get_job("monzo-mle")
    assert updated.status == "applied"
    assert updated.notes == "First round recruiter screen"
    assert updated.date_applied is not None

    # Flag
    repo.set_flag("monzo-mle", "followup_needed")
    flagged = repo.get_job("monzo-mle")
    assert flagged.flag == "followup_needed"


def test_csv_sync(tmp_path: Path):
    db_file = tmp_path / "test.db"
    csv_file = tmp_path / "jobs.csv"
    repo = JobRepository(db_file)

    rec1 = JobRecord(
        id="faculty-ai-applied-ai",
        company="Faculty AI",
        title="Applied AI Engineer",
        status="target",
        date_added="2026-09-14"
    )
    repo.upsert_job(rec1)

    # Export to CSV
    count = CsvSync.export_to_csv(repo, csv_file)
    assert count == 1
    assert csv_file.exists()

    content = csv_file.read_text(encoding="utf-8")
    assert "Faculty AI" in content
    assert "Applied AI Engineer" in content
