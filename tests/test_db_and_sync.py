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


def test_db_delete_job(tmp_path: Path):
    db_file = tmp_path / "test.db"
    repo = JobRepository(db_file)

    rec = JobRecord(
        id="stripe-infra",
        company="Stripe",
        title="Infrastructure Engineer",
        status="tailored",
        date_added="2026-10-14"
    )
    repo.upsert_job(rec)
    assert repo.get_job("stripe-infra") is not None

    # Delete existing job
    deleted = repo.delete_job("stripe-infra")
    assert deleted is True
    assert repo.get_job("stripe-infra") is None

    # Delete non-existent job
    deleted_again = repo.delete_job("stripe-infra")
    assert deleted_again is False


def test_db_migration_002(tmp_path: Path):
    import sqlite3
    db_file = tmp_path / "legacy.db"

    # Create a legacy table without the new columns
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                location TEXT,
                portal_type TEXT,
                status TEXT NOT NULL,
                match_score INTEGER,
                persona TEXT,
                date_added TEXT NOT NULL,
                date_applied TEXT,
                folder_path TEXT,
                notes TEXT,
                flag TEXT
            )
        """)
        conn.execute("""
            INSERT INTO jobs (id, company, title, status, match_score, date_added)
            VALUES ('old-job', 'Legacy Co', 'Software Engineer', 'target', 88, '2026-09-01')
        """)
        conn.commit()

    # Initializing JobRepository triggers automatic migration 002
    repo = JobRepository(db_file)
    migrated_job = repo.get_job("old-job")
    assert migrated_job is not None
    assert migrated_job.match_score == 88
    assert migrated_job.ats_score == 88
    assert migrated_job.provenance_status == "unverified"
    assert migrated_job.contract_path is None

    # Upsert with new columns
    migrated_job.xyz_score = 92
    migrated_job.domain_recall_score = 95
    migrated_job.provenance_status = "verified"
    repo.upsert_job(migrated_job)

    updated = repo.get_job("old-job")
    assert updated.xyz_score == 92
    assert updated.domain_recall_score == 95
    assert updated.provenance_status == "verified"


def test_job_record_score_and_contract_sync(tmp_path: Path):
    app_folder = tmp_path / "apps" / "acme"
    app_folder.mkdir(parents=True)
    contract_file = app_folder / "job.json"
    contract_file.write_text('{"metadata": {"role": "MLE"}}', encoding="utf-8")

    # When match_score is passed, ats_score should sync
    rec1 = JobRecord(
        id="acme-1",
        company="Acme",
        title="MLE",
        match_score=90,
        date_added="2026-10-01",
        folder_path=str(app_folder)
    )
    assert rec1.ats_score == 90
    assert rec1.contract_path == str(contract_file)

    # When ats_score is passed, match_score should sync
    rec2 = JobRecord(
        id="acme-2",
        company="Acme",
        title="MLE",
        ats_score=95,
        date_added="2026-10-01"
    )
    assert rec2.match_score == 95
    assert rec2.contract_path is None

