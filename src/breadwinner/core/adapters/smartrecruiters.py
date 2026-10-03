"""SmartRecruiters First-Class ATS Adapter using public postings API."""

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


class SmartRecruitersAdapter(BaseATSAdapter):
    """Adapter for SmartRecruiters job postings via api.smartrecruiters.com."""

    @property
    def name(self) -> str:
        return "smartrecruiters"

    def matches(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return "smartrecruiters.com" in netloc or "smrtr.io" in netloc

    def parse_company_and_posting_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # jobs.smartrecruiters.com/{company}/{posting_id}
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    def extract(self, url: str) -> IngestedJobResult:
        company_slug, posting_id = self.parse_company_and_posting_id(url)
        if not company_slug or not posting_id:
            raise ValueError(f"Could not parse SmartRecruiters company and posting ID from {url}")

        headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}
        api_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{posting_id}"
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        title = data.get("name", "Target Role")
        company = data.get("company", {}).get("name") or company_slug.replace("-", " ").title()

        loc = data.get("location") or {}
        location = loc.get("city") or loc.get("region")

        # Sections
        sections = data.get("jobAd", {}).get("sections") or {}
        md_parts = []
        for sec_name, sec_obj in sections.items():
            sec_title = sec_obj.get("title") or sec_name.title()
            sec_text = sec_obj.get("text") or ""
            sec_md = self.html_to_markdown(sec_text)
            if sec_md:
                md_parts.append(f"### {sec_title}\n{sec_md}")

        cleaned_markdown = "\n\n".join(md_parts)

        # Questions from screening-questions endpoint
        questions: List[ApplicationQuestion] = []
        cover_letter_status = CoverLetterRequirement.OPTIONAL
        cover_letter_guidance = "SmartRecruiters applications allow optional cover letter notes by default."

        try:
            q_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{posting_id}/screening-questions"
            q_resp = requests.get(q_url, headers=headers, timeout=8)
            if q_resp.status_code == 200:
                q_data = q_resp.json()
                raw_qs = q_data.get("questions") or []
                for q in raw_qs:
                    q_label = (q.get("label") or "").strip()
                    q_req = bool(q.get("required", False))
                    q_type_str = (q.get("type") or "text").lower()

                    if "cover letter" in q_label.lower():
                        if q_req:
                            cover_letter_status = CoverLetterRequirement.MANDATORY
                            cover_letter_guidance = "Cover letter is required on this SmartRecruiters application."
                        else:
                            cover_letter_status = CoverLetterRequirement.OPTIONAL
                            cover_letter_guidance = "Cover letter is optional on this SmartRecruiters application."
                        continue

                    q_type = QuestionType.TEXT
                    options = []
                    if "textarea" in q_type_str or "essay" in q_type_str:
                        q_type = QuestionType.TEXTAREA
                    elif "single_choice" in q_type_str or "dropdown" in q_type_str:
                        q_type = QuestionType.DROPDOWN
                        raw_opts = q.get("values") or []
                        options = [opt.get("label", "") for opt in raw_opts if isinstance(opt, dict) and opt.get("label")]
                    elif "numeric" in q_type_str or "number" in q_type_str:
                        q_type = QuestionType.NUMBER

                    if q_label:
                        questions.append(
                            ApplicationQuestion(
                                id=str(q.get("id") or len(questions) + 1),
                                prompt=q_label,
                                required=q_req,
                                question_type=q_type,
                                source=QuestionSource.FORM_FIELD,
                                options=options
                            )
                        )
        except Exception:
            pass

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
