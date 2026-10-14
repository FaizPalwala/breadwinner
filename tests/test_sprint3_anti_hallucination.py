"""Unit tests for Sprint 3: Deterministic Anti-Hallucination & Prompt Engineering Engine."""

import pytest
from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Project,
    SkillCategory,
    JobPosting,
    TailoredApplication,
    MatchAnalysis
)
from breadwinner.core.persona import Persona, PersonaManager
from breadwinner.core.deconstruct import JDDeconstructor, DeconstructedJob
from breadwinner.core.provenance import (
    ProvenanceValidator,
    ProvenanceCertificate,
    DEFAULT_BANNED_WORDS
)
from breadwinner.core.tailor import TailoringEngine
from breadwinner.providers.factory import MockLLMProvider


def test_stage1_heuristic_jd_deconstruction():
    raw_jd = """
    We are hiring a Senior Platform Engineer at HighScale Labs.
    Domain: Distributed Systems & Cloud Infrastructure.
    
    Requirements:
    - 5+ years of production experience with Go and Python.
    - Deep expertise in Kubernetes and Docker container orchestration.
    - Experience managing Kafka clusters under high-throughput conditions.
    
    Nice to Have:
    - Experience with Terraform and AWS.
    - Low-latency systems tuning (sub-10ms).
    
    Responsibilities:
    - Architect distributed streaming pipelines handling 1M QPS.
    - Maintain 99.99% availability across multi-region deployments.
    """
    job = JobPosting(
        id="job-scale-01",
        company="HighScale Labs",
        title="Senior Platform Engineer",
        raw_text=raw_jd
    )

    deconstructed = JDDeconstructor.deconstruct(job, provider=None)
    assert isinstance(deconstructed, DeconstructedJob)
    assert deconstructed.company == "HighScale Labs"
    assert deconstructed.job_title == "Senior Platform Engineer"
    assert "Go" in deconstructed.technical_stack or "Python" in deconstructed.technical_stack
    assert "Kubernetes" in deconstructed.technical_stack
    assert len(deconstructed.hard_must_haves) > 0
    assert any("Go" in h or "5+" in h or "Kubernetes" in h for h in deconstructed.hard_must_haves)
    assert any("sub-10ms" in s or "1m qps" in s or "99.99%" in s for s in deconstructed.scale_constraints)


def test_stage1_llm_jd_deconstruction():
    mock = MockLLMProvider()
    job = JobPosting(
        id="job-mock-01",
        company="Cloud Corp",
        title="Senior Platform Engineer",
        raw_text="Looking for platform engineers with Go and Kubernetes handling 1M QPS."
    )
    deconstructed = JDDeconstructor.deconstruct(job, provider=mock)
    assert isinstance(deconstructed, DeconstructedJob)
    assert deconstructed.company == "Cloud Corp"
    assert "Go" in deconstructed.technical_stack
    assert "Kubernetes" in deconstructed.technical_stack
    assert len(deconstructed.hard_must_haves) >= 3


def test_stage3_auto_healing_reverts_invented_metrics():
    """Verify that an adversarial bullet with invented metrics is automatically reverted to verified baseline."""
    profile = CandidateProfile(
        full_name="Sam Morgan",
        title="Backend Engineer",
        experiences=[
            WorkExperience(
                company="DataStream",
                role="Backend Engineer",
                start_date="2021",
                end_date="2023",
                bullets=["Maintained Postgres relational database and wrote internal REST APIs in Python."]
            )
        ]
    )

    job = JobPosting(
        id="j-test",
        company="StreamCo",
        title="Senior Backend",
        raw_text="Backend engineer needed."
    )

    # Adversarial application hallucinating 90% latency reduction and $120k savings
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=80),
        tailored_summary="Backend specialist in databases.",
        tailored_experiences=[
            WorkExperience(
                company="DataStream",
                role="Backend Engineer",
                start_date="2021",
                end_date="2023",
                bullets=["Spearheaded Postgres query tuning, reducing latency by 90% and saving $120k/year."]
            )
        ]
    )

    healed_app, cert = ProvenanceValidator.verify_and_heal_application(app, profile)
    assert isinstance(cert, ProvenanceCertificate)
    assert cert.hallucinations_detected >= 1
    assert cert.hallucinations_healed >= 1
    # Bullet should have reverted to the verified source bullet from DataStream
    healed_bullet = healed_app.tailored_experiences[0].bullets[0]
    assert "90%" not in healed_bullet
    assert "$120k" not in healed_bullet
    assert "Maintained Postgres" in healed_bullet or "REST APIs" in healed_bullet
    assert cert.is_valid is True
    assert cert.grounding_score == 100


def test_stage3_auto_healing_sanitizes_banned_slop():
    """Verify that AI buzzwords (spearheaded, seamlessly, passionate) are cleaned/replaced."""
    profile = CandidateProfile(
        full_name="Sam Morgan",
        title="Backend Engineer",
        experiences=[
            WorkExperience(
                company="DataStream",
                role="Backend Engineer",
                start_date="2021",
                end_date="2023",
                bullets=["Architected API pipeline serving 10k requests daily."]
            )
        ]
    )

    job = JobPosting(id="j1", company="Acme", title="Engineer", raw_text="Hiring.")
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=85),
        tailored_summary="Passionate engineer who seamlessly delivers value.",
        tailored_experiences=[
            WorkExperience(
                company="DataStream",
                role="Backend Engineer",
                start_date="2021",
                end_date="2023",
                bullets=["Spearheaded API pipeline serving 10k requests daily seamlessly."]
            )
        ]
    )

    healed_app, cert = ProvenanceValidator.verify_and_heal_application(app, profile)
    healed_bullet = healed_app.tailored_experiences[0].bullets[0]
    assert "spearheaded" not in healed_bullet.lower()
    assert "seamlessly" not in healed_bullet.lower()
    assert "Led" in healed_bullet or "Architected" in healed_bullet
    assert "passionate" not in healed_app.tailored_summary.lower()
    assert cert.slop_words_cleaned >= 2


def test_end_to_end_sprint3_pipeline_with_mock():
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)
    persona = PersonaManager.load_persona("tech_ai")

    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Staff Engineer",
        skills=[
            SkillCategory(category="Languages", skills=["Go", "Python"]),
            SkillCategory(category="Infrastructure", skills=["Kubernetes", "Docker", "AWS"])
        ],
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
        id="job-cloud-01",
        company="Cloud Corp",
        title="Staff Engineer",
        raw_text="Requirements: 5+ years Go, Kubernetes, and high-throughput systems."
    )

    tailored_app = engine.analyze_and_tailor(profile, job, persona)
    assert isinstance(tailored_app, TailoredApplication)
    assert tailored_app.provenance_report is not None
    assert tailored_app.provenance_report.get("is_valid") is True
    assert tailored_app.provenance_report.get("grounding_score") == 100
    assert "Pantry: Verified (Strict)" in tailored_app.provenance_report.get("summary", "")
