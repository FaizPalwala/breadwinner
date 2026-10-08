"""Bi-directional synchronization between SQLite tracker and CSV files."""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from breadwinner.db.repository import JobRepository, JobRecord


class CsvSync:
    """Synchronizes SQLite job records with human-editable CSV files."""

    CSV_HEADERS = [
        "ID", "Company", "Role", "Status", "Match Score", "Date Added",
        "Date Applied", "URL", "Notes", "Flag"
    ]

    @classmethod
    def export_to_csv(cls, repo: JobRepository, csv_path: Path) -> int:
        """Export all jobs from SQLite into CSV."""
        jobs = repo.list_jobs()
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cls.CSV_HEADERS)
            for j in jobs:
                writer.writerow([
                    j.id,
                    j.company,
                    j.title,
                    j.status,
                    j.match_score if j.match_score is not None else "",
                    j.date_added,
                    j.date_applied or "",
                    j.url or "",
                    j.notes,
                    j.flag or ""
                ])
        return len(jobs)

    @classmethod
    def import_from_csv(cls, repo: JobRepository, csv_path: Path) -> int:
        """Import jobs from existing CSV file (such as job_tracker.csv or ai_job_target_tracker.csv)."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            return 0

        count = 0
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize field names
                norm_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                
                company = norm_row.get("company") or "Target Company"
                title = norm_row.get("target role") or norm_row.get("role") or norm_row.get("title") or "Role"
                url = norm_row.get("careers url") or norm_row.get("url") or norm_row.get("link")
                notes = norm_row.get("why target them") or norm_row.get("notes") or ""
                status = norm_row.get("status") or "target"
                
                # Use explicit ID if provided, otherwise slug id
                explicit_id = norm_row.get("id")
                if explicit_id:
                    job_id = explicit_id
                else:
                    safe_company = re.sub(r'[^a-zA-Z0-9]+', '-', company.lower()).strip('-')
                    safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
                    job_id = f"{safe_company}-{safe_title}"

                match_score_str = norm_row.get("match score") or norm_row.get("match_score") or norm_row.get("match")
                match_score = None
                if match_score_str:
                    try:
                        match_score = int(float(match_score_str.rstrip("%")))
                    except ValueError:
                        pass

                date_added = norm_row.get("date added") or norm_row.get("date_added") or datetime.now().strftime("%Y-%m-%d")
                date_applied = norm_row.get("date applied") or norm_row.get("date_applied")
                flag = norm_row.get("flag") or None

                record = JobRecord(
                    id=job_id,
                    company=company,
                    title=title,
                    url=url,
                    status=status.lower(),
                    match_score=match_score,
                    date_added=date_added,
                    date_applied=date_applied,
                    notes=notes,
                    flag=flag
                )
                repo.upsert_job(record)
                count += 1

        return count
