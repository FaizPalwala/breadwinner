"""Ashby First-Class ATS Adapter using public unauthenticated posting API and Next.js data."""

import re
import json
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple, List
from bs4 import BeautifulSoup

from breadwinner.core.adapters.base import BaseATSAdapter
from breadwinner.core.models import (
    IngestedJobResult,
    ApplicationQuestion,
    QuestionType,
    QuestionSource,
    CoverLetterRequirement,
    KnockoutLogistics
)


class AshbyAdapter(BaseATSAdapter):
    """Adapter for Ashby job postings via public posting API and hydration data."""

    @property
    def name(self) -> str:
        return "ashby"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "ashbyhq.com" in netloc

    def parse_org_and_posting_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # jobs.ashbyhq.com/{org_slug}/{posting_id}
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    def extract(self, url: str) -> IngestedJobResult:
        org_slug, posting_id = self.parse_org_and_posting_id(url)
        if not org_slug or not posting_id:
            raise ValueError(f"Could not parse Ashby organization and posting ID from {url}")

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        # 1. Fetch page HTML to extract server-rendered __NEXT_DATA__
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        next_data_script = soup.find("script", id="__NEXT_DATA__")

        job_posting_data = None
        app_form_data = None

        if next_data_script and next_data_script.string:
            try:
                next_json = json.loads(next_data_script.string)
                page_props = next_json.get("props", {}).get("pageProps", {})
                job_posting_data = page_props.get("jobPosting")
                app_form_data = page_props.get("applicationForm") or (job_posting_data.get("applicationForm") if job_posting_data else None)
            except Exception:
                pass

        # 2. If __NEXT_DATA__ lacked job posting, query Ashby public posting API directly
        if not job_posting_data:
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org_slug}/application-form"
            try:
                api_resp = requests.post(
                    api_url,
                    headers={"User-Agent": self.USER_AGENT, "Content-Type": "application/json"},
                    json={"jobPostingId": posting_id},
                    timeout=10
                )
                if api_resp.status_code == 200:
                    api_json = api_resp.json()
                    job_posting_data = api_json.get("jobPosting") or api_json
                    app_form_data = api_json.get("applicationForm")
            except Exception:
                pass

        title = "Target Role"
        company = org_slug.replace("-", " ").title()
        location = None
        desc_html = ""

        if job_posting_data:
            title = job_posting_data.get("title") or title
            location = job_posting_data.get("locationName") or job_posting_data.get("departmentName")
            desc_html = job_posting_data.get("descriptionHtml") or ""
        else:
            # Fallback to HTML title/h1
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text().strip()

        cleaned_markdown = self.html_to_markdown(desc_html) if desc_html else ""
        if not cleaned_markdown:
            # Extract content div if present
            main = soup.find("main") or soup.find("div", class_=lambda c: c and "description" in c.lower())
            if main:
                cleaned_markdown = self.html_to_markdown(str(main))

        # Questions & Cover Letter from Ashby Application Form
        questions: List[ApplicationQuestion] = []
        cover_letter_status = CoverLetterRequirement.PROHIBITED
        cover_letter_guidance = "No cover letter upload slot found on this Ashby application form."

        if app_form_data:
            fields = app_form_data.get("fields") or app_form_data.get("sections") or []
            # Flatten if sections
            flat_fields = []
            for item in fields:
                if isinstance(item, dict):
                    if "fields" in item:
                        flat_fields.extend(item.get("fields", []))
                    else:
                        flat_fields.append(item)

            for f in flat_fields:
                f_title = (f.get("title") or f.get("label") or "").strip()
                f_path = (f.get("path") or "").lower()
                f_type = (f.get("type") or "").lower()
                f_req = bool(f.get("isRequired", False) or f.get("required", False))

                # Check for cover letter field
                if "coverletter" in f_path or "cover letter" in f_title.lower():
                    if f_req:
                        cover_letter_status = CoverLetterRequirement.MANDATORY
                        cover_letter_guidance = "Cover letter is required on this Ashby application."
                    else:
                        cover_letter_status = CoverLetterRequirement.OPTIONAL
                        cover_letter_guidance = "Cover letter is optional on this Ashby application."
                    continue

                # Skip core identity fields
                if any(k in f_path for k in ["_systemfield_name", "_systemfield_email", "_systemfield_phone", "_systemfield_resume"]):
                    continue

                q_type = QuestionType.TEXT
                options = []
                if "longanswer" in f_type or "textarea" in f_type:
                    q_type = QuestionType.TEXTAREA
                elif "dropdown" in f_type or "multiplechoice" in f_type:
                    q_type = QuestionType.DROPDOWN
                    opts = f.get("options") or []
                    options = [o.get("label") or str(o) for o in opts if o]
                elif "fileupload" in f_type or "file" in f_type:
                    q_type = QuestionType.FILE

                if f_title:
                    questions.append(
                        ApplicationQuestion(
                            id=str(f.get("id") or len(questions) + 1),
                            prompt=f_title,
                            required=f_req,
                            question_type=q_type,
                            source=QuestionSource.FORM_FIELD,
                            options=options,
                            description=f.get("description")
                        )
                    )

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
            questions=questions,
            cover_letter_status=cover_letter_status,
            cover_letter_guidance=cover_letter_guidance,
            logistics=KnockoutLogistics()
        )
