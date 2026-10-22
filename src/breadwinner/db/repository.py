"""SQLite database repository for tracking applications."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, model_validator


class JobRecord(BaseModel):
    id: str
    company: str
    title: str
    url: Optional[str] = None
    location: Optional[str] = None
    portal_type: Optional[str] = "general"
    status: str = "target"  # target, tailored, applied, interviewing, offer, rejected, archived
    match_score: Optional[int] = None
    persona: Optional[str] = None
    date_added: str
    date_applied: Optional[str] = None
    folder_path: Optional[str] = None
    notes: Optional[str] = ""
    flag: Optional[str] = None  # e.g. "followup_needed", "high_priority", "link_broken"
    contract_path: Optional[str] = None
    ats_score: Optional[int] = None
    xyz_score: Optional[int] = None
    domain_recall_score: Optional[int] = None
    provenance_status: Optional[str] = "unverified"

    @model_validator(mode="after")
    def sync_scores_and_contract(self) -> "JobRecord":
        if self.notes is None:
            self.notes = ""
        if self.ats_score is not None and self.match_score is None:
            self.match_score = self.ats_score
        elif self.match_score is not None and self.ats_score is None:
            self.ats_score = self.match_score

        if not self.contract_path and self.folder_path:
            candidate = Path(self.folder_path) / "job.json"
            if candidate.exists():
                self.contract_path = str(candidate)
        return self


class JobRepository:
    """Manages CRUD operations on SQLite tracker database."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
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
                    flag TEXT,
                    contract_path TEXT,
                    ats_score INTEGER,
                    xyz_score INTEGER,
                    domain_recall_score INTEGER,
                    provenance_status TEXT DEFAULT 'unverified'
                )
            """)
            # Check for existing schema to apply migration 002 if needed
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            migrations = [
                ("contract_path", "TEXT"),
                ("ats_score", "INTEGER"),
                ("xyz_score", "INTEGER"),
                ("domain_recall_score", "INTEGER"),
                ("provenance_status", "TEXT DEFAULT 'unverified'"),
            ]
            for col_name, col_type in migrations:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")

            # Backfill ats_score from match_score
            conn.execute("UPDATE jobs SET ats_score = match_score WHERE ats_score IS NULL AND match_score IS NOT NULL")
            conn.execute("UPDATE jobs SET match_score = ats_score WHERE match_score IS NULL AND ats_score IS NOT NULL")
            conn.commit()

    def upsert_job(self, record: JobRecord) -> None:
        """Insert or update a job record."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, company, title, url, location, portal_type, status,
                    match_score, persona, date_added, date_applied, folder_path, notes, flag,
                    contract_path, ats_score, xyz_score, domain_recall_score, provenance_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    company = excluded.company,
                    title = excluded.title,
                    url = COALESCE(excluded.url, jobs.url),
                    location = COALESCE(excluded.location, jobs.location),
                    portal_type = COALESCE(excluded.portal_type, jobs.portal_type),
                    status = excluded.status,
                    match_score = COALESCE(excluded.match_score, jobs.match_score),
                    persona = COALESCE(excluded.persona, jobs.persona),
                    date_applied = COALESCE(excluded.date_applied, jobs.date_applied),
                    folder_path = COALESCE(excluded.folder_path, jobs.folder_path),
                    notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE jobs.notes END,
                    flag = COALESCE(excluded.flag, jobs.flag),
                    contract_path = COALESCE(excluded.contract_path, jobs.contract_path),
                    ats_score = COALESCE(excluded.ats_score, jobs.ats_score),
                    xyz_score = COALESCE(excluded.xyz_score, jobs.xyz_score),
                    domain_recall_score = COALESCE(excluded.domain_recall_score, jobs.domain_recall_score),
                    provenance_status = COALESCE(excluded.provenance_status, jobs.provenance_status)
            """, (
                record.id, record.company, record.title, record.url, record.location,
                record.portal_type, record.status, record.match_score, record.persona,
                record.date_added, record.date_applied, record.folder_path,
                record.notes, record.flag, record.contract_path, record.ats_score,
                record.xyz_score, record.domain_recall_score, record.provenance_status
            ))
            conn.commit()

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return JobRecord(**dict(row))
        return None

    def list_jobs(self, status: Optional[str] = None, flag: Optional[str] = None) -> List[JobRecord]:
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if flag:
            query += " AND flag = ?"
            params.append(flag)
        query += " ORDER BY date_added DESC"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [JobRecord(**dict(row)) for row in cursor.fetchall()]

    def update_status(self, job_id: str, new_status: str, notes: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            params: List[Any] = [new_status]
            set_clauses = ["status = ?"]
            
            if new_status == "applied":
                set_clauses.append("date_applied = ?")
                params.append(datetime.now().strftime("%Y-%m-%d"))

            if notes:
                set_clauses.append("notes = ?")
                params.append(notes)

            params.append(job_id)
            cursor = conn.execute(f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0

    def set_flag(self, job_id: str, flag: Optional[str]) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE jobs SET flag = ? WHERE id = ?", (flag, job_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_notes(self, job_id: str, notes: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        """Permanently delete a job record from the database."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

