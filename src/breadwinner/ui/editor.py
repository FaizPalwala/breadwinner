"""Dual-Pane Interactive Bullet Fine-Tuning Studio with Live XYZ Metric Audit."""

import re
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Label, Button, TextArea, Markdown
from textual.binding import Binding
from textual.screen import ModalScreen

from breadwinner.core.models import CandidateProfile, TailoredApplication, WorkExperience
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.ui.audio_widgets import AudioDictationModal


STRONG_ACTION_VERBS = {
    "architected", "engineered", "designed", "implemented", "spearheaded",
    "developed", "scaled", "optimized", "streamlined", "accelerated",
    "automated", "reduced", "increased", "decreased", "eliminated",
    "mentored", "orchestrated", "refactored", "migrated", "delivered",
    "authored", "built", "launched", "executed", "configured", "deployed",
    "benchmarked", "evaluated", "trained", "quantized", "ablated",
    "finetuned", "fine-tuned", "curated"
}

METRIC_PATTERNS = [
    r"\b\d+%\b",                  # 45%
    r"\b\d+x\b|\b\d+X\b",         # 10x
    r"\$\d+[\d,.]*[kKmMbB]?",     # $100k, $1.5M
    r"\b\d+[\d,.]*\s*[kKmMbB]\b", # 10M, 500k
    r"\b\d{1,3}(,\d{3})+\b",      # 75,000, 1,000,000
    r"\b\d+\s*gpu[- ]hours?\b",   # 500 gpu-hours
    r"\b(auc|f1|accuracy|loss|precision|recall|perplexity)\b", # Evaluation metrics
    r"\b0\.\d+\b",                # Decimals like 0.94, 0.02
    r"\b\d+[bBmM]\s*(parameters|tokens|weights)\b", # LLM scale like 7b parameters, 70b tokens
    r"\b\d+\+?\s*(events|users|requests|qps|ms|seconds|minutes|hours|days|engineers|services|nodes|clusters)\b",
    r"\b(zero|single-digit)\s*(downtime|latency)\b",
    r"\bp9[0-9]\b"                # p99, p95
]


@dataclass
class XYZMetricReport:
    """Audit report for Google XYZ formula compliance and multi-gauge telemetry."""
    total_bullets: int
    quantified_bullets: int
    action_verbs_count: int
    compliance_percentage: int
    coaching_tip: str
    quantified_score: int = 0
    action_verbs_score: int = 0
    groundedness_score: int = 100
    bake_health_score: int = 0


def analyze_bullets_xyz(text: str, profile: Optional[CandidateProfile] = None) -> XYZMetricReport:
    """Analyze bullet points for metrics, action verbs, and Google XYZ formula adherence."""
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            b_text = line.lstrip("-*• ").strip()
            if b_text:
                bullets.append(b_text)

    if not bullets:
        return XYZMetricReport(
            total_bullets=0,
            quantified_bullets=0,
            action_verbs_count=0,
            compliance_percentage=0,
            coaching_tip="Add bullet points starting with a dash (-) to begin XYZ analysis.",
            quantified_score=0,
            action_verbs_score=0,
            groundedness_score=0,
            bake_health_score=0
        )

    quantified_count = 0
    action_verbs_found = 0
    weak_bullet_index = None

    for idx, b in enumerate(bullets, 1):
        b_lower = b.lower()
        has_metric = any(re.search(p, b_lower) for p in METRIC_PATTERNS)
        if has_metric:
            quantified_count += 1
        elif weak_bullet_index is None:
            weak_bullet_index = idx

        first_word = re.findall(r"^[A-Za-z]+(?:-[A-Za-z]+)?", b)
        if first_word and first_word[0].lower() in STRONG_ACTION_VERBS:
            action_verbs_found += 1

    quantified_score = int((quantified_count / len(bullets)) * 100) if bullets else 0
    action_verbs_score = int((action_verbs_found / len(bullets)) * 100) if bullets else 0

    # Grounding analysis against candidate profile facts
    groundedness_score = 95
    if profile:
        known_terms = set()
        for sk_cat in getattr(profile, "skills", []):
            for s in getattr(sk_cat, "skills", []):
                known_terms.add(s.lower())
        for exp in getattr(profile, "experiences", []):
            known_terms.add(exp.company.lower())
            known_terms.add(exp.role.lower())
            for t in getattr(exp, "technologies", []):
                known_terms.add(t.lower())

        matches = 0
        for b in bullets:
            b_low = b.lower()
            if any(term in b_low for term in known_terms if len(term) > 2):
                matches += 1
        groundedness_score = max(70, min(100, int((matches / len(bullets)) * 100) if bullets else 90))

    bake_health_score = int(0.4 * quantified_score + 0.3 * action_verbs_score + 0.3 * groundedness_score)

    if quantified_score >= 80:
        tip = "[✓] [bold #50fa7b]Outstanding![/bold #50fa7b] Strong quantifiable metrics across your achievements."
    elif weak_bullet_index:
        tip = (
            f"[!] [bold #f1fa8c]Coaching Tip:[/] Bullet {weak_bullet_index} lacks a measurable outcome. "
            "Add scale, throughput, or percentage impact (e.g. 'reducing latency by 35%')."
        )
    else:
        tip = "[!] [bold #f1fa8c]Coaching Tip:[/] Aim for at least 80% quantified bullets (Google XYZ formula)."

    return XYZMetricReport(
        total_bullets=len(bullets),
        quantified_bullets=quantified_count,
        action_verbs_count=action_verbs_found,
        compliance_percentage=quantified_score,
        coaching_tip=tip,
        quantified_score=quantified_score,
        action_verbs_score=action_verbs_score,
        groundedness_score=groundedness_score,
        bake_health_score=bake_health_score
    )


STUDIO_CSS = """
DualPaneFineTuneModal {
    align: center middle;
}

#finetune-studio-container {
    width: 96%;
    height: 92%;
    background: #16161E;
    border: heavy #D18F52;
    padding: 1;
}

#studio-title-bar {
    height: 1;
    margin-bottom: 1;
    color: #FFB86C;
    text-style: bold;
}

#studio-panes {
    height: 1fr;
}

.pane-half {
    width: 1fr;
    height: 100%;
    padding: 0 1;
}

#left-editor-pane {
    border-right: solid #2A2E3D;
    background: #16161E;
}

.pane-header {
    text-style: bold;
    margin-bottom: 0;
}

#finetune-editor {
    height: 1fr;
    margin-top: 1;
    background: #0C0E14;
    border: round #D18F52;
    color: #F8F8F2;
}

#xyz-validator-box {
    height: auto;
    min-height: 7;
    max-height: 9;
    margin-top: 1;
    padding: 0 1;
    background: #212330;
    border: round #50FA7B;
}

#live-preview-box {
    height: 1fr;
    margin-top: 1;
    padding: 1;
    background: #0C0E14;
    border: round #334155;
}

#studio-action-bar {
    height: 3;
    margin-top: 1;
    align: center middle;
}

#studio-action-bar Button {
    margin: 0 1;
    min-width: 22;
}

#btn-save-finetune {
    background: #1b4332;
    color: #d8f3dc;
    border: heavy #52b788;
    text-style: bold;
}

#btn-save-finetune:hover {
    background: #2d6a4f;
}

#btn-format-xyz {
    background: #582f0e;
    color: #faedcd;
    border: heavy #f4a261;
    text-style: bold;
}

#btn-format-xyz:hover {
    background: #7f4f24;
}

#btn-cancel-finetune {
    background: #1e293b;
    color: #94a3b8;
    border: heavy #475569;
}

#btn-cancel-finetune:hover {
    background: #334155;
}
"""


def make_gauge_bar(score: int, width: int = 12) -> str:
    """Renders a retro arcade filled-block gauge bar."""
    color = "#50fa7b" if score >= 75 else ("#ffb86c" if score >= 50 else "#ff5555")
    filled = int((score / 100) * width)
    empty = width - filled
    return f"[{color}]{'█' * filled}[/][#334155]{'░' * empty}[/] [bold {color}]{score:>3}%[/]"


class ScrollableMarkdown(Markdown):
    """Interactive markdown preview widget with keyboard and mouse scrollability."""

    can_focus = True

    BINDINGS = [
        Binding("up,k", "scroll_up", "Scroll Up", show=False),
        Binding("down,j", "scroll_down", "Scroll Down", show=False),
        Binding("pageup,page_up", "page_up", "Page Up", show=False),
        Binding("pagedown,page_down", "page_down", "Page Down", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
    ]


class XYZValidatorWidget(Static):
    """Real-time Google XYZ Formula multi-gauge telemetry display."""

    def __init__(self, id: Optional[str] = "xyz-validator-box"):
        placeholder = (
            "[bold #ffb86c]METRIC AUDIT[/bold #ffb86c]\n"
            "[dim]Awaiting experience bullets... Enter or paste bullets above to calculate metrics.[/dim]"
        )
        super().__init__(placeholder, id=id)
        self.latest_report: Optional[XYZMetricReport] = None
        self.latest_provenance: Optional[Dict[str, Any]] = None

    def update_report(self, report: XYZMetricReport, provenance_info: Optional[Dict[str, Any]] = None) -> None:
        self.latest_report = report
        if provenance_info is not None:
            self.latest_provenance = provenance_info

        if report.total_bullets == 0:
            content = (
                "[bold #ffb86c]METRIC AUDIT[/bold #ffb86c]\n"
                f"[dim]{report.coaching_tip}[/dim]"
            )
            self.update(content)
            return

        g_xyz = make_gauge_bar(report.quantified_score, width=20)
        g_verb = make_gauge_bar(report.action_verbs_score, width=20)
        g_ground = make_gauge_bar(report.groundedness_score, width=20)
        g_bake = make_gauge_bar(report.bake_health_score, width=20)

        prov_line = ""
        if self.latest_provenance:
            summary = self.latest_provenance.get("summary", "100% Grounded • 0 Hallucinations")
            prov_line = f" [dim]•[/] [bold #50fa7b]{summary}[/bold #50fa7b]"
            healed = self.latest_provenance.get("hallucinations_healed", 0)
            if healed > 0:
                prov_line += f" [bold #8be9fd]({healed} healed)[/]"

        content = (
            f"[bold #ffb86c]METRIC AUDIT[/bold #ffb86c]{prov_line}\n"
            f" [#c9b5a2]• XYZ Formula[/]    [dim]({report.quantified_bullets}/{report.total_bullets})[/dim]  {g_xyz}\n"
            f" [#c9b5a2]• Action Verbs[/]   [dim]({report.action_verbs_count}/{report.total_bullets})[/dim]  {g_verb}\n"
            f" [#c9b5a2]• Fact Grounding[/] [dim](Facts)[/dim]  {g_ground}\n"
            f" [#c9b5a2]• Quality Score[/]  [dim](Total)[/dim]  {g_bake}\n"
            f"{report.coaching_tip}"
        )
        self.update(content)


class DualPaneFineTuneModal(ModalScreen):
    """Full-featured split-pane studio for refining experience bullets with live preview."""

    DEFAULT_CSS = STUDIO_CSS

    BINDINGS = [
        ("ctrl+r", "dictate_bullet", "Dictate Bullet"),
    ]

    def __init__(
        self,
        initial_text: str,
        profile: Optional[CandidateProfile] = None,
        app_result: Optional[TailoredApplication] = None,
        template_name: str = "jakes"
    ):
        super().__init__()
        self.initial_text = initial_text
        self.profile = profile
        self.app_result = app_result
        self.template_name = template_name
        self.renderer = TemplateRenderer()

    def compose(self) -> ComposeResult:
        with Vertical(id="finetune-studio-container"):
            with Horizontal(id="studio-title-bar"):
                yield Label("[·] BREADWINNER BULLET LABORATORY & LIVE ATS AUDIT")

            with Horizontal(id="studio-panes"):
                # LEFT PANE: BULLET LABORATORY
                with Vertical(classes="pane-half", id="left-editor-pane"):
                    yield Label("[bold #8be9fd]Experience Bullets (Markdown Format):[/bold #8be9fd]", classes="pane-header")
                    yield TextArea(self.initial_text, id="finetune-editor", show_line_numbers=True)
                    yield XYZValidatorWidget(id="xyz-validator-box")

                # RIGHT PANE: LIVE ATS RESUME PREVIEW
                with Vertical(classes="pane-half", id="right-preview-pane"):
                    yield Label("[bold #50fa7b][DOC] Live Jake's Resume ATS Preview (ats):[/bold #50fa7b]", classes="pane-header")
                    with VerticalScroll(id="live-preview-box"):
                        yield Markdown(self.build_preview_markdown(self.initial_text), id="live-preview-md")

            with Horizontal(id="studio-action-bar"):
                yield Button("Apply & Re-Bake PDF (Enter)", variant="success", id="btn-save-finetune")
                yield Button("Format All with XYZ", variant="warning", id="btn-format-xyz")
                yield Button("[»] Dictate Bullet (Ctrl+R)", variant="primary", id="btn-dictate-bullet")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel-finetune")

    def on_mount(self) -> None:
        # Initial XYZ analysis with provenance
        report = analyze_bullets_xyz(self.initial_text, self.profile)
        prov = self.app_result.provenance_report if self.app_result else None
        self.query_one("#xyz-validator-box", XYZValidatorWidget).update_report(report, provenance_info=prov)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Reactive live preview and metric checker update on every keystroke."""
        current_text = event.text_area.text
        report = analyze_bullets_xyz(current_text, self.profile)
        self.query_one("#xyz-validator-box", XYZValidatorWidget).update_report(report)

        preview_md = self.build_preview_markdown(current_text)
        self.query_one("#live-preview-md", Markdown).update(preview_md)

    def build_preview_markdown(self, editor_text: str) -> str:
        """Generates dynamic resume preview from edited bullets."""
        if not self.profile or not self.app_result:
            return f"# Resume Preview\n\n{editor_text}"

        # Parse temporary experiences from editor text
        new_experiences: List[WorkExperience] = []
        curr_role = None
        curr_company = None
        curr_bullets = []

        for line in editor_text.splitlines():
            line_s = line.strip()
            if line_s.startswith("### "):
                if curr_role and curr_company:
                    new_experiences.append(
                        WorkExperience(
                            company=curr_company,
                            role=curr_role,
                            bullets=list(curr_bullets)
                        )
                    )
                header_parts = line_s[4:].split("@")
                curr_role = header_parts[0].strip() if header_parts else "Role"
                curr_company = header_parts[1].strip() if len(header_parts) > 1 else "Company"
                curr_bullets = []
            elif line_s.startswith(("-", "*", "•")):
                b = line_s.lstrip("-*• ").strip()
                if b:
                    curr_bullets.append(b)

        if curr_role and curr_company:
            new_experiences.append(
                WorkExperience(
                    company=curr_company,
                    role=curr_role,
                    bullets=list(curr_bullets)
                )
            )

        # Temporary app result with updated experiences
        temp_app = TailoredApplication(
            job=self.app_result.job,
            persona=self.app_result.persona,
            match_analysis=self.app_result.match_analysis,
            tailored_summary=self.app_result.tailored_summary,
            tailored_experiences=new_experiences or self.app_result.tailored_experiences,
            tailored_projects=self.app_result.tailored_projects,
            tailored_skills=self.app_result.tailored_skills,
            cover_letter=self.app_result.cover_letter,
            portal_answers=self.app_result.portal_answers
        )

        return self.renderer.render_resume(self.profile, temp_app, "ats")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-save-finetune":
            editor = self.query_one("#finetune-editor", TextArea)
            self.dismiss(editor.text)
        elif bid == "btn-format-xyz":
            editor = self.query_one("#finetune-editor", TextArea)
            # Add metric hints to unquantified bullets
            lines = []
            for l in editor.text.splitlines():
                if l.strip().startswith("- ") and not any(re.search(p, l.lower()) for p in METRIC_PATTERNS):
                    lines.append(l + " resulting in [X% improvement].")
                else:
                    lines.append(l)
            editor.text = "\n".join(lines)
            self.app.notify("Added Google XYZ metric placeholders to unquantified bullets!", title="XYZ Formatted")
        elif bid == "btn-dictate-bullet":
            self.action_dictate_bullet()
        else:
            self.dismiss(None)

    def action_dictate_bullet(self) -> None:
        """Open universal voice dictation modal to capture and append a new bullet."""
        def on_dictated(text: Optional[str]):
            if text:
                editor = self.query_one("#finetune-editor", TextArea)
                clean_bullet = f"- {text.strip().lstrip('-*• ')}"
                existing = editor.text.strip()
                if existing:
                    editor.text = f"{existing}\n{clean_bullet}\n"
                else:
                    editor.text = f"{clean_bullet}\n"
                editor.focus()
                self.app.notify("✓ Dictated bullet added to laboratory!", title="Speech Captured")
        self.app.push_screen(AudioDictationModal(prompt_title="Dictate Experience Bullet"), on_dictated)
