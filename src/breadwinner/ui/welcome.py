"""First-run interactive onboarding modal for Breadwinner with Pokémon-style bakery aesthetic.

Supports a guided 3-step setup:
Step 1: Configure AI Providers & API Keys (multi-provider switcher pills & status badges)
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
from breadwinner.providers.discovery import ProviderDiscovery
from breadwinner.ui.retro import PokemonBakeryCounter


WELCOME_MODAL_CSS = """
BakeryWelcomeModal {
    align: center middle;
}

#welcome-container {
    width: 96;
    height: auto;
    max-height: 94%;
    background: #10141f;
    border: heavy #d4a373;
    padding: 1 2;
    overflow-x: hidden;
}

.welcome-title {
    text-align: center;
    color: #f4a261;
    text-style: bold;
    margin-bottom: 0;
}

.welcome-subtitle {
    text-align: center;
    color: #a89f91;
    margin-bottom: 1;
}

#welcome-mascot-row {
    height: auto;
    margin-bottom: 1;
}

.step-heading {
    text-align: center;
    color: #f4a261;
    text-style: bold;
    margin-bottom: 0;
}

.step-subheading {
    text-align: center;
    color: #a89f91;
    margin-bottom: 1;
    width: 100%;
}

/* ========================================================================= */
/* STEP 1: CONFIGURE AI ENGINES & API KEYS                                   */
/* ========================================================================= */

#welcome-ai-step {
    height: auto;
    margin-bottom: 1;
}

#welcome-provider-pills {
    height: 1;
    align: center middle;
    margin-bottom: 1;
}

.prov-pill {
    height: 1;
    min-width: 14;
    margin: 0 1;
    padding: 0 1;
    border: none;
    background: #1a2234;
    color: #94a3b8;
}

.prov-pill:hover {
    background: #25334d;
    color: #fefae0;
}

.active-pill {
    background: #2b3954;
    color: #fefae0;
    text-style: bold;
    border-bottom: heavy #52b788;
}

#select-welcome-provider, #select-welcome-model, #select-active-provider {
    margin-bottom: 1;
}

#select-welcome-provider SelectCurrent, #select-welcome-model SelectCurrent, #select-active-provider SelectCurrent {
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
}

#welcome-mode-tabs {
    height: 1;
    align: center middle;
    margin: 1 0;
}

.tab-btn {
    height: 1;
    min-width: 20;
    margin: 0 1;
    padding: 0 1;
    border: none;
    background: #1a2234;
    color: #94a3b8;
}

.tab-btn:hover {
    background: #25334d;
    color: #fefae0;
}

.active-tab {
    background: #2b3954;
    color: #fefae0;
    text-style: bold;
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
    display: none;
    height: 6;
    margin-bottom: 1;
}

#input-welcome-bio {
    height: 1fr;
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

PROVIDER_MODELS: Dict[str, List[Tuple[str, str]]] = {
    "gemini": [
        ("Gemini 2.0 Flash (Fastest, 1M context - Recommended)", "gemini-2.0-flash"),
        ("Gemini 2.0 Flash-Lite (Ultra-fast, lowest latency)", "gemini-2.0-flash-lite"),
        ("Gemini 1.5 Pro (Deep reasoning & 2M context)", "gemini-1.5-pro"),
        ("Gemini 1.5 Flash (Ultra-low latency legacy)", "gemini-1.5-flash"),
    ],
    "openrouter": [
        ("Claude 3.7 Sonnet (Anthropic flagship via OpenRouter)", "anthropic/claude-3.7-sonnet"),
        ("Claude 3.5 Sonnet (High intelligence via OpenRouter)", "anthropic/claude-3.5-sonnet"),
        ("GPT-4o (OpenAI flagship via OpenRouter)", "openai/gpt-4o"),
        ("Gemini 2.0 Flash (Google via OpenRouter)", "google/gemini-2.0-flash-001"),
        ("DeepSeek R1 (Chain of thought logic via OpenRouter)", "deepseek/deepseek-r1"),
        ("Llama 3.3 70B (Meta open weights via OpenRouter)", "meta-llama/llama-3.3-70b-instruct"),
    ],
    "anthropic": [
        ("Claude 3.7 Sonnet (Hybrid fast/extended reasoning - Recommended)", "claude-3-7-sonnet-20250219"),
        ("Claude 3.5 Sonnet (Gold standard prose & precision)", "claude-3-5-sonnet-20241022"),
        ("Claude 3.5 Haiku (Fast & affordable lightweight model)", "claude-3-5-haiku-20241022"),
    ],
    "openai": [
        ("GPT-4o (Flagship multimodal intelligence - Recommended)", "gpt-4o"),
        ("GPT-4o Mini (High-speed & cost-efficient)", "gpt-4o-mini"),
        ("o3-mini (High-speed STEM & logic reasoning)", "o3-mini"),
        ("o1 (Deep analytical complex reasoning)", "o1"),
    ],
    "deepseek": [
        ("DeepSeek-V3 Chat (Fast reasoning & coding - Default)", "deepseek-chat"),
        ("DeepSeek-R1 Reasoner (Chain-of-thought logic)", "deepseek-reasoner"),
    ],
    "groq": [
        ("Llama 3.3 70B (High speed versatile - Default)", "llama-3.3-70b-versatile"),
        ("Qwen 2.5 32B (Advanced reasoning)", "qwen-2.5-32b"),
        ("Llama 3.1 8B Instant (Sub-second speed)", "llama-3.1-8b-instant"),
    ],
    "mistral": [
        ("Mistral Large (Premier frontier reasoning)", "mistral-large-latest"),
        ("Codestral (State-of-the-art coding)", "codestral-latest"),
        ("Mistral Small (Fast & responsive)", "mistral-small-latest"),
    ],
    "lmstudio": [
        ("local-model (Active loaded model in LM Studio)", "local-model"),
    ],
    "ollama": [
        ("llama3.2 (Meta Llama 3.2 3B - Default)", "llama3.2"),
        ("mistral (Mistral 7B Instruct)", "mistral"),
        ("deepseek-r1 (DeepSeek R1 Distill)", "deepseek-r1"),
    ],
    "mock": [
        ("mock-deterministic (Offline Anti-Slop Engine)", "mock-deterministic"),
    ],
}


class BakeryWelcomeModal(ModalScreen):
    """First-run onboarding window for non-technical users with Pokémon bakery aesthetic."""

    DEFAULT_CSS = WELCOME_MODAL_CSS

    def __init__(self, pantry: PantryManager, initial_step: str = "pantry"):
        super().__init__()
        self.pantry = pantry
        self.initial_step = initial_step
        self.current_step = 1 if initial_step == "ai" else 3
        self.provider_opts: List[Tuple[str, str]] = [
            ("Google Gemini", "gemini"),
            ("OpenRouter", "openrouter"),
            ("Anthropic Claude", "anthropic"),
            ("OpenAI", "openai"),
            ("DeepSeek", "deepseek"),
            ("Groq Cloud", "groq"),
            ("Mistral AI", "mistral"),
            ("LM Studio (Local)", "lmstudio"),
            ("Ollama (Local)", "ollama"),
            ("Offline Mock", "mock"),
        ]
        self.provider_keys: Dict[str, str] = {}
        # Prepopulate with existing configured environment keys
        if settings.gemini_api_key:
            self.provider_keys["gemini"] = settings.gemini_api_key
        if settings.openrouter_api_key:
            self.provider_keys["openrouter"] = settings.openrouter_api_key
        if settings.anthropic_api_key:
            self.provider_keys["anthropic"] = settings.anthropic_api_key
        if settings.openai_api_key:
            self.provider_keys["openai"] = settings.openai_api_key
        if settings.deepseek_api_key:
            self.provider_keys["deepseek"] = settings.deepseek_api_key
        if settings.groq_api_key:
            self.provider_keys["groq"] = settings.groq_api_key
        if settings.mistral_api_key:
            self.provider_keys["mistral"] = settings.mistral_api_key

    def get_styled_provider_opts(self) -> List[Tuple[str, str]]:
        """Return provider options formatted with live status indicators."""
        opts = []
        for label, slug in self.provider_opts:
            has_key = bool(self.provider_keys.get(slug, "").strip())
            if slug in ("lmstudio", "ollama", "mock"):
                opts.append((f"🟢 {label} (Ready)", slug))
            elif has_key:
                opts.append((f"🟢 {label} (Key set)", slug))
            else:
                opts.append((f"⚪ {label}", slug))
        return opts

    def render_keys_summary(self) -> str:
        """Render badge summary of configured keys."""
        slug_to_label = {slug: label for label, slug in self.provider_opts}
        configured = [
            slug_to_label.get(p, p)
            for p, k in self.provider_keys.items()
            if k and p not in ("lmstudio", "ollama", "mock")
        ]
        if configured:
            summary = " • ".join(f"[bold #52b788]{name} ✓[/]" for name in configured)
            return f"[dim]Configured engines:[/] {summary}"
        return "[dim]No keys entered yet. Configure one or more providers above.[/dim]"

    def update_pills(self, active_prov: str) -> None:
        """Update provider switcher pills with active state and status icons."""
        pills = ["gemini", "openrouter", "anthropic", "openai"]
        pill_names = {
            "gemini": "Gemini",
            "openrouter": "OpenRouter",
            "anthropic": "Anthropic",
            "openai": "OpenAI"
        }
        for p in pills:
            try:
                pill = self.query_one(f"#pill-prov-{p}", Button)
                has_key = bool(self.provider_keys.get(p, "").strip())
                status_icon = "🟢" if has_key else "⚪"
                pill.label = f"{status_icon} {pill_names[p]}"
                if p == active_prov:
                    pill.add_class("active-pill")
                else:
                    pill.remove_class("active-pill")
            except Exception:
                pass

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
            # STEP 1: CONFIGURE AI ENGINES & API KEYS
            # -------------------------------------------------------------
            with Vertical(id="welcome-ai-step"):
                yield Label("STEP 1 OF 3: CONFIGURE AI ENGINES & API KEYS", classes="step-heading")
                yield Label(
                    "[dim]Configure one or multiple providers. Switch between pills or the dropdown to enter keys.[/dim]",
                    classes="step-subheading"
                )

                # Quick Engine Switcher Pills
                with Horizontal(id="welcome-provider-pills"):
                    yield Button("🟢 Gemini", id="pill-prov-gemini", classes="prov-pill active-pill")
                    yield Button("⚪ OpenRouter", id="pill-prov-openrouter", classes="prov-pill")
                    yield Button("⚪ Anthropic", id="pill-prov-anthropic", classes="prov-pill")
                    yield Button("⚪ OpenAI", id="pill-prov-openai", classes="prov-pill")
                    yield Button("All Engines ▾", id="pill-prov-more", classes="prov-pill")

                cur_prov = settings.breadwinner_llm_provider
                valid_cur = cur_prov if any(v == cur_prov for _, v in self.provider_opts) else "gemini"

                yield Select(
                    self.get_styled_provider_opts(),
                    value=valid_cur,
                    id="select-welcome-provider"
                )

                initial_key = self.provider_keys.get(valid_cur, "")
                yield Input(
                    value=initial_key,
                    placeholder="Enter Google Gemini API Key (AIzaSy...)",
                    password=True,
                    id="input-welcome-api-key"
                )

                yield Static(
                    "[dim]Free API key: [underline]https://aistudio.google.com/app/apikey[/underline] (Free 15 RPM)[/dim]",
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

                yield Select(
                    self.provider_opts,
                    value=valid_cur,
                    id="select-active-provider"
                )

                yield Static(
                    "[dim]Connecting to provider model registry...[/dim]",
                    id="label-live-model-status"
                )

                initial_models = list(PROVIDER_MODELS.get(valid_cur, [("Default Model", "default")]))
                initial_models.append(("✎ Custom Model ID...", "custom"))
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
            cur_prov = str(self.query_one("#select-welcome-provider", Select).value)
            self.update_pills(cur_prov)
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
        models_with_custom.append(("✎ Custom Model ID...", "custom"))
        model_select.set_options(models_with_custom)
        if models_with_custom:
            model_select.value = models_with_custom[0][1]

        slug_to_label = {slug: label for label, slug in self.provider_opts}
        prov_name = slug_to_label.get(provider, provider.upper())
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
        """Handle dropdown updates across Step 1 and Step 2."""
        if event.select.id == "select-welcome-provider":
            # STEP 1: Provider selection
            provider = str(event.value)
            key_input = self.query_one("#input-welcome-api-key", Input)
            hint = self.query_one("#label-welcome-ai-hint", Static)
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

            # Pre-load whatever key is known for this provider
            key_input.value = self.provider_keys.get(provider, "")
            self.update_pills(provider)

            hints = {
                "gemini": (
                    "Enter Google Gemini API Key (AIzaSy...)",
                    "[dim]Free API key: [underline]https://aistudio.google.com/app/apikey[/underline] (Free 15 RPM)[/dim]",
                    "Google Gemini selected! Generous free tier and ultra-high quality."
                ),
                "openrouter": (
                    "Enter OpenRouter API Key (sk-or-...)",
                    "[dim]Universal Gateway key: [underline]https://openrouter.ai/keys[/underline] (Access 300+ models)[/dim]",
                    "OpenRouter selected! Universal access to Claude, GPT, DeepSeek, and Llama."
                ),
                "anthropic": (
                    "Enter Anthropic Claude API Key (sk-ant-...)",
                    "[dim]Anthropic API key: [underline]https://console.anthropic.com/settings/keys[/underline][/dim]",
                    "Anthropic Claude selected! Gold standard career narrative reasoning."
                ),
                "openai": (
                    "Enter OpenAI API Key (sk-proj-...)",
                    "[dim]OpenAI API key: [underline]https://platform.openai.com/api-keys[/underline][/dim]",
                    "OpenAI selected! Flagship GPT-4o intelligence and reasoning models."
                ),
                "deepseek": (
                    "Enter DeepSeek API Key (sk-...)",
                    "[dim]DeepSeek API key: [underline]https://platform.deepseek.com[/underline] (V3 & R1 models)[/dim]",
                    "DeepSeek selected! Ultra-low cost frontier reasoning."
                ),
                "groq": (
                    "Enter Groq API Key (gsk_...)",
                    "[dim]Free Groq API key: [underline]https://console.groq.com/keys[/underline] (Llama 3.3)[/dim]",
                    "Groq Cloud selected! Ultra-fast inference speeds."
                ),
                "mistral": (
                    "Enter Mistral API Key (API key...)",
                    "[dim]Mistral API key: [underline]https://console.mistral.ai/api-keys[/underline][/dim]",
                    "Mistral AI selected! Premier open-weights frontier reasoning."
                ),
                "lmstudio": (
                    "No API key required for local server",
                    "[dim]Local inference via LM Studio at [underline]http://localhost:1234/v1[/underline][/dim]",
                    "LM Studio selected! 100% offline local privacy on your hardware."
                ),
                "ollama": (
                    "No API key required for local server",
                    "[dim]Local inference via Ollama at [underline]http://localhost:11434/v1[/underline][/dim]",
                    "Ollama selected! Local open-source models running on localhost."
                ),
                "mock": (
                    "No API key required (Mock Test Drive)",
                    "[dim]Instant testing mode without any API keys or network connection[/dim]",
                    "Offline Mock selected! Perfect for an instant zero-setup test drive."
                ),
            }
            placeholder, hint_text, mascot_msg = hints.get(
                provider,
                ("Enter API Key...", "[dim]Enter API Key[/dim]", f"{provider.upper()} selected.")
            )
            key_input.placeholder = placeholder
            if provider in ("lmstudio", "ollama", "mock"):
                key_input.disabled = True
                key_input.value = ""
            else:
                key_input.disabled = False
            hint.update(hint_text)
            if self.current_step == 1:
                mascot.set_dialogue(mascot_msg, status=f"Engine: {provider.upper()}")

        elif event.select.id == "select-active-provider":
            # STEP 2: Active provider changed
            if self.current_step == 2:
                self.load_step_2_models(str(event.value))

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
            prov = str(self.query_one("#select-welcome-provider", Select).value)
            if prov not in ("lmstudio", "ollama", "mock"):
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

        # Clean dragged terminal string (strip quotes, file://, unescape spaces, expand ~)
        clean = raw_val.strip("'\"")
        if clean.startswith("file://"):
            clean = clean[7:]
        clean = clean.replace(r"\ ", " ")
        clean_expanded = os.path.expanduser(clean)
        path_obj = Path(clean_expanded)

        if path_obj.is_file():
            size_kb = max(1, path_obj.stat().st_size // 1024)
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
        elif clean.startswith("http://") or clean.startswith("https://"):
            badge.update(f"[bold #52b788]✓ WEB PORTFOLIO:[/] [bold white]{clean}[/] [dim](Universal Scraper Ready)[/]")
            mascot.set_dialogue(
                "Target portfolio identified! I'll scrape your case studies and structure your pantry facts!",
                status="Online Portfolio"
            )
        else:
            badge.update(f"[bold #f4a261]• Input:[/] [white]{clean}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        # Quick Provider Switcher Pills
        if bid and bid.startswith("pill-prov-"):
            target_prov = bid.replace("pill-prov-", "")
            if target_prov == "more":
                try:
                    self.query_one("#select-welcome-provider", Select).focus()
                except Exception:
                    pass
            else:
                sel = self.query_one("#select-welcome-provider", Select)
                sel.value = target_prov
                self.update_pills(target_prov)
            return

        # -------------------------------------------------------------
        # STEP 1 -> STEP 2 (Save Keys & Trigger Live Discovery)
        # -------------------------------------------------------------
        if bid == "btn-welcome-save-ai":
            current_prov = str(self.query_one("#select-welcome-provider", Select).value)
            key_val = self.query_one("#input-welcome-api-key", Input).value.strip()
            if key_val:
                self.provider_keys[current_prov] = key_val

            required_key_providers = ("gemini", "openrouter", "anthropic", "openai", "deepseek", "groq", "mistral")
            has_any_key = any(bool(k.strip()) for k in self.provider_keys.values())

            if current_prov in required_key_providers and not self.provider_keys.get(current_prov) and not has_any_key:
                self.app.notify("Please enter an API key, or choose 'Test Drive'!", severity="warning")
                return

            # Save all non-empty configured keys into .env
            env_vars: Dict[str, str] = {
                "AUTO_GENERATE_PDF": "true",
            }
            env_key_map = {
                "gemini": "GEMINI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "groq": "GROQ_API_KEY",
                "mistral": "MISTRAL_API_KEY",
            }
            for p, k in self.provider_keys.items():
                if k and p in env_key_map:
                    env_vars[env_key_map[p]] = k
            if env_vars:
                save_env_config(env_vars)

            # Transition to Step 2
            self.current_step = 2
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-models-step").styles.display = "block"
            self.query_one("#welcome-pantry-step").styles.display = "none"

            active_select = self.query_one("#select-active-provider", Select)
            active_select.set_options(self.provider_opts)
            active_select.value = current_prov

            self.load_step_2_models(current_prov)

        # -------------------------------------------------------------
        # STEP 2 -> STEP 3 (Save Default Model & Transition to Pantry)
        # -------------------------------------------------------------
        elif bid == "btn-welcome-save-model":
            active_prov = str(self.query_one("#select-active-provider", Select).value)
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
            cur_prov = str(self.query_one("#select-welcome-provider", Select).value)
            self.update_pills(cur_prov)

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
            source_raw = self.query_one("#input-welcome-source", Input).value.strip()
            clean_source = source_raw.strip("'\"")
            if clean_source.startswith("file://"):
                clean_source = clean_source[7:]
            clean_source = clean_source.replace(r"\ ", " ")
            clean_source = os.path.expanduser(clean_source) if clean_source else ""

            bio_val = self.query_one("#input-welcome-bio", TextArea).text.strip()

            if clean_source:
                self.dismiss({"action": "import", "source": clean_source})
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
