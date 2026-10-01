"""Core 8-Bit Pixel Art & TrueColor Sub-Pixel Half-Block Engine for Textual.

Renders authentic retro arcade sprites, animations, and visual meters in standard ANSI
terminals using the Unicode Lower Half Block (U+2584, '▄') with 24-bit TrueColor.
Every character cell represents two perfectly square RGB pixels:
- Background Color: Top Pixel
- Foreground Color: Bottom Pixel
"""

import time
from typing import List, Tuple, Dict, Optional, Union
from textual.widgets import Static


RGBColor = Tuple[int, int, int]


def hex_to_rgb(hex_code: str) -> RGBColor:
    """Convert hex color string (#RRGGBB) to (R, G, B) tuple."""
    hex_clean = hex_code.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) != 6:
        return (0, 0, 0)
    return (
        int(hex_clean[0:2], 16),
        int(hex_clean[2:4], 16),
        int(hex_clean[4:6], 16),
    )


class PixelCanvas:
    """2D RGB Pixel buffer rendered via Unicode half-blocks with 24-bit TrueColor."""

    def __init__(self, width: int, height: int, default_color: RGBColor = (22, 22, 30)):
        self.width = width
        # Height must be even for 2-pixel half-blocks
        self.height = height if height % 2 == 0 else height + 1
        self.default_color = default_color
        self.buffer: List[List[RGBColor]] = [
            [default_color for _ in range(self.width)]
            for _ in range(self.height)
        ]

    def set_pixel(self, x: int, y: int, color: Union[RGBColor, str]) -> None:
        """Set a single pixel at (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            if isinstance(color, str):
                self.buffer[y][x] = hex_to_rgb(color)
            else:
                self.buffer[y][x] = color

    def fill_rect(self, x: int, y: int, w: int, h: int, color: Union[RGBColor, str]) -> None:
        """Fill a rectangle with a solid color."""
        c = hex_to_rgb(color) if isinstance(color, str) else color
        for row in range(y, min(self.height, y + h)):
            for col in range(x, min(self.width, x + w)):
                self.buffer[row][col] = c

    def render_half_blocks(self) -> str:
        """Render the 2D pixel buffer into a multi-line half-block ANSI TrueColor string."""
        lines = []
        for y in range(0, self.height, 2):
            line_parts = []
            for x in range(self.width):
                top_r, top_g, top_b = self.buffer[y][x]
                bot_r, bot_g, bot_b = self.buffer[y + 1][x]
                # ANSI TrueColor: \x1b[38;2;R;G;Bm (fg) and \x1b[48;2;R;G;Bm (bg)
                line_parts.append(
                    f"\x1b[48;2;{top_r};{top_g};{top_b}m\x1b[38;2;{bot_r};{bot_g};{bot_b}m▄\x1b[0m"
                )
            lines.append("".join(line_parts))
        return "\n".join(lines)


class PixelSpriteSheet:
    """Container for multi-frame pixel art animations."""

    def __init__(self, frames: List[List[str]], color_palette: Dict[str, RGBColor]):
        """
        frames: list of 2D character matrices (rows of strings).
        color_palette: mapping from single characters to RGB tuples. '.' is transparent/background.
        """
        self.frames = frames
        self.palette = color_palette
        self.bg_color = color_palette.get(".", (22, 22, 30))

    def render_frame(self, frame_idx: int) -> str:
        """Render a specific frame index into half-block ANSI TrueColor string."""
        if not self.frames:
            return ""
        frame = self.frames[frame_idx % len(self.frames)]
        height = len(frame)
        width = max(len(row) for row in frame) if height > 0 else 0

        canvas = PixelCanvas(width, height, default_color=self.bg_color)
        for y, row in enumerate(frame):
            for x, char in enumerate(row):
                color = self.palette.get(char, self.bg_color)
                canvas.set_pixel(x, y, color)
        return canvas.render_half_blocks()


from rich.text import Text


class PixelSpriteWidget(Static):
    """Textual widget that displays and animates pixel art sprites smoothly."""

    def __init__(
        self,
        sprite_sheet: PixelSpriteSheet,
        fps: float = 8.0,
        auto_play: bool = True,
        id: Optional[str] = None,
        classes: Optional[str] = None
    ):
        super().__init__("", id=id, classes=classes)
        self.sprite_sheet = sprite_sheet
        self.fps = fps
        self.auto_play = auto_play
        self.current_frame: int = 0
        self.timer = None

    def on_mount(self) -> None:
        if self.auto_play and len(self.sprite_sheet.frames) > 1:
            interval = 1.0 / max(1.0, self.fps)
            self.timer = self.set_interval(interval, self.advance_frame)

    def advance_frame(self) -> None:
        self.current_frame = (self.current_frame + 1) % len(self.sprite_sheet.frames)
        self.refresh()

    def set_frame(self, frame_idx: int) -> None:
        self.current_frame = frame_idx % len(self.sprite_sheet.frames)
        self.refresh()

    def render(self):
        rendered = self.sprite_sheet.render_frame(self.current_frame)
        return Text.from_ansi(rendered)

