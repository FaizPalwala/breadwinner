"""Breadwinner interactive Textual TUI root application."""

from pathlib import Path
from typing import Optional, List, Dict, Any

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Label, Markdown, TabbedContent, TextArea

from breadwinner.config import settings
from breadwinner.core.models import CandidateProfile, TailoredApplication
from breadwinner.core.pantry import PantryManager
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.ui.geometry import get_preset_geometry, apply_app_layout_preset, sync_app_sidebar
from breadwinner.ui.screen_guard import ScreenGuardScreen
from breadwinner.ui.editor import analyze_bullets_xyz, XYZValidatorWidget
from breadwinner.ui.visuals import CrustSpectrumWidget
from breadwinner.ui.retro import BakeryStepper

# Re-exports for backwards compatibility across tests and CLI
from breadwinner.ui.screens import (
    PaletteModelItem, PaletteSearchInput, PromptTextArea,
    ModelQuickSwitcherModal, BakerySettingsModal, ModelsScreenMixin,
    StatusModal, FlagModal, DeleteJobModal, BreadboxScreenMixin,
    JobStrategyModal, PersonaSynthesizerModal, DiffModal, FineTuneModal,
    StudioScreenMixin, PantryIngestModal, PantryInterviewModal,
    PantryHistoryModal, PantryEditorModal, PantryScreenMixin,
)
from breadwinner.ui.screens.models import VerticalEngineBlade
from breadwinner.ui.screens.studio import get_persona_select_options
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer
from breadwinner.providers.factory import get_llm_provider
from breadwinner.core.ingestor import UniversalIngestor
from breadwinner.core.scraper import JobScraper
from breadwinner.core.persona import PersonaManager
from breadwinner.ui.welcome import BakeryWelcomeModal

__all__ = [
    "BreadwinnerApp", "JobStrategyModal", "PersonaSynthesizerModal", "DiffModal",
    "FineTuneModal", "PantryIngestModal", "PantryInterviewModal", "PantryHistoryModal",
    "PantryEditorModal", "StatusModal", "FlagModal", "DeleteJobModal",
    "PaletteModelItem", "PaletteSearchInput", "PromptTextArea", "ModelQuickSwitcherModal",
    "BakerySettingsModal", "VerticalEngineBlade", "get_persona_select_options",
    "BreadboxScreenMixin", "StudioScreenMixin", "PantryScreenMixin", "ModelsScreenMixin",
    "render_html_to_pdf", "open_file_in_viewer", "get_llm_provider", "UniversalIngestor",
    "JobScraper", "PersonaManager", "BakeryWelcomeModal",
]

MIN_TERMINAL_WIDTH = 76
MIN_TERMINAL_HEIGHT = 22


class BreadwinnerApp(BreadboxScreenMixin, StudioScreenMixin, PantryScreenMixin, ModelsScreenMixin, App):
    """Breadwinner Interactive TUI Application."""

    TITLE = "Breadwinner"
    SUB_TITLE = "Local 8-Bit Anti-Slop Career Studio ◈"
    CSS_PATH = ["styles/base.tcss", "styles/breadbox.tcss", "styles/studio.tcss", "styles/pantry.tcss"]

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True), Binding("1", "tab_pipeline", "Breadbox", show=True),
        Binding("2", "tab_studio", "Studio", show=True), Binding("3", "tab_profile", "Pantry", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar", show=False), Binding("[", "toggle_sidebar", "Toggle Sidebar", show=False),
        Binding("f11", "cycle_preset", "Cycle Preset", show=False), Binding("m", "switch_model", "Model Switcher", show=True),
        Binding("comma", "open_settings", "Settings", show=False), Binding("f2", "open_settings", "Settings", show=False),
        Binding("ctrl+s", "save_active_editor", "Save File", show=False), Binding("b", "bake_pdf", "Bake PDF", show=True),
        Binding("v", "view_pdf", "View PDF", show=True), Binding("s", "change_status", "Cycle Status", show=True),
        Binding("e", "pipeline_edit_studio", "Studio", show=False), Binding("i", "pantry_ingest", "Ingest", show=False),
        Binding("h", "pantry_history", "History", show=False), Binding("f", "toggle_flag", "Toggle Flag", show=False),
        Binding("o", "open_folder", "Open Folder", show=False), Binding("d", "delete_job", "Delete", show=True),
        Binding("r", "rebake_job", "Re-bake", show=True),
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
        self._last_width: Optional[int] = None
        self._pending_bake_retry: Optional[Dict[str, Any]] = None
        self._pending_refined_bullets: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="app-header-deck"):
            with Horizontal(id="app-top-bar"):
                with Horizontal(id="top-bar-left"):
                    yield Button("◄", id="btn-sidebar-toggle", classes="icon-toggle-btn")
                    yield Button(self.get_active_model_chip_text(), id="btn-active-model-chip")
                with Horizontal(id="top-bar-center"):
                    yield Label("[bold #FFB86C]◈ BREADWINNER[/]", id="top-bar-brand")
                    yield Label(" [dim]/[/] [bold white]BREADBOX[/]", id="top-bar-screen-title")
                with Horizontal(id="top-bar-right"):
                    yield Button("⛶ View: Normal (F11)", id="btn-app-cycle-preset")
                    yield Button("✕ Quit (q)", id="btn-app-quit")
            with Horizontal(id="top-bar-nav-pills"):
                yield Button("▣ Breadbox (1)", id="btn-tab-breadbox", classes="top-nav-btn -active")
                yield Button("♨ Studio (2)", id="btn-tab-studio", classes="top-nav-btn")
                yield Button("▤ Pantry (3)", id="btn-tab-pantry", classes="top-nav-btn")

        with Horizontal(id="app-workspace-split"):
            with Vertical(id="app-sidebar"):
                with Vertical(id="sidebar-flows"):
                    yield Button("▣ Breadbox (1)", id="btn-sidebar-breadbox", classes="sidebar-flow-btn -active")
                    yield Button("♨ Studio (2)", id="btn-sidebar-studio", classes="sidebar-flow-btn")
                    yield Button("▤ Pantry (3)", id="btn-sidebar-pantry", classes="sidebar-flow-btn")
                yield Vertical(classes="sidebar-spacer")
                with Vertical(id="sidebar-bottom"):
                    yield Button(self.get_active_model_chip_text(), id="btn-sidebar-model", classes="sidebar-bottom-btn")
                    yield VerticalEngineBlade(provider=self.get_active_provider_name(), id="blade-sidebar-engine")
                    yield Button("[§] Settings", id="btn-sidebar-settings", classes="sidebar-bottom-btn")

            with TabbedContent(initial="tab-pipeline", id="main-tabs"):
                yield self.compose_breadbox_tab()
                yield from self.compose_studio_tab()
                yield from self.compose_pantry_tab()

        yield Footer()

    def on_resize(self, event: events.Resize) -> None:
        """Enforce screen guard sentinel and auto-responsive layout adapting."""
        if event.size.width <= 0 or event.size.height <= 0:
            return
        is_too_small = event.size.width < MIN_TERMINAL_WIDTH or event.size.height < MIN_TERMINAL_HEIGHT
        guard = isinstance(getattr(self, "screen", None), ScreenGuardScreen)
        if is_too_small:
            if not guard:
                self.push_screen(ScreenGuardScreen(min_cols=MIN_TERMINAL_WIDTH, min_rows=MIN_TERMINAL_HEIGHT))
            else:
                self.screen.update_dimensions(event.size.width, event.size.height)
            return
        elif guard:
            self.pop_screen()

        self._update_quick_keys_hint(event.size.width)
        nav_style = getattr(settings, "navigation_style", "auto")
        if nav_style == "auto" and self._last_width is not None and event.size.width != self._last_width:
            self._last_width = event.size.width
            if event.size.width < 100 and self.layout_preset != "split":
                self.apply_layout_preset("split", resize_window=False)
            elif event.size.width >= 100 and self.layout_preset == "split":
                self.apply_layout_preset("normal", resize_window=False)

    def _update_quick_keys_hint(self, width: int) -> None:
        try:
            hint = self.query_one("#pipeline-table-hint", Label)
            hint.update(
                "[dim]Quick keys: (s) Status • (f) Flag • (e) Studio • (r) Re-bake\n            (b) Bake • (v) PDF • (o) Folder • (d) Delete[/dim]"
                if width < 150 else
                "[dim]Quick keys: (s) Status • (f) Flag • (e) Studio • (r) Re-bake • (b) Bake • (v) PDF • (o) Folder • (d) Delete[/dim]"
            )
        except Exception:
            pass

    def on_mount(self) -> None:
        self.apply_layout_preset("normal")
        self._last_width = self.size.width
        self._update_quick_keys_hint(self.size.width)
        self._update_active_top_nav("tab-pipeline")
        self.load_pipeline_table()
        self.load_models_tab()
        self.load_pantry_ide()

        if self.size.width > 0 and self.size.height > 0:
            if self.size.width < MIN_TERMINAL_WIDTH or self.size.height < MIN_TERMINAL_HEIGHT:
                if not isinstance(self.screen, ScreenGuardScreen):
                    self.push_screen(ScreenGuardScreen(min_cols=MIN_TERMINAL_WIDTH, min_rows=MIN_TERMINAL_HEIGHT))

        import os
        from breadwinner.config import get_env_path
        has_key = any(os.environ.get(k) for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY"))
        needs_ai, needs_pantry = not get_env_path().exists() and not has_key, not self.pantry.is_initialized()
        if needs_pantry:
            self.notify("No career profile detected in pantry/. Drop your resume PDF into 'pantry/' or run 'breadwinner ingest --resume <path/to/resume.pdf>' to initialize your experience ledger.", title="Pantry Empty", severity="warning")
        if needs_ai or needs_pantry:
            self.push_screen(BakeryWelcomeModal(self.pantry, initial_step="ai" if needs_ai else "pantry"), self._on_welcome_modal_dismissed)

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
            for prefix in ("btn-tab-", "btn-sidebar-"):
                for tab in ("breadbox", "studio", "pantry"):
                    self.query_one(f"#{prefix}{tab}", Button).remove_class("-active")

            tab_map = {"pipeline": ("breadbox", "BREADBOX"), "studio": ("studio", "STUDIO"), "profile": ("pantry", "PANTRY")}
            for key, (cls, title) in tab_map.items():
                if key in active_tab:
                    self.query_one(f"#btn-tab-{cls}", Button).add_class("-active")
                    self.query_one(f"#btn-sidebar-{cls}", Button).add_class("-active")
                    self.query_one("#top-bar-screen-title", Label).update(f"[dim]/[/] [bold white]{title}[/]")
                    break
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._sync_sidebar_state()

    def _sync_sidebar_state(self) -> None:
        sync_app_sidebar(self)

    def action_cycle_preset(self) -> None:
        order = ["normal", "split", "full"]
        try:
            curr_idx = order.index(self.layout_preset)
        except ValueError:
            curr_idx = 0
        self.apply_layout_preset(order[(curr_idx + 1) % len(order)])

    def apply_layout_preset(self, preset: str, resize_window: bool = True) -> None:
        apply_app_layout_preset(self, preset, resize_window)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Reactive stage sync and top nav active state when switching tabs."""
        tab_id = getattr(getattr(event, "pane", None), "id", None) or event.tab.id or ""
        self._update_active_top_nav(tab_id)
        if "profile" in tab_id:
            self.set_global_stage(0)
            self.load_pantry_ide()
        elif "models" in tab_id:
            self.set_global_stage(1)
        elif "studio" in tab_id:
            self.set_global_stage(2)
        elif "pipeline" in tab_id:
            self.set_global_stage(4)

    def action_quit(self) -> None:
        self.exit()

    def action_tab_pipeline(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-pipeline"
        self._update_active_top_nav("tab-pipeline")

    def action_tab_studio(self) -> None:
        if self.selected_job and self.selected_job.folder_path:
            p_dir = Path(self.selected_job.folder_path)
            if not p_dir.is_absolute():
                p_dir = settings.applications_dir / p_dir
            if not p_dir.exists() and (settings.applications_dir / Path(self.selected_job.folder_path).name).exists():
                p_dir = settings.applications_dir / Path(self.selected_job.folder_path).name
            if p_dir.exists() and (p_dir / "resume.md").exists():
                self.action_pipeline_edit_studio()
                return
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

    def action_save_active_editor(self) -> None:
        """Smart save handler for Ctrl+S hotkey."""
        active_tab = getattr(self.query_one("#main-tabs", TabbedContent), "active", "")
        if "studio" in active_tab:
            self.action_save_lab_resume()
        elif "profile" in active_tab:
            self.action_save_pantry_ide_file()
        elif "pipeline" in active_tab:
            self.action_save_notes()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input-job-url":
            self.refresh_skill_constellation(event.value.strip())
        elif hasattr(super(), "on_input_changed"):
            super().on_input_changed(event)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "lab-bullet-editor":
            try:
                report = analyze_bullets_xyz(event.text_area.text, self.current_profile)
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
            except Exception:
                pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pantry-ai-prompt":
            self.action_pantry_ai_refine()
        elif event.input.id == "lab-refine-prompt":
            self.action_lab_refine_diff()
        elif event.input.id == "input-job-url":
            self.action_bake_job()

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
        elif not (self.handle_breadbox_button(bid) or self.handle_studio_button(bid) or self.handle_pantry_button(bid, event)):
            pass
