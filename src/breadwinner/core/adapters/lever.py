"""Lever First-Class ATS Adapter using public unauthenticated postings API."""

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


class LeverAdapter(BaseATSAdapter):
    """Adapter for Lever job postings via api.lever.co."""

    @property
    def name(self) -> str:
        return "lever"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "lever.co" in netloc

    def parse_company_and_posting_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # jobs.lever.co/{company}/{posting_id} or jobs.lever.co/{company}/{posting_id}/apply
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    def extract(self, url: str) -> IngestedJobResult:
        company_slug, posting_id = self.parse_company_and_posting_id(url)
        if not company_slug or not posting_id:
            raise ValueError(f"Could not parse Lever company and posting ID from {url}")

        api_url = f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}"
        headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        title = data.get("text", "Target Role")
        company = company_slug.replace("-", " ").title()

        categories = data.get("categories") or {}
        location = categories.get("location") or categories.get("team")

        # Build clean markdown from content blocks
        md_sections = []
        content = data.get("content") or {}
        desc_html = content.get("description", "")
        if desc_html:
            md_sections.append(self.html_to_markdown(desc_html))

        lists = content.get("lists") or []
        for lst in lists:
            header = lst.get("text", "")
            items_html = lst.get("content", "")
            items_md = self.html_to_markdown(items_html)
            if header:
                md_sections.append(f"\n### {header}\n{items_md}")
            else:
                md_sections.append(items_md)

        closing_html = content.get("closing", "")
        if closing_html:
            md_sections.append(self.html_to_markdown(closing_html))

        cleaned_markdown = "\n\n".join(s for s in md_sections if s.strip())

        # If content blocks empty, fallback to descriptionPlain
        if not cleaned_markdown.strip() and data.get("descriptionPlain"):
            cleaned_markdown = data["descriptionPlain"].strip()

        # Questions & Cover Letter
        questions: List[ApplicationQuestion] = []
        cover_letter_status = CoverLetterRequirement.OPTIONAL
        cover_letter_guidance = "Lever applications provide optional attachment/notes by default."

        custom_questions = data.get("customQuestions") or []
        for q in custom_questions:
            q_text = (q.get("text") or "").strip()
            q_req = bool(q.get("required", False))
            q_type_str = (q.get("type") or "text").lower()

            if "cover letter" in q_text.lower():
                if q_req:
                    cover_letter_status = CoverLetterRequirement.MANDATORY
                    cover_letter_guidance = "Cover letter prompt is required on the Lever application form."
                else:
                    cover_letter_status = CoverLetterRequirement.OPTIONAL
                    cover_letter_guidance = "Cover letter prompt is optional on the Lever application form."
                continue

            q_type = QuestionType.TEXT
            options: List[str] = []
            if "textarea" in q_type_str:
                q_type = QuestionType.TEXTAREA
            elif "dropdown" in q_type_str or "multiple-choice" in q_type_str:
                q_type = QuestionType.DROPDOWN
                raw_options = q.get("options") or []
                options = [opt.get("text", "") for opt in raw_options if isinstance(opt, dict) and opt.get("text")]
            elif "file" in q_type_str:
                q_type = QuestionType.FILE

            if q_text:
                questions.append(
                    ApplicationQuestion(
                        id=str(len(questions) + 1),
                        prompt=q_text,
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
