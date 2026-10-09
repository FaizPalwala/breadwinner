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
