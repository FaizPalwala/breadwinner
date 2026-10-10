"""Tests for Sprint 5: Pixel Engine, Domed Hearth, Retro Visualizations, and Zero-Emoji Invariant."""

import os
import re
import pytest
from rich.text import Text

from breadwinner.ui.pixel_engine import (
    PixelCanvas,
    PixelSpriteSheet,
    PixelSpriteWidget,
    hex_to_rgb,
)
from breadwinner.ui.visuals import (
    DomedHearthPixelWidget,
    SkillConstellationWidget,
    CrustSpectrumWidget,
    PipelineFunnelWidget,
    PantryMaturityWidget,
    PALETTE_HEARTH,
    HEARTH_FRAMES,
)


def test_hex_to_rgb():
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("#0000ff") == (0, 0, 255)
    assert hex_to_rgb("f00") == (255, 0, 0)
    assert hex_to_rgb("invalid") == (0, 0, 0)


def test_pixel_canvas_set_and_fill():
    canvas = PixelCanvas(width=10, height=10, default_color=(10, 10, 10))
    assert canvas.width == 10
    assert canvas.height == 10
    assert canvas.buffer[0][0] == (10, 10, 10)

    # Set single pixel
    canvas.set_pixel(2, 3, (255, 200, 100))
    assert canvas.buffer[3][2] == (255, 200, 100)

    # Set with hex string
    canvas.set_pixel(4, 5, "#38bdf8")
    assert canvas.buffer[5][4] == (56, 189, 248)

    # Out of bounds ignored gracefully
    canvas.set_pixel(99, 99, (255, 255, 255))
    canvas.set_pixel(-1, -1, (255, 255, 255))

    # Fill rectangle
    canvas.fill_rect(0, 0, 3, 2, (100, 150, 200))
    for r in range(2):
        for c in range(3):
            assert canvas.buffer[r][c] == (100, 150, 200)


def test_pixel_canvas_half_block_rendering():
    canvas = PixelCanvas(width=4, height=4, default_color=(20, 20, 20))
    canvas.set_pixel(0, 0, (255, 0, 0))    # top pixel of cell (0, 0)
    canvas.set_pixel(0, 1, (0, 255, 0))    # bottom pixel of cell (0, 0)

    rendered = canvas.render_half_blocks()
    assert "▄" in rendered
    # Must contain ANSI TrueColor sequences
    assert "\x1b[48;2;" in rendered
    assert "\x1b[38;2;" in rendered

    # Textual / Rich parser must parse it cleanly into text without crashing
    parsed = Text.from_ansi(rendered)
    assert len(parsed.plain) > 0


def test_pixel_sprite_sheet_and_widget():
    mini_palette = {
        ".": (20, 20, 20),
        "R": (255, 0, 0),
        "G": (0, 255, 0),
    }
    frames = [
        ["R.", ".G"],
        [".R", "G."],
    ]
    sheet = PixelSpriteSheet(frames, mini_palette)
    frame0 = sheet.render_frame(0)
    frame1 = sheet.render_frame(1)
    assert len(frame0) > 0
    assert len(frame1) > 0

    widget = PixelSpriteWidget(sheet, fps=5.0, auto_play=False)
    assert widget.current_frame == 0
    widget.advance_frame()
    assert widget.current_frame == 1
    widget.advance_frame()
    assert widget.current_frame == 0


def test_domed_hearth_pixel_widget():
    widget = DomedHearthPixelWidget()
    assert widget.sprite_sheet is not None
    assert len(widget.sprite_sheet.frames) == len(HEARTH_FRAMES)
    widget.set_frame(2)
    assert widget.current_frame == 2
    rendered = widget.sprite_sheet.render_frame(2)
    assert "▄" in rendered


def test_skill_constellation_widget():
    widget = SkillConstellationWidget()
    # Empty case
    widget.update_constellation(set(), [])
    assert "Awaiting job description" in str(widget.render())

    # With skills
    candidate = {"Python", "FastAPI", "PostgreSQL", "Docker"}
    demanded = ["Python", "FastAPI", "Kubernetes", "Redis"]
    must_haves = ["Python", "Kubernetes"]

    widget.update_constellation(candidate, demanded, must_haves)
    rendered = str(widget.render())
    assert "CORE TECHNICAL ALIGNMENT CONSTELLATION" in rendered
    assert "VERIFIED" in rendered
    assert "MUST-HAVE GAP" in rendered
    assert "HARD ALIGNMENT INDEX" in rendered


def test_crust_spectrum_widget():
    widget = CrustSpectrumWidget()
    widget.update_spectrum(
        quantified_pct=85,
        action_verb_pct=90,
        seniority_velocity=[2, 4, 6, 8, 9],
        provenance_verified=True,
    )
    rendered = str(widget.render())
    assert "IMPACT BREAKDOWN" in rendered
    assert "CAREER VELOCITY" in rendered
    assert "PROVENANCE: 100% GROUNDED" in rendered

    # Warning case
    widget.update_spectrum(provenance_verified=False)
    rendered_warn = str(widget.render())
    assert "PROVENANCE WARNING" in rendered_warn


def test_pipeline_funnel_widget():
    widget = PipelineFunnelWidget()
    widget.update_pipeline(draft_count=3, applied_count=5, interview_count=2, offer_count=1)
    rendered = str(widget.render())
    assert "PIPELINE MOMENTUM" in rendered
    assert "DRAFT: 3" in rendered
    assert "APPLIED: 5" in rendered
    assert "INTERVIEWING: 2" in rendered
    assert "OFFER: 1" in rendered
    assert "Total: 11" in rendered


def test_pantry_maturity_widget():
    widget = PantryMaturityWidget()
    # Low maturity
    widget.update_maturity(exp_count=0, proj_count=1, facts_count=2)
    rendered_low = str(widget.render())
    assert "DEVELOPING DOUGH" in rendered_low

    # High maturity
    widget.update_maturity(exp_count=4, proj_count=4, facts_count=15)
    rendered_high = str(widget.render())
    assert "LEVAIN ACTIVE" in rendered_high


def test_zero_emoji_invariant_in_ui():
    """Strict architectural invariant: ZERO double-width or variation selector emojis in UI.
    
    Ensures zero terminal column glitches and clean, single-width typography.
    """
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe0f]")
    ui_dir = "src/breadwinner/ui"
    allowed_typographic = {"✓", "✔", "★", "✕", "⛶", "♨", "⚑", "✦", "✧"}

    violations = []
    for root, _, files in os.walk(ui_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    for line_idx, line in enumerate(fh, 1):
                        clean_line = line
                        for allowed in allowed_typographic:
                            clean_line = clean_line.replace(allowed, "")
                        found = emoji_pattern.findall(clean_line)
                        if found:
                            violations.append(
                                f"{path}:{line_idx} contains emoji {found}: {line.strip()[:60]}"
                            )

    assert not violations, f"Emoji invariant violated in UI:\n" + "\n".join(violations)
