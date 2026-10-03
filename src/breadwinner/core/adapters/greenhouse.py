"""Greenhouse First-Class ATS Adapter using public unauthenticated boards API."""

import re
import html
import requests
from urllib.parse import urlparse, parse_qs
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


class GreenhouseAdapter(BaseATSAdapter):
    """Adapter for Greenhouse boards via boards-api.greenhouse.io."""

    @property
    def name(self) -> str:
        return "greenhouse"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        if "greenhouse.io" in netloc or "gh_jid" in url:
            return True
        return False

    def parse_board_and_job_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts board token and job ID from various Greenhouse URL shapes."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]

        # Case 1: ?gh_jid=12345 (Embedded board on custom domain)
        qs = parse_qs(parsed.query)
        if "gh_jid" in qs and qs["gh_jid"]:
            job_id = qs["gh_jid"][0]
            # Try to get board token from path or subdomain
            board_token = parts[0] if parts else netloc.split(".")[0]
            return board_token, job_id

        # Case 2: boards.greenhouse.io/{board_token}/jobs/{job_id}
        # or job-boards.greenhouse.io/{board_token}/jobs/{job_id}
        if "greenhouse.io" in netloc:
            if len(parts) >= 3 and parts[1] == "jobs":
                return parts[0], parts[2]
            elif len(parts) == 2 and parts[0] == "jobs":
                # e.g. subdomain.greenhouse.io/jobs/123
                subdomain = netloc.split(".")[0]
                return subdomain, parts[1]

        return None, None

    def extract(self, url: str) -> IngestedJobResult:
        board_token, job_id = self.parse_board_and_job_id(url)
        if not board_token or not job_id:
            raise ValueError(f"Could not parse Greenhouse board token and job ID from {url}")

        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true"
        headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        title = data.get("title", "Target Role")
        company = board_token.replace("-", " ").title()
        location_obj = data.get("location") or {}
        location = location_obj.get("name") if isinstance(location_obj, dict) else str(location_obj)

        # Content is HTML escaped in Greenhouse
        raw_content = html.unescape(data.get("content", ""))
        cleaned_markdown = self.html_to_markdown(raw_content)

        # Questions & Cover Letter
        questions: List[ApplicationQuestion] = []
        cover_letter_status = CoverLetterRequirement.NOT_SPECIFIED
        cover_letter_guidance = ""

        raw_questions = data.get("questions") or []
        for q in raw_questions:
            q_fields = q.get("fields") or []
            field_names = [f.get("name", "").lower() for f in q_fields if isinstance(f, dict)]
            if q.get("name"):
                field_names.append(q.get("name").lower())
            primary_name = field_names[0] if field_names else (q.get("name") or "").lower()
            q_label = q.get("label", "").strip()
            q_req = bool(q.get("required", False))
            field_type_str = q_fields[0].get("type", "input_text") if q_fields else "input_text"

            # Check cover letter
            if any("cover_letter" in fn for fn in field_names) or "cover letter" in q_label.lower():
                if q_req:
                    cover_letter_status = CoverLetterRequirement.MANDATORY
                    cover_letter_guidance = "Cover letter is marked as required on the Greenhouse application form."
                else:
                    cover_letter_status = CoverLetterRequirement.OPTIONAL
                    cover_letter_guidance = "Cover letter upload slot is optional on the Greenhouse application form."
                continue

            # Skip standard contact name/email/phone/resume fields
            if any(fn in ["first_name", "last_name", "email", "phone", "resume", "resume_text", "data_compliance"] for fn in field_names):
                continue

            # Map field type
            q_type = QuestionType.TEXT
            options: List[str] = []
            if "textarea" in field_type_str:
                q_type = QuestionType.TEXTAREA
            elif "multi_value" in field_type_str or "select" in field_type_str:
                q_type = QuestionType.DROPDOWN
                values = q_fields[0].get("values", []) if q_fields else []
                options = [v.get("label", "") for v in values if isinstance(v, dict) and v.get("label")]
            elif "boolean" in field_type_str:
                q_type = QuestionType.BOOLEAN
            elif "file" in field_type_str:
                q_type = QuestionType.FILE

            if q_label:
                questions.append(
                    ApplicationQuestion(
                        id=str(q.get("name") or len(questions) + 1),
                        prompt=q_label,
                        required=q_req,
                        question_type=q_type,
                        source=QuestionSource.FORM_FIELD,
                        options=options,
                        description=q.get("description")
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
