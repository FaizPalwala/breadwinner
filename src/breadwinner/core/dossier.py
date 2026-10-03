"""Application Dossier Renderer (`portal_answers.md`).

Renders an artisan, human-readable markdown dossier of knockout criteria,
matched technology tags, calculated years of experience, and tailored answers.
"""

from datetime import datetime
from typing import Optional

from breadwinner.core.models import (
    IngestedJobResult,
    CandidateProfile,
    CoverLetterRequirement
)
from breadwinner.core.persona import Persona


def render_application_dossier(
    job: IngestedJobResult,
    profile: Optional[CandidateProfile] = None,
    persona: Optional[Persona] = None
) -> str:
    """Renders the complete Application Dossier for quick portal filling."""
    log = job.logistics
    now_str = datetime.now().strftime("%Y-%m-%d")

    # Header
    tier_label = "Tier 1: Verified ATS API" if job.extraction_method == "tier_1_api" else "Tier 2: Universal Fallback"
    lines = [
        "# 🥐 BREADWINNER APPLICATION DOSSIER",
        f"**Target Role:** {job.title} at {job.company}",
        f"**Portal Type:** {job.portal_type.upper()} ({tier_label})  ",
        f"**Generated At:** {now_str}  ",
        f"**Source URL:** {job.url or 'Manual / Text Ingestion'}",
        "",
        "---",
        "",
        "## 1. QUICK-FILL FIELDS (Knockout & Logistics)",
        f"- **Full Name:** {profile.full_name if profile else 'Candidate'}",
        f"- **Email:** {profile.email if profile else 'candidate@example.com'}",
        f"- **Phone:** {profile.phone if profile else 'N/A'}",
        f"- **Location:** {profile.location if profile else (job.location or 'Remote / Local')}",
    ]

    # Links
    if log.profile_links:
        for name, link in log.profile_links.items():
            lines.append(f"- **{name}:** {link}")

    # Legal & Logistics
    auth_str = "YES" if log.work_authorized else "NO"
    spons_str = "YES" if log.visa_sponsorship_needed else "NO"
    lines.extend([
        f"- **Work Authorized:** {auth_str} ({log.visa_status})",
        f"- **Visa Sponsorship Required:** {spons_str}",
        f"- **Notice Period:** {log.notice_period}",
    ])

    if log.salary_numeric > 0:
        lines.append(f"- **Desired Base Salary:** {log.salary_currency} {log.salary_numeric:,} (Numeric: `{log.salary_numeric}` | Range: `{log.salary_range_display}`)")

    # 2. Matched Technology Tags
    lines.extend([
        "",
        "## 2. MATCHED TECHNOLOGY TAGS (Copy & Paste into Skills field)",
    ])
    if log.matched_technology_tags:
        lines.append(f"`{', '.join(log.matched_technology_tags)}`")
    else:
        lines.append("*No direct technology tags matched against profile.*")

    # 3. Calculated Years of Experience
    lines.extend([
        "",
        "## 3. CALCULATED YEARS OF EXPERIENCE (Mathematical Audit from Career Pantry)",
    ])
    if log.calculated_years_of_experience:
        for tech, yrs in sorted(log.calculated_years_of_experience.items(), key=lambda x: -x[1]):
            lines.append(f"- **{tech}:** {yrs} Year{'s' if yrs != 1 else ''}")
    else:
        lines.append("*Experience duration not computed or no profile supplied.*")

    # 4. Detected Application Questions
    lines.extend([
        "",
        "## 4. DETECTED APPLICATION QUESTIONS (Form Fields & In-Text Stealth Prompts)",
    ])
    if job.questions:
        for idx, q in enumerate(job.questions, 1):
            req_badge = "**[REQUIRED]**" if q.required else "[OPTIONAL]"
            src_badge = "Form Field" if q.source.value == "form_field" else "In-Text Screening Prompt"
            type_str = q.question_type.value.upper()

            lines.append(f"### Q{idx}. {req_badge} {src_badge} ({type_str})")
            lines.append(f"> **Prompt:** {q.prompt}")
            if q.options:
                lines.append(f"> *Available Choices:* {', '.join(q.options)}")
            if q.answer:
                lines.append(f"\n**Synthesized Answer:**\n{q.answer}\n")
            else:
                lines.append("\n*Answer ready to synthesize via Breadwinner Studio or CLI.*\n")
    else:
        lines.append("*No custom application questions or in-text screening prompts detected.*")

    # 5. Cover Letter Status
    lines.extend([
        "",
        "## 5. COVER LETTER STATUS & GUIDANCE",
    ])
    if job.cover_letter_status == CoverLetterRequirement.MANDATORY:
        lines.append("**Status:** `[✓] MANDATORY`  ")
        lines.append(f"**Guidance:** {job.cover_letter_guidance or 'Portal requires a cover letter.'}")
    elif job.cover_letter_status == CoverLetterRequirement.OPTIONAL:
        lines.append("**Status:** `[·] OPTIONAL`  ")
        lines.append(f"**Guidance:** {job.cover_letter_guidance or 'Portal provides an optional cover letter slot.'}")
    elif job.cover_letter_status == CoverLetterRequirement.PROHIBITED:
        lines.append("**Status:** `[✕] PROHIBITED / NOT SUPPORTED`  ")
        lines.append(f"**Guidance:** {job.cover_letter_guidance or 'Application form does not accept cover letters.'}")
    else:
        lines.append("**Status:** `[?] NOT SPECIFIED`  ")
        lines.append("**Guidance:** Cover letter requirement could not be confirmed.")

    lines.append("")
    return "\n".join(lines)
