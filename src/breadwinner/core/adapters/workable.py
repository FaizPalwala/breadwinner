"""Workable First-Class ATS Adapter using public unauthenticated widget API."""

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


class WorkableAdapter(BaseATSAdapter):
    """Adapter for Workable job postings via apply.workable.com API."""

    @property
    def name(self) -> str:
        return "workable"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "workable.com" in netloc

    def parse_company_and_code(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # apply.workable.com/{company}/j/{code}
        if len(parts) >= 3 and parts[1] == "j":
            return parts[0], parts[2]
        elif len(parts) == 2 and parts[0] == "j":
            # e.g. company.workable.com/j/code
            sub = parsed.netloc.split(".")[0]
            return sub, parts[1]
        return None, None

    def extract(self, url: str) -> IngestedJobResult:
        company_slug, shortcode = self.parse_company_and_code(url)
        if not company_slug or not shortcode:
            raise ValueError(f"Could not parse Workable company slug and shortcode from {url}")

        api_url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}/jobs/{shortcode}"
        headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        title = data.get("title", "Target Role")
        company = company_slug.replace("-", " ").title()

        loc = data.get("location") or {}
        location = loc.get("city") if isinstance(loc, dict) else str(loc)

        # Build clean markdown
        desc_md = self.html_to_markdown(data.get("description", ""))
        reqs_md = self.html_to_markdown(data.get("requirements", ""))
        benefits_md = self.html_to_markdown(data.get("benefits", ""))

        md_parts = []
        if desc_md:
            md_parts.append(desc_md)
        if reqs_md:
            md_parts.append(f"### Requirements\n{reqs_md}")
        if benefits_md:
            md_parts.append(f"### Benefits\n{benefits_md}")

        cleaned_markdown = "\n\n".join(md_parts)

        # Questions & Cover Letter
        questions: List[ApplicationQuestion] = []
        app_form = data.get("application_form") or {}

        cl_setting = (app_form.get("cover_letter") or "").lower()
        if cl_setting == "required":
            cover_letter_status = CoverLetterRequirement.MANDATORY
            cover_letter_guidance = "Cover letter is required on this Workable job."
        elif cl_setting == "optional":
            cover_letter_status = CoverLetterRequirement.OPTIONAL
            cover_letter_guidance = "Cover letter is optional on this Workable job."
        elif cl_setting == "off":
            cover_letter_status = CoverLetterRequirement.PROHIBITED
            cover_letter_guidance = "Cover letters are disabled on this Workable job."
        else:
            cover_letter_status = CoverLetterRequirement.NOT_SPECIFIED
            cover_letter_guidance = ""

        raw_questions = app_form.get("questions") or []
        for q in raw_questions:
            q_body = (q.get("body") or q.get("title") or "").strip()
            q_req = bool(q.get("required", False))
            q_type_str = (q.get("type") or "text").lower()

            q_type = QuestionType.TEXT
            options = []
            if "paragraph" in q_type_str or "textarea" in q_type_str:
                q_type = QuestionType.TEXTAREA
            elif "dropdown" in q_type_str or "multiple_choice" in q_type_str:
                q_type = QuestionType.DROPDOWN
                opts = q.get("options") or []
                options = [opt.get("body", "") for opt in opts if isinstance(opt, dict) and opt.get("body")]
            elif "boolean" in q_type_str:
                q_type = QuestionType.BOOLEAN
            elif "numeric" in q_type_str or "number" in q_type_str:
                q_type = QuestionType.NUMBER

            if q_body:
                questions.append(
                    ApplicationQuestion(
                        id=str(q.get("id") or len(questions) + 1),
                        prompt=q_body,
                        required=q_req,
                        question_type=q_type,
                        source=QuestionSource.FORM_FIELD,
                        options=options
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
