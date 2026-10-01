"""Screen Guard Sentinel for Breadwinner.

Displays a retro bakery notice when the user's terminal window is too compact
to render the interface safely, preventing glitching, clipping, or truncated widgets.
Automatically dismisses as soon as the user expands their terminal to minimum bounds.
"""

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label
from textual.containers import Vertical, Center


SCREEN_GUARD_CSS = """
ScreenGuardScreen {
    align: center middle;
    background: #0b0e17;
}

#guard-container {
    width: 62;
    max-width: 96%;
    height: auto;
    border: heavy #f4a261;
    background: #10141f;
    padding: 1 2;
}

.guard-title {
    text-align: center;
    color: #f4a261;
    text-style: bold;
    margin-bottom: 1;
}

.guard-dialogue {
    text-align: center;
    color: #fefae0;
    margin-bottom: 1;
}

.guard-dimensions {
    text-align: center;
    color: #52b788;
    text-style: bold;
    margin-bottom: 1;
}

.guard-hint {
    text-align: center;
    color: #94a3b8;
}
"""


class ScreenGuardScreen(Screen):
    """Full-screen defensive overlay active when terminal is under minimum resolution."""

    DEFAULT_CSS = SCREEN_GUARD_CSS

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True),
    ]

    def __init__(self, min_cols: int = 76, min_rows: int = 22):
        super().__init__()
        self.min_cols = min_cols
        self.min_rows = min_rows

    def compose(self) -> ComposeResult:
        cur_w = self.app.size.width if self.app else 0
        cur_h = self.app.size.height if self.app else 0

        with Center():
            with Vertical(id="guard-container"):
                yield Label("[■] CRUMB'S HEARTH GUARD", classes="guard-title")
                yield Label(
                    "( o . o )  \"The oven needs a bit more hearth room to bake!\n             Please expand your terminal window.\"",
                    classes="guard-dialogue"
                )
                yield Label(
                    f"Current: {cur_w} cols × {cur_h} rows  •  Minimum: {self.min_cols} × {self.min_rows}",
                    id="guard-dimensions-label",
                    classes="guard-dimensions"
                )
                yield Label(
                    "[dim]Drag your window edge or zoom out ([bold white]Cmd -[/]) • Press [bold white]q[/] to quit[/dim]",
                    classes="guard-hint"
                )

    def on_resize(self, event: events.Resize) -> None:
        """Update live terminal dimensions reactively as user drags window edge."""
        self.update_dimensions(event.size.width, event.size.height)

    def update_dimensions(self, current_cols: int, current_rows: int) -> None:
        """Update live terminal dimensions label."""
        try:
            lbl = self.query_one("#guard-dimensions-label", Label)
            lbl.update(f"Current: {current_cols} cols × {current_rows} rows  •  Minimum: {self.min_cols} × {self.min_rows}")
        except Exception:
            pass

    def action_quit_app(self) -> None:
        """Allow user to cleanly quit from the screen guard."""
        self.app.exit()

