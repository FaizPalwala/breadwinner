"""First-run interactive onboarding modal for Breadwinner."""

from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, VerticalScroll
from textual.widgets import Static, Label, Button, Input, TextArea
from textual.screen import ModalScreen

from breadwinner.config import settings
from breadwinner.core.pantry import PantryManager
from breadwinner.core.ingestor import UniversalIngestor
from breadwinner.onboarding import STARTER_JSON_RESUME
from breadwinner.providers.factory import get_llm_provider
from breadwinner.ui.retro import AnimatedMascot


WELCOME_MODAL_CSS = """
BakeryWelcomeModal {
    align: center middle;
}

#welcome-container {
    width: 82;
    height: auto;
    max-height: 92%;
    background: #0f1422;
    border: double #f59e0b;
    padding: 1 2;
}

.welcome-title {
    text-align: center;
    color: #f59e0b;
    text-style: bold;
    margin-bottom: 1;
}

.welcome-subtitle {
    text-align: center;
    color: #94a3b8;
    margin-bottom: 1;
}

.section-label {
    color: #50fa7b;
    text-style: bold;
    margin-top: 1;
}

#welcome-mascot-row {
    height: auto;
    margin-bottom: 1;
    align: center middle;
}

#welcome-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
}

#welcome-action-bar Button {
    margin: 0 1;
}
"""


class BakeryWelcomeModal(ModalScreen):
    """First-run onboarding window for non-technical users."""

    DEFAULT_CSS = WELCOME_MODAL_CSS

    def __init__(self, pantry: PantryManager):
        super().__init__()
        self.pantry = pantry

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="welcome-container"):
            yield Label("╔══════════════════════════════════════════════════════════════════╗", classes="welcome-title")
            yield Label("║          🥖 WELCOME TO BREADWINNER: THE ANTI-SLOP BAKERY        ║", classes="welcome-title")
            yield Label("╚══════════════════════════════════════════════════════════════════╝", classes="welcome-title")

            yield Label(
                "Breadwinner is your local-first career studio. We tailor job applications using "
                "[bold #50fa7b]strictly verified facts[/bold #50fa7b] from your Career Pantry.\n"
                "No hallucinated experience, no keyword-stuffing slop, and complete privacy (BYOK).",
                classes="welcome-subtitle"
            )

            with Center(id="welcome-mascot-row"):
                mascot = AnimatedMascot(id="welcome-mascot")
                mascot.active_message = "Welcome! Let's stock your pantry!"
                yield mascot

            yield Label("Option A: Import from URL or File Path:", classes="section-label")
            yield Input(
                placeholder="https://yourportfolio.dev, /path/to/resume.pdf, or .docx / .json",
                id="input-welcome-source"
            )

            yield Label("Option B: Paste Bio / Raw Text Summary (Optional):", classes="section-label")
            yield TextArea(
                "",
                id="input-welcome-bio",
                classes="retro-box"
            )

            with Horizontal(id="welcome-action-bar"):
                yield Button("Stock Pantry (Enter)", variant="success", id="btn-welcome-stock")
                yield Button("Load Demo Loaf 🥖", variant="warning", id="btn-welcome-demo")
                yield Button("Skip for Now", variant="default", id="btn-welcome-skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-welcome-stock":
            source_val = self.query_one("#input-welcome-source", Input).value.strip()
            bio_val = self.query_one("#input-welcome-bio", TextArea).text.strip()

            if source_val:
                self.dismiss({"action": "import", "source": source_val})
            elif bio_val:
                self.dismiss({"action": "import", "source": bio_val})
            else:
                self.app.notify("Please enter a URL, file path, or bio—or click 'Load Demo Loaf'!", severity="warning")
        elif bid == "btn-welcome-demo":
            self.dismiss({"action": "demo"})
        else:
            self.dismiss(None)
