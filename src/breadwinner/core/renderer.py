"""Template rendering engine using Jinja2 for multi-format export."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import re
from jinja2 import Environment, FileSystemLoader

from breadwinner.core.models import CandidateProfile, TailoredApplication, WorkExperience


class TemplateRenderer:
    """Renders tailored application components to HTML, Markdown, and JSON Resume."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or (Path(__file__).parent.parent / "templates")
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render_resume(
        self,
        profile: CandidateProfile,
        app: TailoredApplication,
        template_name: str = "jakes"
    ) -> str:
        """Render resume using the specified template (jakes, modern, ats)."""
        template_map = {
            "jakes": "resume/jakes.html.jinja2",
            "modern": "resume/modern.html.jinja2",
            "ats": "resume/ats.md.jinja2",
            "markdown": "resume/ats.md.jinja2"
        }
        tpl_path = template_map.get(template_name.lower(), "resume/jakes.html.jinja2")
        template = self.env.get_template(tpl_path)
        return template.render(
            profile=profile,
            app=app,
            today=datetime.now().strftime("%B %Y")
        )

    def render_cover_letter(
        self,
        profile: CandidateProfile,
        app: TailoredApplication
    ) -> str:
        """Render tailored cover letter."""
        template = self.env.get_template("cover_letter/standard.md.jinja2")
        return template.render(
            profile=profile,
            app=app,
            today=datetime.now().strftime("%B %d, %Y")
        )

    def render_cover_letter_html(
        self,
        profile: CandidateProfile,
        app: Optional[TailoredApplication] = None,
        cover_letter_text: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        template_name: str = "jakes"
    ) -> str:
        """Render tailored cover letter to print-ready HTML matching Jake's styling."""
        raw_text = cover_letter_text or (app.cover_letter if app else "")
        body_text = raw_text
        if "---" in raw_text:
            parts = raw_text.split("---")
            if len(parts) >= 2:
                candidate_body = parts[1].strip()
                if candidate_body:
                    body_text = candidate_body

        paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        if not paragraphs and raw_text:
            paragraphs = [raw_text.strip()]

        comp = company or (app.job.company if app and app.job else "")
        job_t = title or (app.job.title if app and app.job else "")

        template = self.env.get_template("cover_letter/cover_letter.html.jinja2")
        return template.render(
            profile=profile,
            app=app,
            company=comp,
            title=job_t,
            paragraphs=paragraphs,
            today=datetime.now().strftime("%B %d, %Y")
        )

    def render_portal_qna(
        self,
        profile: CandidateProfile,
        app: TailoredApplication
    ) -> str:
        """Render pre-formatted answers to portal screening questions."""
        template = self.env.get_template("portal/qna.md.jinja2")
        return template.render(
            profile=profile,
            app=app
        )

    def export_json_resume(self, profile: CandidateProfile) -> str:
        """Export candidate profile in standard JSON Resume schema."""
        return json.dumps(profile.to_json_resume(), indent=2)


def parse_markdown_resume_experiences(
    md_text: str,
    existing_experiences: Optional[List[WorkExperience]] = None
) -> Tuple[List[WorkExperience], str]:
    """Parse resume markdown into structured WorkExperience objects and a bullet editor string.

    Extracts experience bullets and role headings from markdown (under ## EXPERIENCE or entire text),
    reconciling them with any existing WorkExperience objects to preserve metadata (dates, locations, etc.).
    Returns (updated_experiences, editor_bullet_text).
    """
    lines = md_text.splitlines()
    in_exp_section = False
    exp_lines = []

    # 1. Look for ## EXPERIENCE section
    has_exp_section = False
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if re.match(r"^##\s+(?:WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT\s+HISTORY|PROFESSIONAL\s+EXPERIENCE)", upper):
            in_exp_section = True
            has_exp_section = True
            continue
        elif in_exp_section and stripped.startswith("## "):
            in_exp_section = False
            break
        elif in_exp_section:
            exp_lines.append(stripped)

    # If no explicit ## EXPERIENCE section found, filter out other known sections
    if not has_exp_section:
        current_sec = ""
        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()
            if stripped.startswith("## "):
                current_sec = upper
                continue
            if any(k in current_sec for k in ("EDUCATION", "PROJECT", "SKILL", "CERTIF", "LANGUAGE", "SUMMARY")):
                continue
            exp_lines.append(stripped)

    # 2. Parse headings and bullets from exp_lines
    parsed_items: List[Dict[str, Any]] = []
    current_item: Optional[Dict[str, Any]] = None
    has_subheadings = any(line.startswith("### ") for line in exp_lines)

    for line in exp_lines:
        if line.startswith("### "):
            heading = line[4:].strip()
            role = heading
            company = ""
            if " - " in heading:
                parts = heading.split(" - ", 1)
                role, company = parts[0].strip(), parts[1].strip()
            elif " @ " in heading:
                parts = heading.split(" @ ", 1)
                role, company = parts[0].strip(), parts[1].strip()
            elif ", " in heading:
                parts = heading.split(", ", 1)
                role, company = parts[0].strip(), parts[1].strip()

            current_item = {"role": role, "company": company, "bullets": []}
            parsed_items.append(current_item)
        elif line.startswith(("- ", "* ", "• ")):
            bullet = re.sub(r"^[-*•\s]+", "", line).strip()
            if bullet:
                if current_item is None:
                    current_item = {"role": "", "company": "", "bullets": []}
                    parsed_items.append(current_item)
                current_item["bullets"].append(bullet)
        elif current_item and current_item["bullets"] and line and not line.startswith(("#", "---")):
            if not line.startswith(("*", "_", "http")):
                current_item["bullets"][-1] += " " + line.strip()

    # If no items parsed, fallback to existing experiences if available
    if not parsed_items and existing_experiences:
        parsed_items = [{"role": e.role, "company": e.company, "bullets": list(e.bullets)} for e in existing_experiences]

    # 3. Reconcile with existing_experiences
    updated_exps: List[WorkExperience] = []
    if existing_experiences:
        if not has_subheadings and parsed_items:
            # Bullets without explicit subheadings default to the first active work experience
            all_bullets = []
            for item in parsed_items:
                all_bullets.extend(item["bullets"])
            for idx, orig in enumerate(existing_experiences):
                exp = orig.model_copy(deep=True)
                if idx == 0:
                    exp.bullets = all_bullets
                else:
                    exp.bullets = []
                updated_exps.append(exp)
        else:
            for idx, item in enumerate(parsed_items):
                if idx < len(existing_experiences):
                    exp = existing_experiences[idx].model_copy(deep=True)
                    exp.bullets = item["bullets"]
                    if item.get("role"):
                        exp.role = item["role"]
                    if item.get("company"):
                        exp.company = item["company"]
                    updated_exps.append(exp)
                else:
                    updated_exps.append(
                        WorkExperience(
                            role=item.get("role") or "Experience",
                            company=item.get("company") or "",
                            bullets=item["bullets"]
                        )
                    )
            for idx in range(len(parsed_items), len(existing_experiences)):
                exp = existing_experiences[idx].model_copy(deep=True)
                exp.bullets = []
                updated_exps.append(exp)
    else:
        for item in parsed_items:
            updated_exps.append(
                WorkExperience(
                    role=item.get("role") or "Experience",
                    company=item.get("company") or "",
                    bullets=item["bullets"]
                )
            )

    # 4. Generate formatted bullet editor text for Studio Lab
    editor_lines = []
    for exp in updated_exps:
        r = exp.role or "Experience"
        c = f" @ {exp.company}" if exp.company else ""
        editor_lines.append(f"### {r}{c}")
        for b in exp.bullets:
            editor_lines.append(f"- {b}")
        editor_lines.append("")

    editor_text = "\n".join(editor_lines).strip()
    return updated_exps, editor_text
