"""Unit and integration tests for Job Strategy Loop and Dynamic Persona Synthesis."""

from pathlib import Path
import pytest
from click.testing import CliRunner

from breadwinner.core.models import JobPosting, CandidateProfile, WorkExperience, Education, Project, SkillCategory
from breadwinner.core.persona import (
    Persona,
    PersonaManager,
    generate_job_strategy_questions,
    synthesize_job_directives,
    synthesize_job_persona,
)
from breadwinner.core.tailor import TailoringEngine
from breadwinner.providers.factory import MockLLMProvider
from breadwinner.cli import main


@pytest.fixture
def sample_job():
    return JobPosting(
        id="job_test_123",
        company="Stripe",
        title="Staff Backend Engineer",
        url="https://stripe.com/jobs/123",
        location="Remote, US",
        portal_type="greenhouse",
        raw_text="Looking for a Staff Backend Engineer to scale real-time payment rails handling 100k events/sec in Go and Kafka."
    )


@pytest.fixture
def sample_profile():
    return CandidateProfile(
        full_name="Alex River",
        title="Senior Software Engineer",
        email="alex@example.com",
        summary="Distributed systems engineer specializing in low latency systems.",
        experiences=[
            WorkExperience(
                company="FinTech Ltd",
                role="Senior Systems Engineer",
                start_date="2021",
                end_date="Present",
                bullets=["Built real-time ledger processing 50M daily transactions with 99.999% uptime."]
            )
        ],
        education=[
            Education(
                institution="MIT",
                degree="B.S. Computer Science"
            )
        ],
        projects=[
            Project(
                name="RaftKV",
                description="Distributed consensus key-value store in Go",
                tech_stack=["Go", "Raft"]
            )
        ],
        skills=[
            SkillCategory(
                category="Languages",
                skills=["Go", "Python", "SQL"]
            )
        ]
    )


def test_generate_job_strategy_questions_fallback(sample_job):
    questions = generate_job_strategy_questions(sample_job, provider=None)
    assert len(questions) == 3
    assert any("Stripe" in q["question"] for q in questions)
    assert any("Staff Backend Engineer" in q["question"] for q in questions)
    assert questions[0]["id"] == "hook"
    assert questions[1]["id"] == "proof"
    assert questions[2]["id"] == "tactics"


def test_generate_job_strategy_questions_mock_provider(sample_job):
    mock = MockLLMProvider()
    questions = generate_job_strategy_questions(sample_job, provider=mock)
    assert len(questions) >= 2
    assert "id" in questions[0]
    assert "question" in questions[0]


def test_synthesize_job_directives_fallback(sample_job):
    answers = {
        "hook": "Longtime admirer of Stripe's API reliability and documentation.",
        "proof": "Engineered Raft consensus store achieving sub-5ms latency across 5 nodes.",
        "tactics": "Downplay web frontend; position strictly as core infrastructure lead."
    }
    directives = synthesize_job_directives(sample_job, answers, provider=None)
    assert "STRATEGIC HOOK" in directives
    assert "CORE PROOF POINT" in directives
    assert "TACTICAL FRAMING" in directives
    assert "Stripe" in directives
    assert "Raft consensus" in directives


def test_synthesize_job_directives_provider(sample_job):
    mock = MockLLMProvider()
    answers = {
        "hook": "Admire payments architecture.",
        "proof": "Scaled 1M QPS queue.",
        "tactics": "Systems focus."
    }
    directives = synthesize_job_directives(sample_job, answers, provider=mock)
    assert "- STRATEGIC HOOK" in directives or "- CORE PROOF POINT" in directives


def test_generate_job_strategy_questions_with_profile_and_persona(sample_job, sample_profile):
    persona = Persona(
        name="UK Systems Lead",
        slug="uk_systems_lead",
        description="UK Stance",
        tone="Authoritative",
        system_directives="Directives",
        cover_letter_directives="CL Directives",
        market="UK/EU",
        logistics={"visa": "UK Citizen / No sponsorship needed"}
    )
    questions = generate_job_strategy_questions(
        job=sample_job,
        profile=sample_profile,
        persona=persona,
        provider=None,
        personal_context="Must be remote or London hybrid."
    )
    assert len(questions) == 3
    # Top project RaftKV should be referenced in proof question
    assert any("RaftKV" in q["question"] for q in questions)
    assert any("Stripe" in q["question"] for q in questions)


def test_synthesize_job_directives_with_application_class(sample_job, sample_profile):
    persona = Persona(
        name="UK Systems Lead",
        slug="uk_systems_lead",
        description="UK Stance",
        tone="Authoritative",
        system_directives="Directives",
        cover_letter_directives="CL Directives",
        market="UK/EU",
        logistics={"visa": "Right-to-Work verified"}
    )
    answers = {
        "hook": "Passionate about financial rails reliability.",
        "proof": "RaftKV store achieves 5ms latency.",
        "tactics": "Bridge Go and Kafka experience."
    }
    directives = synthesize_job_directives(
        job=sample_job,
        answers=answers,
        profile=sample_profile,
        persona=persona,
        provider=None
    )
    assert "MARKET STANCE (UK/EU)" in directives
    assert "LOGISTICAL BOUNDS" in directives
    assert "Right-to-Work" in directives


def test_synthesize_and_save_new_persona(tmp_path, sample_job):
    mock = MockLLMProvider()
    answers = {
        "hook": "Mission alignment with distributed ledger scale.",
        "proof": "RaftKV store and payment rails experience.",
        "tactics": "Highlight reliability."
    }
    base = PersonaManager.load_persona("tech_ai")
    new_persona = synthesize_job_persona(
        name="Stripe Systems Architect",
        slug="stripe_systems_architect",
        job=sample_job,
        answers=answers,
        base_persona=base,
        provider=mock
    )

    assert new_persona.name == "Stripe Systems Architect"
    assert new_persona.slug == "stripe_systems_architect"

    # Save to custom test dir
    saved_file = PersonaManager.save_persona(new_persona, custom_dir=tmp_path)
    assert saved_file.exists()

    # Load back
    loaded = PersonaManager.load_persona("stripe_systems_architect", custom_dir=tmp_path)
    assert loaded.name == new_persona.name
    assert loaded.slug == "stripe_systems_architect"

    # Delete
    deleted = PersonaManager.delete_persona("stripe_systems_architect", custom_dir=tmp_path)
    assert deleted is True
    assert not saved_file.exists()


def test_tailoring_engine_with_job_directives(sample_profile, sample_job):
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)
    persona = PersonaManager.load_persona("tech_ai")

    directives = "- STRATEGIC HOOK: Lead with low-latency Go systems."
    app = engine.analyze_and_tailor(
        profile=sample_profile,
        job=sample_job,
        persona=persona,
        job_directives=directives
    )

    assert app.match_analysis.match_score >= 80
    assert len(app.tailored_experiences) > 0
    assert app.cover_letter != ""


def test_cli_personas_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(PersonaManager, "get_user_dir", classmethod(lambda cls: tmp_path))
    runner = CliRunner()

    # 1. List personas
    res_list = runner.invoke(main, ["personas", "list"])
    assert res_list.exit_code == 0
    assert "tech_ai" in res_list.output

    # 2. View built-in persona
    res_view = runner.invoke(main, ["personas", "view", "tech_ai"])
    assert res_view.exit_code == 0
    assert "Tech & AI Engineer" in res_view.output

    # 3. Create custom persona
    res_create = runner.invoke(
        main,
        ["personas", "create", "-n", "Fintech Quant", "-s", "fintech_quant", "-d", "For quantitative trading roles", "-t", "Precise"],
        input="\n\n"
    )
    assert res_create.exit_code == 0
    assert "Created and saved persona 'fintech_quant'" in res_create.output

    # 4. View newly created persona
    res_view_custom = runner.invoke(main, ["personas", "view", "fintech_quant"])
    assert res_view_custom.exit_code == 0
    assert "Fintech Quant" in res_view_custom.output

    # 5. Delete custom persona
    res_del = runner.invoke(main, ["personas", "delete", "fintech_quant"])
    assert res_del.exit_code == 0
    assert "deleted from user_personas" in res_del.output


def test_cli_apply_no_strategy(tmp_path, monkeypatch):
    # Set up temp profile and applications dir
    app_dir = tmp_path / "apps"
    app_dir.mkdir()
    monkeypatch.setattr("breadwinner.config.settings.applications_dir", app_dir)
    monkeypatch.setattr("breadwinner.config.settings.database_path", tmp_path / "test.db")
    monkeypatch.setattr("breadwinner.config.settings.portfolio_path", tmp_path / "pantry")
    monkeypatch.setattr("breadwinner.config.settings.auto_generate_pdf", False)

    # Write a test job file
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("We need Go and Kubernetes experts.")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "apply",
            str(jd_file),
            "-c", "AcmeCorp",
            "-t", "Platform Engineer",
            "-p", "tech_ai",
            "--provider", "mock",
            "--no-strategy"
        ]
    )

    assert result.exit_code == 0
    assert "Target Role Ingested" in result.output
    assert "Platform Engineer" in result.output
    assert "AcmeCorp" in result.output


def test_cli_apply_with_strategy_loop(tmp_path, monkeypatch):
    app_dir = tmp_path / "apps"
    app_dir.mkdir()
    monkeypatch.setattr("breadwinner.config.settings.applications_dir", app_dir)
    monkeypatch.setattr("breadwinner.config.settings.database_path", tmp_path / "test.db")
    monkeypatch.setattr("breadwinner.config.settings.portfolio_path", tmp_path / "pantry")
    monkeypatch.setattr("breadwinner.config.settings.auto_generate_pdf", False)
    monkeypatch.setattr(PersonaManager, "get_user_dir", classmethod(lambda cls: tmp_path / "user_personas"))

    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("We need Go and Kubernetes experts.")

    runner = CliRunner()
    inputs = "Passionate about scaling\nLed raft cluster\nFocus on infra\ny\nAcme Platform Lead\nacme_platform_lead\n"

    result = runner.invoke(
        main,
        [
            "apply",
            str(jd_file),
            "-c", "AcmeCorp",
            "-t", "Platform Engineer",
            "--strategy",
            "--provider", "mock"
        ],
        input=inputs
    )

    assert result.exit_code == 0
    assert "Target Strategy Discovery Loop" in result.output
    assert "Synthesized Job Directives" in result.output
    assert "Saved persona 'acme_platform_lead'" in result.output
    assert (tmp_path / "user_personas" / "acme_platform_lead.yaml").exists()

