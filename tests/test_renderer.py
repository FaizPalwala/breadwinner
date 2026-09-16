"""Unit tests for template rendering."""

from breadwinner.core.models import (
    CandidateProfile,
    JobPosting,
    MatchAnalysis,
    TailoredApplication,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)
from breadwinner.core.renderer import TemplateRenderer


def test_render_all_templates():
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="AI/ML Engineer",
        email="alex.taylor@example.com",
        location="London, UK",
        experiences=[
            WorkExperience(
                company="Tech Corp",
                role="SDE 2",
                start_date="2023",
                end_date="2024",
                bullets=["Engineered data pipelines processing 3M+ inbound records."]
            )
        ],
        education=[
            Education(
                institution="University of Technology",
                degree="MSc Advanced Computer Science",
                start_date="2025",
                end_date="2026"
            )
        ],
        projects=[
            Project(
                name="Serverless Heatmap",
                description="GitHub calendar action",
                tech_stack=["TypeScript"]
            )
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Python", "Java"])
        ]
    )

    job = JobPosting(
        id="monzo-mle",
        company="Monzo",
        title="Machine Learning Engineer"
    )

    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(
            match_score=92,
            matched_skills=["Python", "Distributed Systems"]
        ),
        tailored_summary="Experienced engineer with 4+ years at Tech Corp.",
        tailored_experiences=profile.experiences,
        tailored_projects=profile.projects,
        tailored_skills=profile.skills,
        cover_letter="Dear Monzo,\n\nI am thrilled to apply for this MLE role.",
        portal_answers={"why_us": "Monzo is transforming banking with ML."}
    )

    renderer = TemplateRenderer()

    # 1. Jake's HTML
    jakes_html = renderer.render_resume(profile, app, "jakes")
    assert "Alex Taylor" in jakes_html
    assert "Tech Corp" in jakes_html
    assert "3M+ inbound records" in jakes_html
    assert "University of Technology" in jakes_html

    # 2. Modern HTML
    modern_html = renderer.render_resume(profile, app, "modern")
    assert "Alex Taylor" in modern_html
    assert "Professional Experience" in modern_html

    # 3. ATS Markdown
    ats_md = renderer.render_resume(profile, app, "ats")
    assert "# Alex Taylor" in ats_md
    assert "## EXPERIENCE" in ats_md
    assert "Tech Corp" in ats_md

    # 4. Cover Letter & Portal Q&A
    cl = renderer.render_cover_letter(profile, app)
    assert "Alex Taylor" in cl
    assert "Monzo" in cl

    qna = renderer.render_portal_qna(profile, app)
    assert "Why Us" in qna
    assert "Monzo is transforming banking" in qna

