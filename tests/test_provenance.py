"""Unit tests for anti-hallucination metric provenance and banned word validation."""

from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Project,
    JobPosting,
    TailoredApplication,
    MatchAnalysis
)
from breadwinner.core.persona import PersonaManager
from breadwinner.core.provenance import ProvenanceValidator, DEFAULT_BANNED_WORDS
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
