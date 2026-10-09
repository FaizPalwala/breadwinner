"""Unit tests for Baker's Interview module."""

from breadwinner.core.models import CandidateProfile
from breadwinner.core.interview import (
    synthesize_context,
    INTERVIEW_QUESTIONS,
    generate_gap_interview_questions,
    generate_adaptive_questions
)
from breadwinner.providers.factory import MockLLMProvider


def test_interview_questions_structure():
    assert len(INTERVIEW_QUESTIONS) == 3
    for q in INTERVIEW_QUESTIONS:
        assert "id" in q
        assert "title" in q
        assert "prompt" in q


def test_synthesize_context():
    mock_provider = MockLLMProvider()
    profile = CandidateProfile(full_name="Alex Taylor", title="Software Engineer")

    answers = {
        "target_roles": "Senior Backend or Applied AI Engineer. Avoid pure front-end.",
        "star_stories": "Designed streaming data engine cutting egress by 40%.",
        "logistics_guardrails": "UK Citizen, hybrid London, minimum £95k."
    }

    result = synthesize_context(profile, answers, mock_provider)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_gap_interview_questions():
    mock_provider = MockLLMProvider()
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Software Engineer",
        experiences=[
            {
                "company": "DataCorp",
                "role": "Backend Engineer",
                "bullets": ["Optimized backend database queries.", "Worked on internal dashboard."]
            }
        ]
    )

    # 1. Test LLM-driven gap questions
    llm_qs = generate_gap_interview_questions(profile, provider=mock_provider, dossier_context="Built custom data store.")
    assert len(llm_qs) >= 2
    assert any("scale" in q["id"].lower() or "scale" in q["prompt"].lower() for q in llm_qs)

    # 2. Test fallback questions without provider
    fallback_qs = generate_gap_interview_questions(profile, provider=None)
    assert len(fallback_qs) >= 2
    assert any("DataCorp" in q["title"] or "DataCorp" in q["prompt"] for q in fallback_qs)

    # 3. Test backward-compatible adaptive wrapper
    adapt_qs = generate_adaptive_questions(profile, provider=mock_provider)
    assert len(adapt_qs) >= 2


def test_fully_quantified_profile_returns_no_questions():
    """Verify that when candidate bullets and projects already have verified metrics, no questions are asked."""
    profile = CandidateProfile(
        full_name="Faiz Palwala",
        title="AI/ML Engineer",
        experiences=[
            {
                "company": "Deloitte",
                "role": "Software Engineer",
                "bullets": [
                    "Architected and scaled resilient enterprise microservices for healthcare platform serving 23M+ members over 4 years."
                ]
            }
        ],
        projects=[
            {
                "name": "SFHQ-VirtualID",
                "description": "A reproducible pipeline that generates synthetic, identity-conditioned face clusters, released as a citable benchmark for machine unlearning.",
                "tech_stack": ["Python", "PyTorch", "Diffusers", "InstantID"],
                "highlights": ["Released as citable benchmark achieving 99% identity erasure."]
            }
        ]
    )

    # Both fallback and provider should acknowledge zero gaps
    qs_fallback = generate_gap_interview_questions(profile, provider=None)
    assert len(qs_fallback) == 0

