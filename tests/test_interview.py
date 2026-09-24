"""Unit tests for Baker's Interview module."""

from breadwinner.core.models import CandidateProfile
from breadwinner.core.interview import synthesize_context, INTERVIEW_QUESTIONS
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
