"""8-bit Retro Bakery Aesthetic and Animated TUI Sprites for Breadwinner."""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle
from textual.widgets import Static, Label, Button
from textual.screen import ModalScreen
from textual import work

from breadwinner.config import settings
from breadwinner.core.models import JobPosting, CandidateProfile, TailoredApplication
from breadwinner.core.persona import Persona, PersonaManager
from breadwinner.core.portfolio import get_profile_source
from breadwinner.core.scraper import JobScraper
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.pdf import render_html_to_pdf, open_file_in_viewer
from breadwinner.db.repository import JobRecord
from breadwinner.db.sync import CsvSync
from breadwinner.providers.factory import get_llm_provider


# ==============================================================================
# 8-BIT SPRITE FRAMES & ARTWORK
# ==============================================================================

OVEN_FRAMES = [
    # Frame 0: Chimney steam puff 1, glowing wood hearth
    r"""
       [#8be9fd]  (  ([/]
       [#8be9fd]   )  )[/]  [#ffb86c]♨[/]
     [#d18f52]╔═════════════════════════╗[/]
     [#d18f52]║[/]  [#ffb86c]🧱 BREADWINNER OVEN 🧱[/]  [#d18f52]║[/]
     [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]
     [#d18f52]║[/]    [#ff5555]/   [#f59e0b]░░[/] [bold #f59e0b]🍞[/] [#f59e0b]░░[/]    \[/]    [#d18f52]║[/]
     [#d18f52]║[/]   [#ff5555]|  [#ff5555]▲[/] [#ffb86c]▲[/] [#ff5555]▲[/] [#ffb86c]▲[/] [#ff5555]▲[/]   |[/]   [#d18f52]║[/]
     [#d18f52]╚═════════════════════════╝[/]
      [#ffb86c]450°F HEARTH • STONE PEEL[/]
    """.strip("\n"),

    # Frame 1: Chimney steam puff 2, flame flicker
    r"""
       [#8be9fd]   )  )[/]
       [#8be9fd]  (  ([/]   [#ffb86c]♨[/]
     [#d18f52]╔═════════════════════════╗[/]
     [#d18f52]║[/]  [#ffb86c]🧱 BREADWINNER OVEN 🧱[/]  [#d18f52]║[/]
     [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]
     [#d18f52]║[/]    [#ff5555]/  [#ffb86c]░░[/] [bold #ffb86c]~🍞~[/] [#ffb86c]░░[/]   \[/]    [#d18f52]║[/]
     [#d18f52]║[/]   [#ff5555]|  [#ffb86c]▲[/] [#ff5555]▲[/] [#ffb86c]▲[/] [#ff5555]▲[/] [#ffb86c]▲[/]   |[/]   [#d18f52]║[/]
     [#d18f52]╚═════════════════════════╝[/]
      [#ffb86c]450°F HEARTH • CRACKLING[/]
    """.strip("\n"),

    # Frame 2: Steam swirl, aroma rise
    r"""
       [#8be9fd]  ~  ~[/]  [#ffb86c]♨[/]
       [#8be9fd]   ~  ~[/]
     [#d18f52]╔═════════════════════════╗[/]
     [#d18f52]║[/]  [#ffb86c]🧱 BREADWINNER OVEN 🧱[/]  [#d18f52]║[/]
     [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]
     [#d18f52]║[/]    [#ff5555]/  [#f1fa8c]✨[/] [bold #f59e0b]🍞[/] [#f1fa8c]✨[/]     \[/]    [#d18f52]║[/]
     [#d18f52]║[/]   [#ff5555]|  [#ff5555]▲[/] [#ff5555]▲[/] [#ffb86c]▲[/] [#ff5555]▲[/] [#ff5555]▲[/]   |[/]   [#d18f52]║[/]
     [#d18f52]╚═════════════════════════╝[/]
      [#ffb86c]450°F HEARTH • GOLDEN CRUST[/]
    """.strip("\n"),

    # Frame 3: Sparkles, caramelization
    r"""
       [#8be9fd]   .  .[/]
       [#8be9fd]  .  . [/]  [#ffb86c]♨[/]
     [#d18f52]╔═════════════════════════╗[/]
     [#d18f52]║[/]  [#ffb86c]🧱 BREADWINNER OVEN 🧱[/]  [#d18f52]║[/]
     [#d18f52]║[/]     [#ff5555].─────────────.[/]     [#d18f52]║[/]
     [#d18f52]║[/]    [#ff5555]/  [bold #50fa7b]★[/] [bold #ffb86c]🍞[/] [bold #50fa7b]★[/]     \[/]    [#d18f52]║[/]
     [#d18f52]║[/]   [#ff5555]|  [#ffb86c]▲[/] [#ffb86c]▲[/] [#ff5555]▲[/] [#ffb86c]▲[/] [#ffb86c]▲[/]   |[/]   [#d18f52]║[/]
     [#d18f52]╚═════════════════════════╝[/]
      [#ffb86c]450°F HEARTH • CARAMELIZING[/]
    """.strip("\n")
]

OVEN_CELEBRATION_FRAME = r"""
   [bold #50fa7b]   ★   ★   ★   ★   ★[/]
   [bold #f1fa8c]  ✨  DING! FRESH LOAF!  ✨[/]
 [#50fa7b]╔═════════════════════════╗[/]
 [#50fa7b]║[/]  [bold #50fa7b]🏆 MASTERPIECE BAKED! 🏆[/]  [#50fa7b]║[/]
 [#50fa7b]║[/]     [#f1fa8c].─────────────.[/]     [#50fa7b]║[/]
 [#50fa7b]║[/]    [#f1fa8c]/  [bold #50fa7b]★ [bold #f59e0b]🍞 GOLDEN[/] ★[/]   \[/]    [#50fa7b]║[/]
 [#50fa7b]║[/]   [#f1fa8c]|   READY TO SERVE    |[/]   [#50fa7b]║[/]
 [#50fa7b]╚═════════════════════════╝[/]
  [bold #50fa7b]CRUST SOUND: *CRUNCH* • 100% DONE[/]
""".strip("\n")

OVEN_BURNT_FRAME = r"""
   [bold #ff5555]      ✖   ✖   ✖[/]
   [bold #ff5555]   ☠   BURNT CRUST!   ☠[/]
 [#ff5555]╔═════════════════════════╗[/]
 [#ff5555]║[/]  [bold #ff5555]🔥 SMOKE ALARM RINGING 🔥[/]  [#ff5555]║[/]
 [#ff5555]║[/]     [#ff5555].─────────────.[/]     [#ff5555]║[/]
 [#ff5555]║[/]    [#ff5555]/   [dim]░░░ [bold white]✘[/] ░░░[/]   \[/]    [#ff5555]║[/]
 [#ff5555]║[/]   [#ff5555]|   OVEN MALFUNCTION  |[/]   [#ff5555]║[/]
 [#ff5555]╚═════════════════════════╝[/]
  [bold #ff5555]CHECK LOGS OR RE-ATTEMPT BAKE[/]
""".strip("\n")

MASCOT_FRAMES = [
    # Frame 0: Idle breathing
    r"""
    [#f1fa8c]   ( 🍞 )   [/]
   [bold white](｡◕‿◕｡)[/]   [#8be9fd]< "Proofing your career..."[/]
  [#d18f52]/| ░░░ |) [/]
   [#d18f52]d     b [/]
    """.strip("\n"),

    # Frame 1: Winking
    r"""
    [#f1fa8c]   ( 🍞 )   [/]
   [bold white](｡◕‿<｡)[/]   [#50fa7b]< "No keyword-stuffing slop!"[/]
  [#d18f52]/| ░░░ |) [/]
   [#d18f52]d     b [/]
    """.strip("\n"),

    # Frame 2: Kneading / Flour dust
    r"""
    [#f1fa8c]   ( 🍞 )   [/]
  [bold white](づ｡◕‿‿◕｡)づ[/] [#f1fa8c]* dusted with flour *[/]
   [#d18f52]| ░░░ | [/]
   [#d18f52]d     b [/]
    """.strip("\n"),

    # Frame 3: Victory celebration
    r"""
  [bold #50fa7b]\(*o*)/  ✨ DING! ✨[/]
   [#f1fa8c]  ( 🍞 )  [/]
  [bold white](｡♥‿♥｡)[/]   [#ffb86c]< "Golden ATS Masterpiece!"[/]
  [#d18f52]/| ░░░ |) [/]
    """.strip("\n")
]

POKEMON_BAKERY_SPRITES = [
    # Frame 0: Welcoming customer behind counter
    (
        "[#f4a261]   ( 🍞 )[/]\n"
        "[bold #fff1e6] ( ^ ‿ ^ )[/]\n"
        "[#e76f51]╭([#fefae0] ░░░░ [/])╮[/]\n"
        "[#bc6c25]═╡═══════╞═[/]\n"
        "[#bc6c25]│[#f4a261]🥖 🥐 🥨[/][#bc6c25]│[/]\n"
        "[#bc6c25]╰────────╯[/]"
    ),
    # Frame 1: Winking & rolling dough
    (
        "[#f4a261]   ( 🍞 )[/]\n"
        "[bold #fff1e6] ( > ‿ ◕ )[/]\n"
        "[#e76f51]╭([#bc6c25]──◎──[/])╮[/]\n"
        "[#bc6c25]═╡═══════╞═[/]\n"
        "[#bc6c25]│[#fff1e6] * ｡ *  [/][#bc6c25]│[/]\n"
        "[#bc6c25]╰────────╯[/]"
    ),
    # Frame 2: Sprinkling flour with joy
    (
        "[#fff1e6] *[#f4a261]( 🍞 )[/]* [/]\n"
        "[bold #fff1e6] ( ˘ ▽ ˘ )[/]\n"
        "[#e76f51](づ[#fff1e6]｡∴｡[/])づ [/]\n"
        "[#bc6c25]═╡═══════╞═[/]\n"
        "[#bc6c25]│[#f4a261]🍞 🥖 🥐[/][#bc6c25]│[/]\n"
        "[#bc6c25]╰────────╯[/]"
    ),
    # Frame 3: Fresh batch celebration ding!
    (
        "[bold #f4a261] ✨DING!✨  [/]\n"
        "[bold #fff1e6] ( ★ ‿ ★ )[/]\n"
        "[#f4a261] \\( 🍞 )/  [/]\n"
        "[#bc6c25]═╡═══════╞═[/]\n"
        "[#bc6c25]│[#52b788]★ 100% ★[/][#bc6c25]│[/]\n"
        "[#bc6c25]╰────────╯[/]"
    )
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

#baking-modal-container {
    width: 76;
    height: auto;
    max-height: 92%;
    background: #0d111a;
    border: double #ffb86c;
    padding: 1 2;
}

#oven-widget {
    text-align: center;
    height: auto;
    margin: 1 0;
}

#mascot-widget {
    height: auto;
    text-align: center;
    margin-bottom: 1;
}

#baking-status-text {
    text-align: center;
    color: #f1fa8c;
    text-style: bold;
    margin: 1 0;
}

#retro-progress-gauge {
    text-align: center;
    margin-bottom: 1;
}

#baking-score-card {
    background: #161c2d;
    border: round #50fa7b;
    padding: 1;
    margin: 1 0;
    display: none;
}

#baking-action-bar {
    align: center middle;
    height: 3;
    margin-top: 1;
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
        super().__init__(MASCOT_FRAMES[0], id=id, classes=classes)
        self.frame_idx: int = 0
        self.active_message: Optional[str] = None
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.9, self.advance_frame)

    def advance_frame(self) -> None:
        self.frame_idx = (self.frame_idx + 1) % len(MASCOT_FRAMES)
        frame_text = MASCOT_FRAMES[self.frame_idx]
        if self.active_message:
            # Inject dynamic message bubble
            frame_text = frame_text.replace('< "Proofing your career..."', f'< "{self.active_message}"')
        self.update(frame_text)

    def set_message(self, message: str) -> None:
        self.active_message = message
        self.advance_frame()


class PokemonBakeryCounter(Static):
    """8-bit Pokémon-style bakery shop counter with animated Baker Crumb and dialogue box."""

    DEFAULT_CSS = """
    PokemonBakeryCounter {
        height: auto;
        margin-bottom: 1;
    }
    #counter-scene-row {
        height: 7;
    }
    #counter-baker-sprite {
        width: 16;
        height: 6;
        margin-right: 1;
    }
    #counter-dialogue-box {
        width: 1fr;
        height: 6;
        background: #141926;
        border: round #d4a373;
        padding: 0 1;
    }
    .poke-dialogue-title {
        color: #f4a261;
        text-style: bold;
    }
    .poke-dialogue-body {
        color: #fefae0;
    }
    .poke-dialogue-status {
        color: #52b788;
        text-style: bold;
        text-align: right;
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
        self.badge_title = "💬 BAKER CRUMB [dim](Lv. 100 Master Baker)[/]"
        self.status_line = "Verified Ingredients Only ♪ ▼"
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
        ("🌾", "PANTRY"),
        ("🥣", "KNEAD"),
        ("🥖", "PROOF"),
        ("♨️", "OVEN"),
        ("🍞", "GOLDEN LOAF")
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

class BakingModal(ModalScreen):
    """Full retro 8-bit arcade baking modal dialog with animated oven & progress tracker."""

    def __init__(
        self,
        task_type: str,  # "tailor" or "bake_pdf"
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
                "🥖 BREADWINNER ARCADE BAKERY 🥖"
                if self.task_type == "tailor"
                else "♨️ HEADLESS OVEN PDF BAKE ♨️"
            )
            yield Label(f"[bold #ffb86c]{header_title}[/bold #ffb86c]", id="baking-title")
            yield BakeryStepper(current_stage=0, id="modal-stepper")
            yield Center(AnimatedOven(id="oven-widget"))
            yield Label("[bold #f1fa8c]Preheating the stone hearth...[/bold #f1fa8c]", id="baking-status-text")
            yield Center(RetroProgressBar(percent=5, id="retro-progress-gauge"))

            with Vertical(id="baking-score-card"):
                yield Label("", id="score-card-title")
                yield Label("", id="score-card-details")

            with Horizontal(id="baking-action-bar"):
                yield Button("Cancel Bake", variant="error", id="btn-modal-cancel")
                yield Button("Collect Loaf (Inspect)", variant="success", id="btn-modal-collect", classes="hidden")
                yield Button("View PDF (v)", variant="primary", id="btn-modal-view-pdf", classes="hidden")
                yield Button("Open Folder (o)", variant="default", id="btn-modal-open-folder", classes="hidden")

    def on_mount(self) -> None:
        # Hide finished buttons initially
        self.query_one("#btn-modal-collect", Button).display = False
        self.query_one("#btn-modal-view-pdf", Button).display = False
        self.query_one("#btn-modal-open-folder", Button).display = False
        self.query_one("#baking-score-card", Vertical).display = False

        # Launch background worker
        if self.task_type == "tailor":
            self.run_tailor_worker()
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
            self.app.call_from_thread(status_lbl.update, "[bold #8be9fd]🌾 Gathering verified pantry facts & parsing JD...[/bold #8be9fd]")
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
            self.app.call_from_thread(
                status_lbl.update,
                f"[bold #ffb86c]🥣 Kneading narrative persona ({persona.name[:25]})...[/bold #ffb86c]"
            )
            time.sleep(0.4)

            provider = get_llm_provider()

            # STAGE 2: PROOF (LLM BULLET TAILORING)
            self.app.call_from_thread(stepper.set_stage, 2)
            self.app.call_from_thread(gauge.update_progress, 60)
            self.app.call_from_thread(
                status_lbl.update,
                "[bold #f1fa8c]🥖 Proofing XYZ formulas & verifiable metrics...[/bold #f1fa8c]"
            )

            engine = TailoringEngine(provider)
            app_result = engine.analyze_and_tailor(profile, job, persona, job_directives=directives)

            # STAGE 3: OVEN (RENDERING TEMPLATES)
            self.app.call_from_thread(stepper.set_stage, 3)
            self.app.call_from_thread(gauge.update_progress, 80)
            self.app.call_from_thread(
                status_lbl.update,
                f"[bold #ff79c6]♨️ Preheating stone peel for {template_name.upper()} template...[/bold #ff79c6]"
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
            (app_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
            (app_dir / "portal_answers.md").write_text(portal_qna, encoding="utf-8")

            # STAGE 4: GOLDEN LOAF (PDF BAKE)
            self.app.call_from_thread(stepper.set_stage, 4)
            self.app.call_from_thread(gauge.update_progress, 95)
            self.app.call_from_thread(status_lbl.update, "[bold #50fa7b]🍞 Caramelizing crust into print-ready PDF...[/bold #50fa7b]")

            pdf_baked = False
            pdf_path = app_dir / "resume.pdf"
            if settings.auto_generate_pdf:
                try:
                    render_html_to_pdf(app_dir / "resume.html", pdf_path, open_after=False)
                    pdf_baked = True
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
                persona=persona.slug,
                date_added=date_slug,
                folder_path=str(app_dir.resolve()),
                notes=f"Tailored via {persona.name}" + (" (with custom strategy loop)" if directives else "")
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
                "template": template_name
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
            html_path = target_dir / "resume.html"
            pdf_path = target_dir / "resume.pdf"

            self.app.call_from_thread(stepper.set_stage, 3)
            self.app.call_from_thread(gauge.update_progress, 40)
            self.app.call_from_thread(status_lbl.update, "[bold #ffb86c]♨️ Launching headless Chromium bakery oven...[/bold #ffb86c]")
            time.sleep(0.4)

            self.app.call_from_thread(stepper.set_stage, 4)
            self.app.call_from_thread(gauge.update_progress, 75)
            self.app.call_from_thread(status_lbl.update, "[bold #50fa7b]🍞 Rendering crisp vector PDF typography...[/bold #50fa7b]")

            render_html_to_pdf(html_path, pdf_path, open_after=False)
            size_kb = round(pdf_path.stat().st_size / 1024, 1)

            self.baking_result = {
                "success": True,
                "app_dir": target_dir,
                "pdf_baked": True,
                "size_kb": size_kb
            }

            time.sleep(0.3)
            self.app.call_from_thread(self._show_victory_pdf_screen, target_dir, size_kb)

        except Exception as e:
            self.app.call_from_thread(self._show_error_screen, str(e))

    # --------------------------------------------------------------------------
    # VICTORY / ERROR SCREEN UPDATES (CALLED ON UI THREAD)
    # --------------------------------------------------------------------------

    def _show_victory_screen(self, score: int, company: str, title: str, app_dir: Path, pdf_baked: bool) -> None:
        self.is_done = True
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("celebrate")

        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        gauge.update_progress(100)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #50fa7b]✨ DING! GOLDEN LOAF CERTIFIED OUT OF THE OVEN! ✨[/bold #50fa7b]")

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #f1fa8c]🏆 HIGH SCORE: {score}% ATS MATCH[/bold #f1fa8c] | [bold #50fa7b]{company} — {title}[/bold #50fa7b]")

        pdf_status = "Baked ✓ (resume.pdf)" if pdf_baked else "Not baked (press 'b')"
        score_details = self.query_one("#score-card-details", Label)
        score_details.update(
            f"[dim]Saved Package:[/] [cyan]{app_dir.name}[/cyan]\n"
            f"[dim]PDF Status:[/] [bold green]{pdf_status}[/bold green]"
        )

        self.query_one("#btn-modal-cancel", Button).display = False
        self.query_one("#btn-modal-collect", Button).display = True
        if pdf_baked:
            self.query_one("#btn-modal-view-pdf", Button).display = True
        self.query_one("#btn-modal-open-folder", Button).display = True

    def _show_victory_pdf_screen(self, app_dir: Path, size_kb: float) -> None:
        self.is_done = True
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("celebrate")

        gauge = self.query_one("#retro-progress-gauge", RetroProgressBar)
        gauge.update_progress(100)

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update("[bold #50fa7b]✨ DING! FRESH PRINT-READY PDF BAKED! ✨[/bold #50fa7b]")

        score_card = self.query_one("#baking-score-card", Vertical)
        score_card.display = True

        score_title = self.query_one("#score-card-title", Label)
        score_title.update(f"[bold #f1fa8c]📄 ATS PDF READY[/bold #f1fa8c] | [bold #50fa7b]{size_kb} KB[/bold #50fa7b]")

        score_details = self.query_one("#score-card-details", Label)
        score_details.update(f"[dim]Location:[/] [cyan]{app_dir / 'resume.pdf'}[/cyan]")

        self.query_one("#btn-modal-cancel", Button).display = False
        self.query_one("#btn-modal-collect", Button).display = True
        self.query_one("#btn-modal-view-pdf", Button).display = True
        self.query_one("#btn-modal-open-folder", Button).display = True

    def _show_error_screen(self, error_msg: str) -> None:
        oven = self.query_one("#oven-widget", AnimatedOven)
        oven.set_state("burnt")

        status_lbl = self.query_one("#baking-status-text", Label)
        status_lbl.update(f"[bold #ff5555]BURNT CRUST: {error_msg}[/bold #ff5555]")

        cancel_btn = self.query_one("#btn-modal-cancel", Button)
        cancel_btn.label = "Dismiss (Esc)"

    # --------------------------------------------------------------------------
    # BUTTON INTERACTIONS
    # --------------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-modal-cancel":
            self.dismiss(None)
        elif bid == "btn-modal-collect":
            self.dismiss(self.baking_result)
        elif bid == "btn-modal-view-pdf":
            if self.baking_result and self.baking_result.get("app_dir"):
                p = self.baking_result["app_dir"] / "resume.pdf"
                if p.exists():
                    open_file_in_viewer(p)
        elif bid == "btn-modal-open-folder":
            if self.baking_result and self.baking_result.get("app_dir"):
                import subprocess
                subprocess.run(["open", str(self.baking_result["app_dir"])])
