"""Tests for LinkedIn URL interception and prevention of unauthenticated scraping."""

import pytest
from unittest.mock import patch

from breadwinner.core.ingestor import (
    UniversalIngestor,
    IngestionError,
    LINKEDIN_INTERCEPT_MESSAGE,
    is_linkedin_url,
)
from breadwinner.ui.retro import clean_error_message
from breadwinner.providers.base import BaseLLMProvider


class DummyProvider(BaseLLMProvider):
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {}

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        return ""


def test_is_linkedin_url_detection():
    """Verify various forms of LinkedIn profile URLs are recognized."""
    valid_profiles = [
        "https://www.linkedin.com/in/alex-taylor",
        "https://www.linkedin.com/in/alex-taylor/",
        "http://linkedin.com/in/alex-taylor",
        "https://uk.linkedin.com/in/alex-taylor?trk=profile",
        "linkedin.com/in/alex-taylor",
        "www.linkedin.com/in/alex-taylor",
        "'https://linkedin.com/in/alex-taylor'",
    ]
    for url in valid_profiles:
        assert is_linkedin_url(url) is True, f"Failed to detect: {url}"

    non_profiles = [
        "https://linkedin.com/jobs/view/12345",
        "https://linkedin.com/company/apex-cloud",
        "https://github.com/alex-taylor",
        "https://alextaylor.dev",
        "~/Downloads/Alex_Resume.pdf",
    ]
    for url in non_profiles:
        assert is_linkedin_url(url) is False, f"False positive for: {url}"


@patch("requests.get")
def test_universal_ingestor_intercepts_linkedin_url(mock_get):
    """Ensure UniversalIngestor.ingest blocks LinkedIn without network calls."""
    provider = DummyProvider()
    url = "https://www.linkedin.com/in/alex-taylor"

    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.ingest(url, provider)

    assert LINKEDIN_INTERCEPT_MESSAGE in str(exc_info.value)
    assert "Save to PDF" in str(exc_info.value)
    mock_get.assert_not_called()


@patch("requests.get")
def test_extract_text_from_url_blocks_linkedin(mock_get):
    """Ensure extract_text_from_url blocks LinkedIn URLs without network calls."""
    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.extract_text_from_url("https://linkedin.com/in/alex-taylor")

    assert LINKEDIN_INTERCEPT_MESSAGE in str(exc_info.value)
    mock_get.assert_not_called()


@patch("requests.get")
def test_extract_deep_portfolio_blocks_linkedin(mock_get):
    """Ensure extract_deep_portfolio blocks LinkedIn URLs without network calls."""
    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.extract_deep_portfolio("https://linkedin.com/in/alex-taylor")

    assert LINKEDIN_INTERCEPT_MESSAGE in str(exc_info.value)
    mock_get.assert_not_called()


@patch("requests.get")
def test_discover_portfolio_routes_blocks_linkedin(mock_get):
    """Ensure discover_portfolio_routes blocks LinkedIn URLs without network calls."""
    with pytest.raises(IngestionError) as exc_info:
        UniversalIngestor.discover_portfolio_routes("https://linkedin.com/in/alex-taylor")

    assert LINKEDIN_INTERCEPT_MESSAGE in str(exc_info.value)
    mock_get.assert_not_called()


def test_clean_error_message_formats_linkedin_notice():
    """Verify clean_error_message provides clean actionable advice for LinkedIn 999."""
    raw_error = f"IngestionError: {LINKEDIN_INTERCEPT_MESSAGE}"
    headline, detail = clean_error_message(raw_error)

    assert "LinkedIn Scraping Blocked" in headline
    assert "Save to PDF" in detail
    assert "breadwinner ingest" in detail
