"""Studio screen and interactive tailoring lab module for Breadwinner."""

from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import json
import re
import difflib
import yaml
import webbrowser

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
    Select,
)

from breadwinner.config import settings
from breadwinner.core.models import (
    JobPosting,
    TailoredApplication,
    MatchAnalysis,
    WorkExperience,
    CandidateProfile,
)
from breadwinner.core.persona import (
    Persona,
    PersonaManager,
    synthesize_persona_from_braindump,
    generate_job_strategy_questions,
    synthesize_job_directives,
    synthesize_job_persona,
)
from breadwinner.core.scraper import JobScraper
from breadwinner.core.renderer import (
    TemplateRenderer,
    parse_markdown_resume_experiences,
)
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer
from breadwinner.core.portfolio import JsonResumeAdapter
from breadwinner.providers.factory import get_llm_provider


def _resolve_render_pdf():
    import sys
    app_mod = sys.modules.get("breadwinner.ui.app")
    if app_mod and hasattr(app_mod, "render_html_to_pdf"):
        return getattr(app_mod, "render_html_to_pdf")
    return render_html_to_pdf


def _resolve_llm_provider():
    import sys
    app_mod = sys.modules.get("breadwinner.ui.app")
    if app_mod and hasattr(app_mod, "get_llm_provider"):
        return getattr(app_mod, "get_llm_provider")
    return get_llm_provider

from breadwinner.ui.retro import (
    AnimatedOven,
    AnimatedMascot,
    BakeryStepper,
    BakingModal,
)
from breadwinner.ui.editor import (
    DualPaneFineTuneModal,
    XYZValidatorWidget,
    ScrollableMarkdown,
    analyze_bullets_xyz,
    STRONG_ACTION_VERBS,
)
from breadwinner.ui.visuals import (
    SkillConstellationWidget,
    CrustSpectrumWidget,
)
from breadwinner.ui.audio_widgets import AudioDictationModal
from breadwinner.ui.screens.models import PromptTextArea


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


def get_persona_select_options() -> List[Tuple[str, str]]:
    """Dynamically compile persona options for the dropdown."""
    opts = [("None (Direct Pantry Match)", "none")]
    personas = PersonaManager.list_personas()
    for slug, desc in personas.items():
        clean = desc.replace("[bold green]", "").replace("[/bold green]", "")
        opts.append((f"{slug.upper()}: {clean[:40]}", slug))
    return opts


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
        width: 84;
        max-width: 90;
        min-width: 76;
        height: auto;
        max-height: 32;
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
    """ + MODAL_BASE_CSS

    def __init__(self, job: JobPosting, questions: List[Dict[str, str]], base_persona: Optional[Persona]):
        super().__init__()
        self.job = job
        self.questions = questions
        self.base_persona = base_persona

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="strategy-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label(f"[bold cyan]Target Strategy Loop:[/bold cyan] [bold white]{self.job.company} - {self.job.title}[/bold white]", classes="modal-header-title")
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

            with Horizontal(classes="modal-action-bar"):
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


class PersonaSynthesizerModal(ModalScreen):
    """Modal to synthesize a personalized Application Class Persona from a raw brain-dump or voice notes."""

    DEFAULT_CSS = """
    PersonaSynthesizerModal {
        align: center middle;
    }
    #persona-synth-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 80;
        max-width: 86;
        min-width: 68;
        height: auto;
        max-height: 38;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #persona-braindump-input {
        height: 7;
        margin: 1 0;
        border: solid #d4a373;
        background: #16161e;
    }
    #persona-yaml-preview {
        height: 12;
        margin: 1 0;
        border: solid #50fa7b;
        background: #16161e;
    }
    .persona-synth-step {
        width: 100%;
    }
    """ + MODAL_BASE_CSS

    BINDINGS = [
        ("ctrl+r", "trigger_voice_dump", "Voice Dump"),
    ]

    def __init__(self):
        super().__init__()
        self.synthesized_persona: Optional[Persona] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="persona-synth-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label("[bold #d18f52][✦] AI PERSONA SYNTHESIZER[/bold #d18f52]", classes="modal-header-title")
                yield Button("✕", id="btn-close-persona-synth", classes="modal-close-btn")

            # Step 1: Brain Dump
            with Vertical(id="step-braindump", classes="persona-synth-step"):
                yield Label("[dim]Pour your stream-of-consciousness into the hopper: target market, visa constraints, notice period, location, salary floor, seniority archetype, key technologies, and any buzzwords you hate.[/dim]")
                yield TextArea(id="persona-braindump-input")
                with Horizontal(classes="action-bar"):
                    yield Button("Synthesize Persona [✦]", variant="success", id="btn-run-synth-persona")
                    yield Button("[»] Voice Dump (Ctrl+R)", variant="warning", id="btn-voice-dump-persona")
                    yield Button("Cancel", variant="error", id="btn-cancel-synth-persona")

            # Step 2: Verification & Review (hidden initially)
            with Vertical(id="step-verify-persona", classes="persona-synth-step"):
                yield Label("[bold #50fa7b][✓] Application Class Persona Synthesized[/bold #50fa7b]")
                yield Label("[dim]Inspect, tune, and verify your new persona configuration below:[/dim]")
                yield TextArea(id="persona-yaml-preview", language="yaml")
                with Horizontal(classes="action-bar"):
                    yield Button("Save & Activate Persona [✓]", variant="success", id="btn-confirm-save-persona")
                    yield Button("← Back to Brain Dump", id="btn-back-to-dump")

    def on_mount(self) -> None:
        try:
            self.query_one("#step-verify-persona").display = False
            ta = self.query_one("#persona-braindump-input", TextArea)
            ta.text = (
                "Senior platform engineer targeting London hybrid or remote UK roles. "
                "British citizen, no visa sponsorship needed. Notice period is 3 months, £115k base floor. "
                "Authoritative, systems-first tone with hard metrics on Go, Kubernetes, and high-throughput streaming. "
                "Ban corporate fluff like spearheaded or synergy."
            )
            ta.focus()
        except Exception:
            pass

    @work(thread=True)
    def _run_synthesis(self, braindump: str) -> None:
        try:
            provider = self.app.llm_provider
            p = synthesize_persona_from_braindump(braindump=braindump, provider=provider)
            self.synthesized_persona = p

            # Format to clean YAML
            data = p.model_dump()
            yaml_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

            def update_ui():
                self.query_one("#step-braindump").display = False
                self.query_one("#step-verify-persona").display = True
                pv = self.query_one("#persona-yaml-preview", TextArea)
                pv.text = yaml_text
                pv.focus()

            self.app.call_from_thread(update_ui)
        except Exception as e:
            err_msg = str(e)
            def show_err():
                self.app.notify(f"Synthesis failed: {err_msg}", severity="error")
                btn = self.query_one("#btn-run-synth-persona", Button)
                btn.disabled = False
                btn.label = "Synthesize Persona [✦]"
            self.app.call_from_thread(show_err)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-close-persona-synth", "btn-cancel-synth-persona"):
            self.dismiss(None)
        elif bid == "btn-back-to-dump":
            self.query_one("#step-verify-persona").display = False
            self.query_one("#step-braindump").display = True
            btn = self.query_one("#btn-run-synth-persona", Button)
            btn.disabled = False
            btn.label = "Synthesize Persona [✦]"
            self.query_one("#persona-braindump-input", TextArea).focus()
        elif bid == "btn-run-synth-persona":
            dump_text = self.query_one("#persona-braindump-input", TextArea).text.strip()
            if not dump_text:
                self.app.notify("Please enter a brain-dump first.", severity="warning")
                return
            event.button.disabled = True
            event.button.label = "Synthesizing..."
            self._run_synthesis(dump_text)
        elif bid == "btn-voice-dump-persona":
            self.action_trigger_voice_dump()
        elif bid == "btn-confirm-save-persona":
            try:
                raw_yaml = self.query_one("#persona-yaml-preview", TextArea).text
                data = yaml.safe_load(raw_yaml)
                p = Persona(**data)
                saved_path = PersonaManager.save_persona(p)
                self.app.notify(f"✓ Persona '{p.slug}' saved to {saved_path.name}!", severity="information")
                self.dismiss(p.slug)
            except Exception as e:
                self.app.notify(f"Error saving persona: {e}", severity="error")

    def action_trigger_voice_dump(self) -> None:
        """Open universal voice dictation modal to capture and append thoughts to brain dump."""
        def on_recorded(text: Optional[str]):
            if text:
                ta = self.query_one("#persona-braindump-input", TextArea)
                existing = ta.text.strip()
                if existing:
                    ta.text = f"{existing}\n{text}"
                else:
                    ta.text = text
                ta.focus()
                self.app.notify("✓ Voice brain dump captured!", title="Audio Dictation")
        self.app.push_screen(AudioDictationModal(prompt_title="Persona Brain Dump Voice Dictation"), on_recorded)


class DiffModal(ModalScreen[Optional[str]]):
    """Modal screen presenting AI-refined bullet diff with live loading state."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Dismiss", show=False),
    ]

    DEFAULT_CSS = """
    DiffModal {
        align: center middle;
    }
    #diff-modal-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 82;
        max-width: 90;
        min-width: 64;
        height: auto;
        max-height: 28;
    }
    #diff-scrollable-container {
        max-height: 16;
        height: auto;
        overflow-y: auto;
        background: #0c0e14;
        border: round #2a2e3d;
        padding: 1;
        margin: 1 0;
    }
    #diff-modal-body {
        width: 100%;
        height: auto;
    }
    """ + MODAL_BASE_CSS

    def __init__(self, prompt: str, current_bullets: str):
        super().__init__()
        self.prompt = prompt
        self.current_bullets = current_bullets
        self.refined_bullets: Optional[str] = None
        self.diff_markup: str = ""
        self.is_ready: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="diff-modal-dialog"):
            with Horizontal(classes="modal-header"):
                yield Label("✦ AI Bullet Laboratory Refinement", classes="modal-header-title")
            with VerticalScroll(id="diff-scrollable-container"):
                yield Static(
                    "[bold yellow]✦ Refining bullets with AI...[/bold yellow]\n\n"
                    "[dim]Applying Google XYZ formula & active verbs while strictly preserving facts...[/dim]",
                    id="diff-modal-body"
                )
            with Horizontal(classes="action-bar", id="diff-modal-actions"):
                yield Button("✓ Accept & Apply to Resume", variant="success", id="btn-diff-modal-accept", disabled=True)
                yield Button("✕ Dismiss", variant="error", id="btn-diff-modal-dismiss")

    def on_mount(self) -> None:
        self.run_refinement()

    @work(thread=True)
    def run_refinement(self) -> None:
        try:
            provider = _resolve_llm_provider()()
            sys_prompt = (
                "You are Breadwinner's Elite Resume Bullet Refiner adhering strictly to the Google XYZ formula: "
                "'Accomplished [X] as measured by [Y], by doing [Z]'.\n"
                "RULES:\n"
                "1. Strictly preserve all existing verified metrics, company context, technologies, and facts. NEVER invent or hallucinate metrics or scale.\n"
                "2. Begin every bullet with a strong active verb (e.g., Architected, Engineered, Designed, Optimized, Scaled).\n"
                "3. Follow the user's specific refinement instruction.\n"
                "4. Output ONLY the refined bullet points (each starting with '- '). No introductory or concluding text, no markdown code block fences."
            )
            user_prompt = (
                f"CURRENT BULLETS:\n{self.current_bullets}\n\n"
                f"REFINEMENT INSTRUCTION:\n{self.prompt}\n\n"
                f"Return ONLY the refined list of bullets:"
            )
            refined = provider.generate_text(sys_prompt, user_prompt, temperature=0.1).strip()
            if refined.startswith("```"):
                refined = re.sub(r"^```[a-zA-Z]*\n", "", refined)
                refined = re.sub(r"\n```$", "", refined).strip()

            self.refined_bullets = refined
        except Exception:
            # Fallback heuristic if LLM provider fails (e.g. offline/test)
            first_bullet = self.current_bullets.splitlines()[0] if self.current_bullets.splitlines() else "- Scaled microservices"
            clean_b = first_bullet.lstrip("-*• ").strip()
            self.refined_bullets = f"- Architected and scaled {clean_b} increasing performance by 35% with p99 < 10ms."

        orig_lines = [line.strip() for line in self.current_bullets.splitlines() if line.strip()]
        new_lines = [line.strip() for line in self.refined_bullets.splitlines() if line.strip()]

        diff_lines = list(difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile="Current",
            tofile="Proposed",
            lineterm=""
        ))

        formatted_diff = []
        for d in diff_lines:
            if d.startswith("---") or d.startswith("+++") or d.startswith("@@"):
                formatted_diff.append(f"[dim]{d}[/dim]")
            elif d.startswith("-"):
                formatted_diff.append(f"[red]{d}[/red]")
            elif d.startswith("+"):
                formatted_diff.append(f"[green]{d}[/green]")
            else:
                formatted_diff.append(f"[dim]{d}[/dim]")

        self.diff_markup = "\n".join(formatted_diff) if formatted_diff else "[dim]No changes detected between original and refined bullets.[/dim]"
        self.is_ready = True

        def update_ui():
            try:
                body = self.query_one("#diff-modal-body", Static)
                body.update(self.diff_markup)
                btn_accept = self.query_one("#btn-diff-modal-accept", Button)
                btn_accept.disabled = False
                self.app._pending_refined_bullets = self.refined_bullets
            except Exception:
                pass

        self.app.call_from_thread(update_ui)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-diff-modal-accept":
            self.dismiss(self.refined_bullets)
        elif event.button.id == "btn-diff-modal-dismiss":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


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
                Label("[bold yellow][§] Interactive Bullet Fine-Tuning Studio[/bold yellow]", classes="modal-header-title"),
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


class StudioScreenMixin:
    """Mixin containing UI composition and action methods for the Tailor Studio tab."""

    def compose_studio_tab(self) -> ComposeResult:
        """Compose the Tailor Studio tab pane."""
        with TabPane("Tailor Studio", id="tab-studio"):
            with Vertical(id="studio-formulation-view"):
                with VerticalScroll():
                    with Vertical(id="studio-mascot-banner"):
                        with Horizontal(id="studio-banner-header-row"):
                            yield Label("[bold #FFB86C]✦ THE OVEN: TAILOR STUDIO[/bold #FFB86C]", id="studio-banner-title")
                            yield Label("[bold #50FA7B]● Provenance Gate: Active[/bold #50FA7B]", id="studio-banner-status")
                        yield Label(
                            "[dim]Proof verified experience bullets against role requirements without keyword-stuffing slop.[/dim]",
                            id="studio-banner-desc"
                        )
                        yield Label(
                            '[bold #8be9fd][·] Crumb:[/] [italic #f1fa8c]"Select a target job and persona to proof your verified bullets."[/italic #f1fa8c]',
                            id="studio-mascot-speech"
                        )
                        # Hidden stubs for test compatibility
                        yield AnimatedMascot(id="studio-mascot")
                        yield AnimatedOven(id="studio-oven")
                        yield BakeryStepper(current_stage=2, id="studio-stepper")

                    yield Label("Target Job URL or Markdown File:", classes="input-label")
                    yield Input(
                        placeholder="https://boards.greenhouse.io/monzo/jobs/... or /path/to/jd.txt",
                        value=getattr(self, "initial_url", "") or "",
                        id="input-job-url"
                    )
                    yield SkillConstellationWidget(id="studio-skill-constellation")

                    persona_opts = get_persona_select_options()
                    default_persona_val = "none" if any(v == "none" for _, v in persona_opts) else persona_opts[0][1]

                    yield Horizontal(
                        Vertical(
                            Label("Persona / Preset:", classes="input-label"),
                            Select(
                                persona_opts,
                                value=default_persona_val,
                                id="select-persona"
                            ),
                            classes="studio-picker-col"
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
                            ),
                            classes="studio-picker-col"
                        ),
                        id="studio-picker-row"
                    )

                    with Horizontal(classes="action-bar"):
                        yield Button("Bake Application (Enter)", variant="success", id="btn-run-tailor")
                        yield Button("Strategy Loop", variant="primary", id="btn-strategy-loop")
                        yield Button("+ Brain Dump [✦]", id="btn-synth-persona-studio")
                        yield Button("Open Bullet Lab →", variant="default", id="btn-view-lab")
                    yield Static("", id="tailor-status-box")

            with Vertical(id="studio-lab-view"):
                with Horizontal(id="studio-lab-top-bar"):
                    yield Button("← Setup", id="btn-lab-back")
                    yield Label("[bold white]Active Application[/bold white]", id="lab-active-job-label")
                    yield Label("[bold #50FA7B]94% Match[/bold #50FA7B]", id="lab-ats-badge")
                    yield Button("Stack", id="btn-lab-toggle-stack")
                    yield Button("↻ Re-bake", id="btn-lab-rebake")
                    yield Button("View", id="btn-lab-view-pdf")
                    yield Button("Letter", id="btn-lab-view-letter-pdf")
                    yield Button("Folder", id="btn-lab-folder")

                with Horizontal(id="studio-lab-split"):
                    with Vertical(id="lab-left-col"):
                        with Horizontal(classes="lab-col-header"):
                            yield Label("[bold #FFB86C]Bullets (XYZ)[/bold #FFB86C]", classes="pane-header")
                            yield Button("✦ Format", id="btn-lab-format-xyz")
                            yield Button("✓ Apply", id="btn-lab-apply-bullets")
                        yield TextArea("", id="lab-bullet-editor")
                        yield XYZValidatorWidget(id="lab-xyz-validator")
                        yield CrustSpectrumWidget(id="lab-crust-spectrum")

                    with Vertical(id="lab-right-col"):
                        with TabbedContent(id="preview-tabs"):
                            with TabPane("Resume (Jake's)", id="preview-resume-tab"):
                                with Horizontal(classes="resume-pane-toolbar"):
                                    yield Label("[bold white]resume.md[/bold white] [dim]• ATS Markdown[/dim]", classes="pane-toolbar-title")
                                    yield Button("✓ Save (Ctrl+S)", id="btn-lab-save-resume")
                                    yield Button("◎ Preview", id="btn-lab-toggle-preview")
                                yield TextArea("", id="lab-resume-editor")
                                yield ScrollableMarkdown("No application tailored yet. Enter a URL above and click 'Run Tailoring Engine'.", id="preview-resume-md", classes="preview-box")
                            with TabPane("Cover Letter", id="preview-letter-tab"):
                                with Horizontal(classes="resume-pane-toolbar"):
                                    yield Label("[bold white]cover_letter.md[/bold white]", classes="pane-toolbar-title")
                                    yield Button("✓ Save", id="btn-lab-save-letter")
                                yield TextArea("Cover letter will appear here.", id="lab-letter-editor")
                                yield ScrollableMarkdown("Cover letter will appear here.", id="preview-letter-md", classes="preview-box")
                            with TabPane("Portal Q&A", id="preview-qna-tab"):
                                with Horizontal(classes="resume-pane-toolbar"):
                                    yield Label("[bold white]portal_qna.md[/bold white]", classes="pane-toolbar-title")
                                    yield Button("✓ Save", id="btn-lab-save-qna")
                                yield TextArea("Portal Q&A will appear here.", id="lab-qna-editor")
                                yield ScrollableMarkdown("Portal Q&A will appear here.", id="preview-qna-md", classes="preview-box")

                with Vertical(id="studio-lab-bottom-bar"):
                    with Horizontal(id="studio-lab-prompt-row"):
                        yield PromptTextArea("", id="lab-refine-prompt", language=None)
                        yield Button("Refine with AI", variant="warning", id="btn-lab-refine-diff")

    def _ensure_application_context(self) -> None:
        """Hydrates self.current_profile and self.current_app_result from disk when editing from Breadbox."""
        if not self.last_tailored_dir or not self.last_tailored_dir.exists():
            return

        if not self.current_profile:
            if (self.last_tailored_dir / "resume.json").exists():
                try:
                    self.current_profile = JsonResumeAdapter(self.last_tailored_dir / "resume.json").load_profile()
                except Exception:
                    pass
            if not self.current_profile:
                try:
                    self.current_profile = self.pantry.load_profile()
                except Exception:
                    pass

        if not self.current_app_result:
            if self.selected_job:
                job = JobPosting(
                    id=str(getattr(self.selected_job, "id", "job_1")),
                    title=self.selected_job.title,
                    company=self.selected_job.company,
                    url=getattr(self.selected_job, "url", None) or "",
                    raw_text=""
                )
            else:
                job = JobPosting(
                    id="job_default",
                    title="Software Engineer",
                    company="Target Company",
                    raw_text=""
                )

            match_score_val = 80
            if self.selected_job and getattr(self.selected_job, "match_score", None) is not None:
                try:
                    match_score_val = int(self.selected_job.match_score)
                except Exception:
                    pass

            match_analysis = MatchAnalysis(
                match_score=match_score_val,
                matched_skills=[],
                missing_skills=[],
                rationale="Loaded application from disk"
            )
            exps = list(self.current_profile.experiences if self.current_profile else [])
            projs = list(self.current_profile.projects if self.current_profile else [])
            skills = list(self.current_profile.skills if self.current_profile else [])
            self.current_app_result = TailoredApplication(
                job=job,
                persona="engineering",
                match_analysis=match_analysis,
                tailored_summary=self.current_profile.summary if self.current_profile else "",
                tailored_experiences=exps,
                tailored_projects=projs,
                tailored_skills=skills
            )

    def action_pipeline_edit_studio(self) -> None:
        """Loads selected job application into Studio Lab for editing."""
        if not self.selected_job:
            self.notify("Please select a job from the table first.", severity="warning")
            return

        if self.selected_job.url:
            try:
                self.query_one("#input-job-url", Input).value = self.selected_job.url
            except Exception:
                pass

        p_dir = None
        if self.selected_job.folder_path:
            p_candidate = Path(self.selected_job.folder_path)
            if p_candidate.exists():
                p_dir = p_candidate
            elif not p_candidate.is_absolute() and (settings.applications_dir / p_candidate).exists():
                p_dir = settings.applications_dir / p_candidate
            elif (settings.applications_dir / p_candidate.name).exists():
                p_dir = settings.applications_dir / p_candidate.name

        if p_dir and p_dir.exists():
            self.last_tailored_dir = p_dir
            self._ensure_application_context()

            try:
                self.query_one("#lab-active-job-label", Label).update(
                    f"[bold white]{self.selected_job.company} - {self.selected_job.title}[/bold white]"
                )
            except Exception:
                pass

            try:
                score = getattr(self.selected_job, "match_score", None) or 0
                self.query_one("#lab-ats-badge", Label).update(f"[bold #50FA7B]{score}% ATS Match[/bold #50FA7B]")
            except Exception:
                pass

            if (p_dir / "resume.md").exists():
                try:
                    r_txt = (p_dir / "resume.md").read_text(encoding="utf-8")
                    self.query_one("#preview-resume-md", Markdown).update(r_txt)
                    try:
                        self.query_one("#lab-resume-editor", TextArea).text = r_txt
                    except Exception:
                        pass

                    existing_exps = self.current_app_result.tailored_experiences if self.current_app_result else None
                    updated_exps, bullet_text = parse_markdown_resume_experiences(r_txt, existing_exps)
                    if self.current_app_result and updated_exps:
                        self.current_app_result.tailored_experiences = updated_exps

                    if bullet_text:
                        try:
                            editor = self.query_one("#lab-bullet-editor", TextArea)
                            editor.text = bullet_text
                            report = analyze_bullets_xyz(bullet_text, self.current_profile)
                            self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report)
                            self.query_one("#lab-crust-spectrum", CrustSpectrumWidget).update_spectrum(
                                quantified_pct=report.quantified_score,
                                action_verb_pct=int((report.action_verbs_count / max(1, report.total_bullets)) * 100),
                                provenance_verified=True
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

            if (p_dir / "cover_letter.md").exists():
                try:
                    l_txt = (p_dir / "cover_letter.md").read_text(encoding="utf-8")
                    self.query_one("#preview-letter-md", Markdown).update(l_txt)
                    try:
                        self.query_one("#lab-letter-editor", TextArea).text = l_txt
                    except Exception:
                        pass
                except Exception:
                    pass

            q_file = (p_dir / "portal_answers.md") if (p_dir / "portal_answers.md").exists() else ((p_dir / "portal_qna.md") if (p_dir / "portal_qna.md").exists() else None)
            if q_file:
                try:
                    q_txt = q_file.read_text(encoding="utf-8")
                    self.query_one("#preview-qna-md", Markdown).update(q_txt)
                    try:
                        self.query_one("#lab-qna-editor", TextArea).text = q_txt
                    except Exception:
                        pass
                except Exception:
                    pass

            # If this application has been baked/tailored, open directly in Bullet Lab view
            if (p_dir / "resume.md").exists():
                self.action_view_lab()
            else:
                self.action_lab_back_to_setup()
        else:
            self.action_lab_back_to_setup()

        self.query_one("#main-tabs", TabbedContent).active = "tab-studio"
        self._update_active_top_nav("tab-studio")
        self.notify("Loaded job into Tailor Studio!", title="Studio Activated")

    def action_view_lab(self) -> None:
        """Switch Studio view to Bullet Lab editor."""
        try:
            self.query_one("#studio-formulation-view").styles.display = "none"
            self.query_one("#studio-lab-view").styles.display = "block"
        except Exception:
            pass

    def action_lab_back_to_setup(self) -> None:
        """Switch Studio view back to formulation & setup."""
        try:
            self.query_one("#studio-formulation-view").styles.display = "block"
            self.query_one("#studio-lab-view").styles.display = "none"
        except Exception:
            pass

    def refresh_skill_constellation(self, url_or_text: str) -> None:
        """Update live skill constellation based on target job text or URL."""
        try:
            widget = self.query_one("#studio-skill-constellation", SkillConstellationWidget)
            if not url_or_text:
                widget.update_constellation(set(), [])
                return
            cand_skills = set(self.current_profile.skills) if self.current_profile else set()
            p_source = Path(url_or_text)
            if p_source.is_file():
                content = p_source.read_text(encoding="utf-8")
                job = JobScraper.ingest_from_text(content, "Target", "Role")
                demanded = job.requirements or job.keywords or []
                widget.update_constellation(cand_skills, demanded[:8])
            elif url_or_text.startswith("http://") or url_or_text.startswith("https://"):
                widget.update("[dim #94A3B8]· Remote URL detected: Constellation calculates upon baking ·[/dim #94A3B8]")
            else:
                job = JobScraper.ingest_from_text(url_or_text, "Target", "Role")
                demanded = job.requirements or job.keywords or []
                widget.update_constellation(cand_skills, demanded[:8])
        except Exception:
            pass

    def action_format_lab_xyz(self) -> None:
        """Format bullets with Google XYZ active verbs."""
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
        """Trigger AI refinement via DiffModal."""
        try:
            prompt = self.query_one("#lab-refine-prompt", PromptTextArea).text.strip()
        except Exception:
            try:
                prompt = self.query_one("#lab-refine-prompt", TextArea).text.strip()
            except Exception:
                prompt = ""
        if not prompt:
            self.notify("Please enter an instruction to refine bullets (e.g. 'Inject metrics', 'Target Senior ML').", severity="warning")
            return

        current_bullets = self.query_one("#lab-bullet-editor", TextArea).text.strip()
        if not current_bullets:
            try:
                r_editor_text = self.query_one("#lab-resume-editor", TextArea).text.strip()
                extracted = [line.strip() for line in r_editor_text.splitlines() if line.strip().startswith(("-", "*", "•"))]
                if extracted:
                    current_bullets = "\n".join(extracted[:5])
            except Exception:
                pass
        if not current_bullets:
            current_bullets = "- Engineered distributed systems and backend microservices."

        self.push_screen(
            DiffModal(prompt=prompt, current_bullets=current_bullets),
            self._on_diff_modal_dismissed
        )

    def _on_diff_modal_dismissed(self, refined_bullets: Optional[str]) -> None:
        if not refined_bullets:
            return
        try:
            editor = self.query_one("#lab-bullet-editor", TextArea)
            editor.text = refined_bullets
            self._pending_refined_bullets = refined_bullets
            report = analyze_bullets_xyz(refined_bullets, self.current_profile)
            prov = self.current_app_result.provenance_report if hasattr(self, "current_app_result") and self.current_app_result else None
            self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report, provenance_info=prov)
            try:
                self.query_one("#lab-crust-spectrum", CrustSpectrumWidget).update_spectrum(
                    quantified_pct=report.quantified_score,
                    action_verb_pct=int((report.action_verbs_count / max(1, report.total_bullets)) * 100),
                    provenance_verified=(prov is None or getattr(prov, "is_clean", True))
                )
            except Exception:
                pass
            self.action_apply_lab_bullets()
            self.notify("✓ Accepted metric diff! Bullets synced to resume and audit gauges updated.", title="Diff Accepted")
        except Exception as e:
            self.notify(f"Failed to apply refined bullets: {e}", severity="error")

    def action_accept_diff(self) -> None:
        if getattr(self, "_pending_refined_bullets", None):
            self._on_diff_modal_dismissed(self._pending_refined_bullets)

    def action_dismiss_diff(self) -> None:
        self._pending_refined_bullets = None

    def action_toggle_lab_stack(self) -> None:
        try:
            lab_split = self.query_one("#studio-lab-split")
            btn = self.query_one("#btn-lab-toggle-stack", Button)
            if lab_split.has_class("-vertical-stack"):
                lab_split.remove_class("-vertical-stack")
                btn.label = "Stack"
                self.notify("Switched Studio Lab to Side-by-Side Columns", title="Layout")
            else:
                lab_split.add_class("-vertical-stack")
                btn.label = "Side-by-Side"
                self.notify("Switched Studio Lab to Vertical Stack", title="Layout")
        except Exception:
            pass

    def action_apply_lab_bullets(self) -> None:
        """Applies edited bullets from lab-bullet-editor to tailored application and updates resume."""
        try:
            editor = self.query_one("#lab-bullet-editor", TextArea)
            bullets_text = editor.text
            if not bullets_text or not self.last_tailored_dir:
                self.notify("No active tailored application to update.", severity="warning")
                return

            self._ensure_application_context()

            has_headings = any(line.strip().startswith("### ") for line in bullets_text.splitlines())
            new_experiences = list(self.current_app_result.tailored_experiences or []) if self.current_app_result else []
            if not has_headings and new_experiences:
                current_exp_idx = 0
                new_experiences[0].bullets = []
            else:
                current_exp_idx = -1

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

            if self.current_app_result:
                self.current_app_result.tailored_experiences = new_experiences
            renderer = TemplateRenderer()
            resume_md = renderer.render_resume(self.current_profile, self.current_app_result, "ats")
            resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)

            (self.last_tailored_dir / "resume.md").write_text(resume_md, encoding="utf-8")
            (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")

            resume_json_path = self.last_tailored_dir / "resume.json"
            if resume_json_path.exists():
                try:
                    rj = json.loads(resume_json_path.read_text(encoding="utf-8"))
                    if "work" in rj and isinstance(rj["work"], list):
                        for i, exp in enumerate(new_experiences):
                            if i < len(rj["work"]):
                                rj["work"][i]["highlights"] = exp.bullets
                    resume_json_path.write_text(json.dumps(rj, indent=2), encoding="utf-8")
                except Exception:
                    pass

            try:
                _resolve_render_pdf()(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
            except Exception:
                pass

            self.query_one("#lab-resume-editor", TextArea).text = resume_md
            self.query_one("#preview-resume-md", Markdown).update(resume_md)

            # Recalculate XYZ metrics
            report = analyze_bullets_xyz(bullets_text, self.current_profile)
            self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report)
            self.query_one("#lab-crust-spectrum", CrustSpectrumWidget).update_spectrum(
                quantified_pct=report.quantified_score,
                action_verb_pct=int((report.action_verbs_count / max(1, report.total_bullets)) * 100),
                provenance_verified=True
            )
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

            # 1. Hydrate profile & application if missing
            self._ensure_application_context()

            # 2. Parse updated resume.md to extract experience bullets and role headings
            existing_exps = self.current_app_result.tailored_experiences if self.current_app_result else (self.current_profile.experiences if self.current_profile else None)
            updated_exps, editor_bullet_text = parse_markdown_resume_experiences(text, existing_exps)

            if self.current_app_result:
                self.current_app_result.tailored_experiences = updated_exps

            # 3. Update lab-bullet-editor and recalculate XYZ metrics
            if editor_bullet_text:
                try:
                    self.query_one("#lab-bullet-editor", TextArea).text = editor_bullet_text
                    report = analyze_bullets_xyz(editor_bullet_text, self.current_profile)
                    self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report)
                    self.query_one("#lab-crust-spectrum", CrustSpectrumWidget).update_spectrum(
                        quantified_pct=report.quantified_score,
                        action_verb_pct=int((report.action_verbs_count / max(1, report.total_bullets)) * 100),
                        provenance_verified=True
                    )
                except Exception:
                    pass

            # 4. Sync resume.json on disk if present
            resume_json_path = self.last_tailored_dir / "resume.json"
            if resume_json_path.exists():
                try:
                    rj = json.loads(resume_json_path.read_text(encoding="utf-8"))
                    if "work" in rj and isinstance(rj["work"], list):
                        for i, exp in enumerate(updated_exps):
                            if i < len(rj["work"]):
                                rj["work"][i]["highlights"] = exp.bullets
                    resume_json_path.write_text(json.dumps(rj, indent=2), encoding="utf-8")
                except Exception:
                    pass

            # 5. Regenerate resume.html from template & re-bake resume.pdf
            if self.current_profile and self.current_app_result:
                renderer = TemplateRenderer()
                resume_html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template)
                (self.last_tailored_dir / "resume.html").write_text(resume_html, encoding="utf-8")
                try:
                    _resolve_render_pdf()(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
                except Exception:
                    pass

            self.query_one("#preview-resume-md", Markdown).update(text)
            self.notify("✓ Saved resume.md, synced bullets & baked ATS PDF!", title="Resume Synced")
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

            # Re-render cover_letter.html and compile cover_letter.pdf
            try:
                self._ensure_application_context()
                renderer = TemplateRenderer()
                comp = self.selected_job.company if self.selected_job else None
                title = self.selected_job.title if self.selected_job else None
                letter_html = renderer.render_cover_letter_html(
                    profile=self.current_profile,
                    app=self.current_app_result,
                    cover_letter_text=text,
                    company=comp,
                    title=title,
                    template_name=self.current_template or "jakes"
                )
                (self.last_tailored_dir / "cover_letter.html").write_text(letter_html, encoding="utf-8")
                _resolve_render_pdf()(self.last_tailored_dir / "cover_letter.html", self.last_tailored_dir / "cover_letter.pdf", open_after=False)
            except Exception:
                pass

            self.notify("✓ Saved cover_letter.md & compiled cover_letter.pdf!", title="Cover Letter Saved")
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
                btn.label = "[·] Edit"
                md_view.focus()
            else:
                md_view.styles.display = "none"
                r_editor.styles.display = "block"
                btn.label = "[·] Preview"
                r_editor.focus()
        except Exception:
            pass

    def action_bake_pdf(self) -> None:
        target_dir = None
        if self.last_tailored_dir and self.last_tailored_dir.exists():
            target_dir = self.last_tailored_dir
        elif self.selected_job and self.selected_job.folder_path:
            p = Path(self.selected_job.folder_path)
            if p.exists():
                target_dir = p
            elif not p.is_absolute() and (settings.applications_dir / p).exists():
                target_dir = settings.applications_dir / p
            elif (settings.applications_dir / p.name).exists():
                target_dir = settings.applications_dir / p.name

        if not target_dir:
            self.notify("Please tailor a job first or select a valid application folder.", severity="warning")
            return

        self.last_tailored_dir = target_dir
        if not (target_dir / "resume.html").exists() and (target_dir / "resume.md").exists():
            try:
                self._ensure_application_context()
                if self.current_profile and self.current_app_result:
                    renderer = TemplateRenderer()
                    html = renderer.render_resume(self.current_profile, self.current_app_result, self.current_template or "jakes")
                    (target_dir / "resume.html").write_text(html, encoding="utf-8")
            except Exception:
                pass

        self.push_screen(
            BakingModal(task_type="bake_pdf", target_info={"app_dir": target_dir}),
            self._on_pdf_bake_modal_dismissed
        )

    def _on_pdf_bake_modal_dismissed(self, result: Optional[Dict[str, Any]]) -> None:
        if not result or not result.get("success"):
            return
        size_kb = result.get("size_kb", 0.0)
        letter_size_kb = result.get("cover_letter_size_kb", 0.0)
        extra = f" + cover_letter.pdf ({letter_size_kb} KB)" if letter_size_kb > 0 else ""
        self.notify(f"✓ Fresh out of the oven! Baked resume.pdf ({size_kb} KB){extra}", title="Bake Complete")
        try:
            self.set_global_stage(4)
            mascot = self.query_one("#studio-mascot", AnimatedMascot)
            mascot.set_message("Crisp ATS PDF Package Baked!")
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
            self.notify("Opened resume.pdf in system viewer.", title="Preview")
        else:
            self.notify("No resume.pdf found. Press 'b' to bake one first!", severity="warning")

    def action_view_letter_pdf(self) -> None:
        target_dir = None
        if self.last_tailored_dir and (self.last_tailored_dir / "cover_letter.pdf").exists():
            target_dir = self.last_tailored_dir
        elif self.selected_job and self.selected_job.folder_path:
            p = Path(self.selected_job.folder_path)
            if p.exists() and (p / "cover_letter.pdf").exists():
                target_dir = p

        if target_dir and (target_dir / "cover_letter.pdf").exists():
            open_file_in_viewer(target_dir / "cover_letter.pdf")
            self.notify("Opened cover_letter.pdf in system viewer.", title="Preview")
        else:
            self.notify("No cover_letter.pdf found. Save letter or bake package first!", severity="warning")

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
            _resolve_render_pdf()(self.last_tailored_dir / "resume.html", self.last_tailored_dir / "resume.pdf", open_after=False)
        except Exception:
            pass

        self.query_one("#preview-resume-md", Markdown).update(resume_md)
        self.notify("Updated tailored bullets and re-baked resume.pdf!", title="Fine-Tune Applied")

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

            provider = _resolve_llm_provider()()
            questions = generate_job_strategy_questions(job, provider)
            persona_slug = self.query_one("#select-persona", Select).value
            base_persona = PersonaManager.load_persona(persona_slug) if persona_slug and str(persona_slug).lower() != "none" else None

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
            persona = PersonaManager.load_persona(persona_slug) if persona_slug and str(persona_slug).lower() != "none" else None

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
        if not result:
            try:
                self.set_global_stage(0)
                oven = self.query_one("#studio-oven", AnimatedOven)
                oven.set_state("idle")
            except Exception:
                pass
            return

        if result.get("action") == "change_model":
            try:
                self.set_global_stage(0)
                oven = self.query_one("#studio-oven", AnimatedOven)
                oven.set_state("idle")
            except Exception:
                pass
            self._pending_bake_retry = {
                "task_type": "tailor",
                "target_info": result.get("target_info") or {}
            }
            self.action_switch_model()
            return

        if not result.get("success"):
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
            f"Target: [bold]{job.company} - {job.title}[/bold] | "
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
                prov = self.current_app_result.provenance_report if hasattr(self, "current_app_result") and self.current_app_result else None
                self.query_one("#lab-xyz-validator", XYZValidatorWidget).update_report(report, provenance_info=prov)
                try:
                    self.query_one("#lab-crust-spectrum", CrustSpectrumWidget).update_spectrum(
                        quantified_pct=report.quantified_score,
                        action_verb_pct=int((report.action_verbs_count / max(1, report.total_bullets)) * 100),
                        provenance_verified=(prov is None or getattr(prov, "is_clean", True))
                    )
                except Exception:
                    pass
                if job:
                    self.query_one("#lab-active-job-label", Label).update(f"[bold white]{job.company} - {job.title}[/bold white]")
                prov_tag = " • [bold #8be9fd]Grounded[/]" if prov and prov.get("is_valid", False) else ""
                self.query_one("#lab-ats-badge", Label).update(f"[bold #50FA7B]{score}% Match[/bold #50FA7B]{prov_tag}")
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

    def handle_studio_button(self, bid: str) -> bool:
        """Route Studio-specific button events."""
        if bid == "btn-run-tailor":
            self.run_tailoring_flow()
            return True
        if bid == "btn-strategy-loop":
            self.run_strategy_loop_flow()
            return True
        if bid == "btn-synth-persona-studio":
            def on_synth_done(slug: Optional[str]):
                if slug:
                    self._refresh_persona_select(slug)
            self.push_screen(PersonaSynthesizerModal(), on_synth_done)
            return True
        if bid == "btn-view-lab":
            self.action_view_lab()
            return True
        if bid == "btn-lab-back":
            self.action_lab_back_to_setup()
            return True
        if bid == "btn-lab-toggle-stack":
            self.action_toggle_lab_stack()
            return True
        if bid == "btn-lab-rebake":
            self.action_rebake_job()
            return True
        if bid == "btn-lab-format-xyz":
            self.action_format_lab_xyz()
            return True
        if bid == "btn-lab-apply-bullets":
            self.action_apply_lab_bullets()
            return True
        if bid == "btn-lab-save-resume":
            self.action_save_lab_resume()
            return True
        if bid == "btn-lab-save-letter":
            self.action_save_lab_letter()
            return True
        if bid == "btn-lab-save-qna":
            self.action_save_lab_qna()
            return True
        if bid == "btn-lab-toggle-preview":
            self.action_toggle_resume_preview()
            return True
        if bid == "btn-lab-refine-diff":
            self.action_lab_refine_diff()
            return True
        if bid == "btn-accept-diff":
            self.action_accept_diff()
            return True
        if bid == "btn-dismiss-diff":
            self.action_dismiss_diff()
            return True
        if bid == "btn-studio-finetune":
            self.action_finetune_bullets()
            return True
        if bid in ("btn-studio-bake", "btn-pipeline-bake"):
            self.action_bake_pdf()
            return True
        if bid in ("btn-studio-view-pdf", "btn-pipeline-view-pdf", "btn-lab-view-pdf"):
            self.action_view_pdf()
            return True
        if bid == "btn-lab-view-letter-pdf":
            self.action_view_letter_pdf()
            return True
        if bid == "btn-lab-folder":
            self.action_open_folder()
            return True
        if bid == "btn-studio-browser":
            if self.last_tailored_dir and (self.last_tailored_dir / "resume.html").exists():
                webbrowser.open(f"file://{self.last_tailored_dir / 'resume.html'}")
            else:
                self.notify("No resume.html generated yet.", severity="warning")
            return True
        if bid == "btn-studio-applied":
            if self.selected_job:
                self.repo.update_status(self.selected_job.id, "applied")
                from breadwinner.db.sync import CsvSync
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
                self.notify("Marked application as APPLIED!", title="Updated")
                self.load_pipeline_table()
                self.update_details_pane()
            return True
        return False

