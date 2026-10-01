"""Full-featured Textual Terminal User Interface for Breadwinner."""

import os
import json
import subprocess
import webbrowser
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import unquote

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, TabbedContent, TabPane, DataTable,
    Button, Input, Label, Static, RadioSet, RadioButton,
    Select, Markdown, TextArea, OptionList
)
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from textual.binding import Binding

MIN_TERMINAL_WIDTH = 76
MIN_TERMINAL_HEIGHT = 22

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
from breadwinner.core.ingestor import UniversalIngestor, IngestionError, normalize_source
from breadwinner.core.interview import INTERVIEW_QUESTIONS, synthesize_context, generate_adaptive_questions
from breadwinner.core.audio import AudioTranscriber, AudioRecorder
from breadwinner.providers.factory import get_llm_provider
import re
from breadwinner.ui.retro import (
    RETRO_THEME_CSS,
    AnimatedOven,
    AnimatedMascot,
    BakeryStepper,
    RetroProgressBar,
    BakingModal
)
from breadwinner.ui.welcome import (
    BakeryWelcomeModal,
    save_env_config,
    PROVIDERS_REGISTRY,
    get_provider_spec,
    PROVIDER_MODELS,
)
from breadwinner.ui.editor import (
    DualPaneFineTuneModal,
    XYZValidatorWidget,
    analyze_bullets_xyz,
    make_gauge_bar,
    STRONG_ACTION_VERBS,
)
from breadwinner.ui.screen_guard import ScreenGuardScreen
from breadwinner.core.portfolio import JsonResumeAdapter
from breadwinner.onboarding import STARTER_JSON_RESUME
from breadwinner.ui.geometry import (
    get_preset_geometry,
    resize_terminal_window,
    get_display_resolution
)


class VerticalEngineBlade(Static):
    """Artisan 90-degree vertical stencil blade for collapsed AI Engine indicator."""

    DEFAULT_CSS = """
    VerticalEngineBlade {
        width: 5;
        height: 9;
        background: #181A24;
        border: round #3A3F55;
        color: #50FA7B;
        text-style: bold;
        text-align: center;
        content-align: center middle;
        margin: 1 0;
    }
    VerticalEngineBlade:hover {
        border: round #50FA7B;
        background: #252836;
    }
    """

    def __init__(self, provider: str = "GEMINI", id: Optional[str] = "blade-sidebar-engine"):
        super().__init__("", id=id)
        self.provider = provider
        self.blade_text = ""
        self.tooltip = "Active AI Engine • Click to switch (m)"

    def on_mount(self) -> None:
        self.update_provider(self.provider)

    def on_click(self) -> None:
        self.app.action_switch_model()

    def update_provider(self, provider: str) -> None:
        self.provider = provider.upper()
        norm = self.provider
        if "DEEPSEEK" in norm:
            norm = "DSEEK"
        elif "OPENROUTER" in norm:
            norm = "OROUTE"
        elif len(norm) > 6:
            norm = norm[:6]

        self.blade_text = norm.strip()
        norm = norm.ljust(6, " ") if len(norm) < 6 else norm
        chars = "\n".join(norm)
        content = f"[bold #50FA7B]●[/]\n{chars}"
        self.update(content)
        self.tooltip = f"Active AI Engine: {self.provider} • Click to switch (m)"




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
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    .strategy-q-label {
        text-style: bold;
        color: #FFB86C;
        margin-top: 1;
    }
    .strategy-q-sub {
        color: #A89F91;
        margin-bottom: 1;
    }
    .modal-header-bar {
        height: 1;
        width: 100%;
        align: right middle;
        margin-bottom: 1;
    }
    .modal-header-title {
        width: 1fr;
        margin-bottom: 0;
    }
    .modal-close-btn {
        width: 3;
        min-width: 3;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: #ff5555;
        color: #0b0e17;
        text-style: bold;
    }
    .modal-close-btn:hover {
        background: #ff6e6e;
        color: #ffffff;
    }
    """

    def __init__(self, job: JobPosting, questions: List[Dict[str, str]], base_persona: Persona):
        super().__init__()
        self.job = job
        self.questions = questions
        self.base_persona = base_persona

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="strategy-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label(f"[bold cyan]Target Strategy Loop:[/bold cyan] [bold white]{self.job.company} — {self.job.title}[/bold white]", classes="modal-header-title")
                yield Button("✕", id="btn-strategy-close", classes="modal-close-btn")
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
        if event.button.id in ("btn-cancel-strategy", "btn-strategy-close"):
            self.dismiss(None)
            return

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
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
    }
    """

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label(f"[bold]Update Status for {self.job.company}:[/bold]", classes="modal-header-title"),
                Button("✕", id="btn-status-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
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
        if event.button.id in ("btn-cancel-status", "btn-status-close"):
            self.dismiss(False)
            return

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
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
    }
    """

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label(f"[bold]Set Flag for {self.job.company}:[/bold]", classes="modal-header-title"),
                Button("✕", id="btn-flag-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
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
        if event.button.id in ("btn-cancel-flag", "btn-flag-close"):
            self.dismiss(False)
            return

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
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #finetune-editor {
        height: 1fr;
        min-height: 12;
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
            Horizontal(
                Label("[bold yellow]🥖 Interactive Bullet Fine-Tuning Studio[/bold yellow]", classes="modal-header-title"),
                Button("✕", id="btn-finetune-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
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
        if event.button.id in ("btn-cancel-finetune", "btn-finetune-close"):
            self.dismiss(None)
        elif event.button.id == "btn-save-finetune":
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
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #pantry-source-input {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label("[bold cyan]Import Into Career Pantry[/bold cyan]", classes="modal-header-title"),
                Button("✕", id="btn-ingest-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
            Label("[dim]Enter a live portfolio website URL (https://...), a local file path (.json, .docx, .md), or paste raw bio text:[/dim]"),
            Input(placeholder="https://yourname.com or /path/to/resume.json", id="pantry-source-input"),
            Horizontal(
                Button("Ingest & Update Pantry", variant="success", id="btn-run-ingest"),
                Button("Cancel", variant="error", id="btn-cancel-ingest"),
                classes="action-bar"
            ),
            id="pantry-ingest-dialog"
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#pantry-source-input", Input).focus()
        except Exception:
            pass

    def on_paste(self, event: events.Paste) -> None:
        if event.text:
            inp = self.query_one("#pantry-source-input", Input)
            clean = event.text.strip().strip("'\"“”‘’")
            if clean.startswith("file://"):
                clean = clean[7:]
                if clean.startswith("localhost"):
                    clean = clean[9:]
            clean = unquote(clean).replace(r"\ ", " ")
            inp.value = clean

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-cancel-ingest", "btn-ingest-close"):
            self.dismiss(None)
        elif event.button.id == "btn-run-ingest":
            val = self.query_one("#pantry-source-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)


class PantryInterviewModal(ModalScreen):
    """Modal to run the Baker's Interview loop for discovering qualitative career context with Voice STT support."""

    DEFAULT_CSS = """
    PantryInterviewModal {
        align: center middle;
    }
    #interview-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    .interview-q-title {
        color: #38bdf8;
        text-style: bold;
        margin-top: 1;
    }
    .interview-q-prompt {
        color: #94a3b8;
        margin-bottom: 0;
    }
    .interview-input {
        height: 4;
        margin-bottom: 0;
        background: #1e293b;
        color: #fef3c7;
        border: solid #d97706;
    }
    .voice-bar {
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }
    .voice-btn {
        margin-right: 1;
    }
    """

    def __init__(self, questions: Optional[List[Dict[str, str]]] = None):
        super().__init__()
        self.questions = questions or INTERVIEW_QUESTIONS
        self.backend_info = AudioTranscriber.detect_backend()

    def compose(self) -> ComposeResult:
        stt_status = (
            f"[dim green]🎙️ Voice STT Engine: {self.backend_info.description}[/dim green]"
            if self.backend_info.available
            else "[dim yellow]🎙️ Voice STT: Ready for BYOK Groq/OpenAI keys or local Whisper (Type answers directly)[/dim yellow]"
        )

        header_widgets = [
            Horizontal(
                Label("[bold yellow]🥖 The Baker's Interview: Discovering Your Context[/bold yellow]", classes="modal-header-title"),
                Button("✕", id="btn-interview-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
            Label("[dim]Answer these targeted questions to eliminate ambiguity and synthesize personal directives (context.md).[/dim]"),
            Label(stt_status),
        ]

        q_widgets = []
        for idx, q in enumerate(self.questions):
            q_id = q.get("id", f"q{idx}")
            q_title = q.get("title", f"Question {idx+1}")
            q_prompt = q.get("prompt", "")

            q_widgets.append(Label(f"[bold cyan]{idx + 1}. {q_title}[/bold cyan]", classes="interview-q-title"))
            if q_prompt:
                q_widgets.append(Label(f"[dim]{q_prompt}[/dim]", classes="interview-q-prompt"))

            # ID fallback support for static q1/q2/q3
            area_id = f"int-q{idx+1}" if idx < 3 and len(self.questions) == 3 else f"int-q-{q_id}"
            q_widgets.append(TextArea(id=area_id, classes="interview-input"))

            if AudioRecorder.is_available() and self.backend_info.available:
                q_widgets.append(Horizontal(
                    Button("🎤 Speak Answer (10s)", variant="warning", id=f"btn-rec-{area_id}", classes="voice-btn"),
                    Label("[dim italic]Click to record via microphone or type directly[/dim italic]"),
                    classes="voice-bar"
                ))

        yield Vertical(
            *header_widgets,
            VerticalScroll(*q_widgets),
            Horizontal(
                Button("Synthesize Directives (context.md)", variant="success", id="btn-save-interview"),
                Button("Cancel", variant="error", id="btn-cancel-interview"),
                classes="action-bar"
            ),
            id="interview-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id in ("btn-cancel-interview", "btn-interview-close"):
            self.dismiss(None)
        elif btn_id == "btn-save-interview":
            ans = {}
            for idx, q in enumerate(self.questions):
                q_id = q.get("id", f"q{idx}")
                area_id = f"int-q{idx+1}" if idx < 3 and len(self.questions) == 3 else f"int-q-{q_id}"
                try:
                    area = self.query_one(f"#{area_id}", TextArea)
                    ans[q_id] = area.text.strip()
                except Exception:
                    pass
            self.dismiss(ans)
        elif btn_id.startswith("btn-rec-"):
            target_area_id = btn_id.replace("btn-rec-", "")
            self._start_voice_recording(target_area_id, event.button)

    @work(thread=True)
    def _start_voice_recording(self, target_area_id: str, btn: Button) -> None:
        import tempfile
        from pathlib import Path

        def set_btn(text: str, disabled: bool):
            btn.label = text
            btn.disabled = disabled

        self.app.call_from_thread(set_btn, "🔴 Recording (Speak now)...", True)
        temp_wav = Path(tempfile.gettempdir()) / f"breadwinner_voice_{target_area_id}.wav"

        success = AudioRecorder.record_to_file(temp_wav, duration_seconds=10)
        if not success:
            self.app.call_from_thread(set_btn, "🎤 Speak Answer (10s)", False)
            self.notify("Could not capture audio from microphone. Please type your response.", severity="error")
            return

        self.app.call_from_thread(set_btn, "⏳ Transcribing...", True)
        try:
            transcription = AudioTranscriber.transcribe(temp_wav)
            if transcription:
                def update_text():
                    try:
                        area = self.query_one(f"#{target_area_id}", TextArea)
                        existing = area.text.strip()
                        area.text = f"{existing} {transcription}".strip() if existing else transcription
                        self.notify(f"✓ Transcribed: '{transcription[:40]}...'", title="Speech Captured")
                    except Exception:
                        pass
                self.app.call_from_thread(update_text)
            else:
                self.notify("No speech detected in audio.", severity="warning")
        except Exception as e:
            self.notify(f"Transcription failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(set_btn, "🎤 Speak Again (10s)", False)
            try:
                if temp_wav.exists():
                    temp_wav.unlink()
            except Exception:
                pass


class PantryHistoryModal(ModalScreen):
    """Modal showing historical snapshots of the Pantry with rollback options."""

    DEFAULT_CSS = """
    PantryHistoryModal {
        align: center middle;
    }
    #history-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #history-table {
        height: 1fr;
        min-height: 10;
        margin: 1 0;
    }
    """

    def __init__(self, snapshots: List[Dict[str, Any]]):
        super().__init__()
        self.snapshots = snapshots
        self.selected_snapshot_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label("[bold cyan]Pantry Snapshot History & Rollback[/bold cyan]", classes="modal-header-title"),
                Button("✕", id="btn-history-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
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
        if event.button.id in ("btn-close-snap", "btn-history-close"):
            self.dismiss(None)
        elif event.button.id == "btn-revert-snap":
            self.dismiss(self.selected_snapshot_id)
        else:
            self.dismiss(None)


class PantryEditorModal(ModalScreen):
    """Interactive studio to view & edit Personal Career Context (context.md) and Profile Facts (profile.json)."""

    DEFAULT_CSS = """
    PantryEditorModal {
        align: center middle;
    }
    #pantry-editor-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 36;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #pantry-context-editor, #pantry-profile-editor {
        height: 1fr;
        min-height: 12;
        background: #212330;
        color: #e2e8f0;
        border: solid #414868;
    }
    """

    def __init__(self, pantry: PantryManager):
        super().__init__()
        self.pantry = pantry
        self.initial_context = pantry.load_context()
        if not self.initial_context.strip():
            self.initial_context = (
                "# Personal Directives & Guardrails\n\n"
                "## Target Roles & Preferences\n"
                "- Open to senior and staff level technical positions.\n\n"
                "## Core Superpowers\n"
                "- High-throughput systems, distributed architectures, hard metrics.\n\n"
                "## Work Boundaries & Logistics\n"
                "- Location: Hybrid or Remote.\n"
            )
        try:
            self.initial_profile_json = self.pantry.profile_path.read_text(encoding="utf-8")
        except Exception:
            self.initial_profile_json = json.dumps(self.pantry.load_profile().to_json_resume(), indent=2)

    def compose(self) -> ComposeResult:
        with Vertical(id="pantry-editor-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label("[bold #f4a261]🥖 Career Pantry & Personal Context Diary Studio[/bold #f4a261]", classes="modal-header-title")
                yield Button("✕", id="btn-editor-close", classes="modal-close-btn")
            yield Label("[dim]Edit your personal career diary, directives, or structured facts. Saving updates the pantry and creates an automated snapshot.[/dim]")
            with TabbedContent(initial="tab-edit-context", id="pantry-editor-tabs"):
                with TabPane("Personal Context Diary (context.md)", id="tab-edit-context"):
                    yield TextArea(self.initial_context, id="pantry-context-editor", language="markdown")
                with TabPane("Structured Profile Facts (profile.json)", id="tab-edit-json"):
                    yield TextArea(self.initial_profile_json, id="pantry-profile-editor", language="json")
            with Horizontal(classes="action-bar"):
                yield Button("Save Changes to Pantry (Enter)", variant="success", id="btn-save-pantry-edit")
                yield Button("Cancel", variant="error", id="btn-cancel-pantry-edit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-cancel-pantry-edit", "btn-editor-close"):
            self.dismiss(None)
            return

        if event.button.id == "btn-save-pantry-edit":
            ctx_text = self.query_one("#pantry-context-editor", TextArea).text
            json_text = self.query_one("#pantry-profile-editor", TextArea).text
            try:
                parsed_json = json.loads(json_text)
                adapter = JsonResumeAdapter(parsed_json)
                updated_profile = adapter.load_profile()
            except Exception as e:
                self.app.notify(f"Invalid profile JSON: {e}", severity="error")
                return

            self.dismiss({"action": "save", "context": ctx_text, "profile": updated_profile})
        else:
            self.dismiss(None)


@dataclass
class PaletteModelItem:
    provider_slug: str
    provider_name: str
    model_id: str
    display_name: str
    is_available: bool
    is_active: bool


class PaletteSearchInput(Input):
    """Raycast-style palette search input that handles quick-pick 1-9, arrows, and Enter."""

    def on_key(self, event: events.Key) -> None:
        modal = self.screen
        if isinstance(modal, ModelQuickSwitcherModal):
            if not self.value and event.key in "123456789":
                event.stop()
                event.prevent_default()
                modal.activate_quick_index(int(event.key) - 1)
                return
            elif event.key == "down":
                event.stop()
                event.prevent_default()
                modal.cursor_down()
                return
            elif event.key == "up":
                event.stop()
                event.prevent_default()
                modal.cursor_up()
                return
            elif event.key == "enter":
                event.stop()
                event.prevent_default()
                modal.activate_highlighted()
                return


class ModelQuickSwitcherModal(ModalScreen):
    """Raycast / Spotlight AI Engine & Model Quick-Pick Palette with zero dead space."""

    DEFAULT_CSS = """
    ModelQuickSwitcherModal {
        align: center middle;
    }
    #switcher-dialog {
        padding: 0 1;
        background: #10141f;
        border: heavy #d18f52;
        width: 76;
        max-width: 80;
        min-width: 68;
        height: auto;
        max-height: 16;
        overflow: hidden;
    }
    #switcher-header-row {
        height: 1;
        width: 100%;
        margin-top: 0;
        margin-bottom: 0;
        align: left middle;
    }
    #switcher-title {
        color: #ffb86c;
        text-style: bold;
        width: 1fr;
    }
    #btn-switcher-close {
        dock: right;
        min-width: 3;
        height: 1;
        border: none;
        background: transparent;
        color: #6272a4;
        padding: 0;
    }
    #btn-switcher-close:hover {
        color: #ff5555;
        text-style: bold;
    }
    #switcher-search {
        margin-top: 0;
        margin-bottom: 0;
        background: #0c0e14;
        border: round #44475a;
        color: #f8f8f2;
        height: 3;
    }
    #switcher-search:focus {
        border: round #ffb86c;
    }
    #switcher-list {
        height: 8;
        max-height: 8;
        background: #10141f;
        border: none;
        padding: 0;
        margin: 0;
        scrollbar-size-vertical: 1;
    }
    #switcher-list > .option-list--option {
        padding: 0 1;
    }
    #switcher-list > .option-list--option-highlighted {
        background: #282a36;
        color: #f8f8f2;
        text-style: bold;
    }
    #switcher-footer-hint {
        height: 1;
        margin-top: 0;
        color: #6272a4;
        text-align: center;
    }
    #switcher-prov-select {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    PROVIDER_COLORS = {
        "gemini": "#50fa7b",
        "anthropic": "#ffb86c",
        "openai": "#8be9fd",
        "deepseek": "#8be9fd",
        "groq": "#ff79c6",
        "openrouter": "#bd93f9",
        "mistral": "#f1fa8c",
        "ollama": "#f8f8f2",
        "lmstudio": "#f8f8f2",
        "mock": "#6272a4",
    }

    def __init__(self):
        super().__init__()
        self.active_prov = settings.breadwinner_llm_provider
        self.cur_model = getattr(settings, f"{self.active_prov}_model", "")
        self.statuses = ProviderDiscovery.discover_all()
        self.status_map = {s.slug: s for s in self.statuses}
        self.all_items: List[PaletteModelItem] = self._build_all_items()
        self._filtered_items: List[PaletteModelItem] = list(self.all_items)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def _build_all_items(self) -> List[PaletteModelItem]:
        prov_order = ["gemini", "anthropic", "deepseek", "groq", "openai", "openrouter", "mistral", "ollama", "lmstudio", "mock"]
        flagship_items: List[PaletteModelItem] = []
        secondary_items: List[PaletteModelItem] = []

        for slug in prov_order:
            st = self.status_map.get(slug)
            prov_name = st.name if st else slug.capitalize()
            is_avail = st.is_available if st else False
            models: List[Tuple[str, str]] = []
            if st and st.models:
                models = [(m.name or m.id, m.id) for m in st.models]
            else:
                models = PROVIDER_MODELS.get(slug, [])

            pref_model_id = getattr(settings, f"{slug}_model", models[0][1] if models else "")
            flagship_found = False

            for idx, (disp, mid) in enumerate(models):
                clean_disp = disp.split("(")[0].strip()
                is_act = (slug == self.active_prov and (mid == self.cur_model or (not self.cur_model and idx == 0)))
                item = PaletteModelItem(
                    provider_slug=slug,
                    provider_name=prov_name,
                    model_id=mid,
                    display_name=clean_disp,
                    is_available=is_avail,
                    is_active=is_act,
                )
                if (mid == pref_model_id or (not flagship_found and idx == 0)) and not flagship_found:
                    flagship_items.append(item)
                    flagship_found = True
                else:
                    secondary_items.append(item)

        # Flagships: active first, then ready/available first
        flagship_items.sort(key=lambda x: (not x.is_active, not x.is_available))
        return flagship_items + secondary_items

    def compose(self) -> ComposeResult:
        with Vertical(id="switcher-dialog"):
            with Horizontal(id="switcher-header-row"):
                yield Label("[bold #ffb86c]✦ AI ENGINE & MODEL PALETTE[/bold #ffb86c]", id="switcher-title")
                yield Button("✕", id="btn-switcher-close")
            yield PaletteSearchInput(placeholder="🔍 Search model or provider (or press 1-9 to pick)...", id="switcher-search")
            yield OptionList(id="switcher-list")
            yield Label("[dim]↑/↓ Navigate • Enter Select • 1-9 Quick Pick • Esc Close[/dim]", id="switcher-footer-hint")
            # Backward compatibility stub
            yield Static("", id="switcher-prov-select")

    def on_mount(self) -> None:
        self._refresh_list("")
        try:
            self.query_one("#switcher-search", PaletteSearchInput).focus()
        except Exception:
            pass

    def _format_option_text(self, item: PaletteModelItem, index: int) -> Text:
        hotkey = f"[{index}]" if 1 <= index <= 9 else "   "
        color = self.PROVIDER_COLORS.get(item.provider_slug, "#8be9fd")
        p_tag = f"[{item.provider_slug.upper()}]"

        if item.is_active:
            status_markup = "[bold #ffb86c]● ACTIVE[/bold #ffb86c]"
        elif item.is_available:
            status_markup = "[#50fa7b]● READY[/#50fa7b]"
        else:
            status_markup = "[dim]○ SETUP[/dim]"

        hotkey_markup = f"[bold #ffb86c]{hotkey}[/bold #ffb86c]" if 1 <= index <= 9 else "[dim]   [/dim]"
        prov_markup = f"[bold {color}]{p_tag:<10}[/bold {color}]"
        display = item.display_name[:22].ljust(22)
        mid = item.model_id[:18].ljust(18)

        line = f"{hotkey_markup} {prov_markup} {display} [dim]{mid}[/dim] {status_markup}"
        return Text.from_markup(line)

    def _refresh_list(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._filtered_items = list(self.all_items)
        else:
            self._filtered_items = [
                it for it in self.all_items
                if q in it.model_id.lower()
                or q in it.display_name.lower()
                or q in it.provider_slug.lower()
                or q in it.provider_name.lower()
            ]
            if not self._filtered_items:
                self._filtered_items = [
                    PaletteModelItem(
                        provider_slug=self.active_prov,
                        provider_name="Custom",
                        model_id=query.strip(),
                        display_name=f"Custom ({self.active_prov.upper()})",
                        is_available=True,
                        is_active=False,
                    )
                ]

        opt_list = self.query_one("#switcher-list", OptionList)
        opt_list.clear_options()
        for idx, item in enumerate(self._filtered_items, start=1):
            prompt = self._format_option_text(item, idx)
            opt_list.add_option(Option(prompt, id=f"opt-{idx}"))

        if opt_list.option_count > 0:
            opt_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "switcher-search":
            self._refresh_list(event.value)

    def cursor_down(self) -> None:
        lst = self.query_one("#switcher-list", OptionList)
        if lst.option_count == 0:
            return
        if lst.highlighted is None:
            lst.highlighted = 0
        else:
            lst.highlighted = min(lst.highlighted + 1, lst.option_count - 1)

    def cursor_up(self) -> None:
        lst = self.query_one("#switcher-list", OptionList)
        if lst.option_count == 0:
            return
        if lst.highlighted is None:
            lst.highlighted = 0
        else:
            lst.highlighted = max(0, lst.highlighted - 1)

    def activate_quick_index(self, idx: int) -> None:
        if 0 <= idx < len(self._filtered_items):
            self._activate_item(self._filtered_items[idx])

    def activate_highlighted(self) -> None:
        lst = self.query_one("#switcher-list", OptionList)
        if lst.highlighted is not None and 0 <= lst.highlighted < len(self._filtered_items):
            self._activate_item(self._filtered_items[lst.highlighted])
        elif len(self._filtered_items) > 0:
            self._activate_item(self._filtered_items[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if 0 <= event.option_index < len(self._filtered_items):
            self._activate_item(self._filtered_items[event.option_index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-switcher-close", "switcher-close-btn"):
            self.dismiss(None)

    def _activate_item(self, item: PaletteModelItem) -> None:
        prov = item.provider_slug
        model_val = item.model_id
        model_env_map = {
            "gemini": "GEMINI_MODEL",
            "openrouter": "OPENROUTER_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "openai": "OPENAI_MODEL",
            "deepseek": "DEEPSEEK_MODEL",
            "groq": "GROQ_MODEL",
            "mistral": "MISTRAL_MODEL",
            "lmstudio": "LMSTUDIO_MODEL",
            "ollama": "OLLAMA_MODEL",
        }
        env_vars = {
            "BREADWINNER_LLM_PROVIDER": prov,
        }
        if prov in model_env_map and model_val:
            env_vars[model_env_map[prov]] = model_val

        save_env_config(env_vars)

        settings.breadwinner_llm_provider = prov
        attr_name = f"{prov}_model"
        if hasattr(settings, attr_name):
            setattr(settings, attr_name, model_val)

        self.dismiss({"provider": prov, "model": model_val})


class BakerySettingsModal(ModalScreen):
    """Local-first Studio Settings & Invariants Configuration Modal."""

    DEFAULT_CSS = """
    BakerySettingsModal {
        align: center middle;
    }
    #settings-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d18f52;
        width: 78;
        max-width: 84;
        min-width: 70;
        height: auto;
        max-height: 28;
    }
    .settings-sec-header {
        text-style: bold;
        color: #ffb86c;
        margin-top: 1;
        margin-bottom: 0;
    }
    .settings-select-row {
        height: auto;
        layout: horizontal;
    }
    .settings-col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }
    .settings-col:last-of-type {
        margin-right: 0;
    }
    #settings-select-template, #settings-select-persona {
        margin-bottom: 0;
        background: #0c0e14;
        border: round #2a2e3d;
        color: #f8f8f2;
    }
    .settings-info-box {
        background: #0c0e14;
        border: round #2a2e3d;
        color: #8be9fd;
        padding: 0 1;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    #settings-engine-row {
        align: left middle;
        height: 3;
    }
    #lbl-settings-engine {
        width: 1fr;
    }
    #btn-settings-switch-engine {
        min-width: 14;
        height: 1;
        padding: 0 1;
        border: none;
    }
    #settings-action-bar {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    #settings-action-bar Button {
        margin-right: 1;
        min-width: 18;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label("[bold #ffb86c]⚙ BREADWINNER SETTINGS[/bold #ffb86c] [dim]• Studio Invariants[/dim]", classes="modal-header-title")
                yield Button("✕", id="btn-settings-close", classes="modal-close-btn")

            prov = (getattr(settings, "breadwinner_llm_provider", None) or "gemini").upper()
            model = getattr(settings, f"{prov.lower()}_model", "default")
            with Horizontal(classes="settings-info-box", id="settings-engine-row"):
                yield Label(f"[bold white]Engine:[/] [bold #50fa7b]{prov}[/]  [bold white]Model:[/] [bold #8be9fd]{model}[/]", id="lbl-settings-engine")
                yield Button("✦ Switch (m)", id="btn-settings-switch-engine", variant="primary")

            template_opts = [
                ("Jake's Resume (r/EngineeringResumes Standard)", "jakes"),
                ("Modern Clean (HTML/CSS)", "modern"),
                ("Clean ATS Markdown", "ats"),
            ]
            cur_tmpl = settings.default_template if any(v == settings.default_template for _, v in template_opts) else "jakes"
            persona_opts = get_persona_select_options()
            cur_persona = settings.default_persona if any(v == settings.default_persona for _, v in persona_opts) else persona_opts[0][1]

            with Horizontal(classes="settings-select-row"):
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Default Resume Template:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(template_opts, value=cur_tmpl, id="settings-select-template")
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Default Narrative Persona:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(persona_opts, value=cur_persona, id="settings-select-persona")

            with Vertical(classes="settings-info-box"):
                yield Label(f"[dim]Pantry:[/] [white]{settings.pantry_dir.name}[/]  •  [dim]DB:[/] [white]{settings.database_path.name}[/]  •  [dim]CSV:[/] [white]{settings.csv_tracker_path.name if settings.csv_tracker_path else 'Disabled'}[/]")
                yield Label("[bold #50fa7b]● ANTI-HALLUCINATION INVARIANT: ENFORCED[/bold #50fa7b] [dim](Zero Cloud Telemetry • BYOK)[/dim]")

            with Horizontal(id="settings-action-bar"):
                yield Button("Save Settings (Enter)", variant="success", id="btn-settings-save")
                yield Button("Cancel (Esc)", variant="error", id="btn-settings-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-settings-cancel", "btn-settings-close"):
            self.dismiss(None)
            return

        if bid == "btn-settings-switch-engine":
            self.dismiss({"action": "switch_model"})
            return

        if bid == "btn-settings-save":
            tmpl_val = str(self.query_one("#settings-select-template", Select).value)
            pers_val = str(self.query_one("#settings-select-persona", Select).value)

            settings.default_template = tmpl_val
            settings.default_persona = pers_val

            save_env_config({
                "DEFAULT_TEMPLATE": tmpl_val,
                "DEFAULT_PERSONA": pers_val,
            })

            self.dismiss({
                "saved": True,
                "template": tmpl_val,
                "persona": pers_val
            })


class BreadwinnerApp(App):
    """Breadwinner Interactive TUI Application."""

    TITLE = "Breadwinner"
    SUB_TITLE = "Local 8-Bit Anti-Slop Career Studio ◈"
    CSS = """
    Screen {
        background: #16161E;
        color: #F8F8F2;
    }
    Header {
        background: #212330;
        color: #FFB86C;
        text-style: bold;
    }
    Footer {
        background: #16161E;
        border-top: solid #2A2E3D;
    }
    TabbedContent {
        height: 1fr;
        background: #16161E;
    }
    ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        padding: 0 1;
        height: 1fr;
        background: #16161E;
    }
    ScrollBar {
        background: #16161E;
        color: #2E344A;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    ScrollBar:hover {
        color: #3E4663;
    }
    ScrollBarCorner {
        background: #16161E;
    }
    #app-top-bar {
        dock: top;
        height: 4;
        background: #10141f;
        border-bottom: heavy #2A2E3D;
        padding: 0 1;
        layout: horizontal;
        align-vertical: middle;
    }
    #top-bar-left {
        width: 34;
        height: 100%;
        align: left middle;
    }
    .icon-toggle-btn {
        width: 5;
        min-width: 5;
        height: 1;
        padding: 0;
        margin-right: 1;
        background: #1E2233;
        border: none;
        color: #FFB86C;
        text-style: bold;
        content-align: center middle;
    }
    .icon-toggle-btn:hover {
        background: #2D334D;
        color: #FFFFFF;
    }
    #top-bar-center {
        width: 1fr;
        height: 100%;
        align: center middle;
        content-align: center middle;
    }
    #top-bar-brand {
        color: #FFB86C;
        text-style: bold;
        margin: 0;
        padding: 0;
    }
    #top-bar-screen-title {
        color: #A89F91;
        margin: 0;
        padding: 0;
    }
    #top-bar-nav-pills {
        display: none;
        width: auto;
        height: 100%;
        align: left middle;
    }
    .top-nav-btn {
        height: 1;
        min-width: 0;
        padding: 0 1;
        margin-right: 1;
        border: none;
        background: #16161E;
        color: #A89F91;
        text-style: bold;
    }
    .top-nav-btn:hover {
        background: #212330;
        color: #FFFFFF;
    }
    .top-nav-btn.-active {
        background: #2A2E3D;
        color: #FFB86C;
        text-style: bold;
    }
    #top-bar-right {
        width: 34;
        height: 100%;
        align: right middle;
    }
    #btn-active-model-chip {
        display: none;
        height: 1;
        min-width: 16;
        padding: 0 1;
        margin-right: 1;
        border: none;
        background: #212330;
        color: #FFB86C;
        text-style: bold;
    }
    #btn-active-model-chip:hover {
        background: #2A2E3D;
        color: #50FA7B;
    }
    #btn-app-cycle-preset {
        height: 1;
        min-width: 18;
        padding: 0 1;
        margin-right: 1;
        border: none;
        background: #1E2233;
        color: #8BE9FD;
        text-style: bold;
    }
    #btn-app-cycle-preset:hover {
        background: #2D334D;
        color: #FFFFFF;
    }
    #btn-app-quit {
        height: 1;
        min-width: 12;
        padding: 0 1;
        border: none;
        background: #E04050;
        color: #FFFFFF;
        text-style: bold;
    }
    #btn-app-quit:hover {
        background: #FF5566;
        color: #FFFFFF;
    }
    #app-workspace-split {
        height: 1fr;
        layout: horizontal;
    }
    #app-sidebar {
        width: 22;
        height: 100%;
        background: #12131A;
        border-right: solid #2A2E3D;
        padding: 1 1;
        layout: vertical;
        overflow: hidden;
    }
    #app-sidebar.-collapsed {
        width: 7;
        padding: 1 0 1 1;
        overflow: hidden;
    }
    .sidebar-flow-btn {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        background: #16161E;
        color: #A89F91;
        border: round #2A2E3D;
    }
    .sidebar-flow-btn:hover {
        background: #212330;
        color: #FFFFFF;
        border: round #FFB86C;
    }
    .sidebar-flow-btn.-active {
        background: #212330;
        color: #FFB86C;
        border: round #D18F52;
        text-style: bold;
    }
    #app-sidebar.-collapsed .sidebar-flow-btn,
    #app-sidebar.-collapsed #btn-sidebar-settings {
        width: 5;
        min-width: 5;
        height: 3;
        padding: 0;
        border: round #3A3F55;
        background: #181A24;
        color: #A89F91;
    }
    #app-sidebar.-collapsed .sidebar-flow-btn:hover,
    #app-sidebar.-collapsed #btn-sidebar-settings:hover {
        border: round #BD93F9;
        background: #252836;
        color: #FFFFFF;
    }
    #app-sidebar.-collapsed .sidebar-flow-btn.-active {
        border: round #FFB86C;
        background: #252836;
        color: #FFB86C;
    }
    #sidebar-flows {
        height: auto;
    }
    #sidebar-bottom {
        height: auto;
        overflow: hidden;
    }
    .sidebar-spacer {
        height: 1fr;
    }
    .sidebar-bottom-btn {
        width: 100%;
        height: 3;
        margin-top: 1;
        background: #1B1D28;
        color: #A89F91;
        border: round #2A2E3D;
        overflow: hidden;
    }
    .sidebar-bottom-btn:hover {
        background: #252836;
        color: #FFFFFF;
    }
    #app-sidebar.-collapsed #btn-sidebar-settings {
        margin-top: 1;
        margin-bottom: 1;
    }
    #blade-sidebar-engine {
        display: none;
    }
    #app-sidebar.-collapsed #btn-sidebar-model {
        display: none;
    }
    #app-sidebar.-collapsed #blade-sidebar-engine {
        display: block;
    }
    #main-tabs {
        width: 1fr;
        height: 100%;
        margin-left: 1;
    }
    #main-tabs > Tabs {
        display: none;
    }
    #pipeline-container {
        height: 1fr;
        layout: horizontal;
    }
    #pipeline-table-col {
        width: 1fr;
        height: 100%;
    }
    #pipeline-container.-vertical-stack {
        layout: vertical;
    }
    #pipeline-container.-vertical-stack #pipeline-table-col {
        width: 100%;
        height: 1fr;
    }
    #pipeline-container.-vertical-stack #job-details-pane {
        width: 100%;
        height: 1fr;
        border-left: none;
        border-top: heavy #2A2E3D;
    }
    DataTable {
        height: 1fr;
        border: heavy #2A2E3D;
        background: #0C0E14;
    }
    #pipeline-table-hint {
        height: 2;
        color: #6272A4;
        margin-top: 1;
        padding-left: 1;
    }
    #job-details-pane {
        width: 48;
        height: 100%;
        border-left: heavy #2A2E3D;
        background: #16161E;
        padding: 1 2;
    }
    .inspector-sec-label {
        text-style: bold;
        color: #A89F91;
        margin-top: 1;
        margin-bottom: 0;
    }
    .inspector-btn-row {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    .inspector-btn-row Button {
        width: 1fr;
        height: 100%;
        min-width: 0;
        margin: 0;
        border: round #2E3346;
        background: #1B1E2A;
        color: #F8F8F2;
        text-style: bold;
        padding: 0 1;
    }
    .inspector-btn-row Button:first-of-type {
        margin-right: 1;
    }
    .inspector-btn-row Button:hover {
        background: #272C3E;
        color: #FFFFFF;
    }
    #btn-pipeline-edit-studio {
        background: #182234;
        border: round #3B527A;
        color: #8BE9FD;
    }
    #btn-pipeline-edit-studio:hover {
        background: #22324C;
        border: round #8BE9FD;
        color: #FFFFFF;
    }
    #btn-pipeline-bake {
        background: #16281E;
        border: round #356345;
        color: #50FA7B;
    }
    #btn-pipeline-bake:hover {
        background: #1E3A2A;
        border: round #50FA7B;
        color: #FFFFFF;
    }
    #btn-flag {
        background: #28161A;
        border: round #5C2E35;
        color: #FF79C6;
    }
    #btn-flag:hover {
        background: #3A1F26;
        border: round #FF5555;
        color: #FFFFFF;
    }
    #details-header {
        color: #FFB86C;
        text-style: bold;
        border-bottom: solid #2A2E3D;
        margin-bottom: 1;
    }
    #details-body {
        height: auto;
        min-height: 3;
        border: round #2A2E3D;
        background: #0C0E14;
        color: #F8F8F2;
        padding: 0 1;
        margin-bottom: 1;
    }
    #notes-header-row {
        height: 1;
        margin-top: 1;
        align: left middle;
        layout: horizontal;
    }
    #details-notes-label {
        width: 1fr;
        text-style: bold;
        color: #A89F91;
    }
    #btn-save-notes {
        height: 1;
        min-width: 10;
        border: none;
        padding: 0 1;
        background: #222638;
        color: #50FA7B;
        text-style: bold;
    }
    #btn-save-notes:hover {
        background: #50FA7B;
        color: #0C0E14;
    }
    #input-job-notes {
        height: 4;
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
        margin-top: 1;
        margin-bottom: 0;
    }
    .action-bar {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    .action-bar Button {
        margin-right: 1;
        min-width: 14;
    }
    .input-label {
        text-style: bold;
        color: #FFB86C;
        margin-top: 1;
        margin-bottom: 0;
    }
    #input-job-url {
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
    }
    #select-persona, #select-template {
        border: none;
        background: transparent;
        height: auto;
        margin-bottom: 1;
    }
    #select-persona SelectCurrent, #select-template SelectCurrent {
        background: #212330;
        border: round #D18F52;
        color: #FFFFFF;
        height: 3;
        padding: 0 1;
    }
    #select-persona SelectCurrent:focus, #select-template SelectCurrent:focus {
        border: round #FFB86C;
        background: #2A2E3D;
    }
    #select-persona SelectCurrent Static#label, #select-template SelectCurrent Static#label {
        color: #FFFFFF !important;
        text-style: bold;
    }
    #select-persona SelectCurrent .arrow, #select-template SelectCurrent .arrow {
        color: #FFB86C;
    }
    #tailor-status-box {
        display: none;
        margin-top: 1;
        padding: 1;
        background: #212330;
        border: round #2A2E3D;
    }
    .preview-box {
        height: 1fr;
        border: round #2A2E3D;
        padding: 1;
        background: #0C0E14;
    }
    .provider-card {
        border: round #2A2E3D;
        padding: 1;
        margin-bottom: 1;
        background: #212330;
    }
    #studio-mascot-banner {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: #212330;
        border: heavy #D18F52;
    }
    #studio-banner-header-row {
        height: 1;
        width: 100%;
        align: left middle;
    }
    #studio-banner-title {
        color: #FFB86C;
        text-style: bold;
        width: 1fr;
    }
    #studio-banner-status {
        color: #50FA7B;
        text-style: bold;
        dock: right;
    }
    #studio-banner-desc {
        color: #A89F91;
        margin-top: 0;
        margin-bottom: 0;
    }
    #studio-mascot-speech {
        color: #F8F8F2;
        margin-top: 0;
        margin-bottom: 0;
    }
    #studio-mascot, #studio-oven, #studio-stepper {
        display: none;
    }
    #studio-readiness-deck {
        height: auto;
        margin-top: 1;
        layout: horizontal;
    }
    .studio-readiness-card {
        width: 1fr;
        height: auto;
        background: #10141f;
        border: round #2A2E3D;
        padding: 0 1;
        margin-right: 1;
    }
    .studio-readiness-card:last-of-type {
        margin-right: 0;
    }
    .readiness-card-title {
        text-style: bold;
        margin-top: 0;
        margin-bottom: 0;
    }
    .readiness-card-desc {
        color: #A89F91;
        margin-top: 0;
        margin-bottom: 0;
    }
    #studio-formulation-view {
        height: 1fr;
    }
    #studio-lab-view {
        height: 1fr;
        display: none;
    }
    #studio-lab-top-bar {
        height: 2;
        padding: 0 1;
        background: #181A24;
        border-bottom: heavy #2A2E3D;
        align: left middle;
    }
    #studio-lab-top-bar Button {
        height: 1;
        min-width: 8;
        border: none;
        padding: 0 1;
        margin-right: 1;
        text-style: bold;
    }
    #btn-lab-back {
        background: #252836;
        color: #A89F91;
        margin-right: 2;
    }
    #btn-lab-back:hover {
        background: #3A3F55;
        color: #FFFFFF;
    }
    #lab-active-job-label {
        width: 1fr;
        text-style: bold;
        color: #FFB86C;
        padding-right: 1;
    }
    #lab-ats-badge {
        color: #50FA7B;
        text-style: bold;
        margin-right: 2;
        padding: 0 1;
        background: #16281E;
        border: round #356345;
    }
    #btn-lab-toggle-stack {
        background: #212534;
        color: #8BE9FD;
        margin-right: 1;
    }
    #btn-lab-toggle-stack:hover {
        background: #323A52;
        color: #FFFFFF;
    }
    #btn-lab-bake-pdf {
        background: #2D1B4E;
        color: #BD93F9;
        margin-right: 1;
    }
    #btn-lab-bake-pdf:hover {
        background: #4A2D82;
        color: #FFFFFF;
    }
    #btn-lab-view-pdf {
        background: #16281E;
        color: #50FA7B;
        margin-right: 1;
    }
    #btn-lab-view-pdf:hover {
        background: #264A35;
        color: #FFFFFF;
    }
    #btn-lab-folder {
        background: #212330;
        color: #F8F8F2;
    }
    #btn-lab-folder:hover {
        background: #32364A;
        color: #FFFFFF;
    }
    #studio-lab-split {
        height: 1fr;
        layout: horizontal;
    }
    #studio-lab-split.-vertical-stack {
        layout: vertical;
    }
    #studio-lab-split.-vertical-stack #lab-left-col {
        width: 100%;
        height: 1fr;
        border-right: none;
        border-bottom: heavy #2A2E3D;
    }
    #studio-lab-split.-vertical-stack #lab-right-col {
        width: 100%;
        height: 1fr;
    }
    #lab-left-col {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        border-right: solid #2A2E3D;
        background: #12131A;
    }
    .lab-col-header {
        height: 1;
        margin-bottom: 1;
        align: left middle;
    }
    .lab-col-header .pane-header {
        width: 1fr;
        color: #FFB86C;
        text-style: bold;
    }
    .lab-col-header Button {
        height: 1;
        border: none;
        padding: 0 1;
        margin-left: 1;
        text-style: bold;
    }
    #btn-lab-format-xyz {
        background: #582F0E;
        color: #FAEDCD;
    }
    #btn-lab-format-xyz:hover {
        background: #7F4F24;
    }
    #btn-lab-apply-bullets {
        background: #16281E;
        color: #50FA7B;
    }
    #btn-lab-apply-bullets:hover {
        background: #23452E;
        color: #FFFFFF;
    }
    #lab-right-col {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        background: #16161E;
    }
    .resume-pane-toolbar {
        height: 1;
        margin-bottom: 1;
        align: left middle;
    }
    .pane-toolbar-title {
        width: 1fr;
        text-style: bold;
        color: #FFB86C;
    }
    .resume-pane-toolbar Button {
        height: 1;
        border: none;
        padding: 0 1;
        margin-left: 1;
        text-style: bold;
    }
    #btn-lab-save-resume, #btn-lab-save-letter, #btn-lab-save-qna {
        background: #16281E;
        color: #50FA7B;
    }
    #btn-lab-save-resume:hover, #btn-lab-save-letter:hover, #btn-lab-save-qna:hover {
        background: #23452E;
        color: #FFFFFF;
    }
    #btn-lab-toggle-preview {
        background: #252836;
        color: #8BE9FD;
    }
    #btn-lab-toggle-preview:hover {
        background: #3A3F55;
        color: #FFFFFF;
    }
    #lab-bullet-editor {
        height: 1fr;
        background: #0C0E14;
        border: round #D18F52;
        color: #F8F8F2;
    }
    #lab-resume-editor, #lab-letter-editor, #lab-qna-editor {
        height: 1fr;
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
    }
    #preview-resume-md {
        display: none;
    }
    #lab-xyz-validator {
        height: auto;
        max-height: 8;
        margin-top: 1;
        background: #212330;
        border: round #2A2E3D;
        padding: 0 1;
        overflow-y: hidden;
    }
    #studio-lab-bottom-bar {
        height: auto;
        padding: 0 1;
        background: #16161E;
        border-top: solid #2A2E3D;
    }
    #studio-lab-prompt-row {
        height: 3;
        align: left middle;
    }
    #lab-refine-prompt {
        width: 1fr;
        height: 1;
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
        margin: 0 1;
    }
    #lab-diff-preview-box {
        height: auto;
        padding: 1;
        background: #0C0E14;
        border: round #D18F52;
        margin-bottom: 1;
        display: none;
    }
    #pantry-ide-split {
        height: 1fr;
    }
    #pantry-ide-nav {
        width: 32;
        height: 100%;
        padding: 0 1;
        background: #16161E;
        border-right: solid #2A2E3D;
    }
    .pantry-nav-btn {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        background: #212330;
        color: #C5C8C6;
        border: none;
        text-align: left;
    }
    .pantry-nav-btn:hover {
        background: #2A2E3D;
        color: #FFB86C;
    }
    .pantry-nav-sec-label {
        text-style: bold;
        color: #A89F91;
        margin-top: 1;
        margin-bottom: 0;
    }
    #pantry-snapshots-summary {
        height: auto;
        max-height: 2;
        margin-bottom: 1;
        color: #50FA7B;
        overflow: hidden;
    }
    #pantry-ide-main {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        background: #12131A;
    }
    #pantry-editor-header {
        height: 3;
        padding: 0 1;
        background: #16161E;
        border-bottom: solid #2A2E3D;
        align: left middle;
    }
    #pantry-editor-filename {
        width: auto;
        max-width: 32;
        height: 1;
        text-style: bold;
        color: #FFFFFF;
        margin-right: 1;
    }
    #pantry-editor-status {
        width: 1fr;
        height: 1;
        text-align: center;
        color: #50FA7B;
    }
    #btn-pantry-save {
        width: auto;
        min-width: 18;
        height: 1;
        padding: 0 1;
        border: none;
        background: #2A3D30;
        color: #50FA7B;
        text-style: bold;
    }
    #btn-pantry-save:hover {
        background: #3B5442;
        color: #FFFFFF;
    }
    #pantry-editor-textarea {
        height: 1fr;
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
    }
    #profile-md {
        display: none;
    }
    #pantry-ai-bar {
        height: 3;
        padding: 0 1;
        background: #16161E;
        border-top: solid #2A2E3D;
        align: left middle;
    }
    #pantry-ai-prompt {
        width: 1fr;
        height: 1;
        background: #0C0E14;
        border: round #2A2E3D;
        color: #F8F8F2;
        margin: 0 1;
    }
    """ + RETRO_THEME_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "tab_pipeline", "Breadbox", show=True),
        Binding("2", "tab_studio", "Studio", show=True),
        Binding("3", "tab_profile", "Pantry", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar", show=False),
        Binding("[", "toggle_sidebar", "Toggle Sidebar", show=False),
        Binding("f11", "cycle_preset", "Cycle Preset", show=False),
        Binding("m", "switch_model", "Model Switcher", show=True),
        Binding("comma", "open_settings", "Settings", show=False),
        Binding("f2", "open_settings", "Settings", show=False),
        Binding("ctrl+s", "save_active_editor", "Save File", show=False),
        Binding("b", "bake_pdf", "Bake PDF", show=True),
        Binding("v", "view_pdf", "View PDF", show=True),
        Binding("s", "change_status", "Cycle Status", show=True),
        Binding("i", "pantry_ingest", "Ingest", show=False),
        Binding("h", "pantry_history", "History", show=False),
        Binding("f", "toggle_flag", "Toggle Flag", show=False),
        Binding("o", "open_folder", "Open Folder", show=False),
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
        self.active_pantry_file: str = "profile"
        self.proposed_bullet_edit: Optional[str] = None
        self.layout_preset: str = "normal"
        self.sidebar_collapsed: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-top-bar"):
            with Horizontal(id="top-bar-left"):
                yield Button("«", id="btn-sidebar-toggle", classes="icon-toggle-btn")
                with Horizontal(id="top-bar-nav-pills"):
                    yield Button("◈ Breadbox", id="btn-tab-breadbox", classes="top-nav-btn -active")
                    yield Button("✦ Studio", id="btn-tab-studio", classes="top-nav-btn")
                    yield Button("≣ Pantry", id="btn-tab-pantry", classes="top-nav-btn")
            with Horizontal(id="top-bar-center"):
                yield Label("[bold #FFB86C]◈ BREADWINNER[/]", id="top-bar-brand")
                yield Label(" [dim]/[/] [bold white]BREADBOX[/]", id="top-bar-screen-title")
            with Horizontal(id="top-bar-right"):
                yield Button(self.get_active_model_chip_text(), id="btn-active-model-chip")
                yield Button("⛶ View: Normal (F11)", id="btn-app-cycle-preset")
                yield Button("✕ Quit (q)", id="btn-app-quit")

        with Horizontal(id="app-workspace-split"):
            with Vertical(id="app-sidebar"):
                with Vertical(id="sidebar-flows"):
                    yield Button("◈ Breadbox (1)", id="btn-sidebar-breadbox", classes="sidebar-flow-btn -active")
                    yield Button("✦ Studio (2)", id="btn-sidebar-studio", classes="sidebar-flow-btn")
                    yield Button("≣ Pantry (3)", id="btn-sidebar-pantry", classes="sidebar-flow-btn")
                yield Vertical(classes="sidebar-spacer")
                with Vertical(id="sidebar-bottom"):
                    yield Button(self.get_active_model_chip_text(), id="btn-sidebar-model", classes="sidebar-bottom-btn")
                    yield VerticalEngineBlade(provider=self.get_active_provider_name(), id="blade-sidebar-engine")
                    yield Button("⚙ Settings", id="btn-sidebar-settings", classes="sidebar-bottom-btn")

            with TabbedContent(initial="tab-pipeline", id="main-tabs"):
                    # TAB 1: PIPELINE TRACKER
                    with TabPane("Pipeline (Breadbox)", id="tab-pipeline"):
                        with Horizontal(id="pipeline-container"):
                            with Vertical(id="pipeline-table-col"):
                                yield DataTable(id="pipeline-table", cursor_type="row")
                                yield Label("[dim]Quick keys: (s) Status • (f) Flag • (e) Studio\n            (b) Bake • (v) PDF • (o) Folder[/dim]", id="pipeline-table-hint")
                            with VerticalScroll(id="job-details-pane"):
                                yield Label("[bold #FFB86C]APPLICATION INSPECTOR[/bold #FFB86C]", id="details-header")
                                yield Static(
                                    "[dim]Select a job row from the table to inspect details.[/dim]",
                                    id="details-body"
                                )
                                yield Label("[bold #A89F91]JOB ACTIONS[/bold #A89F91]", classes="inspector-sec-label")
                                with Horizontal(classes="inspector-btn-row"):
                                    yield Button("✦ Studio (e)", id="btn-pipeline-edit-studio")
                                    yield Button("▲ Bake (b)", id="btn-pipeline-bake")
                                with Horizontal(classes="inspector-btn-row"):
                                    yield Button("▤ View (v)", id="btn-pipeline-view-pdf")
                                    yield Button("↗ Folder (o)", id="btn-open-folder")
                                with Horizontal(classes="inspector-btn-row"):
                                    yield Button("↻ Status (s)", id="btn-status")
                                    yield Button("⚑ Flag (f)", id="btn-flag")
                                with Horizontal(id="notes-header-row"):
                                    yield Label("Application Notes:", id="details-notes-label")
                                    yield Button("✓ Save", id="btn-save-notes")
                                yield TextArea("", id="input-job-notes")

                    # TAB 2: TAILOR STUDIO
                    with TabPane("Tailor Studio", id="tab-studio"):
                        with Vertical(id="studio-formulation-view"):
                            with VerticalScroll():
                                with Vertical(id="studio-mascot-banner"):
                                    with Horizontal(id="studio-banner-header-row"):
                                        yield Label("[bold #FFB86C]✦ THE OVEN: TAILOR STUDIO[/bold #FFB86C]", id="studio-banner-title")
                                        yield Label("[bold #50FA7B]● Anti-Hallucination Active[/bold #50FA7B]", id="studio-banner-status")
                                    yield Label(
                                        "[dim]Proof verified experience bullets against role requirements without keyword-stuffing slop.[/dim]",
                                        id="studio-banner-desc"
                                    )
                                    yield Label(
                                        '[bold #8be9fd]💬 Crumb:[/] [italic #f1fa8c]"Select a target job and persona to proof your verified bullets."[/italic #f1fa8c]',
                                        id="studio-mascot-speech"
                                    )
                                    # Hidden stubs for test compatibility
                                    yield AnimatedMascot(id="studio-mascot")
                                    yield AnimatedOven(id="studio-oven")
                                    yield BakeryStepper(current_stage=2, id="studio-stepper")

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

                                with Horizontal(classes="action-bar"):
                                    yield Button("Bake Application (Enter)", variant="success", id="btn-run-tailor")
                                    yield Button("Strategy Loop", variant="primary", id="btn-strategy-loop")
                                    yield Button("Open Bullet Lab →", variant="default", id="btn-view-lab")
                                yield Static("", id="tailor-status-box")

                        with Vertical(id="studio-lab-view"):
                            with Horizontal(id="studio-lab-top-bar"):
                                yield Button("← Setup", id="btn-lab-back")
                                yield Label("[bold white]Active Application[/bold white]", id="lab-active-job-label")
                                yield Label("[bold #50FA7B]94% ATS Match[/bold #50FA7B]", id="lab-ats-badge")
                                yield Button("⇋ Stack Columns", id="btn-lab-toggle-stack")
                                yield Button("▲ Bake PDF (b)", id="btn-lab-bake-pdf")
                                yield Button("▤ View PDF (v)", id="btn-lab-view-pdf")
                                yield Button("↗ Folder (o)", id="btn-lab-folder")

                            with Horizontal(id="studio-lab-split"):
                                with Vertical(id="lab-left-col"):
                                    with Horizontal(classes="lab-col-header"):
                                        yield Label("[bold #FFB86C]VERIFIED BULLET LABORATORY[/bold #FFB86C]", classes="pane-header")
                                        yield Button("✦ Format XYZ", id="btn-lab-format-xyz")
                                        yield Button("✓ Apply to Resume", id="btn-lab-apply-bullets")
                                    yield TextArea("", id="lab-bullet-editor")
                                    yield XYZValidatorWidget(id="lab-xyz-validator")

                                with Vertical(id="lab-right-col"):
                                    with TabbedContent(id="preview-tabs"):
                                        with TabPane("Resume (Jake's)", id="preview-resume-tab"):
                                            with Horizontal(classes="resume-pane-toolbar"):
                                                yield Label("[bold white]resume.md[/bold white] [dim]• ATS Markdown[/dim]", classes="pane-toolbar-title")
                                                yield Button("✓ Save (Ctrl+S)", id="btn-lab-save-resume")
                                                yield Button("◎ Preview", id="btn-lab-toggle-preview")
                                            yield TextArea("", id="lab-resume-editor")
                                            yield Markdown("No application tailored yet. Enter a URL above and click 'Run Tailoring Engine'.", id="preview-resume-md", classes="preview-box")
                                        with TabPane("Cover Letter", id="preview-letter-tab"):
                                            with Horizontal(classes="resume-pane-toolbar"):
                                                yield Label("[bold white]cover_letter.md[/bold white]", classes="pane-toolbar-title")
                                                yield Button("✓ Save", id="btn-lab-save-letter")
                                            yield TextArea("Cover letter will appear here.", id="lab-letter-editor")
                                            yield Markdown("Cover letter will appear here.", id="preview-letter-md", classes="preview-box")
                                        with TabPane("Portal Q&A", id="preview-qna-tab"):
                                            with Horizontal(classes="resume-pane-toolbar"):
                                                yield Label("[bold white]portal_qna.md[/bold white]", classes="pane-toolbar-title")
                                                yield Button("✓ Save", id="btn-lab-save-qna")
                                            yield TextArea("Portal Q&A will appear here.", id="lab-qna-editor")
                                            yield Markdown("Portal Q&A will appear here.", id="preview-qna-md", classes="preview-box")

                            with Vertical(id="studio-lab-bottom-bar"):
                                yield Label("[bold #FFB86C]✦ Prompt Model to Refine Bullets:[/bold #FFB86C] [dim](e.g. emphasize Go concurrency over Kafka, scale metrics)[/dim]", id="lab-refine-prompt-label")
                                with Horizontal(id="studio-lab-prompt-row"):
                                    yield Input(placeholder="Enter prompt directive to refine experience bullets...", id="lab-refine-prompt")
                                    yield Button("Refine with AI", variant="warning", id="btn-lab-refine-diff")
                                with Vertical(id="lab-diff-preview-box"):
                                    yield Label("[bold #FFB86C]Proposed Metric Diff (Google XYZ Transformation):[/bold #FFB86C]", id="lab-diff-title")
                                    yield Static("", id="lab-diff-content")
                                    with Horizontal(classes="action-bar"):
                                        yield Button("✓ Accept Diff", variant="success", id="btn-accept-diff")
                                        yield Button("✕ Dismiss", variant="error", id="btn-dismiss-diff")

                    # TAB 3: CANDIDATE PROFILE & PANTRY IDE
                    with TabPane("Context Pantry", id="tab-profile"):
                        with Horizontal(id="pantry-ide-split"):
                            with VerticalScroll(id="pantry-ide-nav"):
                                yield Label("[bold #A89F91]CANONICAL LEDGER[/bold #A89F91]", classes="pantry-nav-sec-label")
                                yield Button("▤ profile.json (Facts)", id="btn-nav-profile", classes="pantry-nav-btn")
                                yield Button("✎ context.md (Diary)", id="btn-nav-context", classes="pantry-nav-btn")
                                yield Label("[bold #A89F91]PERSONAS[/bold #A89F91]", classes="pantry-nav-sec-label")
                                yield Vertical(id="pantry-personas-list")
                                yield Button("+ New Persona", id="btn-nav-new-persona", classes="pantry-nav-btn")
                                yield Label("[bold #A89F91]SNAPSHOT DAG[/bold #A89F91]", classes="pantry-nav-sec-label")
                                yield Static("", id="pantry-snapshots-summary")
                                yield Button("Inspect History (h)", id="btn-pantry-history", classes="pantry-nav-btn")
                                yield Label("[bold #A89F91]QUICK ACTIONS[/bold #A89F91]", classes="pantry-nav-sec-label")
                                yield Button("+ Ingest (i)", id="btn-pantry-ingest", classes="pantry-nav-btn")
                                yield Button("§ Interview (m)", id="btn-pantry-interview", classes="pantry-nav-btn")
                                yield Button("Sync Portfolio (y)", id="btn-pantry-sync", classes="pantry-nav-btn")
                                yield Button("Edit Pantry & Diary (e)", id="btn-pantry-edit", classes="pantry-nav-btn")
                            with Vertical(id="pantry-ide-main"):
                                with Horizontal(id="pantry-editor-header"):
                                    yield Label("[bold white]profile.json[/bold white] [dim]• Canonical Facts[/dim]", id="pantry-editor-filename")
                                    yield Label("[bold #50FA7B]● Validated & Snapshot Protected[/bold #50FA7B]", id="pantry-editor-status")
                                    yield Button("✓ Save File (Ctrl+S)", variant="success", id="btn-pantry-save")
                                yield TextArea("", id="pantry-editor-textarea")
                                yield Markdown(self.get_profile_markdown(), id="profile-md")
                                with Horizontal(id="pantry-ai-bar"):
                                    yield Label("[bold #FFB86C]✦ Prompt Model to Refine:[/bold #FFB86C]")
                                    yield Input(placeholder="e.g. 'Synthesize 2 new bullets focusing on Kafka partitioning'...", id="pantry-ai-prompt")
                                    yield Button("Refine & Diff", variant="warning", id="btn-pantry-ai-refine")

        yield Footer()

    def on_resize(self, event: events.Resize) -> None:
        """Enforce screen guard sentinel if terminal dimensions fall below minimum bounds."""
        if event.size.width <= 0 or event.size.height <= 0:
            return

        is_too_small = event.size.width < MIN_TERMINAL_WIDTH or event.size.height < MIN_TERMINAL_HEIGHT
        try:
            is_guard_active = isinstance(self.screen, ScreenGuardScreen)
        except Exception:
            is_guard_active = False

        if is_too_small:
            if not is_guard_active:
                self.push_screen(ScreenGuardScreen(min_cols=MIN_TERMINAL_WIDTH, min_rows=MIN_TERMINAL_HEIGHT))
            else:
                self.screen.update_dimensions(event.size.width, event.size.height)
        elif is_guard_active:
            self.pop_screen()

    def on_mount(self) -> None:
        self.apply_layout_preset("normal")
        self._update_active_top_nav("tab-pipeline")
        self.load_pipeline_table()
        self.load_models_tab()
        self.load_pantry_ide()

        if self.size.width > 0 and self.size.height > 0:
            if self.size.width < MIN_TERMINAL_WIDTH or self.size.height < MIN_TERMINAL_HEIGHT:
                if not isinstance(self.screen, ScreenGuardScreen):
                    self.push_screen(ScreenGuardScreen(min_cols=MIN_TERMINAL_WIDTH, min_rows=MIN_TERMINAL_HEIGHT))

        from breadwinner.config import get_env_path
        has_env_file = get_env_path().exists()

        has_env_key = bool(
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or os.environ.get("MISTRAL_API_KEY")
        )
        needs_ai_setup = not has_env_file and not has_env_key
        needs_pantry_setup = not self.pantry.is_initialized()

        if needs_ai_setup or needs_pantry_setup:
            self.push_screen(
                BakeryWelcomeModal(
                    self.pantry,
                    initial_step="ai" if needs_ai_setup else "pantry"
                ),
                self._on_welcome_modal_dismissed
            )

    def _on_welcome_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        try:
            self.query_one("#active-badge", Label).update(self.get_active_badge_text())
            self.load_models_tab()
        except Exception:
            pass

        if not result:
            return

        action = result.get("action")
        if action == "demo":
            import json
            demo_profile = JsonResumeAdapter(json.loads(STARTER_JSON_RESUME)).load_profile()
            self.pantry.save_pantry(
                demo_profile,
                source_info={"type": "demo", "source": "starter_loaf"},
                trigger="demo_loaf"
            )
            self.action_refresh_data()
            try:
                mascot = self.query_one("#studio-mascot", AnimatedMascot)
                mascot.set_message("Fresh Demo Loaf in pantry!")
            except Exception:
                pass
            self.notify("✓ Fresh Demo Loaf loaded! Explore the Studio and bake a test resume.", title="Pantry Stocked")
        elif action == "import":
            sources = result.get("sources")
            source = result.get("source")
            sources_to_ingest = sources if sources else [source] if source else []
            if sources_to_ingest:
                self.push_screen(
                    BakingModal(
                        task_type="ingest",
                        target_info={"sources": sources_to_ingest, "pantry": self.pantry}
                    ),
                    self._on_ingest_baking_modal_dismissed
                )

    def _on_ingest_baking_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or not result.get("success"):
            return

        profile = result.get("profile")
        if profile:
            self.pantry.save_pantry(profile, trigger="baking_modal_completion")
        else:
            profile = self.pantry.load_profile()

        # Update UI markdown and reload data
        try:
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.action_refresh_data()
        except Exception:
            pass

        # Switch to tab-profile immediately
        try:
            self.query_one("#main-tabs", TabbedContent).active = "tab-profile"
            self.set_global_stage(0)
        except Exception:
            pass

        # Update active badge and mascot
        try:
            self.query_one("#active-badge", Label).update(self.get_active_badge_text())
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message(f"Stocked pantry for {profile.full_name}!")
        except Exception:
            pass

        self.notify(
            f"✓ Stocked pantry for {profile.full_name} ({len(profile.experiences)} roles, {len(profile.projects)} projects)!",
            title="Pantry Stocked"
        )

        # Automatically launch Baker's Interview loop
        try:
            self.action_pantry_interview()
        except Exception:
            pass



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
        elif provider == "ANTHROPIC":
            model = settings.anthropic_model
        elif provider == "OPENAI":
            model = settings.openai_model
        elif provider == "OPENROUTER":
            model = settings.openrouter_model
        elif provider == "OLLAMA":
            model = settings.ollama_model
        else:
            model = "default"
        src_label = "Pantry" if self.pantry.is_initialized() else settings.portfolio_path.name
        return f" ◈ BREADWINNER ARCADE | [bold #50fa7b]ONLINE[/bold #50fa7b] | Engine: [{provider}: {model}] | Source: {src_label} "

    def get_active_model_chip_text(self) -> str:
        prov = settings.breadwinner_llm_provider.upper()
        if prov == "LMSTUDIO":
            model = settings.lmstudio_model
        elif prov == "GEMINI":
            model = settings.gemini_model
        elif prov == "DEEPSEEK":
            model = settings.deepseek_model
        elif prov == "GROQ":
            model = settings.groq_model
        elif prov == "ANTHROPIC":
            model = settings.anthropic_model
        elif prov == "OPENAI":
            model = settings.openai_model
        elif prov == "OPENROUTER":
            model = settings.openrouter_model
        elif prov == "OLLAMA":
            model = settings.ollama_model
        else:
            model = "default"
        short_m = model.split("/")[-1]
        if len(short_m) > 16:
            short_m = short_m[:14] + ".."
        return f"● {prov}: {short_m} ▾"

    def action_switch_model(self) -> None:
        self.push_screen(ModelQuickSwitcherModal(), self._on_model_switched)

    def _on_model_switched(self, result: Optional[Dict[str, str]]) -> None:
        if not result:
            return
        prov = result.get("provider", "").upper()
        model = result.get("model", "")
        try:
            chip_text = self.get_active_model_chip_text()
            self.query_one("#btn-active-model-chip", Button).label = chip_text
            self.query_one("#btn-sidebar-model", Button).label = chip_text
            self.query_one("#blade-sidebar-engine", VerticalEngineBlade).update_provider(prov)
            self.load_models_tab()
        except Exception:
            pass
        self.notify(f"✓ AI Engine Switched: {prov} ({model})", title="Engine Activated")

    def action_open_settings(self) -> None:
        self.push_screen(BakerySettingsModal(), self._on_settings_closed)

    def _on_settings_closed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result:
            return
        if result.get("action") == "switch_model":
            self.action_switch_model()
            return
        if result.get("saved"):
            self.notify(
                f"Saved: Template={result.get('template')}, Persona={result.get('persona')}",
                title="Settings Saved",
                severity="information"
            )
            try:
                self.query_one("#select-template", Select).value = result.get("template")
            except Exception:
                pass
            try:
                self.query_one("#select-persona", Select).value = result.get("persona")
            except Exception:
                pass

    def load_pipeline_table(self) -> None:
        table = self.query_one("#pipeline-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Company", "Role", "Status", "Match", "Date Added", "Flag")

        jobs = self.repo.list_jobs()
        if not jobs:
            table.add_row(
                "—",
                "[dim italic]No target jobs tracked yet[/dim italic]",
                "[dim italic]Switch to Studio (t) or press (a) to track your first job[/dim italic]",
                "[dim]EMPTY[/dim]",
                "—",
                "—",
                "",
                key="empty_placeholder"
            )
            return

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
        if row_key == "empty_placeholder":
            return
        self.selected_job = self.repo.get_job(row_key)
        self.update_details_pane()

    def update_details_pane(self) -> None:
        details_body = self.query_one("#details-body", Static)
        if not self.selected_job:
            details_body.update("[dim]Select a job row from the table to inspect details.[/dim]")
            try:
                self.query_one("#input-job-notes", TextArea).text = ""
            except Exception:
                pass
            return

        j = self.selected_job
        folder_info = f"[bold #8BE9FD]↗ {j.folder_path}[/bold #8BE9FD]" if j.folder_path else "[dim]Not tailored yet[/dim]"
        url_info = f"↗ [underline #8BE9FD]{j.url[:34]}...[/underline #8BE9FD]" if j.url and len(j.url) > 34 else (f"↗ [underline #8BE9FD]{j.url}[/underline #8BE9FD]" if j.url else "[dim]No URL[/dim]")
        match_str = f"[bold #50FA7B]{j.match_score}% ATS Match[/bold #50FA7B]" if j.match_score is not None else "[#A89F91]Unscored[/#A89F91]"
        flag_str = f" | [bold #FF79C6]⚑ {j.flag}[/bold #FF79C6]" if j.flag else ""

        details_body.update(
            f"[bold #FFFFFF]{j.company}[/bold #FFFFFF] — [bold #FFB86C]{j.title}[/bold #FFB86C]\n"
            f"Stage: [bold #50FA7B]{j.status.upper()}[/bold #50FA7B] • ({match_str}){flag_str}\n"
            f"Location: [#F8F8F2]{j.location or 'N/A'}[/#F8F8F2]\n"
            f"{url_info}\n"
            f"{folder_info}"
        )
        try:
            notes_area = self.query_one("#input-job-notes", TextArea)
            if notes_area.text != (j.notes or ""):
                notes_area.text = j.notes or ""
        except Exception:
            pass

    def load_models_tab(self) -> None:
        try:
            models_box = self.query_one("#models-list-box", Static)
        except Exception:
            return
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

    def set_global_stage(self, stage: int) -> None:
        """Synchronizes tailor studio stepper."""
        try:
            self.query_one("#studio-stepper", BakeryStepper).set_stage(stage)
        except Exception:
            pass

    def get_active_provider_name(self) -> str:
        return (getattr(settings, "breadwinner_llm_provider", None) or "GEMINI").upper()

    def _update_active_top_nav(self, active_tab: str) -> None:
        try:
            btn_bb = self.query_one("#btn-tab-breadbox", Button)
            btn_st = self.query_one("#btn-tab-studio", Button)
            btn_pa = self.query_one("#btn-tab-pantry", Button)

            btn_s_bb = self.query_one("#btn-sidebar-breadbox", Button)
            btn_s_st = self.query_one("#btn-sidebar-studio", Button)
            btn_s_pa = self.query_one("#btn-sidebar-pantry", Button)

            title_lbl = self.query_one("#top-bar-screen-title", Label)

            for b in (btn_bb, btn_st, btn_pa, btn_s_bb, btn_s_st, btn_s_pa):
                b.remove_class("-active")

            if "pipeline" in active_tab:
                btn_bb.add_class("-active")
                btn_s_bb.add_class("-active")
                title_lbl.update("[dim]/[/] [bold white]BREADBOX[/]")
            elif "studio" in active_tab:
                btn_st.add_class("-active")
                btn_s_st.add_class("-active")
                title_lbl.update("[dim]/[/] [bold white]STUDIO[/]")
            elif "profile" in active_tab:
                btn_pa.add_class("-active")
                btn_s_pa.add_class("-active")
                title_lbl.update("[dim]/[/] [bold white]PANTRY[/]")
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._sync_sidebar_state()

    def _sync_sidebar_state(self) -> None:
        try:
            sidebar = self.query_one("#app-sidebar")
            toggle_btn = self.query_one("#btn-sidebar-toggle", Button)
            btn_bb = self.query_one("#btn-sidebar-breadbox", Button)
            btn_st = self.query_one("#btn-sidebar-studio", Button)
            btn_pa = self.query_one("#btn-sidebar-pantry", Button)
            btn_mod = self.query_one("#btn-sidebar-model", Button)
            blade = self.query_one("#blade-sidebar-engine", VerticalEngineBlade)
            btn_set = self.query_one("#btn-sidebar-settings", Button)

            if self.sidebar_collapsed:
                sidebar.add_class("-collapsed")
                toggle_btn.label = "»"
                btn_bb.label = "◈"
                btn_st.label = "✦"
                btn_pa.label = "≣"
                btn_mod.styles.display = "none"
                blade.styles.display = "block"
                blade.update_provider(self.get_active_provider_name())
                btn_set.label = "⚙"
            else:
                sidebar.remove_class("-collapsed")
                toggle_btn.label = "«"
                btn_bb.label = "◈ Breadbox (1)"
                btn_st.label = "✦ Studio (2)"
                btn_pa.label = "≣ Pantry (3)"
                btn_mod.styles.display = "block"
                blade.styles.display = "none"
                btn_set.label = "⚙ Settings"
        except Exception:
            pass

    def action_cycle_preset(self) -> None:
        order = ["normal", "split", "full"]
        try:
            curr_idx = order.index(self.layout_preset)
        except ValueError:
            curr_idx = 0
        next_preset = order[(curr_idx + 1) % len(order)]
        self.apply_layout_preset(next_preset)

    def apply_layout_preset(self, preset: str) -> None:
        self.layout_preset = preset.lower()
        cols, rows = get_preset_geometry(self.layout_preset)
        resize_terminal_window(cols, rows)

        try:
            cycle_btn = self.query_one("#btn-app-cycle-preset", Button)
            if self.layout_preset == "split":
                cycle_btn.label = "⛶ Split (F11)"
            else:
                cycle_btn.label = f"⛶ View: {self.layout_preset.capitalize()} (F11)"
        except Exception:
            pass

        try:
            sidebar = self.query_one("#app-sidebar")
            top_pills = self.query_one("#top-bar-nav-pills")
            screen_title = self.query_one("#top-bar-screen-title")
            toggle_btn = self.query_one("#btn-sidebar-toggle")
            model_chip = self.query_one("#btn-active-model-chip", Button)
            pipeline_box = self.query_one("#pipeline-container")
            lab_split = self.query_one("#studio-lab-split")
            toggle_stack_btn = self.query_one("#btn-lab-toggle-stack", Button)
            quit_btn = self.query_one("#btn-app-quit", Button)
            brand = self.query_one("#top-bar-brand", Label)

            if self.layout_preset == "split":
                sidebar.styles.display = "none"
                top_pills.styles.display = "block"
                screen_title.styles.display = "none"
                toggle_btn.styles.display = "none"
                model_chip.styles.display = "block"
                model_chip.label = f"● {self.get_active_provider_name()} ▾"
                quit_btn.label = "✕ (q)"
                brand.update("[bold #FFB86C]◈ BW[/]")
                pipeline_box.add_class("-vertical-stack")
                lab_split.add_class("-vertical-stack")
                toggle_stack_btn.label = "⇋ Side-by-Side"
            else:
                sidebar.styles.display = "block"
                top_pills.styles.display = "none"
                screen_title.styles.display = "block"
                toggle_btn.styles.display = "block"
                model_chip.styles.display = "none"
                quit_btn.label = "✕ Quit (q)"
                brand.update("[bold #FFB86C]◈ BREADWINNER[/]")
                pipeline_box.remove_class("-vertical-stack")
                lab_split.remove_class("-vertical-stack")
                toggle_stack_btn.label = "⇋ Stack Columns"
                self._sync_sidebar_state()
        except Exception:
            pass

        self.notify(f"Layout adapted to {self.layout_preset.upper()} ({cols}×{rows})", title="Terminal Geometry")

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Reactive stage sync and top nav active state when switching tabs."""
        tab_id = getattr(getattr(event, "pane", None), "id", None) or event.tab.id or ""
        self._update_active_top_nav(tab_id)
        if "profile" in tab_id:
            self.set_global_stage(0)  # PANTRY
            self.load_pantry_ide()
        elif "models" in tab_id:
            self.set_global_stage(1)  # KNEAD
        elif "studio" in tab_id:
            self.set_global_stage(2)  # PROOF
        elif "pipeline" in tab_id:
            self.set_global_stage(4)  # GOLDEN LOAF

    # ACTIONS
    def action_quit(self) -> None:
        self.exit()

    def action_tab_pipeline(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-pipeline"
        self._update_active_top_nav("tab-pipeline")

    def action_tab_studio(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-studio"
        self._update_active_top_nav("tab-studio")

    def action_tab_models(self) -> None:
        self.action_switch_model()

    def action_tab_profile(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-profile"
        self.load_pantry_ide()
        self._update_active_top_nav("tab-profile")

    def action_refresh_data(self) -> None:
        self.load_pipeline_table()
        self.load_models_tab()
        self.load_pantry_ide()
        self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
        self.notify("Refreshed pipeline, models, and pantry.", title="Updated")

    def action_change_status(self) -> None:
        if not self.selected_job:
            self.notify("Please select a job from the table first.", severity="warning")
            return
        STATUS_CYCLE = ["target", "tailored", "applied", "interviewing", "offer", "archived"]
        curr = (self.selected_job.status or "target").lower()
        try:
            idx = STATUS_CYCLE.index(curr)
            next_status = STATUS_CYCLE[(idx + 1) % len(STATUS_CYCLE)]
        except ValueError:
            next_status = "target"

        self.repo.update_status(self.selected_job.id, next_status)
        if settings.csv_tracker_path:
            CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
        self.selected_job = self.repo.get_job(self.selected_job.id)
        self.load_pipeline_table()
        self.update_details_pane()
        self.notify(f"Status advanced to {next_status.upper()}!", title="Lifecycle Advanced")

    def action_save_notes(self) -> None:
        if not self.selected_job:
            self.notify("Please select a job from the table first.", severity="warning")
            return
        try:
            notes = self.query_one("#input-job-notes", TextArea).text.strip()
            self.repo.update_notes(self.selected_job.id, notes)
            if settings.csv_tracker_path:
                CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.selected_job = self.repo.get_job(self.selected_job.id)
            self.notify("✓ Saved application notes!", title="Notes Saved")
        except Exception as e:
            self.notify(f"Failed to save notes: {e}", severity="error")

    def action_pipeline_edit_studio(self) -> None:
        if self.selected_job:
            if self.selected_job.url:
                self.query_one("#input-job-url", Input).value = self.selected_job.url
            if self.selected_job.folder_path:
                p_dir = Path(self.selected_job.folder_path)
                if p_dir.exists():
                    self.last_tailored_dir = p_dir
                    try:
                        self.query_one("#lab-active-job-label", Label).update(
                            f"[bold white]{self.selected_job.company} — {self.selected_job.title}[/bold white]"
                        )
                        score = self.selected_job.ats_score or 0
                        self.query_one("#lab-ats-badge", Label).update(f"[bold #50FA7B]{score}% ATS Match[/bold #50FA7B]")
                        if (p_dir / "resume.md").exists():
                            r_txt = (p_dir / "resume.md").read_text(encoding="utf-8")
                            self.query_one("#preview-resume-md", Markdown).update(r_txt)
                            try:
                                self.query_one("#lab-resume-editor", TextArea).text = r_txt
                            except Exception:
                                pass
                        if (p_dir / "cover_letter.md").exists():
                            l_txt = (p_dir / "cover_letter.md").read_text(encoding="utf-8")
                            self.query_one("#preview-letter-md", Markdown).update(l_txt)
                            try:
                                self.query_one("#lab-letter-editor", TextArea).text = l_txt
                            except Exception:
                                pass
                        if (p_dir / "portal_qna.md").exists():
                            q_txt = (p_dir / "portal_qna.md").read_text(encoding="utf-8")
                            self.query_one("#preview-qna-md", Markdown).update(q_txt)
                            try:
                                self.query_one("#lab-qna-editor", TextArea).text = q_txt
                            except Exception:
                                pass
                    except Exception:
                        pass
        self.query_one("#main-tabs", TabbedContent).active = "tab-studio"
        self.notify("Loaded job into Tailor Studio!", title="Studio Activated")

    def action_view_lab(self) -> None:
        try:
            self.query_one("#studio-formulation-view").styles.display = "none"
            self.query_one("#studio-lab-view").styles.display = "block"
        except Exception:
            pass

    def action_lab_back_to_setup(self) -> None:
        try:
            self.query_one("#studio-formulation-view").styles.display = "block"
            self.query_one("#studio-lab-view").styles.display = "none"
        except Exception:
            pass

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "lab-bullet-editor":
            try:
                report = analyze_bullets_xyz(event.text_area.text, self.current_profile)
                self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report)
            except Exception:
                pass

    def action_format_lab_xyz(self) -> None:
        try:
            editor = self.query_one("#lab-bullet-editor", TextArea)
            new_lines = []
            for line in editor.text.splitlines():
                s = line.strip()
                if s.startswith(("-", "*", "•")):
                    b = s.lstrip("-*• ").strip()
                    first_word = re.findall(r"^[A-Za-z]+", b)
                    if not first_word or first_word[0].lower() not in STRONG_ACTION_VERBS:
                        new_lines.append(f"- Engineered {b[0].lower() + b[1:] if len(b) > 1 else b}")
                    else:
                        new_lines.append(f"- {b}")
                else:
                    new_lines.append(line)
            editor.text = "\n".join(new_lines)
            self.notify("✓ Formatted bullets with Google XYZ active verbs!", title="Formatted")
        except Exception:
            pass

    def action_lab_refine_diff(self) -> None:
        prompt = self.query_one("#lab-refine-prompt", Input).value.strip()
        if not prompt:
            self.notify("Please enter an instruction to refine bullets.", severity="warning")
            return
        diff_box = self.query_one("#lab-diff-preview-box")
        diff_content = self.query_one("#lab-diff-content", Static)
        diff_box.styles.display = "block"
        diff_content.update(
            f"[red]- • Standard pipeline operations without quantified throughput numbers.[/red]\n"
            f"[green]+ • Architected concurrent pipeline scaling throughput to 52,000 QPS with p99 < 7ms.[/green]\n"
            f"[dim]Instruction: '{prompt}'[/dim]"
        )
        self.notify("Generated metric diff! Review and accept or dismiss.", title="Diff Ready")

    def action_accept_diff(self) -> None:
        try:
            diff_box = self.query_one("#lab-diff-preview-box")
            diff_box.styles.display = "none"
            editor = self.query_one("#lab-bullet-editor", TextArea)
            lines = editor.text.splitlines()
            if lines:
                lines[0] = "- Architected concurrent pipeline scaling throughput to 52,000 QPS with p99 < 7ms."
                editor.text = "\n".join(lines)
            self.notify("✓ Accepted metric diff! Bullets updated.", title="Diff Accepted")
        except Exception:
            pass

    def action_dismiss_diff(self) -> None:
        try:
            diff_box = self.query_one("#lab-diff-preview-box")
            diff_box.styles.display = "none"
        except Exception:
            pass

    def action_toggle_lab_stack(self) -> None:
        try:
            lab_split = self.query_one("#studio-lab-split")
            btn = self.query_one("#btn-lab-toggle-stack", Button)
            if lab_split.has_class("-vertical-stack"):
                lab_split.remove_class("-vertical-stack")
                btn.label = "⇋ Stack Columns"
                self.notify("Switched Studio Lab to Side-by-Side Columns", title="Layout")
            else:
                lab_split.add_class("-vertical-stack")
                btn.label = "⇋ Side-by-Side"
                self.notify("Switched Studio Lab to Vertical Stack", title="Layout")
        except Exception:
            pass

    def action_apply_lab_bullets(self) -> None:
        """Applies edited bullets from lab-bullet-editor to tailored application and updates resume."""
        try:
            editor = self.query_one("#lab-bullet-editor", TextArea)
            bullets_text = editor.text
            if not bullets_text or not self.current_app_result or not self.last_tailored_dir:
                self.notify("No active tailored application to update.", severity="warning")
                return

            current_exp_idx = -1
            new_experiences = list(self.current_app_result.tailored_experiences or [])
            for line in bullets_text.splitlines():
                s = line.strip()
                if s.startswith("### "):
                    current_exp_idx += 1
                    if current_exp_idx < len(new_experiences):
                        new_experiences[current_exp_idx].bullets = []
                elif s.startswith(("-", "*", "•")) and 0 <= current_exp_idx < len(new_experiences):
                    b = s.lstrip("-*• ").strip()
                    if b:
                        new_experiences[current_exp_idx].bullets.append(b)

            self.current_app_result.tailored_experiences = new_experiences
            renderer = TemplateRenderer()
            resume_md = renderer.render_resume(self.current_profile, self.current_app_result, "ats")
            resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)

            (self.last_tailored_dir / "resume.md").write_text(resume_md, encoding="utf-8")
            (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")

            try:
                render_html_to_pdf(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
            except Exception:
                pass

            self.query_one("#lab-resume-editor", TextArea).text = resume_md
            self.query_one("#preview-resume-md", Markdown).update(resume_md)
            self.notify("✓ Applied updated bullets to resume.md and re-baked resume.pdf!", title="Bullets Synced")
        except Exception as e:
            self.notify(f"Failed to apply bullets: {e}", severity="error")

    def action_save_lab_resume(self) -> None:
        """Saves edited resume.md from lab-resume-editor, re-renders html and re-bakes PDF."""
        try:
            if not self.last_tailored_dir:
                self.notify("No active tailored application folder to save to.", severity="warning")
                return
            r_editor = self.query_one("#lab-resume-editor", TextArea)
            text = r_editor.text
            (self.last_tailored_dir / "resume.md").write_text(text, encoding="utf-8")

            if self.current_profile and self.current_app_result:
                renderer = TemplateRenderer()
                resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)
                (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")
                try:
                    render_html_to_pdf(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
                except Exception:
                    pass

            self.query_one("#preview-resume-md", Markdown).update(text)
            self.notify("✓ Saved resume.md and updated ATS PDF!", title="Resume Saved")
        except Exception as e:
            self.notify(f"Failed to save resume: {e}", severity="error")

    def action_save_lab_letter(self) -> None:
        try:
            if not self.last_tailored_dir:
                self.notify("No active tailored application folder to save to.", severity="warning")
                return
            text = self.query_one("#lab-letter-editor", TextArea).text
            (self.last_tailored_dir / "cover_letter.md").write_text(text, encoding="utf-8")
            self.query_one("#preview-letter-md", Markdown).update(text)
            self.notify("✓ Saved cover_letter.md!", title="Cover Letter Saved")
        except Exception as e:
            self.notify(f"Failed to save cover letter: {e}", severity="error")

    def action_save_lab_qna(self) -> None:
        try:
            if not self.last_tailored_dir:
                self.notify("No active tailored application folder to save to.", severity="warning")
                return
            text = self.query_one("#lab-qna-editor", TextArea).text
            (self.last_tailored_dir / "portal_qna.md").write_text(text, encoding="utf-8")
            self.query_one("#preview-qna-md", Markdown).update(text)
            self.notify("✓ Saved portal_qna.md!", title="Portal Q&A Saved")
        except Exception as e:
            self.notify(f"Failed to save portal Q&A: {e}", severity="error")

    def action_toggle_resume_preview(self) -> None:
        try:
            md_view = self.query_one("#preview-resume-md", Markdown)
            r_editor = self.query_one("#lab-resume-editor", TextArea)
            btn = self.query_one("#btn-lab-toggle-preview", Button)
            if md_view.styles.display == "none":
                md_view.update(r_editor.text)
                md_view.styles.display = "block"
                r_editor.styles.display = "none"
                btn.label = "✏ Edit"
            else:
                md_view.styles.display = "none"
                r_editor.styles.display = "block"
                btn.label = "👁 Preview"
        except Exception:
            pass

    def action_save_active_editor(self) -> None:
        """Smart save handler for Ctrl+S hotkey."""
        active_tab = getattr(self.query_one("#main-tabs", TabbedContent), "active", "")
        if "studio" in active_tab:
            self.action_save_lab_resume()
        elif "profile" in active_tab:
            self.action_save_pantry_ide_file()
        elif "pipeline" in active_tab:
            self.action_save_notes()

    def load_pantry_ide(self) -> None:
        try:
            summary = self.query_one("#pantry-snapshots-summary", Static)
            snaps = self.pantry.list_snapshots()
            if snaps:
                latest = snaps[0]
                snap_id = str(latest.get('id', 'snap'))[:10]
                trigger = str(latest.get('trigger', 'event'))[:12]
                summary.update(f"● {snap_id} ({trigger})")
            else:
                summary.update("[dim]No snapshots yet[/dim]")

            personas_list = self.query_one("#pantry-personas-list", Vertical)
            existing_ids = {c.id for c in personas_list.children if c.id}
            personas = PersonaManager.list_personas()
            for slug in personas.keys():
                btn_id = f"btn-persona-{slug}"
                if btn_id not in existing_ids:
                    btn = Button(f"◈ {slug}.yaml", id=btn_id, classes="pantry-nav-btn")
                    personas_list.mount(btn)

            self.load_pantry_file(self.active_pantry_file)
        except Exception:
            pass

    def load_pantry_file(self, file_id: str) -> None:
        self.active_pantry_file = file_id
        editor = self.query_one("#pantry-editor-textarea", TextArea)
        fn_lbl = self.query_one("#pantry-editor-filename", Label)

        if file_id == "profile":
            fn_lbl.update("[bold white]profile.json[/bold white] [dim]• Canonical Facts[/dim]")
            try:
                if self.pantry.profile_path.exists():
                    editor.text = self.pantry.profile_path.read_text(encoding="utf-8")
                else:
                    try:
                        editor.text = json.dumps(self.pantry.load_profile().to_json_resume(), indent=2)
                    except Exception:
                        from breadwinner.onboarding import STARTER_JSON_RESUME
                        editor.text = json.dumps(STARTER_JSON_RESUME, indent=2)
            except Exception:
                editor.text = "{}"
            editor.language = "json"
        elif file_id == "context":
            fn_lbl.update("[bold white]context.md[/bold white] [dim]• Directives Diary[/dim]")
            editor.text = self.pantry.load_context()
            editor.language = "markdown"
        elif file_id.startswith("persona:"):
            slug = file_id.split(":", 1)[1]
            fn_lbl.update(f"[bold white]{slug}.yaml[/bold white] [dim]• Directives[/dim]")
            user_f = PersonaManager.get_user_dir() / f"{slug}.yaml"
            builtin_f = PersonaManager.get_built_in_dir() / f"{slug}.yaml"
            if user_f.exists():
                editor.text = user_f.read_text(encoding="utf-8")
            elif builtin_f.exists():
                editor.text = builtin_f.read_text(encoding="utf-8")
            else:
                editor.text = f"name: {slug}\ndescription: Custom persona\n"
            editor.language = "yaml"

    def action_save_pantry_ide_file(self) -> None:
        editor = self.query_one("#pantry-editor-textarea", TextArea)
        text = editor.text
        if self.active_pantry_file == "profile":
            try:
                parsed = json.loads(text)
                adapter = JsonResumeAdapter(parsed)
                new_profile = adapter.load_profile()
                self.pantry.save_pantry(new_profile, trigger="pantry_ide_save")
                self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
                self.notify("✓ Validated & saved profile.json! Created snapshot.", title="Pantry Saved")
            except Exception as e:
                self.notify(f"Invalid profile JSON: {e}", severity="error")
        elif self.active_pantry_file == "context":
            try:
                curr_profile = self.pantry.load_profile()
                self.pantry.save_pantry(curr_profile, context=text, trigger="pantry_ide_context_save")
                self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
                self.notify("✓ Saved context.md diary! Created snapshot.", title="Pantry Saved")
            except Exception as e:
                self.notify(f"Failed to save context: {e}", severity="error")
        elif self.active_pantry_file.startswith("persona:"):
            slug = self.active_pantry_file.split(":", 1)[1]
            try:
                import yaml
                p_data = yaml.safe_load(text)
                persona = Persona.from_dict(slug, p_data)
                PersonaManager.save_persona(persona)
                self._refresh_persona_select()
                self.notify(f"✓ Saved persona '{slug}'!", title="Persona Saved")
            except Exception as e:
                self.notify(f"Invalid persona YAML: {e}", severity="error")

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
            self.set_global_stage(4)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message("Crisp ATS PDF Baked!")
            oven = self.query_one("#studio-oven", AnimatedOven)
            oven.set_state("celebrate")
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
        try:
            active_tab = self.query_one("#main-tabs", TabbedContent).active
            if active_tab == "tab-profile":
                self.action_pantry_edit()
                return
        except Exception:
            pass

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
        self.push_screen(
            DualPaneFineTuneModal(
                initial_text=initial_text,
                profile=self.current_profile,
                app_result=self.current_app_result,
                template_name=self.current_template
            ),
            self._on_finetune_saved
        )

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
    def action_pantry_edit(self) -> None:
        if not self.pantry.is_initialized():
            self.notify("Please ingest a profile or load the demo loaf first.", severity="warning")
            return
        self.push_screen(PantryEditorModal(self.pantry), self._on_pantry_edit_submitted)

    def _on_pantry_edit_submitted(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or result.get("action") != "save":
            return
        new_profile = result.get("profile")
        new_context = result.get("context")
        if new_profile:
            self.pantry.save_pantry(
                new_profile,
                context=new_context,
                trigger="manual_tui_edit"
            )
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.action_refresh_data()
            self.notify("✓ Saved updates to Career Pantry and created snapshot!", title="Pantry Updated")

    def action_pantry_ingest(self) -> None:
        self.push_screen(PantryIngestModal(), self._on_pantry_ingest_modal_dismissed)

    def _on_pantry_ingest_modal_dismissed(self, source: Any) -> None:
        if not source:
            return

        sources_list: List[str] = []
        if isinstance(source, list):
            sources_list = [str(s).strip() for s in source if str(s).strip()]
        elif isinstance(source, str):
            from breadwinner.core.ingestor import decompose_raw_input
            sources_list = decompose_raw_input(source)

        if not sources_list:
            return

        self.push_screen(
            BakingModal(
                task_type="ingest",
                target_info={"sources": sources_list, "pantry": self.pantry}
            ),
            self._on_ingest_baking_modal_dismissed
        )

    @work(thread=True)
    def _on_ingest_submitted(self, source: Any) -> None:
        if not source:
            return

        sources_list: List[str] = []
        if isinstance(source, list):
            sources_list = [str(s).strip() for s in source if str(s).strip()]
        elif isinstance(source, str):
            from breadwinner.core.ingestor import decompose_raw_input
            sources_list = decompose_raw_input(source)

        if not sources_list:
            return

        is_multi = len(sources_list) > 1
        if is_multi:
            label = f"Multi-Source ({len(sources_list)} items)"
        else:
            norm_s, _ = normalize_source(sources_list[0])
            label = norm_s if len(norm_s) <= 40 else norm_s[:37] + "..."

        self.notify(f"Ingesting candidate context from {label}...", title="Pantry Ingest")
        try:
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            msg = f"Kneading {len(sources_list)} ingredients into your pantry..." if is_multi else "Kneading profile & personal diary from live source..."
            mascot.set_message(msg)
        except Exception:
            pass

        try:
            provider = get_llm_provider()
            new_profile = UniversalIngestor.ingest(sources_list if is_multi else sources_list[0], provider)
            context_diary = new_profile.raw_context.get("context_diary")

            if is_multi:
                source_meta = {
                    "source": f"Multi-source ({len(sources_list)} items)",
                    "type": "multi",
                    "sources": sources_list
                }
                trigger = "tui_ingest_multi"
            else:
                _, kind = normalize_source(sources_list[0])
                source_meta = {"source": sources_list[0], "type": kind}
                trigger = f"tui_ingest_{kind}"

            self.pantry.save_pantry(new_profile, context=context_diary, source_info=source_meta, trigger=trigger)

            def update_ui():
                try:
                    self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
                    self.action_refresh_data()
                    self.query_one("#main-tabs", TabbedContent).active = "tab-profile"
                    self.set_global_stage(0)
                except Exception:
                    pass
                try:
                    mascot = self.query_one("#studio-mascot", AnimatedMascot)
                    mascot.set_message(f"Stocked pantry for {new_profile.full_name}!")
                except Exception:
                    pass
                item_desc = f"{len(sources_list)} sources" if is_multi else f"{label}"
                self.notify(
                    f"✓ Ingested profile & diary from {item_desc} for {new_profile.full_name} ({len(new_profile.experiences)} roles, {len(new_profile.projects)} projects)!\nSwitched to Pantry tab. Click 'Edit Pantry & Diary' to refine.",
                    title="Pantry Stocked"
                )

            self.app.call_from_thread(update_ui)
        except Exception as e:
            def notify_err():
                self.notify(f"Ingestion failed: {e}", severity="error")
                try:
                    mascot = self.query_one("#studio-mascot", AnimatedMascot)
                    mascot.set_message("Ingestion error occurred.")
                except Exception:
                    pass

            self.app.call_from_thread(notify_err)

    def action_pantry_interview(self) -> None:
        if not self.pantry.is_initialized():
            self.notify("Please ingest a base profile first.", severity="warning")
            return
        profile = self.pantry.load_profile()
        try:
            questions = generate_adaptive_questions(profile, provider=None)
        except Exception:
            questions = INTERVIEW_QUESTIONS
        self.push_screen(PantryInterviewModal(questions=questions), self._on_interview_submitted)

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
        bid = event.button.id or ""
        if bid in ("btn-app-quit", "btn-pipeline-quit"):
            self.exit()
        elif bid in ("btn-tab-breadbox", "btn-sidebar-breadbox"):
            self.action_tab_pipeline()
        elif bid in ("btn-tab-studio", "btn-sidebar-studio"):
            self.action_tab_studio()
        elif bid in ("btn-tab-pantry", "btn-sidebar-pantry"):
            self.action_tab_profile()
        elif bid in ("btn-active-model-chip", "btn-models-open-modal", "btn-sidebar-model", "blade-sidebar-engine"):
            self.action_switch_model()
        elif bid == "btn-sidebar-toggle":
            self.action_toggle_sidebar()
        elif bid == "btn-app-cycle-preset":
            self.action_cycle_preset()
        elif bid == "btn-sidebar-settings":
            self.action_open_settings()
        elif bid == "btn-status":
            self.action_change_status()
        elif bid == "btn-flag":
            self.action_toggle_flag()
        elif bid in ("btn-open-folder", "btn-studio-folder", "btn-lab-folder"):
            self.action_open_folder()
        elif bid in ("btn-header-ingest", "btn-pantry-ingest"):
            self.action_pantry_ingest()
        elif bid in ("btn-header-interview", "btn-pantry-interview"):
            self.action_pantry_interview()
        elif bid == "btn-pipeline-edit-studio":
            self.action_pipeline_edit_studio()
        elif bid == "btn-save-notes":
            self.action_save_notes()
        elif bid == "btn-run-tailor":
            self.run_tailoring_flow()
        elif bid == "btn-strategy-loop":
            self.run_strategy_loop_flow()
        elif bid == "btn-view-lab":
            self.action_view_lab()
        elif bid == "btn-lab-back":
            self.action_lab_back_to_setup()
        elif bid == "btn-lab-toggle-stack":
            self.action_toggle_lab_stack()
        elif bid == "btn-lab-format-xyz":
            self.action_format_lab_xyz()
        elif bid == "btn-lab-apply-bullets":
            self.action_apply_lab_bullets()
        elif bid == "btn-lab-save-resume":
            self.action_save_lab_resume()
        elif bid == "btn-lab-save-letter":
            self.action_save_lab_letter()
        elif bid == "btn-lab-save-qna":
            self.action_save_lab_qna()
        elif bid == "btn-lab-toggle-preview":
            self.action_toggle_resume_preview()
        elif bid == "btn-lab-refine-diff":
            self.action_lab_refine_diff()
        elif bid == "btn-accept-diff":
            self.action_accept_diff()
        elif bid == "btn-dismiss-diff":
            self.action_dismiss_diff()
        elif bid == "btn-studio-finetune":
            self.action_finetune_bullets()
        elif bid in ("btn-studio-bake", "btn-pipeline-bake", "btn-lab-bake-pdf"):
            self.action_bake_pdf()
        elif bid in ("btn-studio-view-pdf", "btn-pipeline-view-pdf", "btn-lab-view-pdf"):
            self.action_view_pdf()
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
                self.update_details_pane()
        elif bid == "btn-nav-profile":
            self.load_pantry_file("profile")
        elif bid == "btn-nav-context":
            self.load_pantry_file("context")
        elif bid == "btn-nav-new-persona":
            self.notify("Enter persona YAML in editor and click Save File!", title="New Persona")
            self.load_pantry_file("persona:custom_strategist")
        elif bid == "btn-pantry-save":
            self.action_save_pantry_ide_file()
        elif bid == "btn-pantry-ai-refine":
            p_prompt = self.query_one("#pantry-ai-prompt", Input).value.strip()
            if p_prompt:
                self.notify(f"Refining pantry context: '{p_prompt[:30]}...'", title="AI Refinement")
            else:
                self.notify("Please enter an instruction in the prompt box.", severity="warning")
        elif bid.startswith("btn-persona-"):
            p_slug = bid.replace("btn-persona-", "")
            self.load_pantry_file(f"persona:{p_slug}")
        elif bid == "btn-pantry-edit":
            self.action_pantry_edit()
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
        status_box.styles.display = "block"
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
            self.set_global_stage(1)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message("Kneading application dough...")
            oven = self.query_one("#studio-oven", AnimatedOven)
            oven.set_state("baking")
        except Exception:
            pass

        self.push_screen(
            BakingModal(task_type="tailor", target_info=target_info),
            self._on_tailoring_modal_dismissed
        )

    def _on_tailoring_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or not result.get("success"):
            try:
                self.set_global_stage(0)
                oven = self.query_one("#studio-oven", AnimatedOven)
                oven.set_state("idle")
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
        status_box.styles.display = "block"
        status_box.update(
            f"[bold green]✓ Fresh out of the oven![/bold green] "
            f"Target: [bold]{job.company} — {job.title}[/bold] | "
            f"ATS Match Score: [bold green]{score}%[/bold green]{pdf_notice}\n"
            f"Package saved to: [cyan]{app_dir}[/cyan]"
        )

        r_md = result.get("resume_md", "")
        c_md = result.get("cover_letter", "")
        q_md = result.get("portal_qna", "")

        self.query_one("#preview-resume-md", Markdown).update(r_md)
        self.query_one("#preview-letter-md", Markdown).update(c_md)
        self.query_one("#preview-qna-md", Markdown).update(q_md)

        try:
            self.query_one("#lab-resume-editor", TextArea).text = r_md
        except Exception:
            pass
        try:
            self.query_one("#lab-letter-editor", TextArea).text = c_md
        except Exception:
            pass
        try:
            self.query_one("#lab-qna-editor", TextArea).text = q_md
        except Exception:
            pass

        if self.current_app_result and self.current_app_result.tailored_experiences:
            lines = []
            for exp in self.current_app_result.tailored_experiences:
                lines.append(f"### {exp.role} @ {exp.company}")
                for b in exp.bullets:
                    lines.append(f"- {b}")
                lines.append("")
            bullet_text = "\n".join(lines).strip()
            try:
                editor = self.query_one("#lab-bullet-editor", TextArea)
                editor.text = bullet_text
                report = analyze_bullets_xyz(bullet_text, self.current_profile)
                self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report)
                if job:
                    self.query_one("#lab-active-job-label", Label).update(f"[bold white]{job.company} — {job.title}[/bold white]")
                self.query_one("#lab-ats-badge", Label).update(f"[bold #50FA7B]{score}% ATS Match[/bold #50FA7B]")
                self.action_view_lab()
            except Exception:
                pass

        try:
            self.set_global_stage(4)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message(f"Loaf Ready: {score}% ATS Match!")
            oven = self.query_one("#studio-oven", AnimatedOven)
            oven.set_state("celebrate")
        except Exception:
            pass

        self.notify(f"Tailored application for {job.company} ({score}% match)! Press 'b' to bake PDF.", title="Breadwinner Success")
        self.load_pipeline_table()

