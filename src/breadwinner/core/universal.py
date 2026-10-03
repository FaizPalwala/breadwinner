"""Universal Job Ingestion Engine.

Coordinates Multi-Hop URL resolution, Tier 1 ATS Adapters, Tier 2 Universal Fallback,
Two-Vector Question extraction, and Mathematical Experience calculation.
"""

import re
import requests
from urllib.parse import urlparse
from typing import Optional, List, Dict
from bs4 import BeautifulSoup

from breadwinner.core.resolver import RedirectResolver
from breadwinner.core.adapters import find_adapter
from breadwinner.core.adapters.base import BaseATSAdapter
from breadwinner.core.prompts_extractor import extract_in_text_prompts
from breadwinner.core.experience import calculate_skills_experience
from breadwinner.core.models import (
    IngestedJobResult,
    JobPosting,
    ApplicationQuestion,
    QuestionType,
    QuestionSource,
    CoverLetterRequirement,
    KnockoutLogistics,
    CandidateProfile
)
from breadwinner.core.persona import Persona


class UniversalJobIngestor:
    """Universal job ingestion orchestrator supporting URLs, files, and pasted text."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    CORE_TECH_PATTERNS = [
        "python", "go", "golang", "rust", "c++", "c#", "java", "typescript", "javascript",
        "react", "next.js", "vue", "angular", "node.js", "django", "fastapi", "spring boot",
        "kubernetes", "docker", "terraform", "ansible", "aws", "gcp", "azure",
        "postgresql", "postgres", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
        "kafka", "rabbitmq", "pulsar", "sqs", "grpc", "graphql", "rest",
        "pytorch", "tensorflow", "scikit-learn", "llm", "rag", "transformers",
        "spark", "flink", "airflow", "snowflake", "databricks", "bigquery",
        "elasticsearch", "opensearch", "prometheus", "grafana", "datadog", "temporal"
    ]

    @classmethod
    def ingest_url(
        cls,
        raw_url: str,
        profile: Optional[CandidateProfile] = None,
        persona: Optional[Persona] = None,
        timeout: int = 10
    ) -> IngestedJobResult:
        """Resolves URL redirects, invokes Tier 1 ATS adapters or Tier 2 fallback, and enriches data."""
        # 1. Multi-hop canonicalization
        canonical_url = RedirectResolver.resolve_canonical_url(raw_url, timeout=timeout)

        # 2. Check Tier 1 ATS Adapters
        adapter = find_adapter(canonical_url)
        if adapter:
            try:
                result = adapter.extract(canonical_url)
            except Exception:
                # If adapter fails (e.g. rate limit or changed path), gracefully fall back to Tier 2
                result = cls._universal_fallback_extract(canonical_url, timeout=timeout)
        else:
            # 3. Tier 2 Universal Fallback
            result = cls._universal_fallback_extract(canonical_url, timeout=timeout)

        # 4. Extract Vector 2 In-Text Stealth Prompts from body text
        in_text_prompts = extract_in_text_prompts(result.cleaned_markdown)
        existing_prompts_lower = {q.prompt.lower().strip() for q in result.questions}
        for itp in in_text_prompts:
            if itp.prompt.lower().strip() not in existing_prompts_lower:
                result.questions.append(itp)
                existing_prompts_lower.add(itp.prompt.lower().strip())

        # 5. Extract demanded skills
        demanded_skills = cls._extract_demanded_technologies(result.cleaned_markdown)
        result.extracted_skills = demanded_skills

        # 6. Enrich Knockout Logistics & Math Experience if profile/persona available
        cls._enrich_logistics(result, profile=profile, persona=persona)

        return result

    @classmethod
    def ingest_text(
        cls,
        text: str,
        company: str = "Target Company",
        title: str = "Target Role",
        location: Optional[str] = None,
        profile: Optional[CandidateProfile] = None,
        persona: Optional[Persona] = None
    ) -> IngestedJobResult:
        """Ingests a job posting from raw text or markdown."""
        cleaned_markdown = text.strip()
        in_text_prompts = extract_in_text_prompts(cleaned_markdown)

        safe_company = re.sub(r"[^a-zA-Z0-9]+", "-", company.lower()).strip("-") or "company"
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "role"
        canonical_id = f"{safe_company}-{safe_title}"

        # Detect cover letter mention in text
        cover_letter_status = CoverLetterRequirement.OPTIONAL
        cl_guidance = ""
        lower = cleaned_markdown.lower()
        if "cover letter required" in lower or "must include a cover letter" in lower:
            cover_letter_status = CoverLetterRequirement.MANDATORY
            cl_guidance = "Job description explicitly requires a cover letter."
        elif "no cover letter" in lower or "do not send a cover letter" in lower:
            cover_letter_status = CoverLetterRequirement.PROHIBITED
            cl_guidance = "Job description explicitly requests no cover letter."

        result = IngestedJobResult(
            id=canonical_id,
            company=company,
            title=title,
            location=location,
            portal_type="text",
            extraction_method="manual_text",
            raw_text=cleaned_markdown,
            cleaned_markdown=cleaned_markdown,
            questions=in_text_prompts,
            cover_letter_status=cover_letter_status,
            cover_letter_guidance=cl_guidance,
            extracted_skills=cls._extract_demanded_technologies(cleaned_markdown),
            logistics=KnockoutLogistics()
        )

        cls._enrich_logistics(result, profile=profile, persona=persona)
        return result

    @classmethod
    def _universal_fallback_extract(cls, url: str, timeout: int = 10) -> IngestedJobResult:
        """Tier 2 Fallback: Scrapes HTML, checks form elements, and extracts clean markdown."""
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Company & Title heuristics
        company = "Target Company"
        title = "Target Role"
        location = None

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title_str = og_title["content"]
            if " at " in title_str:
                t, c = title_str.split(" at ", 1)
                title, company = t.strip(), c.strip()
            elif " - " in title_str:
                t, c = title_str.split(" - ", 1)
                title, company = t.strip(), c.strip()
            else:
                title = title_str.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            company = og_site["content"].strip()
        elif company == "Target Company":
            domain = urlparse(url).netloc.lower()
            parts = domain.split(".")
            company = parts[-2].capitalize() if len(parts) >= 2 else domain

        # 2. Form Inspection for Questions & Cover Letter BEFORE decomposing tags
        questions: List[ApplicationQuestion] = []
        cover_letter_status = CoverLetterRequirement.OPTIONAL
        cl_guidance = ""

        forms = soup.find_all("form")
        for form in forms:
            # Check inputs
            for inp in form.find_all(["input", "textarea", "select"]):
                name = (inp.get("name") or inp.get("id") or "").lower()
                placeholder = (inp.get("placeholder") or "").lower()
                aria = (inp.get("aria-label") or "").lower()
                is_req = inp.has_attr("required")

                if any("cover" in k and "letter" in k for k in [name, placeholder, aria]):
                    if is_req:
                        cover_letter_status = CoverLetterRequirement.MANDATORY
                        cl_guidance = "Cover letter upload field marked required in HTML form."
                    else:
                        cover_letter_status = CoverLetterRequirement.OPTIONAL
                        cl_guidance = "Cover letter upload field found in HTML form."

        # 3. Clean Text to Markdown
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()

        cleaned_markdown = BaseATSAdapter.html_to_markdown(str(soup))

        safe_company = re.sub(r"[^a-zA-Z0-9]+", "-", company.lower()).strip("-") or "company"
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or "role"
        canonical_id = f"{safe_company}-{safe_title}"

        return IngestedJobResult(
            id=canonical_id,
            company=company,
            title=title,
            url=url,
            location=location,
            portal_type="universal_web",
            extraction_method="tier_2_universal",
            raw_text=cleaned_markdown,
            cleaned_markdown=cleaned_markdown,
            questions=questions,
            cover_letter_status=cover_letter_status,
            cover_letter_guidance=cl_guidance,
            logistics=KnockoutLogistics()
        )

    @classmethod
    def _extract_demanded_technologies(cls, text: str) -> List[str]:
        """Detects demanded technologies in the job description using word boundary matching."""
        if not text:
            return []
        lower = text.lower()
        found: List[str] = []
        for tech in cls.CORE_TECH_PATTERNS:
            pattern = rf"\b{re.escape(tech)}\b"
            if re.search(pattern, lower):
                found.append(tech.title() if len(tech) > 3 else tech.upper())
        return list(dict.fromkeys(found))

    @classmethod
    def _enrich_logistics(
        cls,
        result: IngestedJobResult,
        profile: Optional[CandidateProfile] = None,
        persona: Optional[Persona] = None
    ) -> None:
        """Enriches the IngestedJobResult with calculated experience years and knockout fields."""
        logistics = result.logistics

        # 1. Profile information (Links & Calculated experience)
        if profile:
            if profile.linkedin_url:
                logistics.profile_links["LinkedIn"] = profile.linkedin_url
            if profile.github_url:
                logistics.profile_links["GitHub"] = profile.github_url
            if profile.portfolio_url:
                logistics.profile_links["Portfolio"] = profile.portfolio_url

            # Calculate mathematical years of experience for demanded technologies
            if result.extracted_skills:
                logistics.calculated_years_of_experience = calculate_skills_experience(
                    profile, result.extracted_skills
                )

            # Matched technology tags
            p_skills = set()
            for sc in profile.skills:
                for s in sc.skills:
                    p_skills.add(s.lower())
            for exp in profile.experiences:
                for t in exp.technologies:
                    p_skills.add(t.lower())

            matched_tags = []
            for ds in result.extracted_skills:
                if ds.lower() in p_skills:
                    matched_tags.append(ds)
            logistics.matched_technology_tags = matched_tags

        # 2. Persona information (Work auth, compensation, notice period)
        if persona:
            p_log = getattr(persona, "logistics", {}) or {}
            logistics.notice_period = p_log.get("notice_period") or getattr(persona, "notice_period", "1 month") or "1 month"
            floor = p_log.get("compensation_floor") or getattr(persona, "compensation_floor", "") or ""
            if floor:
                logistics.salary_range_display = f"{floor}+"
                num_m = re.search(r"(\d[\d,.]*)", floor)
                if num_m:
                    cleaned_num = num_m.group(1).replace(",", "")
                    try:
                        logistics.salary_numeric = int(float(cleaned_num))
                    except ValueError:
                        pass
                if "£" in floor or "gbp" in floor.lower():
                    logistics.salary_currency = "GBP"
                elif "$" in floor or "usd" in floor.lower():
                    logistics.salary_currency = "USD"
                elif "€" in floor or "eur" in floor.lower():
                    logistics.salary_currency = "EUR"

            # Check visa rules
            visa_str = p_log.get("visa") or ""
            rules = getattr(persona, "system_rules", []) or []
            rules_text = (visa_str + " " + " ".join(rules)).lower()
            if "no sponsorship needed" in rules_text or "citizen" in rules_text or "authorized" in rules_text:
                logistics.work_authorized = True
                logistics.visa_sponsorship_needed = False
                logistics.visa_status = "Authorized (No Sponsorship Required)"
            elif "require" in rules_text and "sponsorship" in rules_text:
                logistics.visa_sponsorship_needed = True
                logistics.visa_status = "Requires Sponsorship"

    @classmethod
    def to_job_posting(cls, result: IngestedJobResult) -> JobPosting:
        """Converts IngestedJobResult into a standard JobPosting model for tailoring."""
        return JobPosting(
            id=result.id,
            company=result.company,
            title=result.title,
            url=result.url,
            location=result.location,
            portal_type=result.portal_type,
            raw_text=result.raw_text,
            cleaned_markdown=result.cleaned_markdown,
            extracted_skills=result.extracted_skills,
            questions=result.questions,
            cover_letter_status=result.cover_letter_status,
            cover_letter_guidance=result.cover_letter_guidance,
            matched_technology_tags=result.logistics.matched_technology_tags,
            calculated_years_of_experience=result.logistics.calculated_years_of_experience,
            extraction_method=result.extraction_method
        )
