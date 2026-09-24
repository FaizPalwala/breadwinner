"""Full-featured Textual Terminal User Interface for Breadwinner."""

import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, TabbedContent, TabPane, DataTable,
    Button, Input, Label, Static, RadioSet, RadioButton,
    Select, Markdown, TextArea
)
from textual.screen import ModalScreen
from textual.binding import Binding

from breadwinner.config import settings
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.db.sync import CsvSync
from breadwinner.providers.discovery import ProviderDiscovery
from breadwinner.core.portfolio import get_profile_source
from breadwinner.core.scraper import JobScraper
from breadwinner.core.persona import PersonaManager
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.models import TailoredApplication, CandidateProfile, WorkExperience
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer, PDFGenerationError
from breadwinner.providers.factory import get_llm_provider


class StatusModal(ModalScreen):
    """Modal screen for updating job status."""

    DEFAULT_CSS = """
    StatusModal {
        align: center middle;
    }
    #status-dialog {
        padding: 1 2;
        background: $surface;
        border: thick $primary;
        width: 50;
        height: auto;
    }
    """

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"[bold]Update Status for {self.job.company}:[/bold]"),
            RadioSet(
                RadioButton("Target", value=self.job.status == "target", id="rb-target"),
                RadioButton("Tailored", value=self.job.status == "tailored", id="rb-tailored"),
                RadioButton("Applied", value=self.job.status == "applied", id="rb-applied"),
                RadioButton("Interviewing", value=self.job.status == "interviewing", id="rb-interviewing"),
                RadioButton("Offer", value=self.job.status == "offer", id="rb-offer"),
                RadioButton("Rejected", value=self.job.status == "rejected", id="rb-rejected"),
                RadioButton("Archived", value=self.job.status == "archived", id="rb-archived"),
                id="status-radios"
            ),
            Horizontal(
                Button("Save", variant="success", id="btn-save-status"),
                Button("Cancel", variant="error", id="btn-cancel-status")
            ),
            id="status-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-status":
            radios = self.query_one("#status-radios", RadioSet)
            selected_rb = radios.pressed_button
            if selected_rb:
                new_status = selected_rb.label.plain.lower()
                self.repo.update_status(self.job.id, new_status)
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.dismiss(True)
        else:
            self.dismiss(False)


class FlagModal(ModalScreen):
    """Modal screen for toggling custom flags."""

    DEFAULT_CSS = """
    FlagModal {
        align: center middle;
    }
    #flag-dialog {
        padding: 1 2;
        background: $surface;
        border: thick $warning;
        width: 50;
        height: auto;
    }
    """

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"[bold]Set Flag for {self.job.company}:[/bold]"),
            RadioSet(
                RadioButton("None (Clear Flag)", value=self.job.flag is None, id="flag-none"),
                RadioButton("High Priority", value=self.job.flag == "high_priority", id="flag-high"),
                RadioButton("Follow-up Needed", value=self.job.flag == "followup_needed", id="flag-follow"),
                RadioButton("Link Broken", value=self.job.flag == "link_broken", id="flag-broken"),
                id="flag-radios"
            ),
            Horizontal(
                Button("Save", variant="success", id="btn-save-flag"),
                Button("Cancel", variant="error", id="btn-cancel-flag")
            ),
            id="flag-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-flag":
            radios = self.query_one("#flag-radios", RadioSet)
            selected_rb = radios.pressed_button
            if selected_rb:
                val = selected_rb.label.plain.lower()
                flag_map = {
                    "none (clear flag)": None,
                    "high priority": "high_priority",
                    "follow-up needed": "followup_needed",
                    "link broken": "link_broken"
                }
                new_flag = flag_map.get(val)
                self.repo.set_flag(self.job.id, new_flag)
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.dismiss(True)
        else:
            self.dismiss(False)


class FineTuneModal(ModalScreen):
    """Modal screen for fine-tuning experience bullet points before final bake."""

    DEFAULT_CSS = """
    FineTuneModal {
        align: center middle;
    }
    #finetune-dialog {
        padding: 1 2;
        background: #0f172a;
        border: thick #f59e0b;
        width: 85%;
        height: 80%;
    }
    #finetune-editor {
        height: 1fr;
        margin: 1 0;
        background: #1e293b;
        color: #fef3c7;
        border: solid #d97706;
    }
    """

    def __init__(self, initial_text: str):
        super().__init__()
        self.initial_text = initial_text

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold yellow]🥖 Interactive Bullet Fine-Tuning Studio[/bold yellow]"),
            Label("[dim]Edit, tighten, or adjust metrics. Each bullet should begin with a dash (-) or be separated by newlines.[/dim]"),
            TextArea(self.initial_text, id="finetune-editor"),
            Horizontal(
                Button("Apply & Re-Bake (Enter)", variant="success", id="btn-save-finetune"),
                Button("Cancel", variant="error", id="btn-cancel-finetune"),
                classes="action-bar"
            ),
            id="finetune-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-finetune":
            editor = self.query_one("#finetune-editor", TextArea)
            self.dismiss(editor.text)
        else:
            self.dismiss(None)


class BreadwinnerApp(App):
    """Breadwinner Interactive TUI Application."""

    TITLE = "Breadwinner"
    SUB_TITLE = "The Anti-Slop Local Career Studio 🍞"
    CSS = """
    Screen {
        background: #0b0f19;
        color: #f8fafc;
    }
    Header {
        background: #1e293b;
        color: #f59e0b;
        text-style: bold;
    }
    Footer {
        background: #1e293b;
    }
    TabbedContent {
        height: 100%;
    }
    TabPane {
        padding: 1;
        height: 100%;
    }
    #active-badge {
        dock: top;
        padding: 0 1;
        background: #1e293b;
        color: #f59e0b;
        text-style: bold;
    }
    DataTable {
        height: 1fr;
        border: solid #334155;
    }
    #job-details-pane {
        height: 8;
        border-top: solid #f59e0b;
        padding: 0 1;
        background: #1e293b;
    }
    .action-bar {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    .action-bar Button {
        margin-right: 1;
    }
    .input-label {
        text-style: bold;
        color: #f59e0b;
        margin-top: 1;
        margin-bottom: 0;
    }
    #tailor-status-box {
        margin-top: 1;
        padding: 1;
        background: #1e293b;
        border: solid #10b981;
    }
    .preview-box {
        height: 1fr;
        border: solid #334155;
        padding: 1;
        background: #090d16;
    }
    .provider-card {
        border: solid #334155;
        padding: 1;
        margin-bottom: 1;
        background: #1e293b;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "tab_pipeline", "Pipeline", show=True),
        Binding("2", "tab_studio", "Studio", show=True),
        Binding("3", "tab_models", "Models", show=True),
        Binding("4", "tab_profile", "Profile", show=True),
        Binding("b", "bake_pdf", "Bake PDF", show=True),
        Binding("v", "view_pdf", "View PDF", show=True),
        Binding("e", "finetune_bullets", "Fine-Tune", show=True),
        Binding("s", "change_status", "Change Status", show=True),
        Binding("f", "toggle_flag", "Toggle Flag", show=True),
        Binding("o", "open_folder", "Open Folder", show=True),
        Binding("r", "refresh_data", "Refresh", show=True),
    ]

    def __init__(self, initial_url: Optional[str] = None):
        super().__init__()
        self.initial_url = initial_url
        self.repo = JobRepository(settings.database_path)
        self.selected_job: Optional[JobRecord] = None
        self.last_tailored_dir: Optional[Path] = None
        self.current_profile: Optional[CandidateProfile] = None
        self.current_app_result: Optional[TailoredApplication] = None
        self.current_template: str = settings.default_template

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(self.get_active_badge_text(), id="active-badge")
        with TabbedContent(initial="tab-pipeline", id="main-tabs"):
            # TAB 1: PIPELINE TRACKER
            with TabPane("Pipeline Tracker (The Breadbox)", id="tab-pipeline"):
                yield DataTable(id="pipeline-table", cursor_type="row")
                yield Vertical(
                    Label("[bold yellow]Selected Application Details:[/bold yellow]", id="details-header"),
                    Static("Select a job row above to inspect details.", id="details-body"),
                    id="job-details-pane"
                )
                yield Horizontal(
                    Button("Update Status (s)", variant="primary", id="btn-status"),
                    Button("Set Flag (f)", variant="warning", id="btn-flag"),
                    Button("Bake PDF (b)", variant="success", id="btn-pipeline-bake"),
                    Button("View PDF (v)", variant="primary", id="btn-pipeline-view-pdf"),
                    Button("Open Folder (o)", variant="default", id="btn-open-folder"),
                    Button("Refresh (r)", variant="default", id="btn-refresh"),
                    classes="action-bar"
                )

            # TAB 2: TAILOR STUDIO
            with TabPane("Tailor Studio (The Oven)", id="tab-studio"):
                with VerticalScroll():
                    yield Label("Target Job URL or Markdown File:", classes="input-label")
                    yield Input(
                        placeholder="https://boards.greenhouse.io/monzo/jobs/... or /path/to/jd.txt",
                        value=self.initial_url or "",
                        id="input-job-url"
                    )
                    
                    yield Horizontal(
                        Vertical(
                            Label("Target Narrative Persona:", classes="input-label"),
                            Select(
                                [
                                    ("Tech & AI (SDE / MLE / Distributed)", "tech_ai"),
                                    ("Bridging Admin (De-tuned / Exact)", "bridging_admin"),
                                    ("Hospitality (Fast-paced / Service)", "hospitality")
                                ],
                                value="tech_ai",
                                id="select-persona"
                            )
                        ),
                        Vertical(
                            Label("Resume Template:", classes="input-label"),
                            Select(
                                [
                                    ("Jake's Resume (r/EngineeringResumes Standard)", "jakes"),
                                    ("Modern Clean (HTML/CSS)", "modern"),
                                    ("Clean ATS Markdown", "ats")
                                ],
                                value="jakes",
                                id="select-template"
                            )
                        )
                    )

                    yield Button("Run Tailoring Engine (1st Draft)", variant="success", id="btn-run-tailor")
                    yield Static("", id="tailor-status-box")

                    with TabbedContent(id="preview-tabs"):
                        with TabPane("Resume Preview", id="preview-resume-tab"):
                            yield Markdown("No application tailored yet. Enter a URL above and click 'Run Tailoring Engine'.", id="preview-resume-md", classes="preview-box")
                        with TabPane("Cover Letter", id="preview-letter-tab"):
                            yield Markdown("Cover letter will appear here.", id="preview-letter-md", classes="preview-box")
                        with TabPane("Portal Q&A", id="preview-qna-tab"):
                            yield Markdown("Portal Q&A will appear here.", id="preview-qna-md", classes="preview-box")

                    yield Horizontal(
                        Button("Fine-Tune Bullets (e)", variant="warning", id="btn-studio-finetune"),
                        Button("Bake ATS PDF (b)", variant="success", id="btn-studio-bake"),
                        Button("View PDF (v)", variant="primary", id="btn-studio-view-pdf"),
                        Button("View HTML (p)", variant="default", id="btn-studio-browser"),
                        Button("Open in Finder (o)", variant="default", id="btn-studio-folder"),
                        Button("Mark Applied (s)", variant="default", id="btn-studio-applied"),
                        classes="action-bar"
                    )

            # TAB 3: MODELS & PROVIDERS
            with TabPane("Model Switcher", id="tab-models"):
                with VerticalScroll(id="models-container"):
                    yield Label("[bold yellow]Discovered LLM Providers & Models:[/bold yellow]")
                    yield Static("Loading provider statuses...", id="models-list-box")

            # TAB 4: CANDIDATE PROFILE
            with TabPane("Portfolio Pantry", id="tab-profile"):
                with VerticalScroll():
                    yield Markdown(self.get_profile_markdown(), id="profile-md")

        yield Footer()

    def on_mount(self) -> None:
        self.load_pipeline_table()
        self.load_models_tab()

    def get_active_badge_text(self) -> str:
        provider = settings.breadwinner_llm_provider.upper()
        if provider == "LMSTUDIO":
            model = settings.lmstudio_model
        elif provider == "GEMINI":
            model = settings.gemini_model
        elif provider == "DEEPSEEK":
            model = settings.deepseek_model
        elif provider == "GROQ":
            model = settings.groq_model
        else:
            model = "default"
        return f" 🥖 Breadwinner Studio | Active Engine: [{provider}: {model}] | Source: {settings.portfolio_path} "

    def load_pipeline_table(self) -> None:
        table = self.query_one("#pipeline-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Company", "Role", "Status", "Match", "Date Added", "Flag")

        jobs = self.repo.list_jobs()
        for j in jobs:
            status_style = {
                "target": "[dim]TARGET[/dim]",
                "tailored": "[cyan]TAILORED[/cyan]",
                "applied": "[blue]APPLIED[/blue]",
                "interviewing": "[bold green]INTERVIEWING[/bold green]",
                "offer": "[bold magenta]OFFER[/bold magenta]",
                "rejected": "[red]REJECTED[/red]",
                "archived": "[dim]ARCHIVED[/dim]"
            }.get(j.status.lower(), j.status.upper())

            match_str = f"{j.match_score}%" if j.match_score is not None else "-"
            flag_str = f"⚠️ {j.flag}" if j.flag else ""

            table.add_row(
                j.id,
                j.company,
                j.title,
                status_style,
                match_str,
                j.date_added,
                flag_str,
                key=j.id
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        self.selected_job = self.repo.get_job(row_key)
        self.update_details_pane()

    def update_details_pane(self) -> None:
        details_body = self.query_one("#details-body", Static)
        if not self.selected_job:
            details_body.update("No job selected.")
            return

        j = self.selected_job
        folder_info = f"Folder: [cyan]{j.folder_path}[/cyan]" if j.folder_path else "Not tailored yet"
        url_info = f"URL: [underline blue]{j.url}[/underline blue]" if j.url else "No URL"
        notes_info = f"Notes: {j.notes}" if j.notes else ""
        details_body.update(
            f"[bold]{j.company}[/bold] — {j.title} | Status: [bold]{j.status.upper()}[/bold]\n"
            f"{url_info} | Location: {j.location or 'N/A'}\n"
            f"{folder_info} | {notes_info}"
        )

    def load_models_tab(self) -> None:
        models_box = self.query_one("#models-list-box", Static)
        statuses = ProviderDiscovery.discover_all()
        lines = []

        for p in statuses:
            is_active = p.slug == settings.breadwinner_llm_provider
            active_str = " [bold green](ACTIVE PROVIDER)[/bold green]" if is_active else ""
            lines.append(f"\n### {p.name}{active_str}")
            lines.append(f"- **Health:** {p.status_text}")
            if p.base_url:
                lines.append(f"- **Base URL:** `{p.base_url}`")
            if p.models:
                lines.append("- **Models:**")
                for m in p.models:
                    marker = "  * 👉 **" if m.is_active else "  * "
                    suffix = "** (Active)" if m.is_active else ""
                    lines.append(f"{marker}`{m.id}`{suffix}")
            else:
                lines.append("- *No models detected or credentials missing in .env*")

        models_box.update("\n".join(lines))

    def get_profile_markdown(self) -> str:
        try:
            adapter = get_profile_source(settings.portfolio_path)
            profile = adapter.load_profile()
            lines = [
                f"# {profile.full_name}",
                f"**Title:** {profile.title} | **Location:** {profile.location}",
                f"\n**Summary:** {profile.summary}",
                "\n---",
                "\n## Verified Work Experiences",
            ]
            for exp in profile.experiences:
                lines.append(f"\n### {exp.role} @ {exp.company} ({exp.start_date} - {exp.end_date})")
                for b in exp.bullets:
                    lines.append(f"- {b}")

            lines.append("\n---")
            lines.append("\n## Projects & Case Studies")
            for proj in profile.projects:
                tech = ", ".join(proj.tech_stack) if proj.tech_stack else "General"
                lines.append(f"\n### {proj.name} ({tech})")
                lines.append(proj.description)

            lines.append("\n---")
            lines.append("\n## Education")
            for edu in profile.education:
                lines.append(f"- **{edu.degree}** @ {edu.institution}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error loading candidate profile: {e}"

    # ACTIONS
    def action_tab_pipeline(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-pipeline"

    def action_tab_studio(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-studio"

    def action_tab_models(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-models"

    def action_tab_profile(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-profile"

    def action_refresh_data(self) -> None:
        self.load_pipeline_table()
        self.load_models_tab()
        self.notify("Refreshed pipeline and models.", title="Updated")

    def action_change_status(self) -> None:
        if self.selected_job:
            self.push_screen(StatusModal(self.selected_job, self.repo), self._on_modal_dismissed)
        else:
            self.notify("Please select a job from the table first.", severity="warning")

    def action_toggle_flag(self) -> None:
        if self.selected_job:
            self.push_screen(FlagModal(self.selected_job, self.repo), self._on_modal_dismissed)
        else:
            self.notify("Please select a job from the table first.", severity="warning")

    def action_open_folder(self) -> None:
        target_dir = None
        if self.selected_job and self.selected_job.folder_path:
            target_dir = Path(self.selected_job.folder_path)
        elif self.last_tailored_dir:
            target_dir = self.last_tailored_dir

        if target_dir and target_dir.exists():
            subprocess.run(["open", str(target_dir)])
            self.notify(f"Opened folder: {target_dir.name}", title="Finder")
        else:
            self.notify("No application folder generated for this job yet.", severity="warning")

    def action_bake_pdf(self) -> None:
        target_dir = None
        if self.last_tailored_dir and (self.last_tailored_dir / "resume.html").exists():
            target_dir = self.last_tailored_dir
        elif self.selected_job and self.selected_job.folder_path:
            p = Path(self.selected_job.folder_path)
            if p.exists() and (p / "resume.html").exists():
                target_dir = p

        if not target_dir:
            self.notify("Please tailor a job first or select a job with resume.html.", severity="warning")
            return

        html_path = target_dir / "resume.html"
        pdf_path = target_dir / "resume.pdf"
        self.notify("Baking print-ready ATS PDF in headless browser...", title="Breadwinner Bakery")

        try:
            render_html_to_pdf(html_path, pdf_path, open_after=False)
            size_kb = round(pdf_path.stat().st_size / 1024, 1)
            self.notify(f"✓ Fresh out of the oven! Baked resume.pdf ({size_kb} KB)", title="Bake Complete")
        except Exception as e:
            self.notify(f"Bake failed: {e}", severity="error")

    def action_view_pdf(self) -> None:
        target_dir = None
        if self.last_tailored_dir and (self.last_tailored_dir / "resume.pdf").exists():
            target_dir = self.last_tailored_dir
        elif self.selected_job and self.selected_job.folder_path:
            p = Path(self.selected_job.folder_path)
            if p.exists() and (p / "resume.pdf").exists():
                target_dir = p

        if target_dir and (target_dir / "resume.pdf").exists():
            open_file_in_viewer(target_dir / "resume.pdf")
            self.notify(f"Opened resume.pdf in system viewer.", title="Preview")
        else:
            self.notify("No resume.pdf found. Press 'b' to bake one first!", severity="warning")

    def action_finetune_bullets(self) -> None:
        if not self.current_app_result or not self.current_app_result.tailored_experiences:
            self.notify("Run the tailoring engine on a job first to fine-tune bullets.", severity="warning")
            return

        # Prepare editable bullet text
        lines = []
        for exp in self.current_app_result.tailored_experiences:
            lines.append(f"### {exp.role} @ {exp.company}")
            for b in exp.bullets:
                lines.append(f"- {b}")
            lines.append("")

        initial_text = "\n".join(lines).strip()
        self.push_screen(FineTuneModal(initial_text), self._on_finetune_saved)

    def _on_finetune_saved(self, updated_text: Optional[str]) -> None:
        if not updated_text or not self.current_app_result or not self.last_tailored_dir:
            return

        # Parse updated bullets back into tailored_experiences
        current_exp_idx = -1
        new_experiences = list(self.current_app_result.tailored_experiences)

        for line in updated_text.splitlines():
            line = line.strip()
            if line.startswith("### "):
                current_exp_idx += 1
                if current_exp_idx < len(new_experiences):
                    new_experiences[current_exp_idx].bullets = []
            elif line.startswith("- ") and current_exp_idx >= 0 and current_exp_idx < len(new_experiences):
                bullet_content = line[2:].strip()
                if bullet_content:
                    new_experiences[current_exp_idx].bullets.append(bullet_content)

        self.current_app_result.tailored_experiences = new_experiences

        # Re-render artifacts
        renderer = TemplateRenderer()
        resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)
        resume_md = renderer.render_resume(self.current_profile, self.current_app_result, "ats")

        (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")
        (self.last_tailored_dir / "resume.md").write_text(resume_md, encoding="utf-8")

        # Auto re-bake PDF
        try:
            render_html_to_pdf(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
        except Exception:
            pass

        self.query_one("#preview-resume-md", Markdown).update(resume_md)
        self.notify("Updated tailored bullets and re-baked resume.pdf!", title="Fine-Tune Applied")

    def _on_modal_dismissed(self, updated: bool) -> None:
        if updated:
            self.load_pipeline_table()
            if self.selected_job:
                self.selected_job = self.repo.get_job(self.selected_job.id)
                self.update_details_pane()

    # BUTTON HANDLERS
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-status":
            self.action_change_status()
        elif bid == "btn-flag":
            self.action_toggle_flag()
        elif bid == "btn-open-folder":
            self.action_open_folder()
        elif bid == "btn-refresh":
            self.action_refresh_data()
        elif bid == "btn-run-tailor":
            self.run_tailoring_flow()
        elif bid == "btn-studio-finetune":
            self.action_finetune_bullets()
        elif bid == "btn-studio-bake" or bid == "btn-pipeline-bake":
            self.action_bake_pdf()
        elif bid == "btn-studio-view-pdf" or bid == "btn-pipeline-view-pdf":
            self.action_view_pdf()
        elif bid == "btn-studio-folder":
            self.action_open_folder()
        elif bid == "btn-studio-browser":
            if self.last_tailored_dir and (self.last_tailored_dir / "resume.html").exists():
                webbrowser.open(f"file://{self.last_tailored_dir / 'resume.html'}")
            else:
                self.notify("No resume.html generated yet.", severity="warning")
        elif bid == "btn-studio-applied":
            if self.selected_job:
                self.repo.update_status(self.selected_job.id, "applied")
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
                self.notify("Marked application as APPLIED!", title="Updated")
                self.load_pipeline_table()

    def run_tailoring_flow(self) -> None:
        url_input = self.query_one("#input-job-url", Input).value.strip()
        if not url_input:
            self.notify("Please enter a job URL or paste a JD file path.", severity="error")
            return

        status_box = self.query_one("#tailor-status-box", Static)
        status_box.update("[bold yellow]⏳ Ingesting job and running tailoring engine...[/bold yellow]")

        try:
            # 1. Ingest Job
            p_source = Path(url_input)
            if url_input.startswith("http://") or url_input.startswith("https://"):
                job = JobScraper.ingest_from_url(url_input)
            elif p_source.is_file():
                job = JobScraper.ingest_from_text(p_source.read_text(encoding="utf-8"), "Company", "Role")
            else:
                job = JobScraper.ingest_from_text(url_input, "Company", "Role")

            # 2. Ingest Profile
            adapter = get_profile_source(settings.portfolio_path)
            profile = adapter.load_profile()
            self.current_profile = profile

            # 3. Persona & Provider
            persona_slug = self.query_one("#select-persona", Select).value
            template_name = self.query_one("#select-template", Select).value
            self.current_template = template_name
            persona = PersonaManager.load_persona(persona_slug)
            provider = get_llm_provider()

            # 4. Tailor
            engine = TailoringEngine(provider)
            app_result = engine.analyze_and_tailor(profile, job, persona)
            self.current_app_result = app_result

            # 5. Render
            renderer = TemplateRenderer()
            resume_html = renderer.render_resume(profile, app_result, template_name)
            resume_md = renderer.render_resume(profile, app_result, "ats")
            cover_letter = renderer.render_cover_letter(profile, app_result)
            portal_qna = renderer.render_portal_qna(profile, app_result)
            json_resume = renderer.export_json_resume(profile)

            # 6. Save
            date_slug = datetime.now().strftime("%Y-%m-%d")
            safe_c = "".join(c for c in job.company if c.isalnum() or c in "-_")
            safe_t = "".join(c for c in job.title if c.isalnum() or c in "-_")
            app_dir = settings.applications_dir / f"{date_slug}_{safe_c}_{safe_t}"
            app_dir.mkdir(parents=True, exist_ok=True)

            (app_dir / "resume.html").write_text(resume_html, encoding="utf-8")
            (app_dir / "resume.md").write_text(resume_md, encoding="utf-8")
            (app_dir / "resume.json").write_text(json_resume, encoding="utf-8")
            (app_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
            (app_dir / "portal_answers.md").write_text(portal_qna, encoding="utf-8")
            self.last_tailored_dir = app_dir

            # 7. Auto-bake PDF
            pdf_notice = ""
            if settings.auto_generate_pdf:
                try:
                    render_html_to_pdf(app_dir / "resume.html", app_dir / "resume.pdf", open_after=False)
                    pdf_notice = " | [bold green]Baked resume.pdf ✓[/bold green]"
                except Exception as pe:
                    pdf_notice = f" | [dim]PDF: run 'b' to bake ({pe})[/dim]"

            # 8. Record in SQLite
            job_rec = JobRecord(
                id=job.id,
                company=job.company,
                title=job.title,
                url=job.url,
                location=job.location,
                portal_type=job.portal_type,
                status="tailored",
                match_score=app_result.match_analysis.match_score,
                persona=persona.slug,
                date_added=date_slug,
                folder_path=str(app_dir.resolve()),
                notes=f"Tailored via {persona.name}"
            )
            self.repo.upsert_job(job_rec)
            self.selected_job = job_rec

            if settings.csv_tracker_path:
                CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)

            # 9. Update UI Previews
            score = app_result.match_analysis.match_score
            status_box.update(
                f"[bold green]✓ Fresh out of the oven![/bold green] "
                f"Target: [bold]{job.company} — {job.title}[/bold] | "
                f"ATS Match Score: [bold green]{score}%[/bold green]{pdf_notice}\n"
                f"Package saved to: [cyan]{app_dir}[/cyan]"
            )

            self.query_one("#preview-resume-md", Markdown).update(resume_md)
            self.query_one("#preview-letter-md", Markdown).update(cover_letter)
            self.query_one("#preview-qna-md", Markdown).update(portal_qna)

            self.notify(f"Tailored application for {job.company} ({score}% match)! Press 'b' to bake PDF.", title="Breadwinner Success")
            self.load_pipeline_table()

        except Exception as e:
            status_box.update(f"[bold red]Error during tailoring: {e}[/bold red]")
            self.notify(f"Tailoring failed: {e}", severity="error")
