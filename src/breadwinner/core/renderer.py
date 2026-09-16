"""Template rendering engine using Jinja2 for multi-format export."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader

from breadwinner.core.models import CandidateProfile, TailoredApplication


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
