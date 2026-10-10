"""Comprehensive 8-Bit Retro Bakery Visualizations & Clean Iconography Widgets.

Provides pixel-crafted UI visualizations using Unicode half-blocks, box drawing,
and single-width geometric icons (strictly avoiding emojis and AI slop).
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from textual.widgets import Static
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult

from breadwinner.ui.pixel_engine import PixelCanvas, PixelSpriteSheet, PixelSpriteWidget, RGBColor
from breadwinner.core.models import CandidateProfile, JobPosting, TailoredApplication


# --- PALETTES ---
PALETTE_HEARTH: Dict[str, RGBColor] = {
    ".": (22, 22, 30),       # Background cast iron (#16161E)
    "B": (60, 64, 80),       # Brick grey / stone
    "D": (180, 80, 50),      # Dark brick / terracotta
    "L": (217, 143, 82),     # Crust gold (#D18F52)
    "W": (255, 255, 255),    # White heat core
    "A": (245, 158, 11),     # Amber fire (#F59E0B)
    "R": (217, 4, 41),       # Crimson flame (#D90429)
    "C": (148, 163, 184),    # Chimney smoke light grey
    "S": (100, 116, 139),    # Dark smoke
    "G": (244, 162, 97),     # Golden bread loaf
    "K": (100, 50, 20),      # Dark bread crust / scoring
    "g": (244, 162, 97),     # Golden bread loaf (fallback)
}

# 24 columns wide, 14 rows high (renders as 24 cols x 7 text rows via half-blocks)
HEARTH_FRAMES = [
    # Frame 0: Cold start / Resting dough
    [
        "........CCCC............",
        "........SSSS............",
        ".....BBBBBBBBBB.........",
        "...BB..........BB.......",
        "..D...WAAAAAAW...D......",
        ".D...AAAAAAAAAA...D.....",
        ".D..AAAAAAAAAAAA..D.....",
        "B...RRRRRRRRRRRR...B....",
        "B...RRRRRRRRRRRR...B....",
        "B.....GGGGGGGG.....B....",
        "B....GGGGGGGGGG....B....",
        "B....GGGGGGGGGG....B....",
        "BBBBBBBBBBBBBBBBBBBB....",
        "BBBBBBBBBBBBBBBBBBBB....",
    ],
    # Frame 1: Flame rising / Dough expanding
    [
        "........S.CC............",
        ".......CC.SS............",
        ".....BBBBBBBBBB.........",
        "...BB..........BB.......",
        "..D...WAAAAAAW...D......",
        ".D...AAAAAAAAAA...D.....",
        ".D..AAAAAAAAAAAA..D.....",
        "B...RRRRAAAARRRR...B....",
        "B...RRRRWWWWRAAA...B....",
        "B...GGGGGGGGGGGG...B....",
        "B..GGGGGGGGGGGGGG..B....",
        "B..GGGGGGGGGGGGGG..B....",
        "BBBBBBBBBBBBBBBBBBBB....",
        "BBBBBBBBBBBBBBBBBBBB....",
    ],
    # Frame 2: Scoring marks appearing / High heat
    [
        ".......CC...S...........",
        "........SS..C...........",
        ".....BBBBBBBBBB.........",
        "...BB..........BB.......",
        "..D...WAAAAAAW...D......",
        ".D...AAAAAAAAAA...D.....",
        ".D..AAAAAAAAAAAA..D.....",
        "B...WWRAAAAAARWW...B....",
        "B...RRRRAAAARRRR...B....",
        "B...GGKGGGGKGGGG...B....",
        "B..GGGKKGGKKGGGGG..B....",
        "B..GGGGKKGGKKGGGG..B....",
        "BBBBBBBBBBBBBBBBBBBB....",
        "BBBBBBBBBBBBBBBBBBBB....",
    ],
    # Frame 3: Oven Spring Complete / Golden Crust Loaf
    [
        ".........CC.SS..........",
        "........CC..SS..........",
        ".....BBBBBBBBBB.........",
        "...BB..........BB.......",
        "..D...WAAAAAAW...D......",
        ".D...AAAAAAAAAA...D.....",
        ".D..AAAAAAAAAAAA..D.....",
        "B...RRRRWWWWRAAA...B....",
        "B...AAARAAAAAAAR...B....",
        "B..LLKLLLLKLLLLG...B....",
        "B..LLLKLLLLKLLLG...B....",
        "B..LLLLKKLLLKKLL...B....",
        "BBBBBBBBBBBBBBBBBBBB....",
        "BBBBBBBBBBBBBBBBBBBB....",
    ],
]


class DomedHearthPixelWidget(PixelSpriteWidget):
    """Animated 8-bit Domed Wood-Fired Hearth Oven with Sourdough Expansion."""

    def __init__(self, id: Optional[str] = "domed-hearth-pixel"):
        sheet = PixelSpriteSheet(HEARTH_FRAMES, PALETTE_HEARTH)
        super().__init__(sheet, fps=6.0, auto_play=True, id=id)


class SkillConstellationWidget(Static):
    """Visual 2D Skill Overlap Radar & Constellation comparing Candidate vs JD."""

    def __init__(self, id: Optional[str] = "skill-constellation-box"):
        super().__init__("", id=id)

    def update_constellation(
        self,
        candidate_skills: Set[str],
        demanded_skills: List[str],
        hard_must_haves: Optional[List[str]] = None
    ) -> None:
        if not demanded_skills:
            self.update("[dim #94A3B8]· Awaiting job description to calculate skill constellation ·[/dim #94A3B8]")
            return

        cand_lower = {s.lower().strip() for s in candidate_skills}
        must_haves_lower = " ".join(hard_must_haves or []).lower()

        lines = [
            "[bold #FFB86C]CORE TECHNICAL ALIGNMENT CONSTELLATION[/bold #FFB86C] [dim]• Verified Pantry vs JD[/dim]"
        ]

        # Group skills into aligned vs gaps
        matched_count = 0
        total_count = min(len(demanded_skills), 8)

        for skill in demanded_skills[:8]:
            s_low = skill.lower().strip()
            is_match = s_low in cand_lower or any(s_low in cs or cs in s_low for cs in cand_lower)
            is_must_have = s_low in must_haves_lower

            if is_match:
                matched_count += 1
                stars = "[bold #50FA7B]✦✦✦✦✦[/bold #50FA7B]"
                status = "[bold #50FA7B]VERIFIED[/]"
            elif is_must_have:
                stars = "[bold #FF5555]✧░░░░[/bold #FF5555]"
                status = "[bold #FF5555]MUST-HAVE GAP[/]"
            else:
                stars = "[#FFB86C]✧✧░░░[/#FFB86C]"
                status = "[dim #94A3B8]NICE-TO-HAVE[/]"

            label_skill = f"{skill:<18}"
            lines.append(f" {label_skill} {stars} {status}")

        pct = int((matched_count / total_count * 100)) if total_count > 0 else 0
        filled = int((pct / 100) * 20)
        empty = 20 - filled
        color = "#50FA7B" if pct >= 75 else ("#FFB86C" if pct >= 50 else "#FF5555")

        bar = f"[{color}]{'█' * filled}[/][#334155]{'░' * empty}[/] [bold {color}]{pct:>3}%[/]"
        lines.append(f"\n HARD ALIGNMENT INDEX: {bar} [dim]({matched_count}/{total_count} Verified Core Skills)[/dim]")

        self.update("\n".join(lines))


class CrustSpectrumWidget(Static):
    """Experience Impact Breakdown & Seniority Progression Sparkline."""

    def __init__(self, id: Optional[str] = "crust-spectrum-box"):
        super().__init__("", id=id)

    def update_spectrum(
        self,
        quantified_pct: int = 80,
        action_verb_pct: int = 85,
        seniority_velocity: Optional[List[int]] = None,
        provenance_verified: bool = True
    ) -> None:
        # Stacked spectrum bar (30 blocks wide)
        high_blocks = int((quantified_pct / 100) * 20)
        med_blocks = int((action_verb_pct / 100) * 7)
        low_blocks = max(0, 30 - high_blocks - med_blocks)

        stacked_bar = (
            f"[bold #50FA7B]{'█' * high_blocks}[/]"
            f"[bold #FFB86C]{'█' * med_blocks}[/]"
            f"[#334155]{'░' * low_blocks}[/]"
        )

        # Seniority sparkline from past experiences
        velocities = seniority_velocity or [2, 3, 5, 7, 8, 9]
        spark_glyphs = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        sparkline = "".join(spark_glyphs[min(len(spark_glyphs) - 1, max(0, int(v * 0.8)))] for v in velocities)

        prov_seal = (
            "[bold #50FA7B]PROVENANCE: 100% GROUNDED[/bold #50FA7B]"
            if provenance_verified
            else "[bold #FFB86C]PROVENANCE WARNING: PENDING CHECK[/bold #FFB86C]"
        )

        content = (
            f"[bold #FFB86C]IMPACT BREAKDOWN[/bold #FFB86C] [dim]• Quantified Outcomes[/dim]\n"
            f" {stacked_bar}  [bold #50FA7B]{quantified_pct}% High[/] [dim]•[/] [bold #FFB86C]{action_verb_pct}% Med[/]\n"
            f" CAREER VELOCITY: [bold #38BDF8]{sparkline}[/bold #38BDF8]\n"
            f" {prov_seal}"
        )
        self.update(content)


class PipelineFunnelWidget(Static):
    """Visual Application Stage Pipeline Funnel."""

    DEFAULT_CSS = """
    PipelineFunnelWidget {
        width: 100%;
        height: 3;
        max-height: 3;
        overflow: hidden;
        margin-bottom: 1;
    }
    """

    def __init__(self, id: Optional[str] = "pipeline-funnel-box"):
        super().__init__("", id=id)
        self.draft_count = 0
        self.applied_count = 0
        self.interview_count = 0
        self.offer_count = 0

    def on_mount(self) -> None:
        self.refresh_box()

    def on_resize(self, event: Any) -> None:
        self.refresh_box(event.size.width)

    def update_pipeline(
        self,
        draft_count: int = 0,
        applied_count: int = 0,
        interview_count: int = 0,
        offer_count: int = 0
    ) -> None:
        self.draft_count = draft_count
        self.applied_count = applied_count
        self.interview_count = interview_count
        self.offer_count = offer_count
        self.refresh_box()

    def refresh_box(self, width: int = 0) -> None:
        if width > 0:
            w = width
        elif self.size.width > 0:
            w = self.size.width
        elif self.is_mounted and hasattr(self.app, "size") and self.app.size.width > 0:
            sidebar_w = 24 if getattr(self.app, "layout_preset", "") != "split" else 0
            w = max(78, self.app.size.width - sidebar_w - 3)
        else:
            w = 80
        w = max(w, 78)
        total = self.draft_count + self.applied_count + self.interview_count + self.offer_count
        c_draft = "#94A3B8"
        c_appl = "#38BDF8"
        c_int = "#F59E0B"
        c_off = "#50FA7B"

        funnel_line = (
            f"[{c_draft}][DRAFT: {self.draft_count}][/] ──> "
            f"[{c_appl}][APPLIED: {self.applied_count}][/] ──> "
            f"[{c_int}][INTERVIEWING: {self.interview_count}][/] ──> "
            f"[{c_off}][OFFER: {self.offer_count}][/]  [dim](Total: {total})[/dim]"
        )

        title = "┌── [bold #FFB86C]PIPELINE MOMENTUM[/bold #FFB86C] "
        title_plain_len = 22  # len('┌── PIPELINE MOMENTUM ')
        dashes_top = max(1, w - title_plain_len - 1)
        top = f"{title}{'─' * dashes_top}┐"

        plain_text = f"[DRAFT: {self.draft_count}] ──> [APPLIED: {self.applied_count}] ──> [INTERVIEWING: {self.interview_count}] ──> [OFFER: {self.offer_count}]  (Total: {total})"
        pad = max(1, w - 1 - 2 - len(plain_text) - 1)
        mid = f"│  {funnel_line}{' ' * pad}│"

        dashes_bottom = max(1, w - 2)
        bottom = f"└{'─' * dashes_bottom}┘"

        self.update(f"{top}\n{mid}\n{bottom}")


class PantryMaturityWidget(Static):
    """Visual Sourdough Starter Jar Maturity & Fact Grounding Meter."""

    def __init__(self, id: Optional[str] = "pantry-maturity-box"):
        super().__init__("", id=id)

    def update_maturity(
        self,
        exp_count: int = 0,
        proj_count: int = 0,
        facts_count: int = 0
    ) -> None:
        # Score maturity based on pantry completeness
        score = min(100, int((exp_count * 15) + (proj_count * 10) + (facts_count * 2)))
        filled = int((score / 100) * 16)
        empty = 16 - filled
        color = "#50FA7B" if score >= 80 else ("#FFB86C" if score >= 40 else "#FF5555")

        bar = f"[{color}]{'█' * filled}[/][#334155]{'░' * empty}[/] [bold {color}]{score:>3}%[/]"
        maturity_label = "LEVAIN ACTIVE (Ready to Bake)" if score >= 80 else "DEVELOPING DOUGH"

        content = (
            f"[bold #FFB86C]PANTRY STARTER MATURITY[/bold #FFB86C] [dim]• {maturity_label}[/dim]\n"
            f" {bar} [dim]({exp_count} Exp • {proj_count} Proj • {facts_count} Verified Facts)[/dim]"
        )
        self.update(content)
