"""Tests for JobContract model, serialization, and disk persistence."""

import json
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from breadwinner.core.models import (
    JobPosting,
    ApplicationQuestion,
    QuestionType,
    CandidateProfile,
    WorkExperience,
)
from breadwinner.core.contract import (
    JobContract,
    ContractMetadata,
    ResumeDeliverable,
    CoverLetterDeliverable,
    PortfolioDeliverable,
    PortalQuestion,
    ContractDeliverables,
    KnockoutRules,
    EvaluationCriteria,
    generate_portal_answers_markdown,
    save_application_contract_bundle,
)
from breadwinner.cli import main
from breadwinner.config import settings


def test_job_contract_schema_serialization(tmp_path: Path):
    """Verify JobContract serializes with $schema alias and can be loaded back."""
    contract = JobContract(
        metadata=ContractMetadata(
            company="Apex Cloud Systems",
            role="Staff Distributed Systems Architect",
            portal_type="workday",
            source_url="https://apex.example.com/jobs/123",
            seniority_level="senior",
            page_budget=2,
            date_ingested="2026-10-22T12:00:00Z"
        ),
        deliverables=ContractDeliverables(
            resume=ResumeDeliverable(required=True, template="executive", target_pages=2),
            cover_letter=CoverLetterDeliverable(status="optional", max_words=200, required_hooks=["raft", "kafka"]),
            portfolio_dossier=PortfolioDeliverable(required=False),
            portal_questions=[
                PortalQuestion(id="q1", prompt="Are you authorized to work?", type="boolean", required=True)
            ]
        ),
        evaluation_criteria=EvaluationCriteria(
            core_domains=["Distributed Systems", "Cloud Infrastructure"],
            essential_keywords=["go", "python", "kafka", "redis"],
            preferred_keywords=["kubernetes", "terraform"],
            knockout_rules=KnockoutRules(min_experience_years=5, immediate_visa_sponsorship_needed=False)
        )
    )

    contract_file = tmp_path / "job.json"
    contract.save(contract_file)

    assert contract_file.exists()
    raw_dict = json.loads(contract_file.read_text(encoding="utf-8"))
    assert "$schema" in raw_dict
    assert raw_dict["$schema"] == "https://breadwinner.tools/schemas/job_contract.v1.json"
    assert raw_dict["metadata"]["company"] == "Apex Cloud Systems"

    # Load back
    loaded = JobContract.load(contract_file)
    assert loaded.metadata.role == "Staff Distributed Systems Architect"
    assert loaded.evaluation_criteria.knockout_rules.min_experience_years == 5
    assert len(loaded.deliverables.portal_questions) == 1


def test_create_contract_from_job_senior_inference():
    """Verify factory accurately infers senior page budget and clusters domains."""
    job = JobPosting(
        id="job_senior_1",
        company="Global Enterprise",
        title="Senior Machine Learning & LLM Systems Engineer",
        raw_text="Requires 6+ years of experience in distributed systems, PyTorch, LLM fine-tuning, and Kafka microservices.",
        cleaned_markdown="## Responsibilities\nScale LLM inference serving using vLLM and PyTorch.",
        extracted_skills=["Python", "PyTorch", "LLM", "Kafka", "Distributed Systems"],
        extracted_requirements=["6+ years of experience building high-throughput systems"],
        questions=[
            ApplicationQuestion(id="q_auth", prompt="Are you legally authorized to work?", required=True, question_type=QuestionType.TEXT)
        ]
    )

    contract = JobContract.create_contract_from_job(job)

    assert contract.metadata.seniority_level == "senior"
    assert contract.metadata.page_budget == 2
    assert contract.deliverables.resume.target_pages == 2
    assert contract.deliverables.resume.template == "executive"
    assert contract.evaluation_criteria.knockout_rules.min_experience_years == 6
    assert any("Large Language Models" in d for d in contract.evaluation_criteria.core_domains)
    assert "pytorch" in contract.evaluation_criteria.essential_keywords


def test_create_contract_from_job_early_career_inference():
    """Verify factory infers 1-page budget for junior or intern roles."""
    job = JobPosting(
        id="job_junior_1",
        company="Startup Co",
        title="Junior Software Engineer (Graduate)",
        raw_text="Seeking a recent graduate with passion for Python and React.",
        extracted_skills=["Python", "React", "Git"]
    )

    contract = JobContract.create_contract_from_job(job)

    assert contract.metadata.seniority_level == "early"
    assert contract.metadata.page_budget == 1
    assert contract.deliverables.resume.target_pages == 1
    assert contract.deliverables.resume.template == "compact_1page"


def test_generate_portal_answers_markdown():
    """Verify portal_answers.md output formatting."""
    contract = JobContract(
        metadata=ContractMetadata(
            company="Acme Corp",
            role="AI Lead",
            portal_type="greenhouse",
            seniority_level="senior",
            page_budget=2,
            date_ingested="2026-10-22T00:00:00Z"
        ),
        deliverables=ContractDeliverables(
            portal_questions=[
                PortalQuestion(id="q1", prompt="Will you require sponsorship?", type="boolean", required=True)
            ]
        ),
        evaluation_criteria=EvaluationCriteria(
            essential_keywords=["python", "pytorch", "fastapi"]
        )
    )

    md = generate_portal_answers_markdown(contract)
    assert "# Application Logistics & Screening Answers" in md
    assert "**Target Company:** Acme Corp"
    assert "**Legally Authorized to Work:** Yes"
    assert "`python`" in md
    assert "Will you require sponsorship?" in md


def test_save_application_contract_bundle(tmp_path: Path):
    """Verify bundle writes all 3 required files atomically."""
    contract = JobContract(
        metadata=ContractMetadata(
            company="Test Company",
            role="Backend Engineer",
            date_ingested="2026-10-22T00:00:00Z"
        )
    )

    bundle = save_application_contract_bundle(
        folder_path=tmp_path,
        contract=contract,
        raw_job_text="Backend Engineer at Test Company. Must know Python and SQL."
    )

    assert bundle["job_description"].exists()
    assert bundle["job_contract"].exists()
    assert bundle["portal_answers"].exists()

    assert "Backend Engineer" in bundle["job_description"].read_text(encoding="utf-8")
    assert bundle["job_contract"].name == "job.json"
    assert bundle["portal_answers"].name == "portal_answers.md"


def test_cli_apply_persists_contract_bundle(tmp_path: Path, monkeypatch):
    """Verify 'breadwinner apply' writes job_description.txt, job.json, and portal_answers.md."""
    # Isolate storage paths
    test_apps = tmp_path / "apps"
    test_pantry = tmp_path / "pantry"
    test_db = tmp_path / "data" / "tracker.db"
    test_apps.mkdir(parents=True)
    test_pantry.mkdir(parents=True)
    test_db.parent.mkdir(parents=True)

    monkeypatch.setattr(settings, "applications_dir", test_apps)
    monkeypatch.setattr(settings, "pantry_dir", test_pantry)
    monkeypatch.setattr(settings, "database_path", test_db)
    monkeypatch.setattr(settings, "auto_generate_pdf", False)

    from breadwinner.core.pantry import PantryManager
    pantry = PantryManager(test_pantry)
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Distributed Systems Architect",
        summary="Distributed systems engineer.",
        experiences=[
            WorkExperience(
                company="Apex Cloud",
                role="Senior Engineer",
                start_date="2020",
                bullets=["Engineered distributed caching layer scaling to 10M events/day."]
            )
        ]
    )
    pantry.save_pantry(profile)

    job_text_file = tmp_path / "job.txt"
    job_text_file.write_text(
        "Job Title: Senior Systems Engineer\nCompany: TargetCo\nDescription: Build high scale systems in Go.",
        encoding="utf-8"
    )

    mock_tailored = MagicMock()
    mock_tailored.match_analysis.match_score = 88
    mock_tailored.match_analysis.matched_skills = ["Go", "Distributed Systems"]
    mock_tailored.match_analysis.missing_skills = []
    mock_tailored.cover_letter = "Cover letter text"
    mock_tailored.portal_answers = {}

    runner = CliRunner()
    with patch("breadwinner.cli.JobScraper.ingest_from_text") as mock_ingest, \
         patch("breadwinner.cli.TailoringEngine.analyze_and_tailor", return_value=mock_tailored):

        mock_job = JobPosting(
            id="test_job_1",
            company="TargetCo",
            title="Senior Systems Engineer",
            raw_text="Raw job posting text for TargetCo Senior Systems Engineer.",
            cleaned_markdown="Clean markdown description"
        )
        mock_ingest.return_value = mock_job

        result = runner.invoke(main, [
            "apply",
            str(job_text_file),
            "--company", "TargetCo",
            "--title", "Senior Systems Engineer",
            "--no-strategy",
            "--persona", "none"
        ])

        assert result.exit_code == 0
        created_dirs = list(test_apps.glob("*TargetCo*"))
        assert len(created_dirs) == 1
        app_dir = created_dirs[0]

        # Verify all persistent contract artifacts exist
        assert (app_dir / "job_description.txt").exists(), "job_description.txt missing!"
        assert (app_dir / "job.json").exists(), "job.json missing!"
        assert (app_dir / "portal_answers.md").exists(), "portal_answers.md missing!"
        assert (app_dir / "resume.html").exists()
        assert (app_dir / "resume.md").exists()
        assert (app_dir / "resume.json").exists()

        # Verify job.json is a valid JobContract
        contract = JobContract.load(app_dir / "job.json")
        assert contract.metadata.company == "TargetCo"
        assert contract.metadata.role == "Senior Systems Engineer"
