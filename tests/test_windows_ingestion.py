"""Unit tests for Windows ingestion fixes, PowerShell operator sanitization, and native launchers."""

import os
from pathlib import Path
from breadwinner.core.ingestor import (
    clean_user_input_path,
    parse_dropped_sources,
    normalize_source,
)
from breadwinner.ui.discovery import discover_all_ingredients


def test_powershell_call_operator_sanitization():
    """Verify that leading PowerShell call operator '&' and surrounding quotes are sanitized."""
    raw_single = "& 'C:\\Users\\Asus\\Documents\\Resume_UK\\Master CV.docx'"
    cleaned = clean_user_input_path(raw_single)
    assert cleaned == "C:\\Users\\Asus\\Documents\\Resume_UK\\Master CV.docx"
    assert not cleaned.startswith("&")
    assert not cleaned.startswith("'")
    assert not cleaned.endswith("'")


def test_parse_dropped_sources_windows_multi_path():
    """Verify that multiple space-separated quoted Windows paths preserve backslashes."""
    raw_multi = "& 'C:\\Users\\Asus\\Documents\\Resume_UK\\Master CV.docx' 'D:\\Data\\Portfolio.pdf'"
    sources = parse_dropped_sources(raw_multi)
    assert len(sources) == 2
    assert sources[0] == "C:\\Users\\Asus\\Documents\\Resume_UK\\Master CV.docx"
    assert sources[1] == "D:\\Data\\Portfolio.pdf"
    # Ensure backslashes were not stripped by posix shlex escaping
    assert "\\" in sources[0]
    assert "\\" in sources[1]


def test_normalize_source_windows_paths():
    """Verify that Windows drive letters and UNC paths are recognized as files or directories."""
    label, kind = normalize_source("C:\\Users\\Asus\\Documents\\Master CV.docx")
    assert label == "Master CV.docx"
    assert kind == "file"

    label2, kind2 = normalize_source("\\\\network_share\\resumes\\candidate.pdf")
    assert label2 == "candidate.pdf"
    assert kind2 == "file"


def test_discover_all_ingredients_missing_file_gate():
    """Verify that non-existent paths with file extensions or separators are flagged as MISSING FILE."""
    missing_windows_path = "C:\\Users\\Asus\\Documents\\Nonexistent_Master_CV.docx"
    missing_posix_path = "/nonexistent/path/to/my_resume.pdf"
    real_notes = "Experienced distributed systems engineer with 8 years building Kafka pipelines."

    ingredients = discover_all_ingredients([missing_windows_path, missing_posix_path, real_notes])

    assert len(ingredients) == 3

    # 1. Missing Windows file
    ing_win = next(i for i in ingredients if missing_windows_path in i.value)
    assert ing_win.category == "missing_file"
    assert ing_win.is_default is False
    assert "[MISSING FILE]" in ing_win.label
    assert "Could not locate file at:" in ing_win.label

    # 2. Missing POSIX file
    ing_posix = next(i for i in ingredients if missing_posix_path in i.value)
    assert ing_posix.category == "missing_file"
    assert ing_posix.is_default is False
    assert "[MISSING FILE]" in ing_posix.label

    # 3. Real personal notes
    ing_notes = next(i for i in ingredients if real_notes in i.value)
    assert ing_notes.category == "notes"
    assert ing_notes.is_default is True
    assert "[NOTES]" in ing_notes.label


def test_root_launchers_exist():
    """Verify root Windows launcher scripts exist and contain required commands."""
    repo_root = Path(__file__).parent.parent

    bat_file = repo_root / "breadwinner.bat"
    assert bat_file.exists()
    bat_content = bat_file.read_text(encoding="utf-8")
    assert "breadwinner.exe" in bat_content
    assert "install.ps1" in bat_content

    ps1_file = repo_root / "install.ps1"
    assert ps1_file.exists()
    ps1_content = ps1_file.read_text(encoding="utf-8")
    assert "install -e ." in ps1_content
    assert "breadwinner.bat" in ps1_content
