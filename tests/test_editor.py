"""Unit tests for the Dual-Pane Fine-Tuning Studio and Google XYZ metric analyzer."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import TextArea, Button

from breadwinner.ui.editor import (
    analyze_bullets_xyz,
    XYZMetricReport,
    DualPaneFineTuneModal,
    XYZValidatorWidget
)
from breadwinner.core.models import (
    CandidateProfile,
    TailoredApplication,
    WorkExperience,
    SkillCategory,
    JobPosting,
    MatchAnalysis
)


def test_analyze_bullets_xyz_empty():
    report = analyze_bullets_xyz("")
    assert report.total_bullets == 0
    assert report.quantified_bullets == 0
    assert report.compliance_percentage == 0
    assert "Add bullet points" in report.coaching_tip


def test_analyze_bullets_xyz_metrics_and_verbs():
    raw_bullets = """
    - Architected distributed data pipeline processing 10M events daily with zero downtime
    - Engineered high-throughput indexing reducing p99 latency by 45%
    - Built internal team tooling
    """
    report = analyze_bullets_xyz(raw_bullets)
    assert report.total_bullets == 3
    assert report.quantified_bullets == 2  # 10M events, 45% / p99
    assert report.action_verbs_count == 3  # Architected, Engineered, Built
    assert report.compliance_percentage == 66
    assert "Bullet 3 lacks a measurable outcome" in report.coaching_tip


def test_analyze_bullets_xyz_telemetry_scores():
    raw_bullets = """
    - Spearheaded migration of 12 microservices to Kubernetes saving $150k annually
    - Accelerated build times by 4x across 85 engineers
    """
    profile = CandidateProfile(
        full_name="Alex Baker",
        email="alex@breadwinner.dev",
        title="Staff SRE",
        skills=[SkillCategory(category="Technical", skills=["Kubernetes"])],
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Senior SRE",
                start_date="2021",
                end_date="Present",
                bullets=["Migration of microservices."]
            )
        ]
    )
    report = analyze_bullets_xyz(raw_bullets, profile=profile)
    assert report.total_bullets == 2
    assert report.quantified_bullets == 2
    assert report.compliance_percentage == 100
    assert report.quantified_score == 100
    assert report.action_verbs_score == 100
    assert report.groundedness_score >= 70
    assert report.bake_health_score >= 80
    assert "Outstanding!" in report.coaching_tip


def test_make_gauge_bar():
    from breadwinner.ui.editor import make_gauge_bar
    bar_high = make_gauge_bar(80, width=10)
    assert "█" * 8 in bar_high
    assert "80%" in bar_high
    assert "#50fa7b" in bar_high

    bar_mid = make_gauge_bar(60, width=10)
    assert "#ffb86c" in bar_mid

    bar_low = make_gauge_bar(30, width=10)
    assert "#ff5555" in bar_low


class ModalHostApp(App):
    """Test harness to mount DualPaneFineTuneModal."""
    def __init__(self, modal):
        super().__init__()
        self.modal = modal
        self.result = None

    def on_mount(self):
        def _cb(res):
            self.result = res
        self.push_screen(self.modal, callback=_cb)


@pytest.mark.anyio
async def test_dual_pane_finetune_modal_mount_and_edit():
    profile = CandidateProfile(
        full_name="Alex Baker",
        email="alex@breadwinner.dev",
        title="Staff SRE",
        skills=[SkillCategory(category="Technical", skills=["Python", "Kubernetes"])],
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Senior SRE",
                start_date="2021",
                end_date="Present",
                bullets=["Engineered Kubernetes cluster."]
            )
        ]
    )
    job = JobPosting(
        id="job_123",
        company="Acme Corp",
        title="Senior SRE",
        raw_text="Kubernetes scale"
    )
    match_analysis = MatchAnalysis(
        match_score=95,
        matched_skills=["Python", "Kubernetes"],
        missing_skills=[],
        rationale="Strong match"
    )
    app_result = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=match_analysis,
        tailored_summary="Expert SRE",
        tailored_experiences=profile.experiences,
        tailored_projects=[],
        tailored_skills=profile.skills,
        cover_letter="Hello",
        portal_answers={}
    )

    initial_md = "### Senior SRE @ Acme Corp\n- Scaled cluster to 500 nodes reducing latency by 40%"
    modal = DualPaneFineTuneModal(
        initial_text=initial_md,
        profile=profile,
        app_result=app_result
    )

    test_app = ModalHostApp(modal)
    async with test_app.run_test(size=(120, 40)) as pilot:
        # Check widgets mounted
        assert modal.query_one("#finetune-editor", TextArea) is not None
        assert modal.query_one("#xyz-validator-box", XYZValidatorWidget) is not None
        assert modal.query_one("#live-preview-md") is not None

        # Format XYZ button triggers hint addition
        btn_format = modal.query_one("#btn-format-xyz", Button)
        btn_format.press()
        await pilot.pause()

        # Click save
        btn_save = modal.query_one("#btn-save-finetune", Button)
        btn_save.press()
        await pilot.pause()

    assert test_app.result is not None
    assert "Acme Corp" in test_app.result
