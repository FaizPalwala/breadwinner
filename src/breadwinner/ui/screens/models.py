"""Model Switcher, Palette Search, and Settings Configuration Screen."""

from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from rich.text import Text

from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Label,
    Button,
    Input,
    TextArea,
    OptionList,
    Static,
    Select,
)
from textual.widgets.option_list import Option

from breadwinner.config import settings
from breadwinner.providers.discovery import ProviderDiscovery
from breadwinner.ui.welcome import save_env_config, PROVIDER_MODELS, BakeryWelcomeModal
from breadwinner.ui.retro import BakingModal


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
        background: transparent;
        color: #6272a4;
        border: none;
        text-style: none;
    }
    Button.modal-close-btn:hover, .modal-close-btn:hover,
    #btn-switcher-close:hover, #btn-settings-close:hover, #btn-strategy-close:hover,
    #btn-modal-close:hover, #btn-ingest-close:hover, #btn-interview-close:hover,
    #btn-history-close:hover, #btn-status-close:hover, #btn-flag-close:hover, #btn-close-persona-synth:hover {
        background: transparent;
        color: #ff5555;
        border: none;
        text-style: bold;
    }
    .modal-action-bar {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    .modal-action-bar Button {
        margin-left: 1;
    }
"""


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
    from breadwinner.core.persona import PersonaManager
    opts = [("None (Direct Pantry Match)", "none")]
    personas = PersonaManager.list_personas()
    for slug, desc in personas.items():
        clean = desc.replace("[bold green]", "").replace("[/bold green]", "")
        opts.append((f"{slug.upper()}: {clean[:40]}", slug))
    return opts


class PaletteModelItem:
    provider_slug: str
    provider_name: str
    model_id: str
    display_name: str
    is_available: bool
    is_active: bool

    def __init__(
        self,
        provider_slug: str,
        provider_name: str,
        model_id: str,
        display_name: str,
        is_available: bool,
        is_active: bool,
    ):
        self.provider_slug = provider_slug
        self.provider_name = provider_name
        self.model_id = model_id
        self.display_name = display_name
        self.is_available = is_available
        self.is_active = is_active


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


class PromptTextArea(TextArea):
    """Multiline prompt input with Ctrl+Enter submit trigger."""

    def on_key(self, event: events.Key) -> None:
        if event.key in ("ctrl+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            if self.id == "lab-refine-prompt":
                self.app.action_lab_refine_diff()
            elif self.id == "pantry-ai-prompt":
                self.app.action_pantry_ai_refine()


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
        max-height: 20;
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
        height: 12;
        max-height: 12;
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
        self._selectable_items: List[PaletteModelItem] = []
        self._option_item_map: Dict[str, PaletteModelItem] = {}

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def _build_all_items(self) -> List[PaletteModelItem]:
        prov_order = ["gemini", "anthropic", "deepseek", "groq", "openai", "openrouter", "mistral", "ollama", "lmstudio", "mock"]
        ready_items: List[PaletteModelItem] = []
        unconfigured_items: List[PaletteModelItem] = []

        for slug in prov_order:
            st = self.status_map.get(slug)
            prov_name = st.name if st else slug.capitalize()
            is_avail = st.is_available if st else False
            models: List[Tuple[str, str]] = []
            if st and st.models:
                models = [(m.name or m.id, m.id) for m in st.models]
            elif slug == "mock":
                models = PROVIDER_MODELS.get("mock", [])

            if is_avail and models:
                pref_model_id = getattr(settings, f"{slug}_model", models[0][1] if models else "")
                prov_ready: List[PaletteModelItem] = []
                for idx, (disp, mid) in enumerate(models):
                    clean_disp = disp.split("(")[0].strip()
                    is_act = (slug == self.active_prov and (mid == self.cur_model or (not self.cur_model and idx == 0)))
                    item = PaletteModelItem(
                        provider_slug=slug,
                        provider_name=prov_name,
                        model_id=mid,
                        display_name=clean_disp,
                        is_available=True,
                        is_active=is_act,
                    )
                    if mid == pref_model_id or (idx == 0 and not prov_ready):
                        prov_ready.insert(0, item)
                    else:
                        prov_ready.append(item)
                ready_items.extend(prov_ready)
            else:
                unconfigured_items.append(
                    PaletteModelItem(
                        provider_slug=slug,
                        provider_name=prov_name,
                        model_id="Key Required" if slug not in ("ollama", "lmstudio") else "Offline",
                        display_name=f"Setup {prov_name}",
                        is_available=False,
                        is_active=(slug == self.active_prov),
                    )
                )

        return ready_items + unconfigured_items

    def compose(self) -> ComposeResult:
        with Vertical(id="switcher-dialog"):
            with Horizontal(id="switcher-header-row"):
                yield Label("[bold #ffb86c]✦ AI ENGINE & MODEL PALETTE[/bold #ffb86c]", id="switcher-title")
                yield Button("✕", id="btn-switcher-close")
            yield PaletteSearchInput(placeholder="[?] Search model or provider (or press 1-9 to pick)...", id="switcher-search")
            yield OptionList(id="switcher-list")
            yield Label("[dim]↑/↓ Navigate • Enter Select • 1-9 Quick Pick • Esc Close[/dim]", id="switcher-footer-hint")
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

        if item.is_active and item.is_available:
            status_markup = "[bold #ffb86c]● ACTIVE[/bold #ffb86c]"
        elif item.is_available:
            status_markup = "[#50fa7b]● READY[/#50fa7b]"
        else:
            status_markup = "[dim]○ UNCONFIGURED[/dim]"

        hotkey_markup = f"[bold #ffb86c]{hotkey}[/bold #ffb86c]" if 1 <= index <= 9 else "[dim]   [/dim]"
        prov_markup = f"[bold {color}]{p_tag:<12}[/bold {color}]"
        display = item.display_name[:24].ljust(24)
        mid = item.model_id[:18].ljust(18)

        line = f"{hotkey_markup} {prov_markup} {display} [dim]{mid}[/dim] {status_markup}"
        return Text.from_markup(line)

    def _refresh_list(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            matching_items = list(self.all_items)
        else:
            matching_items = [
                it for it in self.all_items
                if q in it.model_id.lower()
                or q in it.display_name.lower()
                or q in it.provider_slug.lower()
                or q in it.provider_name.lower()
            ]
            if not matching_items:
                matching_items = [
                    PaletteModelItem(
                        provider_slug=self.active_prov,
                        provider_name="Custom",
                        model_id=query.strip(),
                        display_name=f"Custom ({self.active_prov.upper()})",
                        is_available=True,
                        is_active=False,
                    )
                ]

        self._filtered_items = matching_items
        self._selectable_items = []
        self._option_item_map = {}

        opt_list = self.query_one("#switcher-list", OptionList)
        opt_list.clear_options()

        ready_group = [it for it in matching_items if it.is_available]
        unconfigured_group = [it for it in matching_items if not it.is_available]

        global_idx = 1
        if ready_group:
            opt_list.add_option(Option(Text.from_markup("[bold #50fa7b]── ◈ READY ENGINES ──────────────────────────────────────[/]"), id="hdr-ready", disabled=True))
            for item in ready_group:
                hotkey_idx = global_idx if 1 <= global_idx <= 9 else 0
                prompt = self._format_option_text(item, hotkey_idx)
                opt_id = f"opt-{global_idx}"
                opt_list.add_option(Option(prompt, id=opt_id))
                self._option_item_map[opt_id] = item
                self._selectable_items.append(item)
                global_idx += 1

        if unconfigured_group:
            opt_list.add_option(Option(Text.from_markup("[bold #6272a4]── ◈ UNCONFIGURED ENGINES (Press Enter to Setup) ──────[/]"), id="hdr-unconfigured", disabled=True))
            for item in unconfigured_group:
                hotkey_idx = global_idx if 1 <= global_idx <= 9 else 0
                prompt = self._format_option_text(item, hotkey_idx)
                opt_id = f"opt-{global_idx}"
                opt_list.add_option(Option(prompt, id=opt_id))
                self._option_item_map[opt_id] = item
                self._selectable_items.append(item)
                global_idx += 1

        if opt_list.option_count > 0:
            opt_list.highlighted = 1 if opt_list.option_count > 1 else 0

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
        if 0 <= idx < len(self._selectable_items):
            self._activate_item(self._selectable_items[idx])

    def activate_highlighted(self) -> None:
        lst = self.query_one("#switcher-list", OptionList)
        if lst.highlighted is not None:
            try:
                opt = lst.get_option_at_index(lst.highlighted)
                if opt and opt.id in self._option_item_map:
                    self._activate_item(self._option_item_map[opt.id])
                    return
            except Exception:
                pass
        if self._selectable_items:
            self._activate_item(self._selectable_items[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id in self._option_item_map:
            self._activate_item(self._option_item_map[event.option.id])
        elif 0 <= event.option_index < len(self._selectable_items):
            self._activate_item(self._selectable_items[event.option_index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-switcher-close", "switcher-close-btn"):
            self.dismiss(None)

    def _activate_item(self, item: PaletteModelItem) -> None:
        prov = item.provider_slug
        if not item.is_available:
            self.dismiss({"action": "setup_provider", "provider": prov})
            return

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

        self.dismiss({"action": "switch_model", "provider": prov, "model": model_val})


class BakerySettingsModal(ModalScreen):
    """Local-first Studio Settings & Invariants Configuration Modal."""

    DEFAULT_CSS = """
    BakerySettingsModal {
        align: center middle;
    }
    #settings-dialog {
        padding: 1 3;
        background: #10141f;
        border: heavy #d18f52;
        width: 88;
        max-width: 94;
        min-width: 78;
        height: auto;
        max-height: 32;
    }
    .settings-sec-header {
        text-style: bold;
        color: #ffb86c;
        margin-top: 0;
        margin-bottom: 0;
        height: 1;
    }
    .settings-header-row {
        height: 1;
        layout: horizontal;
        align: left middle;
        margin-bottom: 0;
    }
    .settings-header-title {
        width: 1fr;
        text-style: bold;
        color: #ffb86c;
    }
    .settings-mini-btn {
        height: 1;
        min-width: 15;
        border: none;
        background: #212330;
        color: #ffb86c;
        padding: 0 1;
        text-style: bold;
    }
    .settings-mini-btn:hover {
        background: #2a2e3d;
        color: #50fa7b;
    }
    .settings-select-row {
        height: auto;
        layout: horizontal;
        margin-bottom: 1;
    }
    .settings-col {
        width: 1fr;
        height: auto;
        margin-right: 3;
    }
    .settings-col:last-of-type {
        margin-right: 0;
    }
    #settings-select-template, #settings-select-persona,
    #settings-select-nav-style, #settings-select-preset,
    #settings-select-lab-mode, #settings-select-voice-engine {
        height: 3;
        margin-top: 0;
        margin-bottom: 0;
        border: none;
        background: transparent;
    }
    BakerySettingsModal SelectCurrent {
        background: #212330;
        border: round #d18f52;
        color: #ffffff;
        height: 3;
        padding: 0 1;
    }
    BakerySettingsModal SelectCurrent:focus {
        border: round #ffb86c;
        background: #2a2e3d;
    }
    BakerySettingsModal SelectCurrent Static#label {
        color: #ffffff !important;
        text-style: bold;
    }
    BakerySettingsModal SelectCurrent .arrow {
        color: #ffb86c;
    }
    .settings-info-box {
        background: #0c0e14;
        border: round #2a2e3d;
        color: #8be9fd;
        padding: 0 1;
        height: auto;
        margin-top: 0;
        margin-bottom: 1;
    }
    #settings-engine-row {
        align: left middle;
        height: 3;
        margin-top: 0;
        margin-bottom: 1;
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
        margin-top: 0;
        align: right middle;
    }
    #settings-action-bar Button {
        margin-left: 1;
        min-width: 18;
    }
    """ + MODAL_BASE_CSS

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            with Horizontal(classes="modal-header-bar"):
                yield Label("[bold #ffb86c][§] BREADWINNER SETTINGS[/bold #ffb86c] [dim]• Studio Invariants[/dim]", classes="modal-header-title")
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
                    with Horizontal(classes="settings-header-row"):
                        yield Label("[bold #ffb86c]Default Narrative Persona:[/bold #ffb86c]", classes="settings-header-title")
                        yield Button("✦ Synth", id="btn-settings-synth-persona", classes="settings-mini-btn")
                    yield Select(persona_opts, value=cur_persona, id="settings-select-persona")

            nav_opts = [
                ("Auto-Adaptive (<100 cols)", "auto"),
                ("Sidebar Rail (Classic)", "sidebar"),
                ("Tiered Top Deck (Ribbon)", "top_deck"),
            ]
            cur_nav = getattr(settings, "navigation_style", "auto")
            preset_opts = [
                ("Normal (120×36 Balanced)", "normal"),
                ("Split View (88×38 Tiered)", "split"),
                ("Panoramic Fullscreen", "fullscreen"),
            ]
            cur_preset = getattr(settings, "default_preset", "normal")

            with Horizontal(classes="settings-select-row"):
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Navigation Ribbon Style:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(nav_opts, value=cur_nav, id="settings-select-nav-style")
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Default Launch Geometry:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(preset_opts, value=cur_preset, id="settings-select-preset")

            lab_opts = [
                ("Side-by-Side (Comparative)", "side_by_side"),
                ("Stacked Columns (Vertical)", "stacked"),
            ]
            cur_lab = getattr(settings, "studio_lab_layout", "side_by_side")
            voice_engine_opts = [
                ("Auto-detect (Fastest Available)", "auto"),
                ("Apple MLX Whisper (Apple Silicon)", "mlx-whisper"),
                ("Groq Whisper (Ultra-low latency)", "groq-whisper"),
                ("OpenAI Whisper API", "openai-whisper"),
                ("Faster-Whisper (Local CPU/CUDA)", "faster-whisper"),
            ]
            cur_voice_eng = getattr(settings, "voice_stt_engine", "auto")

            with Horizontal(classes="settings-select-row"):
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Bullet Lab Layout Mode:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(lab_opts, value=cur_lab, id="settings-select-lab-mode")
                with Vertical(classes="settings-col"):
                    yield Label("[bold #ffb86c]Voice STT Speech Engine:[/bold #ffb86c]", classes="settings-sec-header")
                    yield Select(voice_engine_opts, value=cur_voice_eng, id="settings-select-voice-engine")

            with Vertical(classes="settings-info-box"):
                yield Label(f"[dim]Pantry:[/] [white]{settings.pantry_dir.name}[/]  •  [dim]DB:[/] [white]{settings.database_path.name}[/]  •  [dim]CSV:[/] [white]{settings.csv_tracker_path.name if settings.csv_tracker_path else 'Disabled'}[/]")

            with Horizontal(id="settings-action-bar"):
                yield Button("Cancel (Esc)", variant="error", id="btn-settings-cancel")
                yield Button("Save Settings (Enter)", variant="success", id="btn-settings-save")

    def on_mount(self) -> None:
        try:
            self.query_one("#settings-select-template").focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-settings-cancel", "btn-settings-close"):
            self.dismiss(None)
            return

        if bid == "btn-settings-switch-engine":
            self.dismiss({"action": "switch_model"})
            return

        if bid == "btn-settings-synth-persona":
            from breadwinner.ui.screens.studio import PersonaSynthesizerModal
            def on_synth_done(slug: Optional[str]):
                if slug:
                    try:
                        sel = self.query_one("#settings-select-persona", Select)
                        opts = get_persona_select_options()
                        sel.set_options(opts)
                        sel.value = slug
                    except Exception:
                        pass
                    if hasattr(self.app, "_refresh_persona_select"):
                        self.app._refresh_persona_select(slug)
            self.app.push_screen(PersonaSynthesizerModal(), on_synth_done)
            return

        if bid == "btn-settings-save":
            tmpl_val = str(self.query_one("#settings-select-template", Select).value)
            pers_val = str(self.query_one("#settings-select-persona", Select).value)
            nav_val = str(self.query_one("#settings-select-nav-style", Select).value)
            preset_val = str(self.query_one("#settings-select-preset", Select).value)
            lab_val = str(self.query_one("#settings-select-lab-mode", Select).value)
            voice_eng_val = str(self.query_one("#settings-select-voice-engine", Select).value)

            settings.default_template = tmpl_val
            settings.default_persona = pers_val
            settings.navigation_style = nav_val
            settings.default_preset = preset_val
            settings.studio_lab_layout = lab_val
            settings.voice_stt_engine = voice_eng_val

            save_env_config({
                "DEFAULT_TEMPLATE": tmpl_val,
                "DEFAULT_PERSONA": pers_val,
                "NAVIGATION_STYLE": nav_val,
                "DEFAULT_PRESET": preset_val,
                "STUDIO_LAB_LAYOUT": lab_val,
                "VOICE_STT_ENGINE": voice_eng_val,
            })

            self.dismiss({
                "saved": True,
                "template": tmpl_val,
                "persona": pers_val,
                "navigation_style": nav_val,
                "default_preset": preset_val,
                "studio_lab_layout": lab_val,
                "voice_stt_engine": voice_eng_val,
            })


class ModelsScreenMixin:
    """Mixin for models palette, active provider state, and settings actions."""

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

    def get_active_provider_name(self) -> str:
        return (getattr(settings, "breadwinner_llm_provider", None) or "GEMINI").upper()

    def action_switch_model(self) -> None:
        self.push_screen(ModelQuickSwitcherModal(), self._on_model_switched)

    def _on_model_switched(self, result: Optional[Dict[str, Any]]) -> None:
        if not result:
            self._pending_bake_retry = None
            return

        if result.get("action") == "setup_provider":
            prov = result.get("provider", "gemini")
            staged_sources = []
            if getattr(self, "_pending_bake_retry", None):
                retry_info = self._pending_bake_retry
                target_info = retry_info.get("target_info", {})
                staged_sources = target_info.get("sources", [])
            self.push_screen(
                BakeryWelcomeModal(
                    pantry=self.pantry,
                    initial_step="ai",
                    initial_provider=prov,
                    initial_sources=staged_sources,
                ),
                self._on_welcome_modal_dismissed,
            )
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

        # Automatically retry pending bake if initiated from an error recovery flow
        if getattr(self, "_pending_bake_retry", None):
            retry_info = self._pending_bake_retry
            self._pending_bake_retry = None
            task_type = retry_info.get("task_type")
            target_info = retry_info.get("target_info", {})
            if task_type == "ingest":
                sources = target_info.get("sources", [])
                if sources:
                    self.notify(f"Re-firing hearth with {model}...", title="Retrying Ingestion")
                    self.push_screen(
                        BakingModal(task_type="ingest", target_info=target_info),
                        self._on_ingest_baking_modal_dismissed
                    )
            elif task_type == "tailor":
                self.notify(f"Re-firing hearth with {model}...", title="Retrying Bake")
                self.push_screen(
                    BakingModal(task_type="tailor", target_info=target_info),
                    self._on_tailoring_modal_dismissed
                )

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
                f"Saved: Template={result.get('template')}, Persona={result.get('persona')}, Nav={result.get('navigation_style')}",
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
            nav_style = result.get("navigation_style")
            if nav_style == "top_deck":
                self.apply_layout_preset("split", resize_window=False)
            elif nav_style == "sidebar":
                self.apply_layout_preset("normal", resize_window=False)
            lab_mode = result.get("studio_lab_layout")
            if lab_mode:
                try:
                    lab_split = self.query_one("#studio-lab-split")
                    btn_lab_stack = self.query_one("#btn-lab-toggle-stack", Button)
                    if lab_mode == "stacked":
                        lab_split.add_class("-vertical-stack")
                        btn_lab_stack.label = "⇋ Side-by-Side"
                    else:
                        lab_split.remove_class("-vertical-stack")
                        btn_lab_stack.label = "⇋ Stack"
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
                    marker = "  * [►] **" if m.is_active else "  * "
                    suffix = "** (Active)" if m.is_active else ""
                    lines.append(f"{marker}`{m.id}`{suffix}")
            else:
                lines.append("- *No models detected or credentials missing in .env*")

        models_box.update("\n".join(lines))
