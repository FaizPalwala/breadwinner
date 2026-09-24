"""First-run interactive onboarding modal for Breadwinner with Pokémon-style bakery aesthetic."""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Label, Button, Input, TextArea
from textual.screen import ModalScreen

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
    margin-bottom: 0;
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

    def __init__(self, pantry: PantryManager):
        super().__init__()
        self.pantry = pantry

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Label("🏪 CRUMB'S BREADWINNER BAKERY • EST. 2026", classes="welcome-title")
            yield Label(
                "Anti-Hallucination Career Studio • Fresh Resumes from Verified Facts",
                classes="welcome-subtitle"
            )

            # Nintendo Pokémon-style Bakery Scene (id="welcome-mascot" for test compatibility)
            with Center(id="welcome-mascot-row"):
                yield PokemonBakeryCounter(id="welcome-mascot")

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
        if bid == "btn-tab-dropzone":
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
            # Clean dropped quotes / file:// / escapes
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
