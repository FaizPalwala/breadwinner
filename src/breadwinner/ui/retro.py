"""8-bit Retro Bakery Aesthetic and Animated TUI Sprites for Breadwinner."""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle
from textual.widgets import Static, Label, Button
from textual.screen import ModalScreen
from textual.binding import Binding
from textual import work

from breadwinner.config import settings
from breadwinner.core.models import JobPosting, CandidateProfile, TailoredApplication
from breadwinner.core.persona import Persona, PersonaManager
from breadwinner.core.portfolio import get_profile_source
from breadwinner.core.scraper import JobScraper
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer, bake_application_package
from breadwinner.db.repository import JobRecord
from breadwinner.db.sync import CsvSync
from breadwinner.providers.factory import get_llm_provider


from rich.cells import cell_len
from rich.text import Text


# ==============================================================================
# 8-BIT SPRITE FRAMES & ARTWORK
# ==============================================================================

def _pad_frame(raw_lines: List[str], target_width: int) -> str:
    """Pad each line of ascii/rich artwork to an exact cell length to guarantee stable borders."""
    out = []
    for line in raw_lines:
        plain = Text.from_markup(line).plain
        cur_len = cell_len(plain)
        diff = target_width - cur_len
        if diff > 0:
            out.append(line + (" " * diff))
        else:
            out.append(line)
    return "\n".join(out)


OVEN_FRAMES = [
    _pad_frame([
        "           [#ffb86c](  ([/]",
        "            [#ffb86c])  )[/]  [#ffb86c]~[/]",
        "  [#d18f52]╔═════════════════════════╗[/]",
        "  [#d18f52]║[/]  [#ffb86c]* BREADWINNER OVEN *[/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]",
        r"  [#d18f52]║[/]    [#ff5555]/  * ( · · ) *  \ [/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]    [#ff5555]|   ▲ ▲ ▲ ▲ ▲   |[/]    [#d18f52]║[/]",
        "  [#d18f52]╚═════════════════════════╝[/]",
        "  [#ffb86c]450°F HEARTH • STONE PEEL  [/]"
    ], 29),
    _pad_frame([
        "            [#ffb86c])  )[/]",
        "           [#ffb86c](  ([/]   [#ffb86c]~[/]",
        "  [#d18f52]╔═════════════════════════╗[/]",
        "  [#d18f52]║[/]  [#ffb86c]* BREADWINNER OVEN *[/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]",
        r"  [#d18f52]║[/]    [#ff5555]/  * ( ~ ~ ) *  \ [/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]    [#ff5555]|   ▲ ▲ ▲ ▲ ▲   |[/]    [#d18f52]║[/]",
        "  [#d18f52]╚═════════════════════════╝[/]",
        "  [#ffb86c]450°F HEARTH • CRACKLING   [/]"
    ], 29),
    _pad_frame([
        "           [#ffb86c]~  ~[/]  [#ffb86c]~[/]",
        "            [#ffb86c]~  ~[/]",
        "  [#d18f52]╔═════════════════════════╗[/]",
        "  [#d18f52]║[/]  [#ffb86c]* BREADWINNER OVEN *[/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]",
        r"  [#d18f52]║[/]    [#ff5555]/  * ( ◉ ◉ ) *  \ [/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]    [#ff5555]|   ▲ ▲ ▲ ▲ ▲   |[/]    [#d18f52]║[/]",
        "  [#d18f52]╚═════════════════════════╝[/]",
        "  [#ffb86c]450°F HEARTH • GOLDEN CRUST[/]"
    ], 29),
    _pad_frame([
        "            [#ffb86c].  .[/]",
        "           [#ffb86c].  .[/]   [#ffb86c]~[/]",
        "  [#d18f52]╔═════════════════════════╗[/]",
        "  [#d18f52]║[/]  [#ffb86c]* BREADWINNER OVEN *[/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]",
        r"  [#d18f52]║[/]    [#ff5555]/  ★ ( ★ ★ ) ★  \ [/]   [#d18f52]║[/]",
        "  [#d18f52]║[/]    [#ff5555]|   ▲ ▲ ▲ ▲ ▲   |[/]    [#d18f52]║[/]",
        "  [#d18f52]╚═════════════════════════╝[/]",
        "  [#ffb86c]450°F HEARTH • CARAMELIZE  [/]"
    ], 29)
]

OVEN_CELEBRATION_FRAME = _pad_frame([
    "    [bold #50fa7b]★    ★    ★    ★    ★[/]",
    "   [bold #f1fa8c]* DING! FRESH LOAF! *[/]",
    "  [#50fa7b]╔═════════════════════════╗[/]",
    "  [#50fa7b]║[/]  [bold #50fa7b]* MASTERPIECE BAKED *[/]  [#50fa7b]║[/]",
    "  [#50fa7b]║[/]     [#f1fa8c].─────────────.[/]     [#50fa7b]║[/]",
    r"  [#50fa7b]║[/]    [#f1fa8c]/  GOLDEN LOAF  \ [/]   [#50fa7b]║[/]",
    "  [#50fa7b]║[/]    [#f1fa8c]| READY TO SERVE|[/]    [#50fa7b]║[/]",
    "  [#50fa7b]╚═════════════════════════╝[/]",
    " [bold #50fa7b]CRUST: CRUNCH • 100% DONE   [/]"
], 29)

OVEN_BURNT_FRAME = _pad_frame([
    "        [bold #ff5555]✕   ✕   ✕   ✕[/]",
    "      [bold #ff5555]* SMOKE ALARM RINGING *[/]",
    "  [#ff5555]╔═════════════════════════╗[/]",
    "  [#ff5555]║[/]   [bold #ff5555]* HEARTH OFF-LINE *[/]   [#ff5555]║[/]",
    "  [#ff5555]║[/]     [#ff5555].─────────────.[/]     [#ff5555]║[/]",
    r"  [#ff5555]║[/]    [#ff5555]/  ░░░  ✕  ░░░  \ [/]   [#ff5555]║[/]",
    "  [#ff5555]║[/]    [#ff5555]|   BURNT CRUST |[/]    [#ff5555]║[/]",
    "  [#ff5555]╚═════════════════════════╝[/]",
    "  [bold #ff5555]450°F HEARTH • COOLDOWN    [/]"
], 29)

MASCOT_FRAMES = [
    _pad_frame([
        "  [#f1fa8c](===)[/]   ",
        " [bold white]( ^ - ^ )[/]",
        "[#d18f52]╭| ░░░ |)[/]",
        "[#d18f52]  d   b   [/]"
    ], 10),
    _pad_frame([
        "  [#f1fa8c](===)[/]   ",
        " [bold white]( > - < )[/]",
        "[#d18f52]╭| ░░░ |)[/]",
        "[#d18f52]  d   b   [/]"
    ], 10),
    _pad_frame([
        "  [#f1fa8c](===)[/]   ",
        " [bold white]( ^ . ^ )[/]",
        "[#d18f52] | ░░░ |  [/]",
        "[#d18f52]  d   b   [/]"
    ], 10),
    _pad_frame([
        r" [bold #50fa7b]\(*o*)/[/]  ",
        "  [#f1fa8c](===)[/]   ",
        " [bold white]( * - * )[/]",
        "[#d18f52]  d   b   [/]"
    ], 10)
]

POKEMON_BAKERY_SPRITES = [
    _pad_frame([
        "[#f4a261]  (===)   [/]",
        "[bold #fff1e6] ( ^ - ^ )[/]",
        "[#e76f51]╭( ░░░░ )╮[/]",
        "[#bc6c25]═╡══════╞═[/]",
        "[#bc6c25]│[#f4a261] ~LOAF~ [/][#bc6c25]│[/]",
        "[#bc6c25]╰────────╯[/]"
    ], 10),
    _pad_frame([
        "[#f4a261]  (===)   [/]",
        "[bold #fff1e6] ( > - < )[/]",
        "[#e76f51]╭( -oo- )╮[/]",
        "[#bc6c25]═╡══════╞═[/]",
        "[#bc6c25]│[#fff1e6] *  . * [/][#bc6c25]│[/]",
        "[#bc6c25]╰────────╯[/]"
    ], 10),
    _pad_frame([
        "[#fff1e6] *[#f4a261](===)[/]*  [/]",
        "[bold #fff1e6] ( ^ . ^ )[/]",
        "[#e76f51]<( .::. )>[/]",
        "[#bc6c25]═╡══════╞═[/]",
        "[#bc6c25]│[#f4a261] {o}{o} [/][#bc6c25]│[/]",
        "[#bc6c25]╰────────╯[/]"
    ], 10),
    _pad_frame([
        "[bold #f4a261] * DING! *[/]",
        "[bold #fff1e6] ( * o * )[/]",
        r"[#f4a261] \(===)/  [/]",
        "[#bc6c25]═╡══════╞═[/]",
        "[#bc6c25]│[#52b788]  100%  [/][#bc6c25]│[/]",
        "[#bc6c25]╰────────╯[/]"
    ], 10)
]


# ==============================================================================
# RETRO CSS STYLING
# ==============================================================================

RETRO_THEME_CSS = """
/* 8-bit Retro Arcade Styling for Breadwinner */
.retro-box {
    border: double #d18f52;
    background: #141724;
    padding: 1;
}

.retro-gold {
    color: #f59e0b;
    text-style: bold;
}

.retro-mint {
    color: #50fa7b;
    text-style: bold;
}

.retro-flame {
    color: #ff5555;
    text-style: bold;
}

.retro-stepper {
    text-align: center;
    padding: 1 0;
    margin-bottom: 1;
    background: #0f131f;
    border: round #d18f52;
}

BakingModal {
    align: center middle;
}

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
Button.modal-close-btn, .modal-close-btn, #btn-modal-close {
    dock: right;
    min-width: 3;
    width: 3;
    height: 1;
    border: none;
    background: transparent;
    color: #6272a4;
    padding: 0;
}
Button.modal-close-btn:focus, .modal-close-btn:focus, #btn-modal-close:focus {
    background: transparent;
    color: #6272a4;
    border: none;
    text-style: none;
}
Button.modal-close-btn:hover, .modal-close-btn:hover, #btn-modal-close:hover {
    background: transparent;
    color: #ff5555;
    border: none;
    text-style: bold;
}

#baking-modal-container {
    width: 88;
    height: auto;
    max-height: 88vh;
    overflow-y: auto;
    scrollbar-size-vertical: 1;
    scrollbar-background: #0d111a;
    scrollbar-color: #6272a4;
    scrollbar-color-hover: #ffb86c;
    scrollbar-color-active: #f1fa8c;
    scrollbar-corner-color: #0d111a;
    background: #0d111a;
    border: double #ffb86c;
    padding: 1 2;
}

#oven-widget {
    text-align: center;
    width: 100%;
    height: auto;
    margin: 0 0;
}

#mascot-widget {
    height: auto;
    width: 100%;
    text-align: center;
    margin-bottom: 1;
}

#baking-status-text {
    width: 100%;
    text-align: center;
    color: #f1fa8c;
    text-style: bold;
    margin: 0 0 1 0;
}

#retro-progress-gauge {
    width: 100%;
    text-align: center;
    margin-bottom: 1;
}

#baking-score-card {
    background: #161c2d;
    border: round #50fa7b;
    padding: 1 2;
    margin: 1 0;
    height: auto;
    min-height: 4;
    display: none;
}

#baking-score-card.error-card {
    background: #1e131d;
    border: round #ff5555;
    padding: 1 2;
    margin: 1 0;
    height: auto;
    min-height: 5;
}

#baking-score-card Label {
    width: 100%;
    height: auto;
}

#baking-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
    width: 100%;
}

#baking-action-bar Button {
    margin: 0 1;
    height: 3;
    min-width: 18;
    border: round #6272a4;
    background: #212638;
    color: #f8f8f2;
}

#btn-modal-cancel {
    background: #212638;
    color: #f8f8f2;
    border: round #6272a4;
}

#btn-modal-cancel:hover {
    background: #2d1a22;
    border: round #ff5555;
    color: #ff5555;
    text-style: bold;
}

#btn-modal-change-model {
    background: #d4a373;
    color: #0d111a;
    border: round #ffb86c;
    text-style: bold;
}

#btn-modal-change-model:hover {
    background: #ffb86c;
    color: #000000;
    border: round #f1fa8c;
    text-style: bold;
}

#btn-modal-collect {
    background: #50fa7b;
    color: #0d111a;
    border: round #50fa7b;
    text-style: bold;
}

#btn-modal-collect:hover {
    background: #69ff94;
    color: #000000;
    border: round #f1fa8c;
}
"""


# ==============================================================================
# ANIMATED SPRITE WIDGETS
# ==============================================================================

class AnimatedOven(Static):
    """Animated brick hearth oven sprite cycling flames, smoke, and baking loaf."""

    def __init__(self, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__(OVEN_FRAMES[0], id=id, classes=classes)
        self.frame_idx: int = 0
        self.state: str = "baking"  # baking | celebrate | burnt | idle
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.35, self.advance_frame)

    def advance_frame(self) -> None:
        if self.state == "baking":
            self.frame_idx = (self.frame_idx + 1) % len(OVEN_FRAMES)
            self.update(OVEN_FRAMES[self.frame_idx])
        elif self.state == "celebrate":
            self.update(OVEN_CELEBRATION_FRAME)
        elif self.state == "burnt":
            self.update(OVEN_BURNT_FRAME)
        elif self.state == "idle":
            self.update(OVEN_FRAMES[0])

    def set_state(self, new_state: str) -> None:
        self.state = new_state
        self.advance_frame()


class AnimatedMascot(Static):
    """Crumb the Baker Loaf mascot who breathes, winks, and dusts flour."""

    def __init__(self, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__("", id=id, classes=classes)
        self.frame_idx: int = 0
        self.active_message: Optional[str] = None
        self._timer = None
        self.update(self.render_current_frame())

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.9, self.advance_frame)

    def advance_frame(self) -> None:
        self.frame_idx = (self.frame_idx + 1) % len(MASCOT_FRAMES)
        self.update(self.render_current_frame())

    def set_message(self, message: str) -> None:
        self.active_message = message
        try:
            if self.app:
                from textual.widgets import Label
                speech_label = self.app.query_one("#studio-mascot-speech", Label)
                speech_label.update(f'[bold #8be9fd][·] Crumb:[/] [italic #f1fa8c]"{message}"[/italic #f1fa8c]')
        except Exception:
            pass

    def render_current_frame(self) -> str:
        return MASCOT_FRAMES[self.frame_idx]


class PokemonBakeryCounter(Static):
    """8-bit Pokémon-style bakery shop counter with animated Baker Crumb and dialogue box."""

    DEFAULT_CSS = """
    PokemonBakeryCounter {
        height: auto;
        margin-bottom: 1;
        overflow-x: hidden;
    }
    #counter-scene-row {
        height: auto;
        min-height: 7;
        overflow-x: hidden;
    }
    #counter-baker-sprite {
        width: 12;
        height: 6;
        margin-right: 1;
    }
    #counter-dialogue-box {
        width: 1fr;
        height: auto;
        min-height: 6;
        background: #141926;
        border: round #d4a373;
        padding: 0 1;
        overflow-x: hidden;
    }
    .poke-dialogue-title {
        color: #f4a261;
        text-style: bold;
        width: 100%;
    }
    .poke-dialogue-body {
        color: #fefae0;
        width: 100%;
    }
    .poke-dialogue-status {
        color: #52b788;
        text-style: bold;
        text-align: right;
        width: 100%;
    }
    """

    def __init__(
        self,
        initial_message: str = "Welcome, Trainer! Drop your resume or portfolio into the dough bin below, and I'll bake an anti-slop masterpiece!",
        id: Optional[str] = "pokemon-bakery-counter",
        classes: Optional[str] = None
    ):
        super().__init__("", id=id, classes=classes)
        self.current_message = initial_message
        self.badge_title = "[·] BAKER CRUMB [dim](Lv. 100 Master Baker)[/]"
        self.status_line = "Verified Ingredients Only [·] ▼"
        self.frame_idx = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="counter-scene-row"):
            yield Static(POKEMON_BAKERY_SPRITES[0], id="counter-baker-sprite")
            with Vertical(id="counter-dialogue-box"):
                yield Label(self.badge_title, id="counter-dialogue-title", classes="poke-dialogue-title")
                yield Label(f'"{self.current_message}"', id="counter-dialogue-body", classes="poke-dialogue-body")
                yield Label(self.status_line, id="counter-dialogue-status", classes="poke-dialogue-status")

    def on_mount(self) -> None:
        self._timer = self.set_interval(1.2, self.advance_frame)

    def advance_frame(self) -> None:
        self.frame_idx = (self.frame_idx + 1) % len(POKEMON_BAKERY_SPRITES)
        try:
            sprite_widget = self.query_one("#counter-baker-sprite", Static)
            sprite_widget.update(POKEMON_BAKERY_SPRITES[self.frame_idx])
        except Exception:
            pass

    def set_dialogue(self, message: str, status: Optional[str] = None, badge: Optional[str] = None) -> None:
        self.current_message = message
        try:
            self.query_one("#counter-dialogue-body", Label).update(f'"{message}"')
            if status is not None:
                self.status_line = status
                self.query_one("#counter-dialogue-status", Label).update(status)
            if badge is not None:
                self.badge_title = badge
                self.query_one("#counter-dialogue-title", Label).update(badge)
        except Exception:
            pass


class BakeryStepper(Static):
    """Retro 8-bit breadcrumb stage tracker for the tailoring lifecycle."""

    STAGES = [
        ("[·]", "PANTRY"),
        ("[~]", "KNEAD"),
        ("[≡]", "PROOF"),
        ("[▲]", "OVEN"),
        ("[★]", "LOAF")
    ]

    def __init__(self, current_stage: int = 0, id: Optional[str] = None, classes: Optional[str] = "retro-stepper"):
        super().__init__("", id=id, classes=classes)
        self.current_stage: int = current_stage
        self.render_stepper()

    def set_stage(self, stage_idx: int) -> None:
        self.current_stage = max(0, min(stage_idx, len(self.STAGES) - 1))
        self.render_stepper()

    def render_stepper(self) -> None:
        parts = []
        for idx, (icon, name) in enumerate(self.STAGES):
            if idx < self.current_stage:
                # Completed
                parts.append(f"[bold #50fa7b][✓ {name}][/bold #50fa7b]")
            elif idx == self.current_stage:
                # Active stage
                parts.append(f"[bold #f1fa8c on #3e2723] ▶ [bold white]{icon} {name}[/bold white] ◀ [/bold #f1fa8c on #3e2723]")
            else:
                # Upcoming
                parts.append(f"[dim][{icon} {name}][/dim]")

        separator = " [bold #d18f52]──▶[/bold #d18f52] "
        stepper_str = separator.join(parts)
        self.update(stepper_str)


class RetroProgressBar(Static):
    """8-bit arcade style block progress bar."""

    def __init__(self, percent: int = 0, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__("", id=id, classes=classes)
        self.percent = percent
        self.update_progress(percent)

    def update_progress(self, percent: int) -> None:
        self.percent = max(0, min(100, percent))
        total_blocks = 24
        filled = int((self.percent / 100) * total_blocks)
        empty = total_blocks - filled

        bar = f"[#50fa7b][[/] [#f59e0b]{'█' * filled}[/][#282a36]{'░' * empty}[/] [#50fa7b]][/] [bold #f1fa8c]{self.percent:3d}%[/]"
        self.update(bar)


# ==============================================================================
# BAKING RETRO MODAL SCREEN
# ==============================================================================

def clean_error_message(raw_msg: str) -> Tuple[str, str]:
    """Extracts a clean user-facing headline and detailed explanation from raw provider errors."""
    msg_str = str(raw_msg).strip()

    # Extract embedded JSON error message if present
    match = re.search(r"['\"]message['\"]:\s*['\"]([^'\"]+)['\"]", msg_str)
    if match:
        clean_snippet = match.group(1).split(". For more information")[0].strip()
    else:
        # Strip long stacktrace or common prefixes
        clean_snippet = msg_str.split("\n")[0].strip()
        if len(clean_snippet) > 180:
            clean_snippet = clean_snippet[:177] + "..."

    # 1. Quota / Rate limit (429)
    if "429" in msg_str or "RESOURCE_EXHAUSTED" in msg_str or "quota" in msg_str.lower():
        headline = "API Quota Exceeded (HTTP 429)"
        detail = (
            f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
            f"[bold #ffb86c]Recommendation:[/] Click 'Change Model' below to switch to another active model or retry in a moment."
        )
        return headline, detail

    # 2. Not found / Retired (404)
    if "404" in msg_str or "NOT_FOUND" in msg_str or "not found" in msg_str.lower():
        headline = "Model Not Found / Retired (HTTP 404)"
        detail = (
            f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
            f"[bold #ffb86c]Recommendation:[/] Click 'Change Model' below to choose an active model in Settings."
        )
        return headline, detail

    # 3. Auth / Invalid Key (401 / 403)
    if any(k in msg_str for k in ["401", "403", "API_KEY_INVALID", "invalid_api_key", "Unauthorized"]):
        headline = "Authentication Failed (HTTP 401/403)"
        detail = (
            f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
            f"[bold #ffb86c]Recommendation:[/] Verify your API key or configure a different provider in Settings."
        )
        return headline, detail

    # 4. Connection / Network errors
    if any(k in msg_str.lower() for k in ["connection", "timeout", "timed out", "max retries", "network"]):
        headline = "Network / Connection Timeout"
        detail = (
            f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
            f"[bold #ffb86c]Recommendation:[/] Check internet connection or target site availability."
        )
        return headline, detail

    # 5. Ingestion / Remote Service (500 / 503)
    if any(k in msg_str.lower() for k in ["ingestionerror", "500", "503", "service unavailable"]):
        headline = "Remote Service Error (HTTP 500/503)"
        detail = (
            f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
            f"[bold #ffb86c]Recommendation:[/] Verify the URL or try again shortly."
        )
        return headline, detail

    # 6. Fallback generic
    headline = "Baking Hearth Malfunction"
    detail = (
        f"[bold #ff5555]{clean_snippet}[/bold #ff5555]\n\n"
        f"[bold #ffb86c]Recommendation:[/] Click 'Change Model' to try another model or check logs."
    )
    return headline, detail


class BakingModal(ModalScreen):
    """Full retro 8-bit arcade baking modal dialog with animated oven & progress tracker."""

    DEFAULT_CSS = RETRO_THEME_CSS

    BINDINGS = [
        Binding("v", "view_resume_pdf", "View Resume PDF", show=False),
        Binding("l", "view_letter_pdf", "View Letter PDF", show=False),
        Binding("o", "open_folder", "Open Folder", show=False),
        Binding("escape", "dismiss_modal", "Dismiss", show=False),
    ]

    def __init__(
        self,
        task_type: str,  # "tailor" or "bake_pdf" or "ingest"
        target_info: Dict[str, Any],
        on_complete_callback=None
    ):
        super().__init__()
        self.task_type = task_type
        self.target_info = target_info
        self.on_complete_callback = on_complete_callback
        self.baking_result: Optional[Dict[str, Any]] = None
        self.is_done: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="baking-modal-container"):
            header_title = (
                "[✦] STOCKING THE CAREER PANTRY [✦]"
                if self.task_type == "ingest"
                else (
                    "[✦] BREADWINNER ARCADE BAKERY [✦]"
                    if self.task_type == "tailor"
                    else "[▲] HEADLESS OVEN PDF BAKE [▲]"
                )
            )
            with Horizontal(classes="modal-header-bar"):
                yield Label(f"[bold #ffb86c]{header_title}[/bold #ffb86c]", id="baking-title", classes="modal-header-title")
                yield Button("✕", id="btn-modal-close", classes="modal-close-btn")
            yield BakeryStepper(current_stage=0, id="modal-stepper")
            yield Center(AnimatedOven(id="oven-widget"))
            yield Label("[bold #f1fa8c]Preheating the stone hearth...[/bold #f1fa8c]", id="baking-status-text")
            yield Center(RetroProgressBar(percent=5, id="retro-progress-gauge"))

            with Vertical(id="baking-score-card"):
                yield Label("", id="score-card-title")
                yield Label("", id="score-card-details")

            with Horizontal(id="baking-action-bar"):
                yield Button("Cancel Bake", variant="error", id="btn-modal-cancel")
                yield Button("Change Model", variant="warning", id="btn-modal-change-model", classes="hidden")
                yield Button("Collect Loaf (Inspect)", variant="success", id="btn-modal-collect", classes="hidden")
                yield Button("View Resume PDF (v)", variant="primary", id="btn-modal-view-pdf", classes="hidden")
                yield Button("View Letter PDF (l)", variant="primary", id="btn-modal-view-letter-pdf", classes="hidden")
                yield Button("Open Folder (o)", variant="default", id="btn-modal-open-folder", classes="hidden")

    def on_mount(self) -> None:
        # Hide finished buttons initially
        self.query_one("#btn-modal-change-model", Button).display = False
        self.query_one("#btn-modal-collect", Button).display = False
        self.query_one("#btn-modal-view-pdf", Button).display = False
        self.query_one("#btn-modal-view-letter-pdf", Button).display = False
        self.query_one("#btn-modal-open-folder", Button).display = False
        self.query_one("#baking-score-card", Vertical).display = False

        # Launch background worker
        if self.task_type == "tailor":
            self.run_tailor_worker()
        elif self.task_type == "ingest":
            self.run_ingest_worker()
        else:
            self.run_pdf_bake_worker()

    # --------------------------------------------------------------------------
    # BACKGROUND WORKERS
    # --------------------------------------------------------------------------

    @work(thread=True)
    def run_tailor_worker(self) -> None:
        """Executes the full anti-slop tailoring pipeline with animated retro stages."""
        stepper = self.query_one("#modal-stepper", BakeryStepper)
        status_lbl = self.query_one("#baking-status-text", Label)
        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        oven = self.query_one("#oven-widget", AnimatedOven)

        import time

        try:
            # STAGE 0: PANTRY & JD INGESTION
            self.app.call_from_thread(stepper.set_stage, 0)
            self.app.call_from_thread(gauge.update_progress, 15)
            self.app.call_from_thread(status_lbl.update, "[bold #8be9fd][·] Gathering verified pantry facts & parsing JD...[/bold #8be9fd]")
            time.sleep(0.3)

            url_input = self.target_info.get("url_input", "")
            pantry = self.target_info.get("pantry")
            repo = self.target_info.get("repo")
            directives = self.target_info.get("job_directives")
            persona = self.target_info.get("persona")
            template_name = self.target_info.get("template_name", "jakes")

            p_source = Path(url_input)
            if url_input.startswith("http://") or url_input.startswith("https://"):
                job = JobScraper.ingest_from_url(url_input)
            elif p_source.is_file():
                job = JobScraper.ingest_from_text(p_source.read_text(encoding="utf-8"), "Company", "Role")
            else:
                job = JobScraper.ingest_from_text(url_input, "Company", "Role")

            if pantry and pantry.is_initialized():
                profile = pantry.load_profile()
            else:
                adapter = get_profile_source(settings.portfolio_path)
                profile = adapter.load_profile()

            # STAGE 1: KNEAD (STRATEGY & PERSONA DIRECTIVES)
            self.app.call_from_thread(stepper.set_stage, 1)
            self.app.call_from_thread(gauge.update_progress, 35)
            persona_label = persona.name[:25] if persona else "Direct Pantry Match"
            self.app.call_from_thread(
                status_lbl.update,
                f"[bold #ffb86c][~] Kneading narrative strategy ({persona_label})...[/bold #ffb86c]"
            )
            time.sleep(0.4)

            provider = get_llm_provider()

            # STAGE 2: PROOF (LLM BULLET TAILORING)
            self.app.call_from_thread(stepper.set_stage, 2)
            self.app.call_from_thread(gauge.update_progress, 60)
            self.app.call_from_thread(
                status_lbl.update,
                "[bold #f1fa8c][≡] Proofing XYZ formulas & verifiable metrics...[/bold #f1fa8c]"
            )

            engine = TailoringEngine(provider)
            app_result = engine.analyze_and_tailor(profile, job, persona, job_directives=directives)

            # STAGE 3: OVEN (RENDERING TEMPLATES)
            self.app.call_from_thread(stepper.set_stage, 3)
            self.app.call_from_thread(gauge.update_progress, 80)
            self.app.call_from_thread(
                status_lbl.update,
                f"[bold #ff79c6][▲] Preheating stone peel for {template_name.upper()} template...[/bold #ff79c6]"
            )
            time.sleep(0.3)

            renderer = TemplateRenderer()
            resume_html = renderer.render_resume(profile, app_result, template_name)
            resume_md = renderer.render_resume(profile, app_result, "ats")
            cover_letter = renderer.render_cover_letter(profile, app_result)
            portal_qna = renderer.render_portal_qna(profile, app_result)
            json_resume = renderer.export_json_resume(profile)

            date_slug = datetime.now().strftime("%Y-%m-%d")
            safe_c = "".join(c for c in job.company if c.isalnum() or c in "-_")
            safe_t = "".join(c for c in job.title if c.isalnum() or c in "-_")
            app_dir = settings.applications_dir / f"{date_slug}_{safe_c}_{safe_t}"
            app_dir.mkdir(parents=True, exist_ok=True)

            (app_dir / "resume.html").write_text(resume_html, encoding="utf-8")
            (app_dir / "resume.md").write_text(resume_md, encoding="utf-8")
            (app_dir / "resume.json").write_text(json_resume, encoding="utf-8")
            if app_result.cover_letter:
                (app_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
                cl_html = renderer.render_cover_letter_html(profile, app_result)
                (app_dir / "cover_letter.html").write_text(cl_html, encoding="utf-8")
            if app_result.portal_answers:
                (app_dir / "portal_answers.md").write_text(portal_qna, encoding="utf-8")

            # STAGE 4: GOLDEN LOAF (PDF BAKE)
            self.app.call_from_thread(stepper.set_stage, 4)
            self.app.call_from_thread(gauge.update_progress, 95)
            self.app.call_from_thread(status_lbl.update, "[bold #50fa7b][★] Caramelizing crust into print-ready PDF...[/bold #50fa7b]")

            pdf_baked = False
            bake_res = {}
            if settings.auto_generate_pdf:
                try:
                    bake_res = bake_application_package(app_dir, open_after=False)
                    pdf_baked = bool(bake_res.get("resume_pdf"))
                except Exception:
                    pass

            # Update DB Record
            score = app_result.match_analysis.match_score
            job_rec = JobRecord(
                id=job.id,
                company=job.company,
                title=job.title,
                url=job.url,
                location=job.location,
                portal_type=job.portal_type,
                status="tailored",
                match_score=score,
                persona=persona.slug if persona else "direct",
                date_added=date_slug,
                folder_path=str(app_dir.resolve()),
                notes=f"Tailored via {persona.name if persona else 'Direct Pantry Match'}" + (" (with custom strategy loop)" if directives else "")
            )
            if repo:
                repo.upsert_job(job_rec)
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(repo, settings.csv_tracker_path)

            self.baking_result = {
                "success": True,
                "job": job,
                "profile": profile,
                "app_result": app_result,
                "app_dir": app_dir,
                "job_rec": job_rec,
                "pdf_baked": pdf_baked,
                "resume_md": resume_md,
                "cover_letter": cover_letter,
                "portal_qna": portal_qna,
                "template": template_name,
                "bake_res": bake_res
            }

            # VICTORY STATE
            time.sleep(0.4)
            self.app.call_from_thread(self._show_victory_screen, score, job.company, job.title, app_dir, pdf_baked)

        except Exception as e:
            self.app.call_from_thread(self._show_error_screen, str(e))

    @work(thread=True)
    def run_pdf_bake_worker(self) -> None:
        """Runs the standalone headless PDF bake in the retro modal."""
        stepper = self.query_one("#modal-stepper", BakeryStepper)
        status_lbl = self.query_one("#baking-status-text", Label)
        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        oven = self.query_one("#oven-widget", AnimatedOven)

        import time

        try:
            target_dir = self.target_info.get("app_dir")

            self.app.call_from_thread(stepper.set_stage, 3)
            self.app.call_from_thread(gauge.update_progress, 40)
            self.app.call_from_thread(status_lbl.update, "[bold #ffb86c][▲] Launching headless Chromium bakery oven...[/bold #ffb86c]")
            time.sleep(0.4)

            self.app.call_from_thread(stepper.set_stage, 4)
            self.app.call_from_thread(gauge.update_progress, 75)
            self.app.call_from_thread(status_lbl.update, "[bold #50fa7b][★] Rendering crisp vector PDF typography...[/bold #50fa7b]")

            bake_res = bake_application_package(target_dir, open_after=False)
            size_kb = bake_res.get("resume_size_kb") or 0.0

            self.baking_result = {
                "success": bool(bake_res.get("resume_pdf")),
                "app_dir": target_dir,
                "pdf_baked": bool(bake_res.get("resume_pdf")),
                "size_kb": size_kb,
                "bake_res": bake_res
            }

            time.sleep(0.3)
            self.app.call_from_thread(self._show_victory_pdf_screen, target_dir, size_kb)

        except Exception as e:
            self.app.call_from_thread(self._show_error_screen, str(e))
    @work(thread=True)
    def run_ingest_worker(self) -> None:
        """Executes the candidate career pantry ingestion pipeline with animated retro stages."""
        stepper = self.query_one("#modal-stepper", BakeryStepper)
        status_lbl = self.query_one("#baking-status-text", Label)
        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        oven = self.query_one("#oven-widget", AnimatedOven)

        import time
        from breadwinner.core.ingestor import UniversalIngestor, normalize_source
        from breadwinner.providers.factory import get_llm_provider

        try:
            sources = self.target_info.get("sources", [])
            pantry = self.target_info.get("pantry")

            # STAGE 0: INGREDIENT HARVESTING
            self.app.call_from_thread(stepper.set_stage, 0)
            self.app.call_from_thread(gauge.update_progress, 15)
            self.app.call_from_thread(
                status_lbl.update,
                f"[bold #8be9fd][·] Harvesting career ingredients ({len(sources)} source{'s' if len(sources) != 1 else ''})...[/bold #8be9fd]"
            )
            time.sleep(0.4)

            # STAGE 1: PORTFOLIO & ARTIFACT EXTRACTION
            self.app.call_from_thread(stepper.set_stage, 1)
            self.app.call_from_thread(gauge.update_progress, 40)
            self.app.call_from_thread(
                status_lbl.update,
                "[bold #ffb86c][~] Extracting documents, route discovery, and text streams...[/bold #ffb86c]"
            )

            target_prov = self.target_info.get("provider") or settings.breadwinner_llm_provider
            provider = get_llm_provider(provider_name=target_prov)
            existing_profile = pantry.load_profile() if pantry and pantry.is_initialized() else None

            # STAGE 2: LLM FACT PARSING & METRIC EXTRACTION
            self.app.call_from_thread(stepper.set_stage, 2)
            self.app.call_from_thread(gauge.update_progress, 70)
            self.app.call_from_thread(
                status_lbl.update,
                "[bold #f1fa8c][≡] Structuring facts, Google XYZ metrics, and skill deduplication...[/bold #f1fa8c]"
            )

            is_multi = len(sources) > 1
            ingest_payload = sources if is_multi else (sources[0] if sources else "")
            new_profile = UniversalIngestor.ingest(ingest_payload, provider, existing_profile=existing_profile)

            # STAGE 3: STOCKING THE CANONICAL PANTRY
            self.app.call_from_thread(stepper.set_stage, 3)
            self.app.call_from_thread(gauge.update_progress, 90)
            self.app.call_from_thread(
                status_lbl.update,
                "[bold #ff79c6][▲] Committing facts to profile.json, context.md, and dossiers...[/bold #ff79c6]"
            )
            time.sleep(0.3)

            if pantry:
                context_diary = new_profile.raw_context.get("context_diary")
                source_meta = {
                    "source": f"Multi-source ({len(sources)} items)" if is_multi else str(sources[0] if sources else ""),
                    "type": "multi" if is_multi else "single",
                    "sources": sources
                }
                pantry.save_pantry(new_profile, context=context_diary, source_info=source_meta, trigger="baking_modal_ingest")

            self.baking_result = {
                "success": True,
                "profile": new_profile,
                "sources": sources
            }

            self.app.call_from_thread(self._show_victory_ingest_screen, new_profile)

        except Exception as e:
            self.app.call_from_thread(self._show_error_screen, str(e))

    def _show_victory_ingest_screen(self, profile: Any) -> None:
        self.is_done = True
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("celebrate")

        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        gauge.update_progress(100)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #50fa7b][★] DING! CAREER PANTRY SUCCESSFULLY STOCKED! [★][/bold #50fa7b]")

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #f1fa8c][★] PANTRY READY[/bold #f1fa8c] | [bold #50fa7b]{profile.full_name} — {profile.title}[/bold #50fa7b]")

        score_details = self.query_one("#score-card-details", Label)
        score_details.update(
            f"[dim]Verified Accomplishments:[/] [cyan]{len(profile.experiences)} roles[/cyan] • "
            f"[cyan]{len(profile.projects)} projects[/cyan] • "
            f"[cyan]{sum(len(s.skills) for s in profile.skills)} skills[/cyan]\n"
            f"[dim]Storage:[/] [green]Canonical Ledgers (profile.json & context.md)[/green]"
        )

        self.query_one("#btn-modal-cancel", Button).display = False
        collect_btn = self.query_one("#btn-modal-collect", Button)
        collect_btn.label = "Enter Bakery Studio (Enter)"
        collect_btn.display = True

    # VICTORY / ERROR SCREEN UPDATES (CALLED ON UI THREAD)
    # --------------------------------------------------------------------------

    def _show_victory_screen(self, score: int, company: str, title: str, app_dir: Path, pdf_baked: bool) -> None:
        self.is_done = True
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("celebrate")

        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        gauge.update_progress(100)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #50fa7b][★] DING! GOLDEN LOAF CERTIFIED OUT OF THE OVEN! [★][/bold #50fa7b]")

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #f1fa8c][★] HIGH SCORE: {score}% ATS MATCH[/bold #f1fa8c] | [bold #50fa7b]{company} — {title}[/bold #50fa7b]")

        resume_pdf = app_dir / "resume.pdf"
        letter_pdf = app_dir / "cover_letter.pdf"

        resume_size = round(resume_pdf.stat().st_size / 1024, 1) if resume_pdf.exists() else None
        letter_size = round(letter_pdf.stat().st_size / 1024, 1) if letter_pdf.exists() else None

        details = [f"[dim]Saved Package:[/] [cyan]{app_dir.name}[/cyan]"]
        if resume_size is not None:
            details.append(f"[dim]Resume PDF:[/] [bold green]{resume_pdf.name} ({resume_size} KB)[/bold green]")
        else:
            details.append("[dim]Resume PDF:[/] [yellow]Not baked (press 'b')[/yellow]")

        if letter_size is not None:
            details.append(f"[dim]Cover Letter PDF:[/] [bold green]{letter_pdf.name} ({letter_size} KB)[/bold green]")

        score_details = self.query_one("#score-card-details", Label)
        score_details.update("\n".join(details))

        self.query_one("#btn-modal-cancel", Button).display = False
        self.query_one("#btn-modal-collect", Button).display = True
        if resume_pdf.exists():
            self.query_one("#btn-modal-view-pdf", Button).display = True
        if letter_pdf.exists():
            self.query_one("#btn-modal-view-letter-pdf", Button).display = True
        self.query_one("#btn-modal-open-folder", Button).display = True

    def _show_victory_pdf_screen(self, app_dir: Path, size_kb: float) -> None:
        self.is_done = True
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("celebrate")

        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        gauge.update_progress(100)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #50fa7b][★] DING! FRESH PRINT-READY PDF BAKED! [★][/bold #50fa7b]")

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #f1fa8c][DOC] ATS PDF READY[/bold #f1fa8c] | [bold #50fa7b]{size_kb} KB[/bold #50fa7b]")

        resume_pdf = app_dir / "resume.pdf"
        letter_pdf = app_dir / "cover_letter.pdf"

        resume_size = round(resume_pdf.stat().st_size / 1024, 1) if resume_pdf.exists() else size_kb
        letter_size = round(letter_pdf.stat().st_size / 1024, 1) if letter_pdf.exists() else None

        details = [f"[dim]Resume PDF:[/] [cyan]{resume_pdf.name}[/cyan] [green]({resume_size} KB)[/green]"]
        if letter_size is not None:
            details.append(f"[dim]Cover Letter PDF:[/] [cyan]{letter_pdf.name}[/cyan] [green]({letter_size} KB)[/green]")
        details.append(f"[dim]Location:[/] [cyan]{app_dir}[/cyan]")

        score_details = self.query_one("#score-card-details", Label)
        score_details.update("\n".join(details))

        self.query_one("#btn-modal-cancel", Button).display = False
        self.query_one("#btn-modal-collect", Button).display = True
        self.query_one("#btn-modal-view-pdf", Button).display = True
        if letter_pdf.exists():
            self.query_one("#btn-modal-view-letter-pdf", Button).display = True
        self.query_one("#btn-modal-open-folder", Button).display = True

    def _show_error_screen(self, error_msg: str) -> None:
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("burnt")

        headline, detail = clean_error_message(error_msg)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #ff5555][✕] Baking Halted — Hearth Malfunction [✕][/bold #ff5555]")

        # Hide progress gauge & stepper on failure so diagnosis card has ample vertical space and no scrollbars
        try:
            gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
            gauge.display = False
        except Exception:
            pass

        try:
            stepper = self.query_one("#modal-stepper", BakeryStepper)
            stepper.display = False
        except Exception:
            pass

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.add_class("error-card")
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #ff5555][!] {headline}[/bold #ff5555]")

        score_details = self.query_one("#score-card-details", Label)
        score_details.update(detail)

        cancel_btn = self.query_one("#btn-modal-cancel", Button)
        cancel_btn.label = "Dismiss (Esc)"

        change_btn = self.query_one("#btn-modal-change-model", Button)
        change_btn.display = True
        change_btn.label = "Change Model"

        try:
            change_btn.focus()
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # BUTTON INTERACTIONS & KEY ACTIONS
    # --------------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-modal-cancel", "btn-modal-close"):
            self.dismiss(None)
        elif bid == "btn-modal-change-model":
            self.dismiss({
                "action": "change_model",
                "task_type": self.task_type,
                "target_info": self.target_info
            })
        elif bid == "btn-modal-collect":
            self.dismiss(self.baking_result)
        elif bid == "btn-modal-view-pdf":
            self.action_view_resume_pdf()
        elif bid == "btn-modal-view-letter-pdf":
            self.action_view_letter_pdf()
        elif bid == "btn-modal-open-folder":
            self.action_open_folder()

    def action_view_resume_pdf(self) -> None:
        if self.baking_result and self.baking_result.get("app_dir"):
            p = self.baking_result["app_dir"] / "resume.pdf"
            if p.exists():
                open_file_in_viewer(p)

    def action_view_letter_pdf(self) -> None:
        if self.baking_result and self.baking_result.get("app_dir"):
            p = self.baking_result["app_dir"] / "cover_letter.pdf"
            if p.exists():
                open_file_in_viewer(p)

    def action_open_folder(self) -> None:
        if self.baking_result and self.baking_result.get("app_dir"):
            import subprocess
            subprocess.run(["open", str(self.baking_result["app_dir"])])

    def action_dismiss_modal(self) -> None:
        self.dismiss(self.baking_result if self.is_done else None)
