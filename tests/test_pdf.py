"""Unit tests for headless browser PDF export engine."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from breadwinner.core.pdf import (
    find_browser_executable,
    render_html_to_pdf,
    PDFGenerationError,
    BrowserNotFoundError
)


def test_find_browser_executable_override():
    custom_path = "/usr/local/bin/custom-browser"
    with patch("breadwinner.core.pdf.Path.exists", return_value=True):
        found = find_browser_executable(custom_path)
        assert found == custom_path


def test_render_html_to_pdf_missing_source(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.html"
    out_pdf = tmp_path / "out.pdf"
    with pytest.raises(FileNotFoundError):
        render_html_to_pdf(non_existent, out_pdf)


def test_render_html_to_pdf_no_browser(tmp_path: Path):
    html_file = tmp_path / "test.html"
    html_file.write_text("<h1>Test</h1>", encoding="utf-8")
    out_pdf = tmp_path / "out.pdf"

    with patch("breadwinner.core.pdf.find_browser_executable", return_value=None):
        with pytest.raises(BrowserNotFoundError):
            render_html_to_pdf(html_file, out_pdf)


def test_render_html_to_pdf_mocked_success(tmp_path: Path):
    html_file = tmp_path / "test.html"
    html_file.write_text("<h1>Test</h1>", encoding="utf-8")
    out_pdf = tmp_path / "out.pdf"

    def fake_subprocess_run(cmd, **kwargs):
        # Create the fake PDF file to simulate successful browser write
        out_pdf.write_bytes(b"%PDF-1.4 Mock PDF content")
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock

    with patch("breadwinner.core.pdf.find_browser_executable", return_value="/fake/chrome"):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            result = render_html_to_pdf(html_file, out_pdf, open_after=False)
            assert result == out_pdf.resolve()
            assert out_pdf.exists()
            assert out_pdf.stat().st_size > 0
