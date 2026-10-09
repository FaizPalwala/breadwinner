"""Unit tests for ADR 002: Universal Candidate Ingestion, Portfolio Route Discovery, and Deduplication."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from breadwinner.core.ingestor import (
    UniversalIngestor,
    normalize_source,
    clean_user_input_path,
    merge_profiles
)
from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)


def test_clean_user_input_path():
    """Verify paths dragged from macOS terminal with quotes and spaces are cleaned."""
    assert clean_user_input_path("'/Users/alex/Desktop/My Resume.pdf'") == "/Users/alex/Desktop/My Resume.pdf"
    assert clean_user_input_path('"file:///Users/alex/My%20Dissertation.pdf"') == "/Users/alex/My Dissertation.pdf"
    assert clean_user_input_path(r"/Users/alex/My\ Work\ History.docx") == "/Users/alex/My Work History.docx"


def test_normalize_source_schemeless_domains():
    """Verify bare domains, URLs, GitHub handles, and local files are classified properly."""
    label, kind = normalize_source("alex-portfolio.dev")
    assert kind == "url"
    assert label == "https://alex-portfolio.dev"

    label, kind = normalize_source("https://example.com/about")
    assert kind == "url"
    assert label == "https://example.com/about"

    label, kind = normalize_source("@octocat")
    assert kind == "url"
    assert label == "https://github.com/octocat"

    label, kind = normalize_source("Just some raw career notes without domains")
    assert kind == "text"


def test_merge_profiles_metric_maximization():
    """Verify that when duplicate bullets exist, the bullet with highest quantified metrics wins."""
    base_exp = WorkExperience(
        company="Acme Corp",
        role="Senior Software Engineer",
        start_date="2022",
        end_date="Present",
        bullets=[
            "Built distributed caching layer using Redis and Go.",
            "Mentored junior developers on software craftsmanship."
        ]
    )
    base_profile = CandidateProfile(
        full_name="Alex Mercer",
        title="Staff AI Engineer",
        experiences=[base_exp]
    )

    # Incoming profile with higher quantified version of the caching bullet
    incoming_exp = WorkExperience(
        company="Acme Corp",
        role="Senior Software Engineer",
        start_date="2022",
        end_date="Present",
        bullets=[
            "Built distributed caching layer using Redis and Go, reducing p99 latency by 45% across 25M daily requests."
        ]
    )
    incoming_profile = CandidateProfile(
        full_name="Alex Mercer",
        title="Staff AI Engineer",
        experiences=[incoming_exp]
    )

    merged = merge_profiles(base_profile, incoming_profile)
    acme = next(e for e in merged.experiences if e.company == "Acme Corp")

    # The higher metric bullet should replace the unquantified version
    assert any("reducing p99 latency by 45% across 25M daily requests" in b for b in acme.bullets)
    # The non-overlapping bullet should still be retained
    assert any("Mentored junior developers" in b for b in acme.bullets)
    assert len(acme.bullets) == 2


def test_discover_portfolio_routes():
    """Verify discovery of canonical routes and direct resume links from an HTML portfolio."""
    mock_html = """
    <html>
      <head><title>Faiz Palwala</title></head>
      <body>
        <nav>
          <a href="/about">About Me</a>
          <a href="/projects">Projects</a>
          <a href="/research">Research</a>
          <a href="/noggin">Technical Blog</a>
          <a href="/resume.pdf">Download Resume (PDF)</a>
        </nav>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.text = mock_html
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        with patch("requests.head", side_effect=Exception("No head")):
            routes = UniversalIngestor.discover_portfolio_routes("https://alex-portfolio.dev")

    cats = {r[1] for r in routes}
    assert "resume_pdf" in cats
    assert "about" in cats
    assert "projects" in cats
    assert "research" in cats
    assert "articles" in cats


def test_universal_ingest_bare_domain_mock():
    """Verify UniversalIngestor.ingest handles bare domain without throwing scheme errors."""
    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "full_name": "Alex Mercer",
        "title": "Lead AI Architect",
        "experiences": [
            {
                "company": "Acme Corp",
                "role": "Senior Consultant",
                "start_date": "2021",
                "end_date": "2023",
                "bullets": ["Engineered production ML pipelines scaling to 10M daily events."]
            }
        ],
        "education": [],
        "projects": [],
        "skills": []
    }

    with patch.object(UniversalIngestor, "extract_deep_portfolio", return_value=("Homepage text", {})):
        profile = UniversalIngestor.ingest("alex-portfolio.dev", mock_provider)

    assert profile.full_name == "Alex Mercer"
    assert len(profile.experiences) == 1
    assert profile.experiences[0].company == "Acme Corp"


def test_multi_source_ingestion_synthesis_and_5_bucket_skills():
    """Verify that multi-source ingestion consolidates bullets, reroutes academic roles, and strictly groups skills."""
    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "full_name": "Faiz Palwala",
        "title": "AI/ML & Distributed Systems Engineer",
        "summary": "Specialist in machine unlearning and enterprise cloud platforms.",
        "experiences": [
            {
                "company": "Deloitte",
                "role": "Senior Consultant",
                "start_date": "2019",
                "end_date": "2023",
                "bullets": [
                    "Architected enterprise healthcare microservices for 23M+ members.",
                    "Architected enterprise healthcare platform serving 23M+ members with 99.99% uptime.",  # Near-duplicate with metric
                    "Automated validation pipeline reducing failure backlog by 40%."
                ]
            },
            {
                "company": "University of Leeds",
                "role": "MSc Graduate Researcher",
                "start_date": "2023",
                "end_date": "2024",
                "bullets": ["Evaluated machine unlearning on synthetic identity face clusters."]
            }
        ],
        "education": [
            {
                "degree": "MSc Advanced Computer Science",
                "institution": "University of Leeds",
                "graduation_year": "2024"
            }
        ],
        "projects": [
            {
                "name": "SFHQ-VirtualID - Synthetic Face Clusters",
                "description": "Synthetic identity clusters for machine unlearning.",
                "tech_stack": ["Python", "PyTorch", "Diffusers"]
            },
            {
                "name": "sfhq virtualid",
                "description": "Reproducible benchmark.",
                "tech_stack": ["InstantID"]
            },
            {
                "name": "GraphContext MCP",
                "description": "macOS code assistant.",
                "tech_stack": ["FastAPI", "MLX"]
            }
        ],
        "skills": [
            {
                "category": "Programming Languages",
                "skills": ["Python", "TypeScript", "SQL"]
            },
            {
                "category": "Machine Learning & AI",
                "skills": ["Python", "PyTorch", "Diffusers", "InstantID"]  # Python is duplicate
            },
            {
                "category": "Backend Technologies",
                "skills": ["FastAPI", "PostgreSQL", "Redis"]
            },
            {
                "category": "DevOps & Cloud",
                "skills": ["Docker", "Linux", "Slurm", "AWS"]
            },
            {
                "category": "UI Engineering",
                "skills": ["React", "Tailwind CSS"]
            }
        ],
        "context_diary": "# Personal Directives & Guardrails\n\n## Engineering Philosophy & Narrative\nEmpirical proofs.",
        "dossier_documents": {
            "research_dissertation.md": "# Research Dissertation\nUnlearning framework.",
            "engineering_voice_and_philosophy.md": "# Engineering Philosophy\nSystems craftsmanship."
        }
    }

    sources = [
        "https://faizpalwala.tech",
        "https://faizpalwala.tech/about",
        "https://faizpalwala.tech/projects",
        "https://faizpalwala.tech/research",
        "https://faizpalwala.tech/noggin"
    ]

    with patch.object(UniversalIngestor, "extract_text_from_url", return_value="Sample portfolio text"):
        profile = UniversalIngestor.ingest(sources, mock_provider)

    # 1. Experience check: University of Leeds rerouted to education; Deloitte consolidated without duplicate bullets
    assert len(profile.experiences) == 1
    assert profile.experiences[0].company == "Deloitte"
    deloitte_bullets = profile.experiences[0].bullets
    # The higher metric bullet won and near-duplicate was merged
    assert len(deloitte_bullets) == 2
    assert any("23M+ members with 99.99% uptime" in b for b in deloitte_bullets)

    # 2. Project check: sfhq virtualid clustered into 1 canonical entity
    assert len(profile.projects) == 2
    canon_names = {p.name for p in profile.projects}
    assert "SFHQ-VirtualID: Synthetic Identity Datasets" in canon_names
    assert "GraphContext MCP" in canon_names
    sfhq_proj = next(p for p in profile.projects if "SFHQ" in p.name)
    assert "InstantID" in sfhq_proj.tech_stack
    assert "PyTorch" in sfhq_proj.tech_stack

    # 3. Skills check: Strictly normalized to the 5 standard categories with zero cross-category duplicates
    skill_cats = {s.category for s in profile.skills}
    assert skill_cats.issubset({
        "Languages",
        "AI/ML & Research",
        "Backend & Distributed Systems",
        "Cloud & Infrastructure",
        "Frontend & Web"
    })

    # Verify zero duplicate skills across categories
    all_skills = []
    for s_cat in profile.skills:
        all_skills.extend([s.lower() for s in s_cat.skills])
    assert len(all_skills) == len(set(all_skills))  # No duplicates!
    lang_cat = next(s for s in profile.skills if s.category == "Languages")
    assert "Python" in lang_cat.skills
    aiml_cat = next(s for s in profile.skills if s.category == "AI/ML & Research")
    assert "Python" not in aiml_cat.skills  # Deduped!

    # 4. Context & Dossiers check
    assert "Personal Directives" in profile.raw_context.get("context_diary", "")
    dossier_docs = profile.raw_context.get("dossier_documents", {})
    assert "research_dissertation.md" in dossier_docs
    assert "engineering_voice_and_philosophy.md" in dossier_docs

