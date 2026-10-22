"""Unit tests for the multi-archetype resume template suite."""

import pytest
from breadwinner.core.models import (
    CandidateProfile,
    JobPosting,
    MatchAnalysis,
    TailoredApplication,
    WorkExperience,
    Education,
    Project,
    SkillCategory,
)
from breadwinner.core.renderer import TemplateRenderer


@pytest.fixture
def sample_profile_and_app():
    profile = CandidateProfile(
        full_name="Jordan Vance",
        title="Principal Distributed Systems Architect",
        email="jordan.vance@example.com",
        phone="+44 7700 900123",
        location="London, UK",
        linkedin_url="https://linkedin.com/in/jordanvance",
        github_url="https://github.com/jordanvance",
        portfolio_url="https://jordanvance.io",
        summary="Strategic systems engineer with 10+ years designing high-throughput distributed backends and event streams.",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Principal Architect",
                start_date="2021",
                end_date="Present",
                location="London, UK",
                bullets=[
                    "**Enterprise Platform Scaling:** Architected event-driven microservices processing 25M+ events/day at sub-10ms p99 latency.",
                    "**Cost Optimization:** Directed cloud migration reducing compute costs by 38% across 120 Kubernetes clusters.",
                ],
            ),
            WorkExperience(
                company="Global Data Labs",
                role="Senior Staff Engineer",
                start_date="2017",
                end_date="2021",
                location="Cambridge, UK",
                bullets=[
                    "**Stream Processing:** Engineered Kafka and Flink pipelines sustaining 150,000 QPS with 99.99% reliability.",
                ],
            ),
        ],
        education=[
            Education(
                institution="University of Oxford",
                degree="MSc Advanced Computer Science",
                start_date="2015",
                end_date="2016",
                grade="Distinction",
            ),
        ],
        projects=[
            Project(
                name="Ternary-Kernel-MLX",
                description="High-performance 1.58-bit quantized matrix multiplication kernels for Apple Silicon.",
                tech_stack=["Python", "Metal", "MLX", "C++"],
                github_url="https://github.com/jordanvance/ternary-kernel-mlx",
                highlights=[
                    "Benchmarked 3.4x faster token generation compared to 4-bit baseline.",
                ],
            ),
        ],
        skills=[
            SkillCategory(
                category="Distributed Systems & Data",
                skills=["Kafka", "Flink", "Redis", "PostgreSQL", "gRPC"],
            ),
            SkillCategory(
                category="Languages & Frameworks",
                skills=["Go", "Python", "Rust", "C++", "PyTorch"],
            ),
        ],
    )

    job = JobPosting(
        id="fintech-principal-1",
        company="Fintech Apex",
        title="Principal Systems Architect",
    )

    app = TailoredApplication(
        job=job,
        persona="backend_dist",
        match_analysis=MatchAnalysis(
            match_score=95,
            matched_skills=["Distributed Systems", "Kafka", "Go", "Kubernetes"],
        ),
        tailored_summary="Principal Systems Architect with track record scaling enterprise platforms to 25M+ daily transactions.",
        tailored_experiences=profile.experiences,
        tailored_projects=profile.projects,
        tailored_skills=profile.skills,
        cover_letter="Dear Hiring Team,\n\nI am writing to express my enthusiastic interest.",
    )

    return profile, app


def test_list_available_templates():
    """Verify that all archetype templates are registered."""
    templates = TemplateRenderer.list_available_templates()
    expected = [
        "jakes",
        "modern",
        "executive",
        "systems_research",
        "compact_1page",
        "consultant",
        "ats",
    ]
    for t in expected:
        assert t in templates


def test_render_executive_template(sample_profile_and_app):
    """Verify the Executive template rendering and section hierarchy."""
    profile, app = sample_profile_and_app
    renderer = TemplateRenderer()

    html = renderer.render_resume(profile, app, "executive")

    assert "Jordan Vance" in html
    assert "Principal Distributed Systems Architect" in html
    assert "Executive Summary" in html
    assert "Core Competencies & Technical Skills" in html
    assert "Leadership & Professional Experience" in html
    assert "Apex Cloud Systems" in html
    assert "25M+ events/day" in html
    assert "Key Projects & Open Source Architecture" in html
    assert "Ternary-Kernel-MLX" in html
    assert "Education & Credentials" in html
    assert "University of Oxford" in html

    # Verify no unrendered Jinja tags
    assert "{{" not in html
    assert "{%" not in html


def test_render_systems_research_template(sample_profile_and_app):
    """Verify the Systems Research template rendering and section hierarchy."""
    profile, app = sample_profile_and_app
    renderer = TemplateRenderer()

    html = renderer.render_resume(profile, app, "systems_research")

    assert "Jordan Vance" in html
    assert "Systems & Research Resume" in html
    assert "Research Focus & System Architectures" in html
    assert "Research Benchmarks & Open Frameworks" in html
    assert "Ternary-Kernel-MLX" in html
    assert "Applied Systems & Industry Experience" in html
    assert "Apex Cloud Systems" in html
    assert "Academic Credentials" in html
    assert "University of Oxford" in html

    assert "{{" not in html
    assert "{%" not in html


def test_render_compact_1page_template(sample_profile_and_app):
    """Verify the Compact 1-Page template rendering."""
    profile, app = sample_profile_and_app
    renderer = TemplateRenderer()

    html = renderer.render_resume(profile, app, "compact_1page")

    assert "Jordan Vance" in html
    assert "Technical Skills" in html
    assert "Experience" in html
    assert "Projects" in html
    assert "Education" in html
    assert "University of Oxford" in html
    assert "Apex Cloud Systems" in html

    assert "{{" not in html
    assert "{%" not in html


def test_render_consultant_template(sample_profile_and_app):
    """Verify the Consultant template rendering and strategic ROI sections."""
    profile, app = sample_profile_and_app
    renderer = TemplateRenderer()

    html = renderer.render_resume(profile, app, "consultant")

    assert "Jordan Vance" in html
    assert "Strategic Value Proposition" in html
    assert "Client Engagements & Commercial ROI" in html
    assert "Apex Cloud Systems" in html
    assert "Technical Architecture & Core Advisory Stacks" in html
    assert "Flagship Deliverables & Systems Architecture" in html
    assert "Education & Credentials" in html

    assert "{{" not in html
    assert "{%" not in html


def test_all_templates_render_cleanly(sample_profile_and_app):
    """Verify every registered template renders without exceptions or leftover template delimiters."""
    profile, app = sample_profile_and_app
    renderer = TemplateRenderer()

    for tpl_name in TemplateRenderer.list_available_templates():
        content = renderer.render_resume(profile, app, tpl_name)
        assert len(content) > 100
        assert "Jordan Vance" in content
        assert "{{" not in content
        assert "{%" not in content


def test_templates_handle_empty_fields_gracefully():
    """Verify that templates handle empty optional fields without errors."""
    minimal_profile = CandidateProfile(
        full_name="Minimal User",
        title="Software Engineer",
        email="minimal@example.com",
    )
    job = JobPosting(id="job-1", company="MinCorp", title="Engineer")
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=80),
        tailored_summary="",
        tailored_experiences=[],
        tailored_projects=[],
        tailored_skills=[],
    )
    renderer = TemplateRenderer()

    for tpl_name in ["executive", "systems_research", "compact_1page", "consultant"]:
        content = renderer.render_resume(minimal_profile, app, tpl_name)
        assert "Minimal User" in content
        assert "{{" not in content
        assert "{%" not in content
