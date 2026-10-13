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

    # 5. Cover Letter HTML (Dual PDF Support)
    cl_html = renderer.render_cover_letter_html(profile, app)
    assert "Alex Taylor" in cl_html
    assert "Monzo" in cl_html
    assert "Machine Learning Engineer" in cl_html
    assert "I am thrilled to apply for this MLE role" in cl_html
    assert "Hiring Team" in cl_html
    assert "Sincerely," in cl_html


def test_template_delimiter_safety_and_graduation_date():
    """Verify missing URLs never render orphan pipe delimiters and graduation dates render cleanly."""
    profile = CandidateProfile(
        full_name="Sarah Connor",
        title="Security Analyst",
        email="sarah@example.com",
        location="Los Angeles, CA",
        # Explicitly no github_url, linkedin_url, portfolio_url
        education=[
            Education(
                institution="Cyberdyne Institute",
                degree="BSc Cybersecurity",
                # Explicitly missing start_date
                start_date=None,
                end_date="May 2024"
            )
        ]
    )
    job = JobPosting(id="sec-1", company="Resistance", title="Analyst")
    app = TailoredApplication(
        job=job,
        persona="security",
        match_analysis=MatchAnalysis(match_score=85),
        tailored_summary="Security specialist.",
        tailored_experiences=[],
        tailored_projects=[],
        tailored_skills=[]
    )
    renderer = TemplateRenderer()

    # Jake's Template
    jakes = renderer.render_resume(profile, app, "jakes")
    assert "sarah@example.com" in jakes
    assert "Los Angeles, CA" in jakes
    # Ensure no double/orphan pipes
    assert " |  | " not in jakes
    assert "| </span>" not in jakes
    # Ensure graduation date rendered cleanly without orphan dash
    assert "May 2024" in jakes
    assert "-- May 2024" not in jakes
    assert "- May 2024" not in jakes

    # Modern Template
    modern = renderer.render_resume(profile, app, "modern")
    assert " |  | " not in modern
    assert "May 2024" in modern

    # ATS Markdown
    ats = renderer.render_resume(profile, app, "ats")
    assert " |  | " not in ats
    assert "Email: sarah@example.com" in ats
    assert "- May 2024" not in ats


def test_parse_markdown_resume_experiences():
    """Verify bidirectional parsing of markdown resume experiences into WorkExperience models."""
    from breadwinner.core.renderer import parse_markdown_resume_experiences

    md_content = """# John Doe
Email: john@example.com | Phone: 555-1234

## EXPERIENCE

### Lead AI Engineer - Cerebras Systems
*2022 - Present | Sunnyvale, CA*
- Scaled distributed training cluster to 64 nodes, improving throughput by 42%.
- Deployed PyTorch models serving 12,000 QPS with 99.9% uptime.

### Machine Learning Engineer @ Graphcore
*2020 - 2022 | Bristol, UK*
- Fine-tuned transformer models on 50B tokens, reducing memory footprint by 28%.

## EDUCATION

### MSc Artificial Intelligence
University of Leeds | 2020
"""

    existing = [
        WorkExperience(
            company="Cerebras Systems",
            role="Lead AI Engineer",
            start_date="2022",
            end_date="Present",
            location="Sunnyvale, CA",
            bullets=["Old bullet 1"]
        ),
        WorkExperience(
            company="Graphcore",
            role="Machine Learning Engineer",
            start_date="2020",
            end_date="2022",
            location="Bristol, UK",
            bullets=["Old bullet 2"]
        )
    ]

    exps, editor_text = parse_markdown_resume_experiences(md_content, existing)

    assert len(exps) == 2
    assert exps[0].role == "Lead AI Engineer"
    assert exps[0].company == "Cerebras Systems"
    assert exps[0].start_date == "2022"  # Preserved from existing
    assert len(exps[0].bullets) == 2
    assert "Scaled distributed training cluster" in exps[0].bullets[0]
    assert "Deployed PyTorch models" in exps[0].bullets[1]

    assert exps[1].role == "Machine Learning Engineer"
    assert exps[1].company == "Graphcore"
    assert len(exps[1].bullets) == 1
    assert "Fine-tuned transformer models" in exps[1].bullets[0]

    # Verify editor text has clean headings
    assert "### Lead AI Engineer @ Cerebras Systems" in editor_text
    assert "### Machine Learning Engineer @ Graphcore" in editor_text


def test_parse_markdown_resume_experiences_no_subheadings():
    """Verify that bullets without explicit role headings default to the first active work experience."""
    from breadwinner.core.renderer import parse_markdown_resume_experiences

    md_content = """## EXPERIENCE
- Optimized SQL execution plans, decreasing query latency by 55%.
- Implemented Redis caching layer handling 10,000 requests/sec.
"""

    existing = [
        WorkExperience(
            company="Acme Tech",
            role="Senior Backend Engineer",
            bullets=["Old bullet"]
        )
    ]

    exps, editor_text = parse_markdown_resume_experiences(md_content, existing)
    assert len(exps) == 1
    assert exps[0].role == "Senior Backend Engineer"
    assert exps[0].company == "Acme Tech"
    assert len(exps[0].bullets) == 2
    assert "Optimized SQL execution plans" in exps[0].bullets[0]
    assert "### Senior Backend Engineer @ Acme Tech" in editor_text

