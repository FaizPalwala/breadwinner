"""Workday First-Class ATS Adapter using public unauthenticated CXS API."""

import re
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple, List

from breadwinner.core.adapters.base import BaseATSAdapter
from breadwinner.core.models import (
    IngestedJobResult,
    ApplicationQuestion,
    QuestionType,
    QuestionSource,
    CoverLetterRequirement,
    KnockoutLogistics
)


class WorkdayAdapter(BaseATSAdapter):
    """Adapter for Workday job postings via the Client Experience Service (CXS) JSON API."""

    @property
    def name(self) -> str:
        return "workday"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "myworkdayjobs.com" in netloc or "workday" in netloc

    def parse_workday_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Parses (host, tenant, site, job_id) from Workday URL."""
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        tenant = host.split(".")[0]
        parts = [p for p in parsed.path.strip("/").split("/") if p]

        # Formats:
        # /{locale}/{site}/job/{location}/{title}_{job_id}
        # /{locale}/{site}/job/{job_id}
        # /{site}/job/{job_id}
        site = None
        job_id = None

        if "job" in parts:
            job_idx = parts.index("job")
            if job_idx > 0:
                site = parts[job_idx - 1]
            if job_idx < len(parts) - 1:
                last_part = parts[-1]
                if "_" in last_part:
                    job_id = last_part.split("_")[-1]
                else:
                    job_id = last_part

        return host, tenant, site, job_id

    def extract(self, url: str) -> IngestedJobResult:
        host, tenant, site, job_id = self.parse_workday_url(url)
        if not host or not site or not job_id:
            raise ValueError(f"Could not parse Workday URL parameters from {url}")

        cxs_url = f"https://{host}/wday/cxs/{tenant}/{site}/job/{job_id}"
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        resp = requests.get(cxs_url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        info = data.get("jobPostingInfo") or data
        title = info.get("title") or "Target Role"
        company = tenant.replace("-", " ").title()
        location = info.get("location")

        desc_html = info.get("jobDescription") or ""
        cleaned_markdown = self.html_to_markdown(desc_html)

        cover_letter_status = CoverLetterRequirement.OPTIONAL
        cover_letter_guidance = "Workday portals typically support an optional cover letter/documents slot."

        safe_company = re.sub(r"[^a-zA-Z0-9]+", "-", company.lower()).strip("-") or "company"
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "role"
        canonical_id = f"{safe_company}-{safe_title}"

        return IngestedJobResult(
            id=canonical_id,
            company=company,
            title=title,
            url=url,
            location=location,
            portal_type=self.name,
            extraction_method="tier_1_api",
            raw_text=cleaned_markdown,
            cleaned_markdown=cleaned_markdown,
            questions=[],
            cover_letter_status=cover_letter_status,
            cover_letter_guidance=cover_letter_guidance,
            logistics=KnockoutLogistics()
        )
