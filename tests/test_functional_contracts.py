"""End-to-end functional contracts verifying core Breadwinner architectural invariants.

These contract tests enforce:
1. Ingestion and Normalization: Greenhouse, Ashby, and raw text normalize into JobPosting.
2. Metric Grounding / Anti-Hallucination: ProvenanceValidator verifies metrics from pantry profile.
3. StoryScope Anti-Slop: Rejection of banned buzzwords (spearheaded, testament, delve, pivotal).
4. Headless PDF Compilation: Real Jake's Resume HTML renders to valid PDF (> 1KB) without fake mocks.
5. Telemetry and Persistence: Atomic SQLite CRUD operations and bi-directional CSV synchronization.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from breadwinner.core.models import (
    CandidateProfile,
    JobPosting,
    TailoredApplication,
    MatchAnalysis,
    WorkExperience
)
from breadwinner.core.adapters.ashby import AshbyAdapter
from breadwinner.core.universal import UniversalJobIngestor
from breadwinner.core.scraper import JobScraper
from breadwinner.core.provenance import ProvenanceValidator
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.pdf import render_html_to_pdf, find_browser_executable, PDFGenerationError
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.db.sync import CsvSync


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def golden_profile() -> CandidateProfile:
    profile_path = FIXTURES_DIR / "golden_profile.json"
    return CandidateProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))


def test_contract_1_ingestion_and_normalization():
    """Contract 1: Greenhouse, Ashby, and raw text normalize into JobPosting."""
    # 1. Raw text ingestion
    raw_path = FIXTURES_DIR / "jobs" / "raw_sample.txt"
    raw_text = raw_path.read_text(encoding="utf-8")
    job_raw = JobScraper.ingest_from_text(
        raw_text,
        company="Apex Cloud Systems",
        title="Staff Distributed Systems Engineer"
    )
    assert isinstance(job_raw, JobPosting)
    assert job_raw.company == "Apex Cloud Systems"
    assert job_raw.title == "Staff Distributed Systems Engineer"
    assert any("go" in s.lower() for s in job_raw.extracted_skills)
    assert any("kafka" in s.lower() for s in job_raw.extracted_skills)

    # 2. Greenhouse HTML parsing
    gh_path = FIXTURES_DIR / "jobs" / "greenhouse_sample.html"
    gh_html = gh_path.read_text(encoding="utf-8")
    company, title, location, text = JobScraper.parse_html_job(
        "https://boards.greenhouse.io/apex-cloud/jobs/101",
        gh_html,
        "greenhouse"
    )
    job_gh = JobScraper.ingest_from_text(text, company=company, title=title)
    assert isinstance(job_gh, JobPosting)
    assert "apex" in job_gh.company.lower()
    assert "Staff Distributed Systems Engineer" in job_gh.title
    assert "10M events/day" in job_gh.cleaned_markdown

    # 3. Ashby Next.js hydration extraction
    ashby_path = FIXTURES_DIR / "jobs" / "ashby_sample.html"
    ashby_html = ashby_path.read_text(encoding="utf-8")
    adapter = AshbyAdapter()
    assert adapter.matches("https://jobs.ashbyhq.com/apex-cloud/101")

    mock_resp = MagicMock()
    mock_resp.text = ashby_html
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        ingested_result = adapter.extract("https://jobs.ashbyhq.com/apex-cloud/101")
        job_ashby = UniversalJobIngestor.to_job_posting(ingested_result)

    assert isinstance(job_ashby, JobPosting)
    assert job_ashby.title == "Staff Distributed Systems Engineer"
    assert "apex" in job_ashby.company.lower()
    assert any("custom_streaming_pipeline_challenge" in q.id or "streaming pipeline" in q.prompt.lower() for q in job_ashby.questions)


def test_contract_2_metric_grounding_and_anti_hallucination(golden_profile: CandidateProfile):
    """Contract 2: Verified metrics pass; unverified metrics are rejected."""
    job = JobPosting(
        id="apex-staff-de",
        company="Apex Cloud Systems",
        title="Staff Distributed Systems Engineer"
    )

    # 1. Clean tailored application using verified facts
    clean_app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=95),
        tailored_summary="Senior Distributed Systems Engineer delivering 99.999% uptime across streaming clusters.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=[
                    "Scaled Kafka event streaming platform handling 10M events/day with sub-10ms p99 latency.",
                    "Reduced cloud infrastructure costs by 45% through database optimization."
                ]
            )
        ]
    )
    clean_report = ProvenanceValidator.validate(clean_app, golden_profile)
    assert clean_report.is_valid is True
    assert len(clean_report.unverified_metrics) == 0
    assert len(clean_report.banned_words_found) == 0

    # 2. Hallucinated application inventing scale and revenue metrics
    hallucinated_app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=95),
        tailored_summary="Generated $5M revenue by optimizing caching layers.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=[
                    "Generated $5M revenue through distributed architecture.",
                    "Scaled platform throughput to 500k QPS across nodes."
                ]
            )
        ]
    )
    hallucinated_report = ProvenanceValidator.validate(hallucinated_app, golden_profile)
    assert hallucinated_report.is_valid is False
    assert len(hallucinated_report.unverified_metrics) >= 2
    assert any("5m" in m for m in hallucinated_report.unverified_metrics)
    assert any("500k" in m for m in hallucinated_report.unverified_metrics)


def test_contract_3_storyscope_anti_slop_lint(golden_profile: CandidateProfile):
    """Contract 3: StoryScope rejects banned buzzwords."""
    job = JobPosting(
        id="apex-staff-de",
        company="Apex Cloud Systems",
        title="Staff Distributed Systems Engineer"
    )
    slop_app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=90),
        tailored_summary="Spearheaded critical initiatives as a testament to engineering excellence.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=[
                    "Delve into core distributed consensus algorithms playing a pivotal role in latency reductions."
                ]
            )
        ]
    )
    slop_report = ProvenanceValidator.validate(slop_app, golden_profile)
    assert slop_report.is_valid is False
    assert "spearheaded" in slop_report.banned_words_found
    assert "testament" in slop_report.banned_words_found
    assert "delve" in slop_report.banned_words_found
    assert "pivotal" in slop_report.banned_words_found


def test_contract_4_headless_pdf_compilation(golden_profile: CandidateProfile, tmp_path: Path):
    """Contract 4: Real Jake's Resume HTML renders to valid PDF (> 1KB) without fake mocks."""
    job = JobPosting(
        id="apex-staff-de",
        company="Apex Cloud Systems",
        title="Staff Distributed Systems Engineer"
    )
    app = TailoredApplication(
        job=job,
        persona="tech_ai",
        match_analysis=MatchAnalysis(match_score=95),
        tailored_summary=golden_profile.summary,
        tailored_experiences=golden_profile.experiences,
        tailored_projects=golden_profile.projects,
        tailored_skills=golden_profile.skills
    )

    renderer = TemplateRenderer()
    html_content = renderer.render_resume(golden_profile, app, template_name="jakes")
    assert "Alex Taylor" in html_content
    assert "Apex Cloud Systems" in html_content

    html_path = tmp_path / "resume.html"
    pdf_path = tmp_path / "resume.pdf"
    html_path.write_text(html_content, encoding="utf-8")

    browser = find_browser_executable()
    if not browser:
        pytest.skip("No chromium browser available in this environment")

    try:
        output_pdf = render_html_to_pdf(html_path, pdf_path, open_after=False)
    except PDFGenerationError as e:
        if "Permission denied" in str(e) or "MachPort" in str(e) or "bootstrap_check_in" in str(e):
            pytest.skip(f"Browser execution restricted by environment sandbox: {e}")
        raise
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1024
    assert output_pdf.read_bytes().startswith(b"%PDF")



def test_contract_5_telemetry_and_persistence(tmp_path: Path):
    """Contract 5: Atomic SQLite CRUD and bi-directional CSV synchronization."""
    db_file = tmp_path / "tracker.db"
    csv_file = tmp_path / "tracker.csv"
    repo = JobRepository(db_file)

    # 1. Insert initial job record
    record = JobRecord(
        id="apex-cloud-staff-de",
        company="Apex Cloud Systems",
        title="Staff Distributed Systems Engineer",
        url="https://example.com/jobs/apex-101",
        status="target",
        match_score=94,
        date_added="2026-10-15"
    )
    repo.upsert_job(record)

    fetched = repo.get_job("apex-cloud-staff-de")
    assert fetched is not None
    assert fetched.company == "Apex Cloud Systems"
    assert fetched.title == "Staff Distributed Systems Engineer"
    assert fetched.match_score == 94
    assert fetched.status == "target"

    # 2. Update status and notes
    repo.update_status("apex-cloud-staff-de", "applied", notes="Applied via referral")
    updated = repo.get_job("apex-cloud-staff-de")
    assert updated is not None
    assert updated.status == "applied"
    assert updated.notes == "Applied via referral"
    assert updated.date_applied is not None

    # 3. Export to CSV
    exported_count = CsvSync.export_to_csv(repo, csv_file)
    assert exported_count == 1
    assert csv_file.exists()
    assert "Apex Cloud Systems" in csv_file.read_text(encoding="utf-8")

    # 4. Round-trip import into clean database
    new_db_file = tmp_path / "tracker_restored.db"
    new_repo = JobRepository(new_db_file)
    imported_count = CsvSync.import_from_csv(new_repo, csv_file)
    assert imported_count == 1
    restored_record = new_repo.get_job("apex-cloud-staff-de")
    assert restored_record is not None
    assert restored_record.company == "Apex Cloud Systems"
    assert restored_record.status == "applied"
