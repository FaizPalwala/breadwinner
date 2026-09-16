"""URL Health check automation to detect expired or dead job postings."""

import requests
from typing import List, Tuple
from breadwinner.db.repository import JobRepository, JobRecord


class JobHealthChecker:
    """Checks the health of job posting URLs and flags dead or expired postings."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    @classmethod
    def check_all_jobs(cls, repo: JobRepository) -> List[Tuple[JobRecord, bool, str]]:
        """Check all active jobs with URLs and flag broken links."""
        jobs = repo.list_jobs()
        results = []

        headers = {"User-Agent": cls.USER_AGENT}
        for j in jobs:
            if not j.url:
                continue
            
            try:
                resp = requests.head(j.url, headers=headers, timeout=8, allow_redirects=True)
                if resp.status_code >= 400:
                    # Retry with GET in case HEAD was blocked
                    resp = requests.get(j.url, headers=headers, timeout=8)

                if resp.status_code < 400:
                    results.append((j, True, f"HTTP {resp.status_code} OK"))
                    if j.flag == "link_broken":
                        repo.set_flag(j.id, None)
                else:
                    results.append((j, False, f"HTTP {resp.status_code} Not Found / Closed"))
                    repo.set_flag(j.id, "link_broken")
            except Exception as e:
                results.append((j, False, f"Connection error: {str(e)[:40]}"))
                repo.set_flag(j.id, "link_broken")

        return results
