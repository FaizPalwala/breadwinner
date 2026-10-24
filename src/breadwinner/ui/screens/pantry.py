"""Career Pantry screen, ledger management, and interview modals for Breadwinner."""

from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import re

from textual import work, events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Label,
    Button,
    TextArea,
    Static,
    TabPane,
    TabbedContent,
    Markdown,
    Input,
    DataTable,
)

from breadwinner.config import settings
from breadwinner.core.models import CandidateProfile
from breadwinner.core.pantry import PantryManager
from breadwinner.core.portfolio import JsonResumeAdapter, get_profile_source
from breadwinner.core.persona import Persona, PersonaManager
from breadwinner.core.ingestor import (
    UniversalIngestor,
    normalize_source,
    clean_user_input_path,
    decompose_raw_input,
)
from breadwinner.core.interview import (
    INTERVIEW_QUESTIONS,
    synthesize_context,
    generate_adaptive_questions,
)
from breadwinner.core.audio import AudioTranscriber, AudioRecorder
from breadwinner.providers.factory import get_llm_provider
from breadwinner.ui.retro import AnimatedMascot, BakingModal
from breadwinner.ui.discovery import IngredientDiscoveryModal
from breadwinner.ui.audio_widgets import AudioDictationModal
from breadwinner.ui.visuals import PantryMaturityWidget
from breadwinner.ui.screens.models import PromptTextArea, VerticalEngineBlade
from breadwinner.onboarding import STARTER_JSON_RESUME


MODAL_BASE_CSS = """
    .modal-header-bar {
        height: 1;
        width: 100%;
        align: left middle;
        margin-bottom: 1;
    }
    .modal-header-title {
        width: 1fr;
        color: #ffb86c;
        text-style: bold;
    }
    Button.modal-close-btn, .modal-close-btn,
    #btn-switcher-close, #btn-settings-close, #btn-strategy-close,
    #btn-modal-close, #btn-ingest-close, #btn-interview-close,
    #btn-history-close, #btn-status-close, #btn-flag-close, #btn-close-persona-synth {
        dock: right;
        min-width: 3;
        width: 3;
        height: 1;
        border: none;
        background: transparent;
        color: #6272a4;
        padding: 0;
    }
    Button.modal-close-btn:focus, .modal-close-btn:focus,
    #btn-switcher-close:focus, #btn-settings-close:focus, #btn-strategy-close:focus,
    #btn-modal-close:focus, #btn-ingest-close:focus, #btn-interview-close:focus,
    #btn-history-close:focus, #btn-status-close:focus, #btn-flag-close:focus, #btn-close-persona-synth:focus {
        color: #ff5555;
        background: transparent;
    }
    .modal-action-bar {
        margin-top: 1;
        height: 1;
        align: right middle;
    }
    .modal-action-bar Button {
        margin-left: 1;
    }
"""


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
        width: 62;
        max-width: 68;
        min-width: 52;
        height: auto;
        max-height: 16;
    }
    #pantry-source-input {
        margin: 1 0;
    }
    """ + MODAL_BASE_CSS

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
                classes="modal-action-bar"
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
            inp.value = clean_user_input_path(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-cancel-ingest", "btn-ingest-close"):
            self.dismiss(None)
        elif event.button.id == "btn-run-ingest":
            val = self.query_one("#pantry-source-input", Input).value.strip()
            if val:
                clean = clean_user_input_path(val)
                label, kind = normalize_source(clean)
                self.dismiss(label if kind == "url" else clean)
            else:
                self.dismiss(None)
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
        width: 84;
        max-width: 90;
        min-width: 76;
        height: auto;
        max-height: 32;
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
    """ + MODAL_BASE_CSS

    def __init__(self, questions: Optional[List[Dict[str, str]]] = None):
        super().__init__()
        self.questions = questions or INTERVIEW_QUESTIONS
        self.backend_info = AudioTranscriber.detect_backend()

    def compose(self) -> ComposeResult:
        stt_status = (
            f"[dim green][»] Voice STT Engine: {self.backend_info.description}[/dim green]"
            if self.backend_info.available
            else "[dim yellow][»] Voice STT: Ready for BYOK Groq/OpenAI keys or local Whisper (Type answers directly)[/dim yellow]"
        )

        header_widgets = [
            Horizontal(
                Label("[bold yellow][§] The Baker's Interview: Discovering Your Context[/bold yellow]", classes="modal-header-title"),
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
                    Button("[»] Speak Answer (PTT)", variant="warning", id=f"btn-rec-{area_id}", classes="voice-btn"),
                    Label("[dim italic]Click to record via microphone or type directly[/dim italic]"),
                    classes="voice-bar"
                ))

        yield Vertical(
            *header_widgets,
            VerticalScroll(*q_widgets),
            Horizontal(
                Button("Synthesize Directives (context.md)", variant="success", id="btn-save-interview"),
                Button("Cancel", variant="error", id="btn-cancel-interview"),
                classes="modal-action-bar"
            ),
            id="interview-dialog"
        )

    def on_mount(self) -> None:
        try:
            area_id = "int-q1" if len(self.questions) == 3 else f"int-q-{self.questions[0].get('id', 'q0')}"
            self.query_one(f"#{area_id}", TextArea).focus()
        except Exception:
            pass

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
            def on_captured(transcription: Optional[str]):
                if transcription:
                    try:
                        area = self.query_one(f"#{target_area_id}", TextArea)
                        existing = area.text.strip()
                        area.text = f"{existing} {transcription}".strip() if existing else transcription
                        self.notify(f"✓ Transcribed: '{transcription[:40]}...'", title="Speech Captured")
                    except Exception:
                        pass
            self.app.push_screen(AudioDictationModal(prompt_title="Speak Interview Answer"), on_captured)


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
        width: 84;
        max-width: 90;
        min-width: 76;
        height: auto;
        max-height: 24;
    }
    #history-table {
        height: 10;
        min-height: 8;
        margin: 1 0;
    }
    """ + MODAL_BASE_CSS

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
                classes="modal-action-bar"
            ),
            id="history-dialog"
        )

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Snapshot ID", "Timestamp", "Trigger Event")
        for s in self.snapshots:
            table.add_row(s.get("id", ""), s.get("timestamp", ""), s.get("trigger", ""), key=s.get("id"))
        try:
            table.focus()
        except Exception:
            pass

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
                yield Label("[bold #f4a261][§] Career Pantry & Personal Context Diary Studio[/bold #f4a261]", classes="modal-header-title")
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


class PantryScreenMixin:
    """Mixin containing UI composition and action methods for the Context Pantry tab."""

    def compose_pantry_tab(self) -> ComposeResult:
        """Compose the Context Pantry tab pane."""
        with TabPane("Context Pantry", id="tab-profile"):
            with Horizontal(id="pantry-ide-split"):
                with VerticalScroll(id="pantry-ide-nav"):
                    yield Label("[bold #A89F91]CANONICAL LEDGERS[/bold #A89F91]", classes="pantry-nav-sec-label")
                    yield Button("▤ profile.yaml (Facts)", id="btn-nav-profile", classes="pantry-nav-btn")
                    yield Button("§ context.md (Diary)", id="btn-nav-context", classes="pantry-nav-btn")
                    yield Label("[bold #A89F91]DEEP DOSSIER[/bold #A89F91]", classes="pantry-nav-sec-label")
                    yield Vertical(id="pantry-dossier-list")
                    yield Label("[bold #A89F91]PERSONAS[/bold #A89F91]", classes="pantry-nav-sec-label")
                    yield Vertical(id="pantry-personas-list")
                    yield Button("+ New Persona", id="btn-nav-new-persona", classes="pantry-nav-btn")
                    yield Label("[bold #A89F91]SNAPSHOT DAG[/bold #A89F91]", classes="pantry-nav-sec-label")
                    yield Static("", id="pantry-snapshots-summary")
                    yield Button("Inspect History (h)", id="btn-pantry-history", classes="pantry-nav-btn")
                    yield Label("[bold #A89F91]QUICK ACTIONS[/bold #A89F91]", classes="pantry-nav-sec-label")
                    yield Button("+ Ingest Source (i)", id="btn-pantry-ingest", classes="pantry-nav-btn")
                    yield Button("§ Interview (m)", id="btn-pantry-interview", classes="pantry-nav-btn")
                    yield Button("Sync Portfolio (y)", id="btn-pantry-sync", classes="pantry-nav-btn")
                    yield Button("Edit Form (e)", id="btn-pantry-edit", classes="pantry-nav-btn")
                with Vertical(id="pantry-ide-main"):
                    with Horizontal(id="pantry-editor-header"):
                        yield Label("[bold white]profile.yaml[/bold white] [dim]• Canonical Facts[/dim]", id="pantry-editor-filename")
                        yield Label("[bold #50FA7B]● Validated & Snapshot Protected[/bold #50FA7B]", id="pantry-editor-status")
                        yield Button("✓ Save File (Ctrl+S)", variant="success", id="btn-pantry-save")
                    yield TextArea("", id="pantry-editor-textarea")
                    yield Markdown(self.get_profile_markdown(), id="profile-md")
                    with Horizontal(id="pantry-ai-bar"):
                        with Horizontal(id="pantry-prompt-box"):
                            yield PromptTextArea("", id="pantry-ai-prompt", language=None)
                            yield Button("✦ Refine & Diff", id="btn-pantry-ai-refine")

    def load_pantry_ide(self) -> None:
        try:
            try:
                prof = self.pantry.load_profile()
                self.query_one("#pantry-maturity-widget", PantryMaturityWidget).update_maturity(
                    exp_count=len(prof.experiences),
                    proj_count=len(prof.projects),
                    facts_count=len(prof.skills)
                )
            except Exception:
                pass

            summary = self.query_one("#pantry-snapshots-summary", Static)
            snaps = self.pantry.list_snapshots()
            if snaps:
                latest = snaps[0]
                snap_id = str(latest.get("id", "snap"))[:10]
                trigger = str(latest.get("trigger", "event"))[:12]
                summary.update(f"● {snap_id} ({trigger})")
            else:
                summary.update("[dim]No snapshots yet[/dim]")

            dossier_list = self.query_one("#pantry-dossier-list", Vertical)
            existing_d_ids = {c.id for c in dossier_list.children if c.id}
            dossier_files = self.pantry.list_dossier_files()
            if not dossier_files and not existing_d_ids:
                dossier_list.mount(Label("[dim italic]No dossier docs yet[/dim italic]", id="lbl-empty-dossier"))
            else:
                for df in dossier_files:
                    d_name = df.get("name", "").strip()
                    if not d_name or d_name.startswith("."):
                        continue
                    rel = df["rel_path"]
                    safe_id = f"btn-dossier-{rel.replace('/', '__').replace('.', '_')}"
                    if safe_id not in existing_d_ids:
                        try:
                            self.query_one("#lbl-empty-dossier").remove()
                        except Exception:
                            pass
                        btn = Button(f"▣ {d_name}", id=safe_id, classes="pantry-nav-btn")
                        btn._dossier_rel = rel
                        dossier_list.mount(btn)

            personas_list = self.query_one("#pantry-personas-list", Vertical)
            existing_ids = {c.id for c in personas_list.children if c.id}
            personas = PersonaManager.list_personas()
            for slug in personas.keys():
                btn_id = f"btn-persona-{slug}"
                if btn_id not in existing_ids:
                    btn = Button(f"◈ {slug}.yaml", id=btn_id, classes="pantry-nav-btn")
                    personas_list.mount(btn)

            self.load_pantry_file(getattr(self, "active_pantry_file", "profile"))
        except Exception:
            pass

    def refresh_pantry_ide(self) -> None:
        """Alias for reloading pantry IDE data."""
        self.load_pantry_ide()

    def load_pantry_file(self, file_id: str) -> None:
        self.active_pantry_file = file_id
        editor = self.query_one("#pantry-editor-textarea", TextArea)
        fn_lbl = self.query_one("#pantry-editor-filename", Label)

        if file_id == "profile":
            fn_lbl.update("[bold white]profile.yaml[/bold white] [dim]• Canonical Facts[/dim]")
            try:
                editor.text = self.pantry.load_profile_yaml()
            except Exception:
                editor.text = ""
            editor.language = "yaml"
        elif file_id == "context":
            fn_lbl.update("[bold white]context.md[/bold white] [dim]• Directives Diary[/dim]")
            editor.text = self.pantry.load_context()
            editor.language = "markdown"
        elif file_id.startswith("dossier:"):
            rel = file_id.split(":", 1)[1]
            fn_lbl.update(f"[bold white]{Path(rel).name}[/bold white] [dim]• Deep Dossier[/dim]")
            try:
                editor.text = self.pantry.load_dossier_file(rel)
            except Exception:
                editor.text = ""
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
                new_profile = self.pantry.save_profile_yaml(text, trigger="pantry_ide_save")
                self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
                self.notify("✓ Validated & saved profile.yaml and synced profile.json! Created snapshot.", title="Pantry Saved")
            except Exception as e:
                self.notify(f"Invalid profile YAML: {e}", severity="error")
        elif self.active_pantry_file == "context":
            try:
                curr_profile = self.pantry.load_profile()
                self.pantry.save_pantry(curr_profile, context=text, trigger="pantry_ide_context_save")
                self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
                self.notify("✓ Saved context.md diary! Created snapshot.", title="Pantry Saved")
            except Exception as e:
                self.notify(f"Failed to save context: {e}", severity="error")
        elif self.active_pantry_file.startswith("dossier:"):
            rel = self.active_pantry_file.split(":", 1)[1]
            try:
                self.pantry.save_dossier_file(rel, text, trigger=f"dossier_ide_save_{Path(rel).stem}")
                self.refresh_pantry_ide()
                self.notify(f"✓ Saved {Path(rel).name}! Created snapshot.", title="Dossier Saved")
            except Exception as e:
                self.notify(f"Failed to save dossier file: {e}", severity="error")
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

    @work(thread=True)
    def action_pantry_ai_refine(self) -> None:
        p_prompt = self.query_one("#pantry-ai-prompt", TextArea).text.strip()
        if not p_prompt:
            self.notify("Please enter an instruction in the prompt box.", severity="warning")
            return
        editor = self.query_one("#pantry-editor-textarea", TextArea)
        current_text = editor.text
        active_file = self.active_pantry_file

        self.notify(f"Refining {active_file} with AI...", title="AI Refinement")
        try:
            provider = get_llm_provider()
            sys_prompt = (
                "You are Breadwinner's Career Strategy Refiner. "
                "The user wants to refine their career document according to their instruction. "
                "RULES:\n"
                "1. Strictly preserve all existing verified metrics, company names, dates, and titles.\n"
                "2. Apply the Google XYZ formula for work bullets.\n"
                "3. Return ONLY the complete updated file content in its exact format (YAML or Markdown). Do NOT wrap in markdown code blocks."
            )
            user_prompt = f"DOCUMENT ({active_file}):\n{current_text}\n\nUSER INSTRUCTION:\n{p_prompt}"
            refined = provider.generate_text(sys_prompt, user_prompt, temperature=0.0).strip()
            if refined.startswith("```yaml") or refined.startswith("```markdown") or refined.startswith("```"):
                refined = re.sub(r"^```[a-zA-Z]*\n", "", refined)
                refined = re.sub(r"\n```$", "", refined)

            def apply_refinement():
                editor.text = refined
                self.notify(f"✓ AI Refinement applied to {active_file}! Press Ctrl+S to save.", title="Refinement Applied")

            self.app.call_from_thread(apply_refinement)
        except Exception as e:
            err_msg = str(e)
            self.app.call_from_thread(lambda: self.notify(f"AI Refinement failed: {err_msg}", severity="error"))

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
            sources_list = decompose_raw_input(source)

        if not sources_list:
            return

        self.push_screen(
            IngredientDiscoveryModal(sources=sources_list),
            self._on_ingredient_discovery_dismissed
        )

    def _on_ingredient_discovery_dismissed(self, selected_sources: Optional[List[str]]) -> None:
        if not selected_sources:
            return
        self.push_screen(
            BakingModal(
                task_type="ingest",
                target_info={
                    "sources": selected_sources,
                    "pantry": self.pantry,
                    "provider": settings.breadwinner_llm_provider
                }
            ),
            self._on_ingest_baking_modal_dismissed
        )

    def _on_ingest_baking_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result:
            return
        if result.get("action") == "change_model":
            self._pending_bake_retry = {
                "task_type": "ingest",
                "target_info": result.get("target_info") or {"sources": result.get("sources", []), "pantry": self.pantry}
            }
            self.action_switch_model()
            return
        if not result.get("success"):
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

    @work(thread=True)
    def _on_ingest_submitted(self, source: Any) -> None:
        if not source:
            return

        sources_list: List[str] = []
        if isinstance(source, list):
            sources_list = [str(s).strip() for s in source if str(s).strip()]
        elif isinstance(source, str):
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
            err_msg = str(e)
            def notify_err():
                self.notify(f"Ingestion failed: {err_msg}", severity="error")
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
        provider = None
        try:
            provider = get_llm_provider()
        except Exception:
            pass

        dossier_text = None
        if hasattr(self.pantry, "get_dossier_summary"):
            try:
                dossier_text = self.pantry.get_dossier_summary()
            except Exception:
                pass

        try:
            questions = generate_adaptive_questions(profile, provider=provider, dossier_context=dossier_text)
        except Exception:
            questions = INTERVIEW_QUESTIONS

        if not questions:
            self.notify("✓ Verified all experience & project details. No clarification needed!", title="Pantry Verified")
            return

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

    def get_profile_markdown(self) -> str:
        """Render markdown representation of candidate profile for UI preview."""
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

    def handle_pantry_button(self, bid: str, event: Button.Pressed) -> bool:
        """Route Pantry-specific button events."""
        if bid in ("btn-header-ingest", "btn-pantry-ingest"):
            self.action_pantry_ingest()
            return True
        if bid in ("btn-header-interview", "btn-pantry-interview"):
            self.action_pantry_interview()
            return True
        if bid == "btn-nav-profile":
            self.load_pantry_file("profile")
            return True
        if bid == "btn-nav-context":
            self.load_pantry_file("context")
            return True
        if bid == "btn-nav-new-persona":
            self.notify("Enter persona YAML in editor and click Save File!", title="New Persona")
            self.load_pantry_file("persona:custom_strategist")
            return True
        if bid == "btn-pantry-save":
            self.action_save_pantry_ide_file()
            return True
        if bid == "btn-pantry-ai-refine":
            self.action_pantry_ai_refine()
            return True
        if bid.startswith("btn-persona-"):
            p_slug = bid.replace("btn-persona-", "")
            self.load_pantry_file(f"persona:{p_slug}")
            return True
        if bid.startswith("btn-dossier-"):
            rel = getattr(event.button, "_dossier_rel", None)
            if not rel:
                raw_slug = bid.replace("btn-dossier-", "")
                rel = raw_slug.replace("__", "/")
                if not rel.endswith(".md"):
                    parts = rel.rsplit("_", 1)
                    rel = f"{parts[0]}.{parts[1]}" if len(parts) == 2 else f"{rel}.md"
            self.load_pantry_file(f"dossier:{rel}")
            return True
        if bid == "btn-pantry-edit":
            self.action_pantry_edit()
            return True
        if bid == "btn-pantry-sync":
            self.action_pantry_sync()
            return True
        if bid == "btn-pantry-history":
            self.action_pantry_history()
            return True
        return False

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
            demo_profile = JsonResumeAdapter(json.loads(STARTER_JSON_RESUME)).load_profile()
            self.pantry.save_pantry(
                demo_profile,
                source_info={"type": "demo", "source": "starter_loaf"},
                trigger="demo_loaf",
            )
            self.action_refresh_data()
            try:
                mascot = self.query_one("#studio-mascot", AnimatedMascot)
                mascot.set_message("Fresh Demo Loaf in pantry!")
            except Exception:
                pass
            self.notify("✓ Fresh Demo Loaf loaded! Explore the Studio and bake a test resume.", title="Pantry Stocked")
        elif action == "import":
            prov = str(result.get("provider") or settings.breadwinner_llm_provider).upper()
            try:
                chip_text = self.get_active_model_chip_text()
                self.query_one("#btn-active-model-chip", Button).label = chip_text
                self.query_one("#btn-sidebar-model", Button).label = chip_text
                self.query_one("#blade-sidebar-engine", VerticalEngineBlade).update_provider(prov)
            except Exception:
                pass
            sources = result.get("sources")
            source = result.get("source")
            sources_to_ingest = sources if sources else [source] if source else []
            if sources_to_ingest:
                self.push_screen(
                    IngredientDiscoveryModal(sources=sources_to_ingest),
                    self._on_ingredient_discovery_dismissed,
                )

    def _on_ingredient_discovery_dismissed(self, selected_sources: Optional[List[str]]) -> None:
        if not selected_sources:
            return
        self.push_screen(
            BakingModal(
                task_type="ingest",
                target_info={
                    "sources": selected_sources,
                    "pantry": self.pantry,
                    "provider": settings.breadwinner_llm_provider,
                },
            ),
            self._on_ingest_baking_modal_dismissed,
        )

    def _on_ingest_baking_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result:
            return
        if result.get("action") == "change_model":
            self._pending_bake_retry = {
                "task_type": "ingest",
                "target_info": result.get("target_info") or {"sources": result.get("sources", []), "pantry": self.pantry},
            }
            self.action_switch_model()
            return
        if not result.get("success"):
            return

        profile = result.get("profile")
        if profile:
            self.pantry.save_pantry(profile, trigger="baking_modal_completion")
        else:
            profile = self.pantry.load_profile()

        try:
            self.query_one("#profile-md", Markdown).update(self.get_profile_markdown())
            self.action_refresh_data()
        except Exception:
            pass

        try:
            self.query_one("#main-tabs", TabbedContent).active = "tab-profile"
            self.set_global_stage(0)
        except Exception:
            pass

        try:
            self.query_one("#active-badge", Label).update(self.get_active_badge_text())
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message(f"Stocked pantry for {profile.full_name}!")
        except Exception:
            pass

        self.notify(
            f"✓ Stocked pantry for {profile.full_name} ({len(profile.experiences)} roles, {len(profile.projects)} projects)!",
            title="Pantry Stocked",
        )

        try:
            self.action_pantry_interview()
        except Exception:
            pass


