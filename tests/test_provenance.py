"""Unit tests for anti-hallucination metric provenance and banned word validation."""

import pytest
from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Project,
    JobPosting,
    TailoredApplication,
    MatchAnalysis
)
from breadwinner.core.persona import PersonaManager
from breadwinner.core.provenance import (
    ProvenanceValidator,
    DEFAULT_BANNED_WORDS,
    ProvenanceAuditError
)
from breadwinner.core.tailor import TailoringEngine
from breadwinner.providers.factory import MockLLMProvider


def test_metric_extraction():
    text = "Scaled distributed cache to 1M QPS with sub-10ms p99 latency, reducing cloud costs by 35% or $50k/month."
    metrics = ProvenanceValidator.extract_metrics(text)
    assert any("1m" in m for m in metrics)
    assert any("10ms" in m for m in metrics)
    assert any("35%" in m for m in metrics)
    assert any("50k" in m for m in metrics)


def test_provenance_validation_clean():
    profile = CandidateProfile(
        full_name="Alex River",
        title="Distributed Systems Engineer",
        experiences=[
            WorkExperience(
                company="FinTech Ltd",
                role="Senior Systems Engineer",
                start_date="2021",
                end_date="Present",
                bullets=["Built real-time ledger processing 50M daily transactions with 99.999% uptime."]
            )
        ],
        projects=[
            Project(
                name="RaftKV",
                description="Distributed key-value store achieving sub-5ms latency across 5 nodes."
            )
        ]
    )

    job = JobPosting(
        id="j1",
        company="Stripe",
        title="Staff Engineer",
        raw_text="Scaling ledger systems."
    )

    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Systems architect specializing in distributed ledgers.",
        tailored_experiences=[
            WorkExperience(
                company="FinTech Ltd",
                role="Senior Systems Engineer",
                start_date="2021",
                end_date="Present",
                bullets=["Engineered high-throughput ledger processing 50M daily transactions with 99.999% uptime."]
            )
        ],
        cover_letter="Achieved sub-5ms latency across 5 nodes in distributed consensus."
    )

    report = ProvenanceValidator.validate(app, profile)
    assert report.is_valid is True
    assert len(report.unverified_metrics) == 0
    assert len(report.banned_words_found) == 0


def test_provenance_validation_detects_hallucinations_and_banned_words():
    profile = CandidateProfile(
        full_name="Alex River",
        title="Software Engineer",
        experiences=[
            WorkExperience(
                company="OldCorp",
                role="Engineer",
                start_date="2020",
                end_date="2022",
                bullets=["Maintained database and backend services."]
            )
        ]
    )

    job = JobPosting(
        id="j1",
        company="TechCorp",
        title="Engineer",
        raw_text="Backend engineer needed."
    )

    # Tailored app invents 95% and $200k, and uses banned words 'spearheaded' and 'passionate'
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=80),
        tailored_summary="Passionate software engineer.",
        tailored_experiences=[
            WorkExperience(
                company="OldCorp",
                role="Engineer",
                start_date="2020",
                end_date="2022",
                bullets=["Spearheaded database optimization cutting latency by 95% and saving $200k."]
            )
        ]
    )

    report = ProvenanceValidator.validate(app, profile)
    assert report.is_valid is False
    assert any("95%" in m for m in report.unverified_metrics)
    assert any("200k" in m for m in report.unverified_metrics)
    assert "spearheaded" in report.banned_words_found
    assert "passionate" in report.banned_words_found


def test_tailoring_engine_attaches_provenance_report():
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)
    persona = PersonaManager.load_persona("tech_ai")

    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Staff Engineer",
        experiences=[
            WorkExperience(
                company="Cloud Corp",
                role="Staff Engineer",
                start_date="2021",
                end_date="Present",
                bullets=["Architected distributed cache handling 1M QPS with sub-10ms latency."]
            )
        ]
    )

    job = JobPosting(
        id="job123",
        company="CloudCo",
        title="Staff Engineer",
        raw_text="We need distributed cache engineers."
    )

    app = engine.analyze_and_tailor(profile, job, persona)
    assert app.provenance_report is not None
    assert "is_valid" in app.provenance_report
    assert "verified_metrics" in app.provenance_report
    assert "warnings" in app.provenance_report


def test_provenance_rejects_tenure_drift():
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Systems Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="Leeds, UK",
                start_date="2022-09",
                end_date="2024-08",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    job = JobPosting(
        id="j1",
        company="Stripe",
        title="Staff Engineer",
        raw_text="Scaling ledger systems."
    )

    # 1. Start date drift: 2021-09 instead of 2022-09
    app_drift_start = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Senior Distributed Systems Engineer.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="Leeds, UK",
                start_date="2021-09",
                end_date="2024-08",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    with pytest.raises(ProvenanceAuditError) as exc_info:
        ProvenanceValidator.validate(app_drift_start, profile)
    assert "Apex Cloud Systems" in str(exc_info.value)
    assert "start_date" in exc_info.value.field

    # 2. End date drift: 2025-01 instead of 2024-08
    app_drift_end = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Senior Distributed Systems Engineer.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="Leeds, UK",
                start_date="2022-09",
                end_date="2025-01",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    with pytest.raises(ProvenanceAuditError) as exc_info:
        ProvenanceValidator.validate(app_drift_end, profile)
    assert "Apex Cloud Systems" in str(exc_info.value)
    assert "end_date" in exc_info.value.field


def test_provenance_rejects_location_drift():
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Systems Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="Leeds, UK",
                start_date="2022-09",
                end_date="2024-08",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    job = JobPosting(
        id="j1",
        company="Stripe",
        title="Staff Engineer",
        raw_text="Scaling ledger systems."
    )

    # Location shifted to London, UK instead of Leeds, UK
    app_drift_loc = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Senior Distributed Systems Engineer.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="London, UK",
                start_date="2022-09",
                end_date="2024-08",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    with pytest.raises(ProvenanceAuditError) as exc_info:
        ProvenanceValidator.validate(app_drift_loc, profile)
    assert "Apex Cloud Systems" in str(exc_info.value)
    assert "location" in exc_info.value.field

    # Test markdown rendered string as well
    rendered_md = (
        "### Senior Systems Engineer - Apex Cloud Systems\n"
        "*Sep 2022 - Aug 2024 | London, UK*\n"
        "- Engineered high-throughput event processing platform."
    )
    with pytest.raises(ProvenanceAuditError) as exc_info_md:
        ProvenanceValidator.validate_experience_headers(rendered_md, profile)
    assert "Apex Cloud Systems" in str(exc_info_md.value)
    assert "location" in exc_info_md.value.field


def test_provenance_error_message_contains_actionable_diff():
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Systems Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="Leeds, UK",
                start_date="Sep 2022",
                end_date="Aug 2024",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    job = JobPosting(
        id="j1",
        company="Stripe",
        title="Staff Engineer",
        raw_text="Scaling ledger systems."
    )

    # Both location and start date drift
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Senior Distributed Systems Engineer.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Systems Engineer",
                location="London, UK",
                start_date="Sep 2021",
                end_date="Aug 2024",
                bullets=["Engineered high-throughput event processing platform."]
            )
        ]
    )

    with pytest.raises(ProvenanceAuditError) as exc_info:
        ProvenanceValidator.validate(app, profile)

    err = exc_info.value
    err_msg = str(err)

    # Assert exact diagnostic structure
    assert "Experience header drift detected in Apex Cloud Systems." in err_msg
    assert "• Field:" in err_msg
    assert "• Expected (pantry/profile.yaml):" in err_msg
    assert "• Rendered (generated resume):" in err_msg
    assert "• Resolution: Restore the canonical pantry value exactly. Do not alter dates or locations." in err_msg

    # Assert machine-readable delta payload
    assert err.delta is not None
    assert err.delta["company"] == "Apex Cloud Systems"
    assert "location" in err.delta["field"] or "start_date" in err.delta["field"]
    assert "Leeds, UK" in err.delta["expected"]
    assert "London, UK" in err.delta["rendered"]
    assert err.delta["resolution"] == "Restore the canonical pantry value exactly. Do not alter dates or locations."

