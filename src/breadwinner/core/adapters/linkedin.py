"""LinkedIn Guest First-Class ATS Adapter using unauthenticated jobPosting guest endpoint."""

import re
import requests
from urllib.parse import urlparse
from typing import Optional
from bs4 import BeautifulSoup

from breadwinner.core.adapters.base import BaseATSAdapter
from breadwinner.core.models import (
    IngestedJobResult,
    CoverLetterRequirement,
    KnockoutLogistics
)


class LinkedInGuestAdapter(BaseATSAdapter):
    """Adapter for native LinkedIn job postings via the public jobs-guest endpoint."""

    @property
    def name(self) -> str:
        return "linkedin"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "linkedin.com" in netloc and "/jobs/" in url

    def parse_job_id(self, url: str) -> Optional[str]:
        # Formats:
        # /jobs/view/{job_id}/...
        # /jobs/view/123456789
        # /jobs/collections/.../?currentJobId={job_id}
        m = re.search(r"/jobs/view/(\d+)", url)
        if m:
            return m.group(1)
        m2 = re.search(r"currentJobId=(\d+)", url)
        if m2:
            return m2.group(1)
        return None

    def extract(self, url: str) -> IngestedJobResult:
        job_id = self.parse_job_id(url)
        if not job_id:
            raise ValueError(f"Could not parse LinkedIn job ID from {url}")

        guest_api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        resp = requests.get(guest_api_url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title = "Target Role"
        company = "Target Company"
        location = None

        t_elem = soup.find(class_=lambda c: c and "topcard__title" in c) or soup.find("h2") or soup.find("h1")
        if t_elem:
            title = t_elem.get_text().strip()

        c_elem = (
            soup.find(class_=lambda c: c and "topcard__flavor" in c and "org-name" in c)
            or soup.find(class_=lambda c: c and "sub-nav-cta__sub-title" in c)
            or soup.find("a", class_=lambda c: c and "topcard__org-name-link" in c)
        )
        if c_elem:
            company = c_elem.get_text().strip()

        loc_elem = soup.find(class_=lambda c: c and "topcard__flavor--bullet" in c)
        if loc_elem:
            location = loc_elem.get_text().strip()

        desc_elem = (
            soup.find("div", class_=lambda c: c and "show-more-less-html__markup" in c)
            or soup.find("div", class_=lambda c: c and "description__text" in c)
            or soup.find("section", class_=lambda c: c and "description" in c)
        )

        cleaned_markdown = self.html_to_markdown(str(desc_elem)) if desc_elem else self.html_to_markdown(resp.text)

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
            cover_letter_status=CoverLetterRequirement.OPTIONAL,
            cover_letter_guidance="LinkedIn Easy Apply and external links typically support optional cover letters/notes.",
            logistics=KnockoutLogistics()
        )
