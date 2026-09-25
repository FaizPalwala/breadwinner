"""Unit tests for universal profile ingestor and document extraction."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from breadwinner.core.ingestor import UniversalIngestor
from breadwinner.providers.factory import MockLLMProvider


def test_extract_text_from_file_markdown(tmp_path: Path):
    md_file = tmp_path / "bio.md"
    md_file.write_text("# John Doe\nExperienced systems engineer with Go and Python expertise.")

    text = UniversalIngestor.extract_text_from_file(md_file)
    assert "John Doe" in text
    assert "systems engineer" in text


def test_parse_text_to_profile():
    mock_provider = MockLLMProvider()
    raw_text = "Jane Doe, Staff Engineer at Cloud Corp. Designed distributed cache handling 1M QPS."

    profile = UniversalIngestor.parse_text_to_profile(raw_text, mock_provider, source_label="Test")
    assert profile.full_name is not None
    assert profile.title is not None
    assert len(profile.experiences) > 0


def test_extract_text_from_url_mocked():
    fake_html = """
    <html>
      <head><title>Portfolio</title></head>
      <body>
        <nav><a href="#">Ignore Nav</a></nav>
        <main>
          <h1>Dev Portfolio</h1>
          <p>Full stack engineer with 5 years experience.</p>
        </main>
        <footer>Ignore footer</footer>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.text = fake_html
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        text = UniversalIngestor.extract_text_from_url("https://example.com/portfolio")
        assert "Dev Portfolio" in text
        assert "5 years experience" in text
        assert "Ignore Nav" not in text
        assert "Ignore footer" not in text


def test_extract_text_from_pdf_real_or_fallback():
    sample_pdf = Path("applications/2026-09-14_Monzo_SeniorAppliedAIEngineer/resume.pdf")
    if sample_pdf.exists():
        text = UniversalIngestor.extract_text_from_file(sample_pdf)
        assert len(text) > 50
        assert "EDUCATION" in text or "EXPERIENCE" in text or "SKILLS" in text
    else:
        # Fallback assertion if sample path absent in other test runners
        with patch.object(UniversalIngestor, "extract_text_from_pdf", return_value="Sample Resume"):
            assert UniversalIngestor.extract_text_from_file(Path("test.pdf")) == "Sample Resume"

