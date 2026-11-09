"""Unit tests for the ATS Cleanliness & Scan-First Density system directive."""

import pytest
import re
from pathlib import Path
from breadwinner.core.models import (
    CandidateProfile,
    JobPosting,
    TailoredApplication,
    WorkExperience,
    Education,
    Project,
    SkillCategory,
    MatchAnalysis
)
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.persona import PersonaManager
from breadwinner.core.tailor import TailoringEngine
from breadwinner.providers.factory import MockLLMProvider
from breadwinner.core.audit import AuditEngine


@pytest.fixture
def enterprise_candidate():
    profile = CandidateProfile(
        full_name="Alex Mercer",
        title="Python Backend Developer",
        email="alex@example.com",
        location="London, UK",
        experiences=[
            WorkExperience(
                company="Deloitte",
                role="Enterprise Software Engineer",
                start_date="2021",
                end_date="Present",
                bullets=[
                    "**Python Batch Processing:** Built automated database reconciliation utilities processing 3M+ inbound records with zero schema regressions.",
                    "**Distributed Foundation:** Maintained high-throughput Spring Boot microservices handling 23M+ records while migrating core data flows to Python.",
                    "**API Engineering:** Deployed FastAPI microservices reducing p99 claims triage latency from 1,200ms to 85ms across 15 downstream consumers."
                ]
            )
        ],
        education=[
            Education(
                institution="University of Manchester",
                degree="BSc Computer Science",
                start_date="2017",
                end_date="2020"
            )
        ],
        skills=[
            SkillCategory(
                category="Backend & Data",
                skills=["Python", "FastAPI", "PostgreSQL", "Kafka", "Docker"]
            )
        ]
    )

    job = JobPosting(
        id="enterprise-se-1",
        company="Fintech Scaleup",
        title="Senior Python Backend Engineer"
    )

    app = TailoredApplication(
        job=job,
        persona="enterprise_python",
        match_analysis=MatchAnalysis(match_score=92, matched_skills=["Python", "FastAPI", "PostgreSQL"]),
        tailored_summary="Python Backend Engineer with 5+ years building resilient APIs and automated reconciliation pipelines.",
        tailored_experiences=profile.experiences,
        tailored_projects=[],
        tailored_skills=profile.skills
    )

    return profile, app


def test_enterprise_python_persona_registered():
    """Verify enterprise_python persona is discovered and satisfies calibration directives."""
    personas = PersonaManager.list_personas()
    assert "enterprise_python" in personas

    p = PersonaManager.load_persona("enterprise_python")
    assert p.archetype == "Python Backend Developer / Enterprise Software Engineer"
    assert "HARD WORD CEILING: Maximum 32 words" in p.system_directives
    assert "FRONT-LOADED ACTION PATTERN" in p.system_directives
    assert "Deloitte" in p.system_directives or "deloitte" in p.system_directives.lower()
    assert "FastAPI/Flask" in p.system_directives


def test_templates_bullet_typography_vertical_breathing_room(enterprise_candidate):
    """Verify templates enforce line-height: 1.35 minimum and margin-bottom: 4pt."""
    profile, app = enterprise_candidate
    renderer = TemplateRenderer()

    # Check Jake's Resume
    html_jakes = renderer.render_resume(profile, app, "jakes")
    assert "margin-bottom: 4pt;" in html_jakes
    assert "line-height: 1.35;" in html_jakes

    # Check Modern
    html_modern = renderer.render_resume(profile, app, "modern")
    assert "margin-bottom: 4pt;" in html_modern

    # Check Compact 1-Page
    html_compact = renderer.render_resume(profile, app, "compact_1page")
    assert "margin-bottom: 4pt;" in html_compact
    assert "line-height: 1.35;" in html_compact


def test_templates_ascii_hyphen_date_boundary(enterprise_candidate):
    """Verify all date ranges render with standard ASCII hyphens (-), no em-dashes (—), en-dashes (–), or double hyphens (--)."""
    profile, app = enterprise_candidate
    renderer = TemplateRenderer()

    templates = ["jakes", "modern", "compact_1page", "consultant", "executive", "systems_research"]
    for tpl in templates:
        html = renderer.render_resume(profile, app, tpl)
        # Check raw rendered markup around dates
        assert "2021 - Present" in html or "2021-Present" in html or "2021 - Present" in html.replace("&ndash;", "-")
        assert "2021 – Present" not in html, f"En-dash found in template {tpl}"
        assert "2021 — Present" not in html, f"Em-dash found in template {tpl}"
        assert "2021 -- Present" not in html, f"Double hyphen found in template {tpl}"


def test_templates_render_bold_anchors_as_strong_elements(enterprise_candidate):
    """Verify front-loaded markdown bold anchors (**Anchor:**) are converted to <strong> tags."""
    profile, app = enterprise_candidate
    renderer = TemplateRenderer()

    html = renderer.render_resume(profile, app, "jakes")
    assert "<strong>Python Batch Processing:</strong>" in html
    assert "<strong>Distributed Foundation:</strong>" in html
    assert "**Python Batch Processing:**" not in html


def test_tailor_heals_bullet_exceeding_word_ceiling():
    """Verify that tailor verification gate trims subordinate clauses if bullet exceeds 32 words."""
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)

    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Software Engineer",
        email="jane@example.com",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Engineer",
                start_date="2021",
                end_date="Present",
                bullets=[
                    "**Python Batch Processing:** Built automated database reconciliation utilities processing 3M+ inbound records with zero schema regressions."
                ]
            )
        ]
    )

    # Bullet with 39 words (exceeds 32-word ceiling)
    overlong_bullet = (
        "**Python Batch Processing:** Built automated database reconciliation utilities processing 3M+ inbound records with zero schema regressions, "
        "collaborating closely with distributed operations teams under complex statutory mandates and internal corporate governance frameworks across 14 enterprise divisions."
    )
    assert len(overlong_bullet.split()) > 32

    draft_experiences = [
        WorkExperience(
            company="Acme Corp",
            role="Engineer",
            start_date="2021",
            end_date="Present",
            bullets=[overlong_bullet]
        )
    ]

    healed = engine._verify_and_heal_tailored_bullets(draft_experiences, profile)
    healed_bullet = healed[0].bullets[0]

    assert len(healed_bullet.split()) <= 32
    assert "3M+ inbound records" in healed_bullet
    assert healed_bullet.endswith(".")


def test_audit_flags_overlong_bullets_and_non_ascii_dashes():
    """Verify AuditEngine recommends trims for bullets > 32 words and non-ASCII dashes."""
    resume_with_issues = """# Jane Doe
Python Backend Developer
jane@example.com

## EXPERIENCE
### Engineer - Acme Corp
2020 – 2022

- **Python Batch Processing:** Built automated database reconciliation utilities processing 3M+ inbound records with zero schema regressions across 14 complex corporate divisions while maintaining active stakeholder alignment with statutory authorities and internal leadership committees.
"""
    contract_json = {
        "metadata": {"company": "Acme Corp", "role": "Python Backend Developer", "page_budget": 1},
        "evaluation_criteria": {"core_domains": ["Backend"]}
    }

    report = AuditEngine.audit(resume_with_issues, contract_json)
    recommendations_str = " ".join(report.recommendations)

    assert "Hard Word Ceiling" in recommendations_str
    assert "Replace non-standard date separators" in recommendations_str
