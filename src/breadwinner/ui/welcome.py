"""First-run interactive onboarding modal for Breadwinner with Pokémon-style bakery aesthetic.

Supports a guided 3-step setup:
Step 1: Configure AI Providers & API Keys (tactile multi-provider switcher pills & real-time badges)
Step 2: Live Model Discovery & Default Model Selection (real-time API handshake)
Step 3: Stock the Career Pantry (Resume Dropzone & Demo Loaf)
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Label, Button, Input, TextArea, Select
from textual.screen import ModalScreen

from breadwinner.config import settings, save_env_config
from breadwinner.core.pantry import PantryManager
from breadwinner.providers.discovery import ProviderDiscovery, PROVIDER_MODELS
from breadwinner.providers.registry import (
    ProviderSpec,
    PROVIDERS_REGISTRY,
    get_provider_spec,
    get_provider_options,
    get_provider_env_vars,
    get_configured_initial_keys,
)
from breadwinner.ui.retro import PokemonBakeryCounter


WELCOME_MODAL_CSS = """
BakeryWelcomeModal {
    align: center middle;
}

#welcome-container {
    width: 90%;
    min-width: 78;
    max-width: 104;
    height: auto;
    max-height: 96%;
    background: #10141f;
    border: heavy #d4a373;
    padding: 1 2;
    overflow-x: hidden;
    overflow-y: hidden;
}

.welcome-title {
    text-align: center;
    content-align: center middle;
    width: 100%;
    color: #f4a261;
    text-style: bold;
    margin-bottom: 0;
}

.welcome-subtitle {
    text-align: center;
    content-align: center middle;
    width: 100%;
    color: #a89f91;
    margin-bottom: 1;
}

#welcome-mascot-row {
    height: auto;
    margin-bottom: 1;
}

.step-heading {
    text-align: center;
    content-align: center middle;
    width: 100%;
    color: #f4a261;
    text-style: bold;
    margin-bottom: 0;
}

.step-subheading {
    text-align: center;
    content-align: center middle;
    color: #a89f91;
    margin-bottom: 1;
    width: 100%;
}

/* ========================================================================= */
/* STEP 1: CONFIGURE AI ENGINES & API KEYS (DYNAMIC PILL SWITCHER)           */
/* ========================================================================= */

#welcome-ai-step {
    height: auto;
    margin-bottom: 1;
}

.pills-row {
    height: 1;
    width: 100%;
    align: center middle;
    margin-bottom: 1;
    overflow: hidden hidden;
}

Button.-style-default.prov-pill, Button.prov-pill {
    height: 1;
    width: 1fr;
    min-width: 8;
    max-width: 18;
    margin: 0 1;
    padding: 0;
    border: none;
    background: #232d42;
    color: #e2e8f0;
    text-style: bold;
}


Button.-style-default.prov-pill:hover, Button.prov-pill:hover {
    background: #3b4d6e;
    color: #ffffff;
    border: none;
}

Button.-style-default.prov-pill:focus, Button.prov-pill:focus {
    border: none;
}

Button.-style-default.configured-pill, Button.prov-pill.configured-pill {
    background: #17382d;
    color: #a7f3d0;
    text-style: bold;
    border: none;
}

Button.-style-default.configured-pill:hover, Button.prov-pill.configured-pill:hover {
    background: #235443;
    color: #ffffff;
    border: none;
}

Button.-style-default.active-pill, Button.prov-pill.active-pill {
    background: #f4a261;
    color: #0b0e17;
    text-style: bold;
    border: none;
}

Button.-style-default.active-pill:hover, Button.prov-pill.active-pill:hover {
    background: #e76f51;
    color: #0b0e17;
    border: none;
}

#select-welcome-model, #select-active-provider {
    margin-bottom: 1;
}

#select-welcome-model SelectCurrent, #select-active-provider SelectCurrent {
    border: round #d4a373;
    background: #0b0e17;
    color: #fefae0;
}

#input-welcome-api-key, #input-welcome-custom-model {
    height: 3;
    background: #0b0e17;
    border: round #d4a373;
    color: #fefae0;
    margin-bottom: 0;
}

#label-welcome-ai-hint {
    text-align: center;
    height: 1;
    color: #a89f91;
    margin-top: 0;
    margin-bottom: 1;
}

#label-configured-keys-summary {
    text-align: center;
    height: 1;
    margin-top: 0;
    margin-bottom: 1;
}

#welcome-ai-action-bar, #welcome-models-action-bar, #welcome-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
}

#welcome-ai-action-bar Button, #welcome-models-action-bar Button, #welcome-action-bar Button {
    margin: 0 1;
    min-width: 12;
    height: 3;
    padding: 0 1;
}

#btn-welcome-save-ai {
    background: #1b4332;
    color: #d8f3dc;
    border: heavy #52b788;
    text-style: bold;
}

#btn-welcome-save-ai:hover {
    background: #2d6a4f;
}

#btn-welcome-mock-drive {
    background: #582f0e;
    color: #faedcd;
    border: heavy #f4a261;
    text-style: bold;
}

#btn-welcome-mock-drive:hover {
    background: #7f4f24;
}

#btn-welcome-skip-ai {
    background: #1e293b;
    color: #94a3b8;
    border: heavy #475569;
}

#btn-welcome-skip-ai:hover {
    background: #334155;
}

#btn-welcome-exit, #btn-welcome-exit-models, #btn-welcome-exit-pantry {
    background: #3a1515;
    color: #ffcccc;
    border: heavy #e63946;
    text-style: bold;
}

#btn-welcome-exit:hover, #btn-welcome-exit-models:hover, #btn-welcome-exit-pantry:hover {
    background: #5c1e1e;
}

/* ========================================================================= */
/* STEP 2: LIVE MODEL REGISTRY & DEFAULT SELECTION                           */
/* ========================================================================= */

#welcome-models-step {
    height: auto;
    margin-bottom: 0;
    display: none;
}

#label-step2-engine-badge {
    text-align: center;
    height: 1;
    margin-top: 0;
    margin-bottom: 1;
    display: none;
}

#label-live-model-status {
    text-align: center;
    height: 1;
    margin-bottom: 1;
}

#input-welcome-custom-model {
    margin-bottom: 1;
    display: none;
}

#btn-welcome-save-model {
    background: #1b4332;
    color: #d8f3dc;
    border: heavy #52b788;
    text-style: bold;
}

#btn-welcome-save-model:hover {
    background: #2d6a4f;
}

#btn-welcome-back-to-keys {
    background: #1e293b;
    color: #94a3b8;
    border: heavy #475569;
}

#btn-welcome-back-to-keys:hover {
    background: #334155;
}

/* ========================================================================= */
/* STEP 3: PANTRY INGREDIENTS SETUP                                          */
/* ========================================================================= */

#welcome-pantry-step {
    height: auto;
    margin-bottom: 0;
    display: none;
}

#welcome-mode-tabs {
    height: 1;
    align: center middle;
    margin: 1 0;
}

Button.-style-default.tab-btn, Button.tab-btn {
    height: 1;
    min-width: 20;
    margin: 0 1;
    padding: 0 1;
    border: none;
    background: #232d42;
    color: #e2e8f0;
    text-style: bold;
}

Button.-style-default.tab-btn:hover, Button.tab-btn:hover {
    background: #3b4d6e;
    color: #ffffff;
    border: none;
}

Button.-style-default.tab-btn:focus, Button.tab-btn:focus {
    border: none;
}

Button.-style-default.active-tab, Button.tab-btn.active-tab {
    background: #f4a261;
    color: #0b0e17;
    text-style: bold;
    border: none;
}

#welcome-dropzone-box {
    height: auto;
    background: #141926;
    border: round #3d4a63;
    padding: 0 1;
    margin-bottom: 1;
}

.dropzone-label {
    color: #f4a261;
    text-style: bold;
    text-align: center;
    margin: 0;
}

#input-welcome-source {
    height: 3;
    background: #0b0e17;
    border: round #d4a373;
    color: #fefae0;
    margin: 0;
}

#ingredient-badge {
    text-align: center;
    height: 1;
    margin: 0;
}

#welcome-bio-box {
    height: auto;
    display: none;
    margin-bottom: 1;
}

#input-welcome-bio {
    height: 6;
    background: #0b0e17;
    border: round #d4a373;
    color: #fefae0;
}

#btn-welcome-stock {
    background: #1b4332;
    color: #d8f3dc;
    border: heavy #52b788;
    text-style: bold;
}

#btn-welcome-stock:hover {
    background: #2d6a4f;
}

#btn-welcome-demo {
    background: #582f0e;
    color: #faedcd;
    border: heavy #f4a261;
    text-style: bold;
}

#btn-welcome-demo:hover {
    background: #7f4f24;
}

#btn-welcome-skip {
    background: #1e293b;
    color: #94a3b8;
    border: heavy #475569;
}

#btn-welcome-skip:hover {
    background: #334155;
}
"""


class BakeryWelcomeModal(ModalScreen):
    """First-run onboarding window for non-technical users with Pokémon bakery aesthetic."""

    DEFAULT_CSS = WELCOME_MODAL_CSS

    def __init__(self, pantry: PantryManager, initial_step: str = "pantry"):
        super().__init__()
        self.pantry = pantry
        self.initial_step = initial_step
        self.current_step = 1 if initial_step == "ai" else 3
        self.provider_opts: List[Tuple[str, str]] = get_provider_options()

        self.active_provider: str = settings.breadwinner_llm_provider
        if not get_provider_spec(self.active_provider):
            self.active_provider = "gemini"

        self.provider_keys: Dict[str, str] = get_configured_initial_keys()

    def get_configured_provider_slugs(self) -> List[str]:
        """Return list of provider slugs that the user explicitly configured with a key or local/mock."""
        configured = []
        for spec in PROVIDERS_REGISTRY:
            has_key = bool(self.provider_keys.get(spec.slug, "").strip())
            if has_key:
                configured.append(spec.slug)
            elif spec.is_local and spec.slug == self.active_provider:
                configured.append(spec.slug)
        if self.active_provider == "mock" and "mock" not in configured:
            configured.append("mock")
        if not configured:
            configured = [self.active_provider]
        elif self.active_provider not in configured:
            configured.insert(0, self.active_provider)
        return configured

    def get_step2_provider_opts(self) -> List[Tuple[str, str]]:
        """Return provider options formatted with live status indicators for Step 2 selector.

        Strictly includes ONLY providers that have an API key configured or are ready local/mock.
        Unconfigured cloud providers are strictly excluded.
        """
        configured_slugs = self.get_configured_provider_slugs()
        if not configured_slugs:
            configured_slugs = [self.active_provider]

        opts = []
        for slug in configured_slugs:
            spec = get_provider_spec(slug)
            name = spec.name if spec else slug.upper()
            is_local = spec.is_local if spec else False
            has_key = bool(self.provider_keys.get(slug, "").strip())
            if is_local:
                opts.append((f"● {name} (Ready)", slug))
            elif has_key:
                opts.append((f"● {name} (Key set)", slug))
            else:
                opts.append((f"○ {name}", slug))
        return opts

    def render_keys_summary(self) -> str:
        """Render badge summary of configured keys."""
        configured = [
            spec.name
            for spec in PROVIDERS_REGISTRY
            if self.provider_keys.get(spec.slug) and not spec.is_local
        ]
        if configured:
            summary = " • ".join(f"[bold #52b788]{name} ✓[/]" for name in configured)
            return f"[dim]Configured engines:[/] {summary}"
        return "[dim]No keys entered yet. Click any pill above to configure.[/dim]"

    def update_pills(self, active_prov: str) -> None:
        """Update provider switcher pills with active state, configured badges, and styling."""
        for spec in PROVIDERS_REGISTRY:
            try:
                pill = self.query_one(f"#pill-prov-{spec.slug}", Button)
                has_key = bool(self.provider_keys.get(spec.slug, "").strip())
                is_ready = has_key or spec.is_local
                status_icon = "●" if is_ready else "○"
                pill.label = f"{status_icon} {spec.pill_label}"

                pill.remove_class("active-pill")
                pill.remove_class("configured-pill")

                if spec.slug == active_prov:
                    pill.add_class("active-pill")
                elif is_ready:
                    pill.add_class("configured-pill")
            except Exception:
                pass

    def select_provider(self, slug: str) -> None:
        """Select an active provider in Step 1, updating pill states, input, hint, and mascot."""
        spec = get_provider_spec(slug)
        if not spec:
            return
        self.active_provider = slug
        self.update_pills(slug)

        key_input = self.query_one("#input-welcome-api-key", Input)
        hint = self.query_one("#label-welcome-ai-hint", Static)
        mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

        key_input.value = self.provider_keys.get(slug, "")
        key_input.placeholder = spec.key_placeholder
        key_input.disabled = not spec.requires_key
        hint.update(spec.hint_text)

        if self.current_step == 1:
            mascot.set_dialogue(spec.mascot_msg, status=f"Engine: {slug.upper()}")

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Label("CRUMB'S BREADWINNER BAKERY • EST. 2026", classes="welcome-title")
            yield Label(
                "Anti-Hallucination Career Studio • Fresh Resumes from Verified Facts",
                classes="welcome-subtitle",
                id="welcome-subtitle"
            )

            # Nintendo Pokémon-style Bakery Scene (id="welcome-mascot" for test compatibility)
            with Center(id="welcome-mascot-row"):
                yield PokemonBakeryCounter(id="welcome-mascot")

            # -------------------------------------------------------------
            # STEP 1: CONFIGURE AI ENGINES & API KEYS (DYNAMIC PILL SWITCHER)
            # -------------------------------------------------------------
            with Vertical(id="welcome-ai-step"):
                yield Label("STEP 1 OF 3: CONFIGURE AI ENGINES & API KEYS", classes="step-heading")
                yield Label(
                    "[dim]Select any engine pill below to enter its key. Configure multiple or just your favorite![/dim]",
                    classes="step-subheading"
                )

                # Row 1: Cloud Frontier & Gateway (5 pills)
                row1_specs = [s for s in PROVIDERS_REGISTRY if s.category in ("cloud", "gateway")][:5]
                row2_specs = [s for s in PROVIDERS_REGISTRY if s not in row1_specs]

                with Horizontal(classes="pills-row", id="welcome-provider-pills-row1"):
                    for spec in row1_specs:
                        yield Button(f"○ {spec.pill_label}", id=f"pill-prov-{spec.slug}", classes="prov-pill")

                # Row 2: Fast Inference, Local & Offline (5 pills)
                with Horizontal(classes="pills-row", id="welcome-provider-pills-row2"):
                    for spec in row2_specs:
                        yield Button(f"○ {spec.pill_label}", id=f"pill-prov-{spec.slug}", classes="prov-pill")

                active_spec = get_provider_spec(self.active_provider) or PROVIDERS_REGISTRY[0]
                initial_key = self.provider_keys.get(self.active_provider, "")

                yield Input(
                    value=initial_key,
                    placeholder=active_spec.key_placeholder,
                    password=True,
                    disabled=not active_spec.requires_key,
                    id="input-welcome-api-key"
                )

                yield Static(
                    active_spec.hint_text,
                    id="label-welcome-ai-hint"
                )

                yield Static(
                    self.render_keys_summary(),
                    id="label-configured-keys-summary"
                )

                with Horizontal(id="welcome-ai-action-bar"):
                    yield Button("Next: Discover Models →", variant="success", id="btn-welcome-save-ai")
                    yield Button("Test Drive", variant="warning", id="btn-welcome-mock-drive")
                    yield Button("Skip AI", variant="default", id="btn-welcome-skip-ai")
                    yield Button("Quit", variant="error", id="btn-welcome-exit")

            # -------------------------------------------------------------
            # STEP 2: LIVE MODEL DISCOVERY & DEFAULT SELECTION
            # -------------------------------------------------------------
            with Vertical(id="welcome-models-step"):
                yield Label("STEP 2 OF 3: LIVE MODEL DISCOVERY & DEFAULT SELECTION", classes="step-heading")
                yield Label(
                    "[dim]Live API handshake complete. Select your active engine and default model from the live registry below.[/dim]",
                    classes="step-subheading"
                )

                yield Static(
                    "",
                    id="label-step2-engine-badge"
                )

                yield Select(
                    self.get_step2_provider_opts(),
                    value=self.active_provider,
                    id="select-active-provider"
                )

                yield Static(
                    "[dim]Connecting to provider model registry...[/dim]",
                    id="label-live-model-status"
                )

                initial_models = list(PROVIDER_MODELS.get(self.active_provider, [("Default Model", "default")]))
                initial_models.append(("[*] Custom Model ID...", "custom"))
                yield Select(
                    initial_models,
                    value=initial_models[0][1],
                    id="select-welcome-model"
                )

                yield Input(
                    placeholder="Enter custom model ID (e.g. gemini-3.8-flash, claude-3-7-sonnet...)",
                    id="input-welcome-custom-model"
                )

                with Horizontal(id="welcome-models-action-bar"):
                    yield Button("Save & Continue to Pantry →", variant="success", id="btn-welcome-save-model")
                    yield Button("← Back to Keys", variant="default", id="btn-welcome-back-to-keys")
                    yield Button("Quit", variant="error", id="btn-welcome-exit-models")

            # -------------------------------------------------------------
            # STEP 3: CAREER PANTRY SETUP
            # -------------------------------------------------------------
            with Vertical(id="welcome-pantry-step"):
                yield Label("STEP 3 OF 3: STOCK THE PANTRY (CAREER INGREDIENTS)", classes="step-heading")
                # Input Mode Selector Tabs
                with Horizontal(id="welcome-mode-tabs"):
                    yield Button("Drop File / URL (Recommended)", id="btn-tab-dropzone", classes="tab-btn active-tab")
                    yield Button("Paste Bio Notes", id="btn-tab-bio", classes="tab-btn")

                # MODE A: Tactile Drag & Drop Dropzone Box
                with Vertical(id="welcome-dropzone-box"):
                    yield Label("DOUGH BIN: Drag & drop resume (.pdf, .docx, .json, .md) or paste link", classes="dropzone-label")
                    yield Input(
                        placeholder="Drop file from desktop or paste URL (e.g. ~/resume.pdf or https://...)",
                        id="input-welcome-source"
                    )
                    yield Static("[dim]Waiting for ingredient drop... (drag file or paste URL)[/dim]", id="ingredient-badge")

                # MODE B: Collapsible Raw Bio Box
                with Vertical(id="welcome-bio-box"):
                    yield TextArea(
                        "",
                        id="input-welcome-bio"
                    )

                # Action Bar
                with Horizontal(id="welcome-action-bar"):
                    yield Button("Stock Pantry (Enter)", variant="success", id="btn-welcome-stock")
                    yield Button("Load Demo Loaf", variant="warning", id="btn-welcome-demo")
                    yield Button("Skip for Now", variant="default", id="btn-welcome-skip")
                    yield Button("Quit", variant="error", id="btn-welcome-exit-pantry")

    def on_mount(self) -> None:
        self.current_step = 1 if self.initial_step == "ai" else 3
        if self.initial_step == "ai":
            self.query_one("#welcome-ai-step").styles.display = "block"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "none"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Welcome, Apprentice! Enter your API key(s) below to ignite the hearth. You can configure multiple providers or just your favorite!",
                status="Step 1 of 3: AI Engine & Keys",
                badge="BREADWINNER SETUP STUDIO"
            )
            self.select_provider(self.active_provider)
        else:
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Welcome, Trainer! Drop your resume or portfolio into the dough bin below, and I'll bake an anti-slop masterpiece!",
                status="Verified Ingredients Only",
                badge="BREADWINNER PANTRY"
            )

    def load_step_2_models(self, provider: str) -> None:
        """Fetch live models for active provider and populate model selector."""
        if self.current_step != 2:
            return

        key = self.provider_keys.get(provider, "")
        status_label = self.query_one("#label-live-model-status", Static)
        model_select = self.query_one("#select-welcome-model", Select)
        custom_input = self.query_one("#input-welcome-custom-model", Input)
        custom_input.styles.display = "none"
        mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

        models, is_live = ProviderDiscovery.fetch_models_with_status(provider, api_key=key)
        models_with_custom = list(models)
        models_with_custom.append(("[*] Custom Model ID...", "custom"))
        model_select.set_options(models_with_custom)
        if models_with_custom:
            model_select.value = models_with_custom[0][1]

        spec = get_provider_spec(provider)
        prov_name = spec.name if spec else provider.upper()
        count = len(models)
        if is_live:
            status_label.update(f"[bold #52b788]✓ Live API Handshake Success:[/] Discovered {count} models directly from {prov_name}!")
            mascot.set_dialogue(
                f"Connected to {prov_name}! Discovered {count} live models. Select your default model or type a custom one!",
                status=f"Live Handshake: {count} Models",
                badge="LIVE REGISTRY"
            )
        else:
            status_label.update(f"[dim]Showing {count} verified curated models for {prov_name}[/dim]")
            mascot.set_dialogue(
                f"Selected {prov_name}. Pick your default model from the verified list below or enter a custom model ID.",
                status=f"Curated: {count} Models",
                badge="MODEL SELECTION"
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle dropdown updates for Step 2 model and provider selection."""
        if event.select.id == "select-active-provider":
            # STEP 2: Active provider changed
            if self.current_step == 2 and event.value != Select.BLANK:
                new_prov = str(event.value)
                self.active_provider = new_prov
                self.load_step_2_models(new_prov)

        elif event.select.id == "select-welcome-model":
            # STEP 2: Model changed (Custom Model toggle)
            custom_input = self.query_one("#input-welcome-custom-model", Input)
            if str(event.value) == "custom":
                custom_input.styles.display = "block"
                custom_input.focus()
            else:
                custom_input.styles.display = "none"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle reactive updates as user types."""
        if event.input.id == "input-welcome-api-key":
            prov = self.active_provider
            spec = get_provider_spec(prov)
            if spec and spec.requires_key:
                self.provider_keys[prov] = event.value.strip()
                summary_label = self.query_one("#label-configured-keys-summary", Static)
                summary_label.update(self.render_keys_summary())
                self.update_pills(prov)
            return

        if event.input.id != "input-welcome-source":
            return

        raw_val = event.value.strip()
        badge = self.query_one("#ingredient-badge", Static)
        mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

        if not raw_val:
            badge.update("[dim]Waiting for ingredient drop... (drag file or paste URL)[/dim]")
            mascot.set_dialogue(
                "Welcome, Trainer! Drop your resume or portfolio into the dough bin below, and I'll bake an anti-slop masterpiece!",
                status="Verified Ingredients Only"
            )
            return

        from breadwinner.core.ingestor import clean_user_input_path, normalize_source
        clean = clean_user_input_path(raw_val)
        display_label, kind = normalize_source(clean)
        path_obj = Path(os.path.expanduser(clean))

        if kind == "file" or path_obj.is_file():
            size_kb = max(1, path_obj.stat().st_size // 1024) if path_obj.exists() else 10
            ext = path_obj.suffix.lower()
            ext_names = {
                ".pdf": "PDF Document",
                ".docx": "Word Document",
                ".json": "JSON Resume",
                ".md": "Markdown Notes",
                ".txt": "Plain Text Notes"
            }
            doc_type = ext_names.get(ext, f"{ext.upper()} File")
            badge.update(f"[bold #52b788]✓ INGREDIENT FOUND:[/] [bold white]{path_obj.name}[/] [dim]({size_kb} KB • {doc_type})[/]")
            mascot.set_dialogue(
                f"Fresh {doc_type} detected ({path_obj.name})! Click [Stock Pantry] to knead your profile!",
                status="Ingredient Verified"
            )
        elif kind == "url":
            badge.update(f"[bold #52b788]✓ WEB PORTFOLIO:[/] [bold white]{display_label}[/] [dim](Universal Scraper Ready)[/]")
            mascot.set_dialogue(
                f"Target portfolio identified ({display_label})! I'll scrape your case studies and structure your pantry facts!",
                status="Online Portfolio"
            )
        else:
            badge.update(f"[bold #f4a261]• Input:[/] [white]{clean}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        # Quick Provider Switcher Pills
        if bid and bid.startswith("pill-prov-"):
            target_prov = bid.replace("pill-prov-", "")
            self.select_provider(target_prov)
            return

        # -------------------------------------------------------------
        # STEP 1 -> STEP 2 (Save Keys & Trigger Live Discovery)
        # -------------------------------------------------------------
        if bid == "btn-welcome-save-ai":
            current_prov = self.active_provider
            spec = get_provider_spec(current_prov)

            key_val = self.query_one("#input-welcome-api-key", Input).value.strip()
            if key_val and spec and spec.requires_key:
                self.provider_keys[current_prov] = key_val

            has_any_key = any(bool(k.strip()) for k in self.provider_keys.values())

            if spec and spec.requires_key and not self.provider_keys.get(current_prov) and not has_any_key:
                self.app.notify("Please enter an API key, or choose 'Test Drive'!", severity="warning")
                return

            # If current active provider has no key and is not local, switch to first configured provider
            if spec and spec.requires_key and not self.provider_keys.get(current_prov):
                for p_slug, p_key in self.provider_keys.items():
                    if p_key.strip():
                        current_prov = p_slug
                        self.active_provider = p_slug
                        break

            # Save all non-empty configured keys into .env
            env_vars: Dict[str, str] = {
                "BREADWINNER_LLM_PROVIDER": current_prov,
                "AUTO_GENERATE_PDF": "true",
            }
            env_key_map = get_provider_env_vars()
            for p, k in self.provider_keys.items():
                if k and p in env_key_map:
                    env_vars[env_key_map[p]] = k
            save_env_config(env_vars)

            # Transition to Step 2
            self.current_step = 2
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "block"
            self.query_one("#welcome-pantry-step").styles.display = "none"

            opts = self.get_step2_provider_opts()
            active_select = self.query_one("#select-active-provider", Select)
            active_select.set_options(opts)
            if current_prov not in [val for _, val in opts]:
                current_prov = opts[0][1]
                self.active_provider = current_prov
            active_select.value = current_prov

            engine_badge = self.query_one("#label-step2-engine-badge", Static)
            if len(opts) == 1:
                active_select.styles.display = "none"
                active_spec = get_provider_spec(current_prov)
                prov_name = active_spec.name if active_spec else current_prov.upper()
                engine_badge.update(
                    f"[bold #f4a261]ENGINE:[/] [bold #50fa7b]{prov_name}[/]  •  [dim]Live API Connected ✓[/dim]"
                )
                engine_badge.styles.display = "block"
            else:
                active_select.styles.display = "block"
                engine_badge.styles.display = "none"

            self.load_step_2_models(current_prov)

        # -------------------------------------------------------------
        # STEP 2 -> STEP 3 (Save Default Model & Transition to Pantry)
        # -------------------------------------------------------------
        elif bid == "btn-welcome-save-model":
            active_prov = self.active_provider
            sel_widget = self.query_one("#select-active-provider", Select)
            if sel_widget.value != Select.BLANK:
                active_prov = str(sel_widget.value)
            model_val = str(self.query_one("#select-welcome-model", Select).value)
            custom_model_val = self.query_one("#input-welcome-custom-model", Input).value.strip()

            if model_val == "custom":
                if not custom_model_val:
                    self.app.notify("Please enter a custom model ID!", severity="warning")
                    return
                model_val = custom_model_val

            env_vars: Dict[str, str] = {
                "BREADWINNER_LLM_PROVIDER": active_prov,
                "AUTO_GENERATE_PDF": "true",
            }
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
            if active_prov in model_env_map and model_val:
                env_vars[model_env_map[active_prov]] = model_val
            if active_prov == "lmstudio":
                env_vars["LMSTUDIO_BASE_URL"] = "http://localhost:1234/v1"
            elif active_prov == "ollama":
                env_vars["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"

            save_env_config(env_vars)

            self.current_step = 3
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                f"Hearth fire lit with {active_prov.upper()} ({model_val})! Drop your resume or click Load Demo Loaf to stock your pantry!",
                status="Step 3 of 3: Stock Career Pantry",
                badge="CRUMB'S PANTRY"
            )
            self.app.notify(f"✓ AI Engine Configured: {active_prov.upper()} ({model_val})", title="Oven Fire Lit")
            self.query_one("#input-welcome-source", Input).focus()

        # -------------------------------------------------------------
        # STEP 2 -> STEP 1 (Back to API Keys)
        # -------------------------------------------------------------
        elif bid == "btn-welcome-back-to-keys":
            self.current_step = 1
            self.query_one("#welcome-ai-step").styles.display = "block"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "none"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Back to keys! Configure more providers or update existing keys.",
                status="Step 1 of 3: AI Engine & Keys",
                badge="SETUP STUDIO"
            )
            self.select_provider(self.active_provider)

        # -------------------------------------------------------------
        # Instant Test Drive / Skip
        # -------------------------------------------------------------
        elif bid == "btn-welcome-mock-drive":
            save_env_config({
                "BREADWINNER_LLM_PROVIDER": "mock",
                "AUTO_GENERATE_PDF": "true"
            })
            self.current_step = 3
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Offline Mock Engine ready! Drop your resume or click Load Demo Loaf to start baking!",
                status="Step 3 of 3: Stock Career Pantry",
                badge="CRUMB'S PANTRY"
            )
            self.app.notify("✓ Instant Test Drive Mode Enabled (Mock Engine)", title="Mock Engine")
            self.query_one("#input-welcome-source", Input).focus()

        elif bid == "btn-welcome-skip-ai":
            self.current_step = 3
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Skipped AI setup. Drop your resume or click Load Demo Loaf to stock your pantry!",
                status="Step 3 of 3: Stock Career Pantry",
                badge="CRUMB'S PANTRY"
            )
            self.query_one("#input-welcome-source", Input).focus()

        # -------------------------------------------------------------
        # STEP 3: Career Pantry Actions
        # -------------------------------------------------------------
        elif bid == "btn-tab-dropzone":
            self.query_one("#welcome-dropzone-box").styles.display = "block"
            self.query_one("#welcome-bio-box").styles.display = "none"
            self.query_one("#btn-tab-dropzone").add_class("active-tab")
            self.query_one("#btn-tab-bio").remove_class("active-tab")
            self.query_one("#input-welcome-source", Input).focus()

        elif bid == "btn-tab-bio":
            self.query_one("#welcome-dropzone-box").styles.display = "none"
            self.query_one("#welcome-bio-box").styles.display = "block"
            self.query_one("#btn-tab-bio").add_class("active-tab")
            self.query_one("#btn-tab-dropzone").remove_class("active-tab")
            self.query_one("#input-welcome-bio", TextArea).focus()

        elif bid == "btn-welcome-stock":
            from breadwinner.core.ingestor import clean_user_input_path, normalize_source
            source_raw = self.query_one("#input-welcome-source", Input).value.strip()
            clean_source = clean_user_input_path(source_raw)

            bio_val = self.query_one("#input-welcome-bio", TextArea).text.strip()

            if clean_source:
                display_label, kind = normalize_source(clean_source)
                final_source = display_label if kind == "url" else clean_source
                self.dismiss({"action": "import", "source": final_source})
            elif bio_val:
                self.dismiss({"action": "import", "source": bio_val})
            else:
                self.app.notify("Please drop a file, paste a link, or click 'Load Demo Loaf'!", severity="warning")

        elif bid == "btn-welcome-demo":
            self.dismiss({"action": "demo"})

        elif bid in ("btn-welcome-exit", "btn-welcome-exit-models", "btn-welcome-exit-pantry"):
            self.app.exit()
            return

        else:
            self.dismiss(None)
