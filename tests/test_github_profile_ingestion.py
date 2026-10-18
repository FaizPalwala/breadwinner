"""Tests for native GitHub profile ingestion and repository dossier synthesis."""

import pytest
from unittest.mock import patch, MagicMock

from breadwinner.core.ingestor import (
    UniversalIngestor,
    IngestionError,
    is_github_profile_url,
    classify_document,
)
from breadwinner.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, response: dict):
        self.response = response

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return self.response

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        return ""


def test_is_github_profile_url_detection():
    """Verify GitHub user profile URLs and handles are accurately detected."""
    valid_profiles = [
        ("https://github.com/alextaylor", "alextaylor"),
        ("https://www.github.com/alextaylor/", "alextaylor"),
        ("http://github.com/alextaylor", "alextaylor"),
        ("github.com/alextaylor", "alextaylor"),
        ("@alextaylor", "alextaylor"),
        ("'@alextaylor'", "alextaylor"),
    ]
    for url, expected_user in valid_profiles:
        detected = is_github_profile_url(url)
        assert detected == expected_user, f"Failed for {url}: expected {expected_user}, got {detected}"

    invalid_profiles = [
        "https://github.com/alextaylor/distributed-db",
        "https://github.com/features",
        "https://github.com/pricing",
        "https://github.com/topics",
        "https://github.com",
        "https://example.com/alextaylor",
        "~/Projects/repo",
    ]
    for url in invalid_profiles:
        assert is_github_profile_url(url) is None, f"False positive for {url}"


def test_classify_document_detects_github_profile():
    """Verify classify_document returns 'github_profile' for GitHub profile URLs."""
    assert classify_document("content", "https://github.com/alextaylor") == "github_profile"
    assert classify_document("content", "@alextaylor") == "github_profile"
    assert classify_document("content", "github.com/alextaylor") == "github_profile"


@patch("requests.get")
def test_extract_github_profile_filtering_and_sorting(mock_get):
    """Verify extract_github_profile filters forks/empty repos and sorts by stars and recency."""
    user_data = {
        "name": "Alex Taylor",
        "bio": "Distributed systems and infrastructure architect.",
        "company": "Apex Cloud Systems",
        "location": "San Francisco, CA",
        "blog": "https://alextaylor.dev",
        "public_repos": 3,
    }

    repos_data = [
        {
            "name": "forked-framework",
            "fork": True,
            "size": 500,
            "description": "A fork of an external tool",
            "stargazers_count": 20,
            "updated_at": "2026-03-01T00:00:00Z",
        },
        {
            "name": "empty-sandbox",
            "fork": False,
            "size": 0,
            "description": "",
            "stargazers_count": 0,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "name": "stream-router",
            "fork": False,
            "size": 350,
            "description": "High-throughput event streaming engine.",
            "language": "Go",
            "stargazers_count": 45,
            "pushed_at": "2026-02-15T00:00:00Z",
            "topics": ["kafka", "distributed-systems"],
        },
        {
            "name": "raft-consensus",
            "fork": False,
            "size": 800,
            "description": "Deterministic consensus algorithm in Go.",
            "language": "Go",
            "stargazers_count": 120,
            "pushed_at": "2026-01-10T00:00:00Z",
            "topics": ["consensus", "raft"],
        },
    ]

    def mock_responses(url, *args, **kwargs):
        mock = MagicMock()
        if "api.github.com/users/alextaylor/repos" in url:
            mock.status_code = 200
            mock.json.return_value = repos_data
        elif "api.github.com/users/alextaylor" in url:
            mock.status_code = 200
            mock.json.return_value = user_data
        elif "raw.githubusercontent.com/alextaylor/raft-consensus" in url:
            mock.status_code = 200
            mock.text = "# Raft Consensus Engine\n\nHigh-performance Raft consensus implementation in Go."
        elif "raw.githubusercontent.com/alextaylor/stream-router" in url:
            mock.status_code = 200
            mock.text = "# Stream Router\n\nSub-10ms event router for streaming architecture."
        else:
            mock.status_code = 404
            mock.text = ""
        return mock

    mock_get.side_effect = mock_responses

    composite_text, dossier_docs = UniversalIngestor.extract_github_profile("alextaylor")

    # 1. Profile information preserved
    assert "Alex Taylor" in composite_text
    assert "Apex Cloud Systems" in composite_text
    assert "San Francisco, CA" in composite_text

    # 2. Forked and empty repos excluded
    assert "forked-framework" not in composite_text
    assert "empty-sandbox" not in composite_text

    # 3. Higher-starred repo appears before lower-starred repo
    raft_idx = composite_text.find("raft-consensus")
    stream_idx = composite_text.find("stream-router")
    assert raft_idx != -1 and stream_idx != -1
    assert raft_idx < stream_idx

    # 4. Dossier documents populated
    assert "projects/raft-consensus.md" in dossier_docs
    assert "projects/stream-router.md" in dossier_docs
    assert "High-performance Raft" in dossier_docs["projects/raft-consensus.md"]


@patch("requests.get")
def test_extract_github_profile_rate_limit(mock_get):
    """Verify GitHub API rate limit (403/429) raises actionable IngestionError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.extract_github_profile("alextaylor")

    assert "rate limit exceeded" in str(exc_info.value).lower()


@patch("requests.get")
def test_extract_github_profile_user_not_found(mock_get):
    """Verify GitHub user 404 raises actionable IngestionError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.extract_github_profile("nonexistent-user-12345")

    assert "not found" in str(exc_info.value).lower()


@patch("requests.get")
def test_universal_ingestor_ingest_github_profile_end_to_end(mock_get):
    """Verify full end-to-end ingestion flow from GitHub URL to CandidateProfile."""
    mock_get.side_effect = [
        # 1. User profile API
        MagicMock(status_code=200, json=lambda: {
            "name": "Alex Taylor",
            "bio": "Staff Cloud Architect",
            "company": "Apex Cloud Systems",
            "location": "Seattle, WA",
            "blog": "",
            "public_repos": 1,
        }),
        # 2. Repositories API
        MagicMock(status_code=200, json=lambda: [{
            "name": "distributed-cache",
            "fork": False,
            "size": 400,
            "description": "Distributed in-memory cache.",
            "language": "Go",
            "stargazers_count": 80,
            "pushed_at": "2026-03-01T00:00:00Z",
            "topics": ["cache", "redis"],
        }]),
        # 3. User profile README probe
        MagicMock(status_code=404, text=""),
        # 4. Repo README probe
        MagicMock(status_code=200, text="# Distributed Cache\n\nHigh-speed replicated caching engine."),
    ]

    llm_payload = {
        "full_name": "Alex Taylor",
        "title": "Staff Cloud Architect",
        "email": "alex@example.com",
        "location": "Seattle, WA",
        "experiences": [
            {
                "company": "Apex Cloud Systems",
                "role": "Staff Cloud Architect",
                "bullets": ["Architected distributed caching layer scaling to 10M events/day."],
            }
        ],
        "projects": [
            {
                "name": "Distributed Cache",
                "description": "High-speed replicated caching engine.",
                "tech_stack": ["Go", "Redis"],
                "highlights": ["Sub-5ms response time"],
            }
        ],
        "skills": [
            {"category": "Languages", "skills": ["Go", "Python"]},
            {"category": "Backend & Distributed Systems", "skills": ["Distributed Systems", "Redis"]},
        ],
        "context_diary": "# Engineering Philosophy\nFocused on predictable distributed performance.",
        "dossier_documents": {
            "projects/distributed-cache.md": "# Distributed Cache\nHigh-speed replicated caching engine."
        },
    }

    provider = MockLLMProvider(llm_payload)
    profile = UniversalIngestor.ingest("https://github.com/alextaylor", provider)

    assert profile.full_name == "Alex Taylor"
    assert profile.title == "Staff Cloud Architect"
    assert len(profile.projects) >= 1
    assert profile.projects[0].name == "Distributed Cache"
    assert "projects/distributed-cache.md" in profile.raw_context.get("dossier_documents", {})
