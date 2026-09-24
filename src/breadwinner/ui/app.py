"""Full-featured Textual Terminal User Interface for Breadwinner."""

import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

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
from breadwinner.core.persona import (
    Persona,
    PersonaManager,
    generate_job_strategy_questions,
    synthesize_job_directives,
    synthesize_job_persona,
)
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.models import TailoredApplication, CandidateProfile, WorkExperience, JobPosting
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer, PDFGenerationError
from breadwinner.core.pantry import PantryManager
from breadwinner.core.ingestor import UniversalIngestor, IngestionError
from breadwinner.core.interview import INTERVIEW_QUESTIONS, synthesize_context
from breadwinner.providers.factory import get_llm_provider
from breadwinner.ui.retro import (
    RETRO_THEME_CSS,
    AnimatedOven,
    AnimatedMascot,
    BakeryStepper,
    RetroProgressBar,
    BakingModal
)


def get_persona_select_options() -> List[tuple]:
    """Dynamically compile persona options for the dropdown."""
    personas = PersonaManager.list_personas()
    opts = []
    for slug, desc in personas.items():
        clean = desc.replace("[bold green]", "").replace("[/bold green]", "")
        opts.append((f"{slug.upper()}: {clean[:40]}", slug))
    return opts or [("Tech & AI (SDE / MLE / Distributed)", "tech_ai")]


class JobStrategyModal(ModalScreen):
    """Modal screen for the target job strategy interview loop."""

    DEFAULT_CSS = """
    JobStrategyModal {
        align: center middle;
    }
    #strategy-dialog {
        padding: 1 2;
        background: $surface;
        border: thick $primary;
        width: 82;
        height: auto;
        max-height: 90%;
    }
    .strategy-q-label {
        font-weight: bold;
        color: $accent;
        margin-top: 1;
    }
    .strategy-q-sub {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, job: JobPosting, questions: List[Dict[str, str]], base_persona: Persona):
        super().__init__()
        self.job = job
        self.questions = questions
        self.base_persona = base_persona

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="strategy-dialog"):
            yield Label(f"[bold cyan]Target Strategy Loop:[/bold cyan] [bold white]{self.job.company} — {self.job.title}[/bold white]")
            yield Label(
                "[dim]Answer these targeted questions to synthesize customized role directives and/or save a new persona.[/dim]"
            )

            for idx, q in enumerate(self.questions, 1):
                yield Label(f"{idx}. {q.get('title', 'Question')}", classes="strategy-q-label")
                yield Label(q.get("question", ""), classes="strategy-q-sub")
                yield Input(
                    placeholder=q.get("placeholder", "Your strategic answer..."),
                    id=f"input-strat-q-{idx}"
                )

            yield Label("[bold]Save as Reusable Persona (Optional):[/bold]", classes="strategy-q-label")
            yield Input(
                placeholder=f"Persona Name (e.g. {self.job.company} {self.job.title} Strategist)",
                id="input-persona-name"
            )
            yield Input(
                placeholder=f"Persona Slug (e.g. {self.job.company.lower()}_{self.job.title.lower()})",
                id="input-persona-slug"
            )

            with Horizontal():
                yield Button("Bake with Strategy", variant="success", id="btn-submit-strategy")
                yield Button("Cancel", variant="error", id="btn-cancel-strategy")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit-strategy":
            answers = {}
            for idx, q in enumerate(self.questions, 1):
                inp = self.query_one(f"#input-strat-q-{idx}", Input)
                if inp.value.strip():
                    answers[q.get("id", f"q{idx}")] = inp.value.strip()

            p_name = self.query_one("#input-persona-name", Input).value.strip()
            p_slug = self.query_one("#input-persona-slug", Input).value.strip()
            save = bool(p_name or p_slug)

            self.dismiss({
                "answers": answers,
                "save_persona": save,
                "persona_name": p_name,
                "persona_slug": p_slug
            })
        else:
            self.dismiss(None)


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


class PantryIngestModal(ModalScreen):
    """Modal to ingest background from a live URL, document file, or paste text."""

    DEFAULT_CSS = """
    PantryIngestModal {
        align: center middle;
    }
    #pantry-ingest-dialog {
        padding: 1 2;
        background: #0f172a;
        border: thick #38bdf8;
        width: 75%;
        height: auto;
    }
    #pantry-source-input {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold cyan]Import Into Career Pantry[/bold cyan]"),
            Label("[dim]Enter a live portfolio website URL (https://...), a local file path (.json, .docx, .md), or paste raw bio text:[/dim]"),
            Input(placeholder="https://yourname.com or /path/to/resume.json", id="pantry-source-input"),
            Horizontal(
                Button("Ingest & Update Pantry", variant="success", id="btn-run-ingest"),
                Button("Cancel", variant="error", id="btn-cancel-ingest"),
                classes="action-bar"
            ),
            id="pantry-ingest-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run-ingest":
            val = self.query_one("#pantry-source-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)


class PantryInterviewModal(ModalScreen):
    """Modal to run the Baker's Interview loop for discovering qualitative career context."""

    DEFAULT_CSS = """
    PantryInterviewModal {
        align: center middle;
    }
    #interview-dialog {
        padding: 1 2;
        background: #0f172a;
        border: thick #f59e0b;
        width: 85%;
        height: 85%;
    }
    .interview-input {
        height: 5;
        margin-bottom: 1;
        background: #1e293b;
        color: #fef3c7;
        border: solid #d97706;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold yellow]🥖 The Baker's Interview: Discovering Your Context[/bold yellow]"),
            Label("[dim]Answer 3 quick questions. Breadwinner will synthesize personal directives (context.md) to guide AI tailoring.[/dim]"),
            VerticalScroll(
                Label("[bold cyan]1. Target Roles & Boundaries:[/bold cyan]"),
                TextArea(id="int-q1", classes="interview-input"),
                Label("[bold cyan]2. Hidden Wins & STAR Proof Points:[/bold cyan]"),
                TextArea(id="int-q2", classes="interview-input"),
                Label("[bold cyan]3. Logistics, Location, Visa & Guardrails:[/bold cyan]"),
                TextArea(id="int-q3", classes="interview-input"),
            ),
            Horizontal(
                Button("Synthesize Directives (context.md)", variant="success", id="btn-save-interview"),
                Button("Cancel", variant="error", id="btn-cancel-interview"),
                classes="action-bar"
            ),
            id="interview-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-interview":
            ans = {
                "target_roles": self.query_one("#int-q1", TextArea).text.strip(),
                "star_stories": self.query_one("#int-q2", TextArea).text.strip(),
                "logistics_guardrails": self.query_one("#int-q3", TextArea).text.strip(),
            }
            self.dismiss(ans)
        else:
            self.dismiss(None)


class PantryHistoryModal(ModalScreen):
    """Modal showing historical snapshots of the Pantry with rollback options."""

    DEFAULT_CSS = """
    PantryHistoryModal {
        align: center middle;
    }
    #history-dialog {
        padding: 1 2;
        background: #0f172a;
        border: thick #38bdf8;
        width: 75%;
        height: 70%;
    }
    #history-table {
        height: 1fr;
        margin: 1 0;
    }
    """

    def __init__(self, snapshots: List[Dict[str, Any]]):
        super().__init__()
        self.snapshots = snapshots
        self.selected_snapshot_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold cyan]Pantry Snapshot History & Rollback[/bold cyan]"),
            Label("[dim]Select a historical snapshot to revert your career knowledge base to that point in time:[/dim]"),
            DataTable(id="history-table", cursor_type="row"),
            Horizontal(
                Button("Revert to Selected", variant="warning", id="btn-revert-snap"),
                Button("Close", variant="default", id="btn-close-snap"),
                classes="action-bar"
            ),
            id="history-dialog"
        )

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Snapshot ID", "Timestamp", "Trigger Event")
        for s in self.snapshots:
            table.add_row(s.get("id", ""), s.get("timestamp", ""), s.get("trigger", ""), key=s.get("id"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_snapshot_id = event.row_key.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-revert-snap":
            self.dismiss(self.selected_snapshot_id)
        else:
            self.dismiss(None)


class BreadwinnerApp(App):
    """Breadwinner Interactive TUI Application."""

    TITLE = "Breadwinner"
    SUB_TITLE = "Local 8-Bit Anti-Slop Career Studio 🍞👾"
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
    #studio-mascot-banner {
        height: auto;
        padding: 1;
        margin-bottom: 1;
        background: #101422;
        border: round #d18f52;
    }
    #studio-mascot {
        width: 34;
        height: auto;
    }
    #studio-mascot-text {
        height: auto;
        padding-left: 1;
    }
    """ + RETRO_THEME_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "tab_pipeline", "Pipeline", show=True),
        Binding("2", "tab_studio", "Studio", show=True),
        Binding("3", "tab_models", "Models", show=True),
        Binding("4", "tab_profile", "Pantry", show=True),
        Binding("b", "bake_pdf", "Bake PDF", show=True),
        Binding("v", "view_pdf", "View PDF", show=True),
        Binding("e", "finetune_bullets", "Fine-Tune", show=True),
        Binding("i", "pantry_ingest", "Ingest", show=True),
        Binding("m", "pantry_interview", "Interview", show=True),
        Binding("y", "pantry_sync", "Sync", show=True),
        Binding("h", "pantry_history", "History", show=True),
        Binding("s", "change_status", "Change Status", show=True),
        Binding("f", "toggle_flag", "Toggle Flag", show=True),
        Binding("o", "open_folder", "Open Folder", show=True),
        Binding("r", "refresh_data", "Refresh", show=True),
    ]

    def __init__(self, initial_url: Optional[str] = None):
        super().__init__()
        self.initial_url = initial_url
        self.repo = JobRepository(settings.database_path)
        self.pantry = PantryManager(settings.pantry_dir)
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
                    with Horizontal(id="studio-mascot-banner"):
                        yield AnimatedMascot(id="studio-mascot")
                        with Vertical(id="studio-mascot-text"):
                            yield Label("[bold #f59e0b]🥖 THE OVEN: TAILOR STUDIO[/bold #f59e0b]")
                            yield Label("[dim]Proofing verified experience bullets against role requirements without keyword-stuffing slop.[/dim]")
                            yield BakeryStepper(current_stage=0, id="studio-stepper")

                    yield Label("Target Job URL or Markdown File:", classes="input-label")
                    yield Input(
                        placeholder="https://boards.greenhouse.io/monzo/jobs/... or /path/to/jd.txt",
                        value=self.initial_url or "",
                        id="input-job-url"
                    )
                    
                    persona_opts = get_persona_select_options()
                    default_persona_val = settings.default_persona if any(v == settings.default_persona for _, v in persona_opts) else persona_opts[0][1]

                    yield Horizontal(
                        Vertical(
                            Label("Target Narrative Persona:", classes="input-label"),
                            Select(
                                persona_opts,
                                value=default_persona_val,
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

                    with Horizontal():
                        yield Button("Run Tailoring Engine (1st Draft)", variant="success", id="btn-run-tailor")
                        yield Button("Target Strategy Loop (Loop Qs)", variant="primary", id="btn-strategy-loop")
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

            # TAB 4: CANDIDATE PROFILE & PANTRY
            with TabPane("Portfolio Pantry (The Pantry)", id="tab-profile"):
                with VerticalScroll():
                    yield Markdown(self.get_profile_markdown(), id="profile-md")
                    yield Horizontal(
                        Button("Import / Ingest (i)", variant="primary", id="btn-pantry-ingest"),
                        Button("Baker's Interview (m)", variant="warning", id="btn-pantry-interview"),
                        Button("Sync from Portfolio (y)", variant="success", id="btn-pantry-sync"),
                        Button("History & Rollback (h)", variant="default", id="btn-pantry-history"),
                        classes="action-bar"
                    )

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
        src_label = "Pantry" if self.pantry.is_initialized() else settings.portfolio_path.name
        return f" 👾 BREADWINNER ARCADE | [bold #50fa7b]ONLINE[/bold #50fa7b] | Engine: [{provider}: {model}] | Source: {src_label} "

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
            if self.pantry.is_initialized():
                profile = self.pantry.load_profile()
                context = self.pantry.load_context()
                meta = self.pantry.load_source_metadata()
                src_note = f"*(Linked Source: {meta.get('source', 'Local')})*" if meta else "*(Canonical Pantry)*"
            else:
                adapter = get_profile_source(settings.portfolio_path)
                profile = adapter.load_profile()
                context = ""
                src_note = f"*(External Source: {settings.portfolio_path})*"

            lines = [
                f"# {profile.full_name} {src_note}",
                f"**Title:** {profile.title} | **Location:** {profile.location} | **Email:** {profile.email}",
                f"\n**Summary:** {profile.summary}",
                "\n---",
                f"\n## Verified Work Experiences ({len(profile.experiences)})",
            ]
            for exp in profile.experiences:
                lines.append(f"\n### {exp.role} @ {exp.company} ({exp.start_date} - {exp.end_date})")
                for b in exp.bullets:
                    lines.append(f"- {b}")

            lines.append("\n---")
            lines.append(f"\n## Projects & Case Studies ({len(profile.projects)})")
            for proj in profile.projects:
                tech = ", ".join(proj.tech_stack) if proj.tech_stack else "General"
                lines.append(f"\n### {proj.name} ({tech})")
                lines.append(proj.description)

            lines.append("\n---")
            lines.append(f"\n## Education ({len(profile.education)})")
            for edu in profile.education:
                lines.append(f"- **{edu.degree}** @ {edu.institution}")

            if context:
                lines.append("\n---")
                lines.append("\n## Personal Directives & Guardrails (`context.md`)")
                lines.append(context)

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
        self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
        self.notify("Refreshed pipeline, models, and pantry.", title="Updated")

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

        self.push_screen(
            BakingModal(task_type="bake_pdf", target_info={"app_dir": target_dir}),
            self._on_pdf_bake_modal_dismissed
        )

    def _on_pdf_bake_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or not result.get("success"):
            return
        size_kb = result.get("size_kb", 0.0)
        self.notify(f"✓ Fresh out of the oven! Baked resume.pdf ({size_kb} KB)", title="Bake Complete")
        try:
            self.query_one("#studio-stepper", BakeryStepper).set_stage(4)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message("Crisp ATS PDF Baked!")
        except Exception:
            pass

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

        renderer = TemplateRenderer()
        resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)
        resume_md = renderer.render_resume(self.current_profile, self.current_app_result, "ats")

        (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")
        (self.last_tailored_dir / "resume.md").write_text(resume_md, encoding="utf-8")

        try:
            render_html_to_pdf(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
        except Exception:
            pass

        self.query_one("#preview-resume-md", Markdown).update(resume_md)
        self.notify("Updated tailored bullets and re-baked resume.pdf!", title="Fine-Tune Applied")

    # PANTRY ACTIONS
    def action_pantry_ingest(self) -> None:
        self.push_screen(PantryIngestModal(), self._on_ingest_submitted)

    def _on_ingest_submitted(self, source: Optional[str]) -> None:
        if not source:
            return

        self.notify(f"Ingesting candidate context from {source[:30]}...", title="Pantry Ingest")
        provider = get_llm_provider()
        try:
            new_profile = UniversalIngestor.ingest(source, provider)
            source_meta = {"source": source, "type": "url" if source.startswith("http") else "file"}
            self.pantry.save_pantry(new_profile, source_info=source_meta, trigger=f"tui_ingest_{source[:15]}")
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.notify(f"✓ Ingested profile for {new_profile.full_name} ({len(new_profile.experiences)} roles)!", title="Pantry Updated")
        except Exception as e:
            self.notify(f"Ingestion failed: {e}", severity="error")

    def action_pantry_interview(self) -> None:
        if not self.pantry.is_initialized():
            self.notify("Please ingest a base profile first.", severity="warning")
            return
        self.push_screen(PantryInterviewModal(), self._on_interview_submitted)

    def _on_interview_submitted(self, answers: Optional[Dict[str, str]]) -> None:
        if not answers or not any(answers.values()):
            return

        self.notify("Synthesizing qualitative personal directives...", title="Baker's Interview")
        provider = get_llm_provider()
        profile = self.pantry.load_profile()
        try:
            context_md = synthesize_context(profile, answers, provider)
            self.pantry.save_pantry(profile, context=context_md, trigger="interview_synthesis")
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.notify("✓ Synthesized directives and updated pantry/context.md!", title="Interview Complete")
        except Exception as e:
            self.notify(f"Interview synthesis failed: {e}", severity="error")

    def action_pantry_sync(self) -> None:
        if not self.pantry.is_initialized():
            self.notify("Pantry not initialized yet.", severity="warning")
            return

        meta = self.pantry.load_source_metadata()
        if not meta.get("source"):
            self.notify("No upstream source linked. Use 'Import / Ingest (i)' first.", severity="warning")
            return

        self.notify(f"Syncing from linked source: {meta['source'][:30]}...", title="Pantry Sync")
        provider = get_llm_provider()
        try:
            diff, new_profile = self.pantry.sync_from_linked_source(provider)
            has_changes = (
                bool(diff.get("added_experiences")) or
                bool(diff.get("modified_experiences")) or
                bool(diff.get("added_projects")) or
                diff.get("summary_changed")
            )
            if not has_changes:
                self.notify("Pantry is completely up to date with your portfolio!", title="Zero Changes")
                return

            curr_context = self.pantry.load_context()
            self.pantry.save_pantry(new_profile, context=curr_context, source_info=meta, trigger="tui_sync")
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.notify("✓ Successfully synced changes from portfolio into Pantry!", title="Sync Merged")
        except Exception as e:
            self.notify(f"Sync failed: {e}", severity="error")

    def action_pantry_history(self) -> None:
        snapshots = self.pantry.list_snapshots()
        if not snapshots:
            self.notify("No snapshots recorded yet.", severity="warning")
            return
        self.push_screen(PantryHistoryModal(snapshots), self._on_history_revert_selected)

    def _on_history_revert_selected(self, snapshot_id: Optional[str]) -> None:
        if not snapshot_id:
            return
        success = self.pantry.revert_snapshot(snapshot_id)
        if success:
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.notify(f"✓ Reverted Pantry to snapshot {snapshot_id}!", title="Pantry Reverted")
        else:
            self.notify("Failed to revert snapshot.", severity="error")

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
        elif bid == "btn-strategy-loop":
            self.run_strategy_loop_flow()
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
        elif bid == "btn-pantry-ingest":
            self.action_pantry_ingest()
        elif bid == "btn-pantry-interview":
            self.action_pantry_interview()
        elif bid == "btn-pantry-sync":
            self.action_pantry_sync()
        elif bid == "btn-pantry-history":
            self.action_pantry_history()

    def run_strategy_loop_flow(self) -> None:
        url_input = self.query_one("#input-job-url", Input).value.strip()
        if not url_input:
            self.notify("Please enter a job URL or paste a JD file path first.", severity="error")
            return

        status_box = self.query_one("#tailor-status-box", Static)
        status_box.update("[bold yellow]⏳ Ingesting job for Strategy Loop...[/bold yellow]")

        try:
            p_source = Path(url_input)
            if url_input.startswith("http://") or url_input.startswith("https://"):
                job = JobScraper.ingest_from_url(url_input)
            elif p_source.is_file():
                job = JobScraper.ingest_from_text(p_source.read_text(encoding="utf-8"), "Company", "Role")
            else:
                job = JobScraper.ingest_from_text(url_input, "Company", "Role")

            provider = get_llm_provider()
            questions = generate_job_strategy_questions(job, provider)
            persona_slug = self.query_one("#select-persona", Select).value
            base_persona = PersonaManager.load_persona(persona_slug)

            def handle_strategy(result: Optional[Dict[str, Any]]) -> None:
                if not result:
                    status_box.update("[dim]Strategy loop canceled.[/dim]")
                    return

                answers = result.get("answers", {})
                save_persona = result.get("save_persona", False)
                p_name = result.get("persona_name", "")
                p_slug = result.get("persona_slug", "")

                directives = synthesize_job_directives(job, answers, provider)
                chosen_persona = base_persona

                if save_persona:
                    target_name = p_name or f"{job.company} {job.title} Strategist"
                    target_slug = p_slug or f"{job.company}_{job.title}"
                    new_p = synthesize_job_persona(
                        name=target_name,
                        slug=target_slug,
                        job=job,
                        answers=answers,
                        base_persona=base_persona,
                        provider=provider
                    )
                    PersonaManager.save_persona(new_p)
                    self._refresh_persona_select(selected=new_p.slug)
                    chosen_persona = new_p
                    self.notify(f"Created and saved persona '{new_p.slug}'!", title="Persona Saved")

                status_box.update("[bold green]Directives synthesized! Baking application...[/bold green]")
                self.run_tailoring_flow(job_directives=directives, persona_override=chosen_persona)

            self.push_screen(JobStrategyModal(job, questions, base_persona), handle_strategy)

        except Exception as e:
            status_box.update(f"[bold red]Failed to launch Strategy Loop: {e}[/bold red]")
            self.notify(f"Error: {e}", severity="error")

    def _refresh_persona_select(self, selected: Optional[str] = None) -> None:
        try:
            sel = self.query_one("#select-persona", Select)
            opts = get_persona_select_options()
            sel.set_options(opts)
            if selected:
                sel.value = selected
        except Exception:
            pass

    def run_tailoring_flow(
        self,
        job_directives: Optional[str] = None,
        persona_override: Optional[Persona] = None
    ) -> None:
        url_input = self.query_one("#input-job-url", Input).value.strip()
        if not url_input:
            self.notify("Please enter a job URL or paste a JD file path.", severity="error")
            return

        if persona_override:
            persona = persona_override
        else:
            persona_slug = self.query_one("#select-persona", Select).value
            persona = PersonaManager.load_persona(persona_slug)

        template_name = self.query_one("#select-template", Select).value
        self.current_template = template_name

        target_info = {
            "url_input": url_input,
            "pantry": self.pantry,
            "repo": self.repo,
            "job_directives": job_directives,
            "persona": persona,
            "template_name": template_name
        }

        try:
            self.query_one("#studio-stepper", BakeryStepper).set_stage(1)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message("Kneading application dough...")
        except Exception:
            pass

        self.push_screen(
            BakingModal(task_type="tailor", target_info=target_info),
            self._on_tailoring_modal_dismissed
        )

    def _on_tailoring_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or not result.get("success"):
            try:
                self.query_one("#studio-stepper", BakeryStepper).set_stage(0)
            except Exception:
                pass
            return

        app_result = result["app_result"]
        job = result["job"]
        app_dir = result["app_dir"]
        job_rec = result["job_rec"]
        score = app_result.match_analysis.match_score
        pdf_baked = result.get("pdf_baked", False)

        self.current_app_result = app_result
        self.last_tailored_dir = app_dir
        self.selected_job = job_rec
        self.current_profile = result.get("profile")

        pdf_notice = " | [bold green]Baked resume.pdf ✓[/bold green]" if pdf_baked else " | [dim]PDF: press 'b' to bake[/dim]"
        status_box = self.query_one("#tailor-status-box", Static)
        status_box.update(
            f"[bold green]✓ Fresh out of the oven![/bold green] "
            f"Target: [bold]{job.company} — {job.title}[/bold] | "
            f"ATS Match Score: [bold green]{score}%[/bold green]{pdf_notice}\n"
            f"Package saved to: [cyan]{app_dir}[/cyan]"
        )

        self.query_one("#preview-resume-md", Markdown).update(result.get("resume_md", ""))
        self.query_one("#preview-letter-md", Markdown).update(result.get("cover_letter", ""))
        self.query_one("#preview-qna-md", Markdown).update(result.get("portal_qna", ""))

        try:
            self.query_one("#studio-stepper", BakeryStepper).set_stage(4)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message(f"Loaf Ready: {score}% ATS Match!")
        except Exception:
            pass

        self.notify(f"Tailored application for {job.company} ({score}% match)! Press 'b' to bake PDF.", title="Breadwinner Success")
        self.load_pipeline_table()
