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



def test_bake_application_package_dual_pdf(tmp_path: Path):
    """Verify bake_application_package compiles dual PDFs (resume.pdf and cover_letter.pdf)."""
    from breadwinner.core.pdf import bake_application_package

    app_dir = tmp_path / "2026-10-13_DeepMind_Research"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "resume.html").write_text("<html><body>Resume</body></html>", encoding="utf-8")
    (app_dir / "cover_letter.md").write_text("Dear DeepMind,\n\nI am thrilled to apply for this role.", encoding="utf-8")

    resume_json_data = {
        "basics": {
            "name": "Demis Hassabis",
            "email": "demis@example.com"
        },
        "work": []
    }
    import json
    (app_dir / "resume.json").write_text(json.dumps(resume_json_data), encoding="utf-8")

    def fake_subprocess_run(cmd, **kwargs):
        # cmd contains --print-to-pdf=<path>
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                pdf_target = Path(arg.split("=", 1)[1])
                pdf_target.write_bytes(b"%PDF-1.4 Mock PDF bytes" * 100)
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock

    with patch("breadwinner.core.pdf.find_browser_executable", return_value="/fake/chrome"):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            res = bake_application_package(app_dir, open_after=False)

            assert res["success"] is True
            assert (app_dir / "resume.pdf").exists()
            assert (app_dir / "cover_letter.pdf").exists()
            assert (app_dir / "cover_letter.html").exists()
            assert res["size_kb"] > 0
            assert res["cover_letter_size_kb"] > 0
