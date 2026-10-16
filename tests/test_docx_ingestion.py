"""Tests for pure-Python zero-dependency docx ingestion."""

import io
from pathlib import Path
import zipfile

import pytest

from breadwinner.core.ingestor import UniversalIngestor, IngestionError


def _create_sample_docx(path: Path, paragraphs: list[str]) -> Path:
    """Helper to synthesize a minimal valid .docx file in-memory and write to disk."""
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        '<w:body>',
    ]
    for p in paragraphs:
        xml_parts.append('<w:p><w:r><w:t>')
        xml_parts.append(p)
        xml_parts.append('</w:t></w:r></w:p>')
    xml_parts.append('</w:body></w:document>')
    doc_xml = "".join(xml_parts)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))

    path.write_bytes(buf.getvalue())
    return path


def test_extract_text_from_docx_valid(tmp_path: Path):
    docx_file = tmp_path / "resume.docx"
    paragraphs = [
        "Alex Taylor",
        "Staff Systems Engineer with 8+ years experience scaling distributed infrastructure.",
        "Architected Go microservices handling 50k QPS with sub-10ms p99 latency.",
    ]
    _create_sample_docx(docx_file, paragraphs)

    extracted = UniversalIngestor.extract_text_from_docx(docx_file)
    assert "Alex Taylor" in extracted
    assert "50k QPS" in extracted
    assert "sub-10ms p99 latency" in extracted

    # Test routing through extract_text_from_file
    from_file = UniversalIngestor.extract_text_from_file(docx_file)
    assert from_file == extracted


def test_extract_text_from_docx_with_line_breaks(tmp_path: Path):
    docx_file = tmp_path / "breaks.docx"
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:r><w:t>Line One</w:t><w:br/><w:t>Line Two</w:t></w:r></w:p>'
        '</w:body></w:document>'
    )
    with zipfile.ZipFile(docx_file, "w") as zf:
        zf.writestr("word/document.xml", doc_xml.encode("utf-8"))

    extracted = UniversalIngestor.extract_text_from_docx(docx_file)
    assert "Line One\nLine Two" in extracted


def test_extract_text_from_docx_missing_file():
    with pytest.raises(FileNotFoundError):
        UniversalIngestor.extract_text_from_docx(Path("/nonexistent/file.docx"))


def test_extract_text_from_docx_bad_zip(tmp_path: Path):
    bad_file = tmp_path / "corrupt.docx"
    bad_file.write_bytes(b"Not a zip file at all")
    with pytest.raises(IngestionError, match="corrupted .docx archive"):
        UniversalIngestor.extract_text_from_docx(bad_file)


def test_extract_text_from_docx_missing_document_xml(tmp_path: Path):
    empty_zip = tmp_path / "empty.docx"
    with zipfile.ZipFile(empty_zip, "w") as zf:
        zf.writestr("other.xml", "<root></root>")

    with pytest.raises(IngestionError, match="word/document.xml"):
        UniversalIngestor.extract_text_from_docx(empty_zip)
