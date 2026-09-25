"""First-run interactive onboarding modal for Breadwinner with Pokémon-style bakery aesthetic.

Supports a guided 2-step setup:
Step 1: Light the Oven Hearth (AI Provider & API Keys)
Step 2: Stock the Career Pantry (Resume Dropzone & Demo Loaf)
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Label, Button, Input, TextArea, Select
from textual.screen import ModalScreen

from breadwinner.config import settings, save_env_config
from breadwinner.core.pantry import PantryManager
from breadwinner.ui.retro import PokemonBakeryCounter


WELCOME_MODAL_CSS = """
BakeryWelcomeModal {
    align: center middle;
}

#welcome-container {
    width: 86;
    height: auto;
    background: #10141f;
    border: heavy #d4a373;
    padding: 1 2;
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

/* ========================================================================= */
/* STEP 1: AI ENGINE SETUP                                                   */
/* ========================================================================= */

#welcome-ai-step {
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
}

#select-welcome-provider {
    height: 3;
    background: #0b0e17;
    border: round #d4a373;
    color: #fefae0;
    margin-bottom: 1;
}

#input-welcome-api-key {
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

#welcome-ai-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
}

#welcome-ai-action-bar Button {
    margin: 0 1;
    min-width: 22;
    height: 3;
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

/* ========================================================================= */
/* STEP 2: PANTRY INGREDIENTS SETUP                                          */
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

#welcome-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
}

#welcome-action-bar Button {
    margin: 0 1;
    min-width: 20;
    height: 3;
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

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Label("🏪 CRUMB'S BREADWINNER BAKERY • EST. 2026", classes="welcome-title")
            yield Label(
                "Anti-Hallucination Career Studio • Fresh Resumes from Verified Facts",
                classes="welcome-subtitle",
                id="welcome-subtitle"
            )

            # Nintendo Pokémon-style Bakery Scene (id="welcome-mascot" for test compatibility)
            with Center(id="welcome-mascot-row"):
                yield PokemonBakeryCounter(id="welcome-mascot")

            # -------------------------------------------------------------
            # STEP 1: AI Engine Setup
            # -------------------------------------------------------------
            with Vertical(id="welcome-ai-step"):
                yield Label("🔥 STEP 1: LIGHT THE OVEN FIRE (AI ENGINE)", classes="step-heading")
                yield Label(
                    "[dim]Choose your AI intelligence engine. Keys are safely stored locally in .env (0600 private permissions).[/dim]",
                    classes="step-subheading"
                )

                provider_opts = [
                    ("🔥 Google Gemini (Free 15 RPM Tier / BYOK - Recommended)", "gemini"),
                    ("🧠 DeepSeek (BYOK • Ultra-low cost reasoning)", "deepseek"),
                    ("⚡ Groq Cloud (Ultra-fast Llama 3.3 • Free / BYOK)", "groq"),
                    ("💻 LM Studio (100% Local / Offline • localhost:1234)", "lmstudio"),
                    ("🦙 Ollama (100% Local / Offline • localhost:11434)", "ollama"),
                    ("🧪 Offline Mock (Instant Test Drive • No key needed)", "mock"),
                ]
                cur_prov = settings.breadwinner_llm_provider
                valid_cur = cur_prov if any(v == cur_prov for _, v in provider_opts) else "gemini"

                yield Select(
                    provider_opts,
                    value=valid_cur,
                    id="select-welcome-provider"
                )

                yield Input(
                    placeholder="Enter Google Gemini API Key (AIzaSy...)",
                    password=True,
                    id="input-welcome-api-key"
                )

                yield Static(
                    "[dim]🔑 Free API key: [underline]https://aistudio.google.com/app/apikey[/underline] (Free 15 RPM)[/dim]",
                    id="label-welcome-ai-hint"
                )

                with Horizontal(id="welcome-ai-action-bar"):
                    yield Button("🔥 Light Hearth & Continue ➔", variant="success", id="btn-welcome-save-ai")
                    yield Button("⚡ Instant Test Drive", variant="warning", id="btn-welcome-mock-drive")
                    yield Button("✖ Skip AI Setup", variant="default", id="btn-welcome-skip-ai")

            # -------------------------------------------------------------
            # STEP 2: Career Pantry Setup
            # -------------------------------------------------------------
            with Vertical(id="welcome-pantry-step"):
                yield Label("🌾 STEP 2: STOCK THE PANTRY (CAREER INGREDIENTS)", classes="step-heading")
                # Input Mode Selector Tabs
                with Horizontal(id="welcome-mode-tabs"):
                    yield Button("📂 Drop File / URL (Recommended)", id="btn-tab-dropzone", classes="tab-btn active-tab")
                    yield Button("📝 Paste Bio Notes", id="btn-tab-bio", classes="tab-btn")

                # MODE A: Tactile Drag & Drop Dropzone Box
                with Vertical(id="welcome-dropzone-box"):
                    yield Label("📥 DOUGH BIN: Drag & drop resume (.pdf, .docx, .json, .md) or paste link", classes="dropzone-label")
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
                    yield Button("🥖 Stock Pantry (Enter)", variant="success", id="btn-welcome-stock")
                    yield Button("🎁 Load Demo Loaf", variant="warning", id="btn-welcome-demo")
                    yield Button("✖ Skip for Now", variant="default", id="btn-welcome-skip")

    def on_mount(self) -> None:
        if self.initial_step == "ai":
            self.query_one("#welcome-ai-step").styles.display = "block"
            self.query_one("#welcome-pantry-step").styles.display = "none"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Welcome, Apprentice! Choose your AI intelligence engine and enter your key (saved locally in .env).",
                status="Step 1 of 2: AI Engine Setup 🔥",
                badge="🏪 BREADWINNER SETUP STUDIO"
            )
        else:
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Welcome, Trainer! Drop your resume or portfolio into the dough bin below, and I'll bake an anti-slop masterpiece!",
                status="Verified Ingredients Only ♪ ▼",
                badge="🏪 BREADWINNER PANTRY"
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Dynamically update key input and hint based on selected provider."""
        if event.select.id != "select-welcome-provider":
            return
        provider = str(event.value)
        key_input = self.query_one("#input-welcome-api-key", Input)
        hint = self.query_one("#label-welcome-ai-hint", Static)
        mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

        hints = {
            "gemini": (
                "Enter Google Gemini API Key (AIzaSy...)",
                "[dim]🔑 Free API key: [underline]https://aistudio.google.com/app/apikey[/underline] (Free 15 RPM)[/dim]",
                "Google Gemini selected! Generous free tier and ultra-high quality."
            ),
            "deepseek": (
                "Enter DeepSeek API Key (sk-...)",
                "[dim]🔑 DeepSeek API key: [underline]https://platform.deepseek.com[/underline] (V3 & R1 models)[/dim]",
                "DeepSeek selected! Ultra-low cost reasoning models."
            ),
            "groq": (
                "Enter Groq API Key (gsk_...)",
                "[dim]🔑 Free Groq API key: [underline]https://console.groq.com/keys[/underline] (Llama 3.3)[/dim]",
                "Groq Cloud selected! Ultra-fast inference speeds."
            ),
            "lmstudio": (
                "No API key required for local server",
                "[dim]💻 Local inference via LM Studio at [underline]http://localhost:1234/v1[/underline][/dim]",
                "LM Studio selected! 100% offline local privacy on your hardware."
            ),
            "ollama": (
                "No API key required for local server",
                "[dim]🦙 Local inference via Ollama at [underline]http://localhost:11434/v1[/underline][/dim]",
                "Ollama selected! Local open-source models running on localhost."
            ),
            "mock": (
                "No API key required (Mock Test Drive)",
                "[dim]🧪 Instant testing mode without any API keys or network connection[/dim]",
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
        mascot.set_dialogue(mascot_msg, status=f"Engine: {provider.upper()} ✓ ▼")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reactive inspection when user drags and drops a file or pastes a link."""
        if event.input.id != "input-welcome-source":
            return

        raw_val = event.value.strip()
        badge = self.query_one("#ingredient-badge", Static)
        mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)

        if not raw_val:
            badge.update("[dim]Waiting for ingredient drop... (drag file or paste URL)[/dim]")
            mascot.set_dialogue(
                "Welcome, Trainer! Drop your resume or portfolio into the dough bin below, and I'll bake an anti-slop masterpiece!",
                status="Verified Ingredients Only ♪ ▼"
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
                status="Ingredient Verified ✓ ▼"
            )
        elif clean.startswith("http://") or clean.startswith("https://"):
            badge.update(f"[bold #52b788]✓ WEB PORTFOLIO:[/] [bold white]{clean}[/] [dim](Universal Scraper Ready)[/]")
            mascot.set_dialogue(
                "Target portfolio identified! I'll scrape your case studies and structure your pantry facts! ♪",
                status="Online Portfolio ✓ ▼"
            )
        else:
            badge.update(f"[bold #f4a261]• Input:[/] [white]{clean}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "btn-welcome-save-ai":
            provider = str(self.query_one("#select-welcome-provider", Select).value)
            key_val = self.query_one("#input-welcome-api-key", Input).value.strip()

            if provider in ("gemini", "deepseek", "groq") and not key_val:
                env_key_map = {
                    "gemini": "GEMINI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "groq": "GROQ_API_KEY",
                }
                existing_key = os.environ.get(env_key_map.get(provider, ""))
                if not existing_key:
                    self.app.notify("Please enter an API key, or choose 'Instant Test Drive'!", severity="warning")
                    return
                key_val = existing_key

            env_vars: Dict[str, str] = {
                "BREADWINNER_LLM_PROVIDER": provider,
                "AUTO_GENERATE_PDF": "true",
            }
            if provider == "gemini":
                if key_val:
                    env_vars["GEMINI_API_KEY"] = key_val
                env_vars["GEMINI_MODEL"] = "gemini-2.5-flash"
            elif provider == "deepseek":
                if key_val:
                    env_vars["DEEPSEEK_API_KEY"] = key_val
                env_vars["DEEPSEEK_MODEL"] = "deepseek-chat"
            elif provider == "groq":
                if key_val:
                    env_vars["GROQ_API_KEY"] = key_val
                env_vars["GROQ_MODEL"] = "llama-3.3-70b-versatile"
            elif provider == "lmstudio":
                env_vars["LMSTUDIO_BASE_URL"] = "http://localhost:1234/v1"
                env_vars["LMSTUDIO_MODEL"] = "local-model"
            elif provider == "ollama":
                env_vars["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"
                env_vars["OLLAMA_MODEL"] = "llama3.2"

            save_env_config(env_vars)

            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                f"Hearth fire lit with {provider.upper()}! Now drop your resume or click Load Demo Loaf to stock your pantry!",
                status="Step 2 of 2: Stock Career Pantry 🌾",
                badge="🏪 CRUMB'S PANTRY"
            )
            self.app.notify(f"✓ AI Engine Configured: {provider.upper()}", title="Oven Fire Lit")
            self.query_one("#input-welcome-source", Input).focus()

        elif bid == "btn-welcome-mock-drive":
            save_env_config({
                "BREADWINNER_LLM_PROVIDER": "mock",
                "AUTO_GENERATE_PDF": "true"
            })
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Offline Mock Engine ready! Now drop your resume or click Load Demo Loaf to start baking!",
                status="Step 2 of 2: Stock Career Pantry 🌾",
                badge="🏪 CRUMB'S PANTRY"
            )
            self.app.notify("✓ Instant Test Drive Mode Enabled (Mock Engine)", title="Mock Engine")
            self.query_one("#input-welcome-source", Input).focus()

        elif bid == "btn-welcome-skip-ai":
            self.query_one("#welcome-ai-step").styles.display = "none"
            self.query_one("#welcome-pantry-step").styles.display = "block"
            mascot = self.query_one("#welcome-mascot", PokemonBakeryCounter)
            mascot.set_dialogue(
                "Skipped AI setup. Drop your resume or click Load Demo Loaf to stock your pantry!",
                status="Step 2 of 2: Stock Career Pantry 🌾",
                badge="🏪 CRUMB'S PANTRY"
            )
            self.query_one("#input-welcome-source", Input).focus()

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

        else:
            self.dismiss(None)
