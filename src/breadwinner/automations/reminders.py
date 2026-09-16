"""Application follow-up reminder automation."""

from datetime import datetime, timedelta
from typing import List, Tuple
from breadwinner.db.repository import JobRepository, JobRecord


class ReminderEngine:
    """Detects submitted applications that are overdue for follow-ups."""

    @classmethod
    def find_overdue_followups(
        cls,
        repo: JobRepository,
        days_threshold: int = 7
    ) -> List[Tuple[JobRecord, int]]:
        """Find applications in 'applied' status older than days_threshold without updates."""
        applied_jobs = repo.list_jobs(status="applied")
        overdue = []
        today = datetime.now().date()

        for j in applied_jobs:
            if not j.date_applied:
                continue
            try:
                applied_date = datetime.strptime(j.date_applied, "%Y-%m-%d").date()
                delta_days = (today - applied_date).days
                if delta_days >= days_threshold:
                    overdue.append((j, delta_days))
                    if j.flag != "followup_needed":
                        repo.set_flag(j.id, "followup_needed")
            except ValueError:
                pass

        return overdue
