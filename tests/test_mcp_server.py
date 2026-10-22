"""Unit tests for the Breadwinner FastMCP Server and 8 core tools."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from breadwinner.mcp.server import (
    mcp,
    breadwinner_ingest_job,
    breadwinner_audit,
    breadwinner_track_job,
    breadwinner_profile,
    breadwinner_dossier,
    breadwinner_personas,
    breadwinner_tailor
)
from breadwinner.core.pantry import PantryManager
from breadwinner.core.models import CandidateProfile, WorkExperience, Education
from breadwinner.core.contract import JobContract, ContractMetadata, EvaluationCriteria
from breadwinner.cli import main


def test_mcp_server_tools_registered():
    """Verify that all 8 required tools are registered in the FastMCP instance."""
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    tool_names = [t.name for t in tools]
    expected_tools = [
        "breadwinner_ingest_job",
        "breadwinner_audit",
        "breadwinner_tailor",
        "breadwinner_bake_pdf",
        "breadwinner_track_job",
        "breadwinner_profile",
        "breadwinner_dossier",
        "breadwinner_personas"
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Expected tool '{exp}' not found in registered MCP tools."


def test_breadwinner_ingest_job_tool(tmp_path: Path):
    """Verify breadwinner_ingest_job creates contract, description, and portal answers."""
    target_dir = tmp_path / "apps" / "datadog"
    jd_payload = """
    # Staff Distributed Systems Engineer - Datadog
    We are looking for an engineer to architect high-throughput Kafka streaming pipelines,
    optimize distributed stateful microservices in Go, and lead cloud infrastructure reliability.
    """

    result = breadwinner_ingest_job(
        target_folder=str(target_dir),
        source_type="text",
        payload=jd_payload,
        company="Datadog",
        title="Staff Distributed Systems Engineer"
    )

    assert result["metadata"]["company"] == "Datadog"
    assert result["metadata"]["role"] == "Staff Distributed Systems Engineer"

    assert (target_dir / "job.json").exists()
    assert (target_dir / "job_description.txt").exists()
    assert (target_dir / "portal_answers.md").exists()


def test_breadwinner_audit_tool(tmp_path: Path):
    """Verify breadwinner_audit performs deterministic 6-pillar analysis."""
    app_dir = tmp_path / "apps" / "monzo"
    app_dir.mkdir(parents=True)

    contract = JobContract(
        metadata=ContractMetadata(company="Monzo", role="Distributed Systems Engineer"),
        evaluation_criteria=EvaluationCriteria(
            core_domains=["Distributed Systems", "Kafka", "Go"],
            essential_keywords=["kafka", "latency"]
        )
    )
    contract_path = app_dir / "job.json"
    contract_path.write_text(contract.to_json(), encoding="utf-8")

    resume_text = """
    # Alex Taylor
    ### Distributed Systems Engineer

    **Professional Summary**
    Distributed Systems Engineer specializing in event-driven streaming and high-availability systems.

    **Work Experience**
    **Apex Cloud Systems** | Senior Distributed Systems Engineer
    - Architected distributed event streaming platform in Go processing 10M events/day.
    - Optimized Kafka clusters achieving sub-10ms latency across regional nodes.
    """
    resume_path = app_dir / "resume.md"
    resume_path.write_text(resume_text, encoding="utf-8")

    report = breadwinner_audit(
        resume_path=str(resume_path),
        contract_path=str(contract_path)
    )

    assert report["provenance_gate"]["status"] == "PASS"
    assert report["ats_alignment"]["domain_recall_score"] == 100
    assert report["quality_metrics"]["total_achievement_bullets"] == 2
    assert report["quality_metrics"]["xyz_compliant_bullets"] == 2


def test_breadwinner_track_job_tool(tmp_path: Path, monkeypatch):
    """Verify breadwinner_track_job persists into SQLite and syncs CSV."""
    db_file = tmp_path / "tracker.db"
    csv_file = tmp_path / "job_tracker.csv"

    from breadwinner.config import settings
    monkeypatch.setattr(settings, "database_path", db_file)
    monkeypatch.setattr(settings, "csv_tracker_path", csv_file)

    app_dir = tmp_path / "apps" / "stripe"
    app_dir.mkdir(parents=True)
    c_path = app_dir / "job.json"
    c_path.write_text("{}", encoding="utf-8")

    record = breadwinner_track_job(
        company="Stripe",
        title="Infrastructure Engineer",
        folder_path=str(app_dir),
        contract_path=str(c_path),
        status="applied",
        ats_score=94,
        xyz_score=88,
        notes="Applied via referral."
    )

    assert record["company"] == "Stripe"
    assert record["status"] == "applied"
    assert record["date_applied"] is not None
    assert record["ats_score"] == 94

    assert db_file.exists()
    assert csv_file.exists()


def test_breadwinner_profile_and_dossier_tools(tmp_path: Path, monkeypatch):
    """Verify breadwinner_profile get/patch operations and dossier lifecycle."""
    pantry_dir = tmp_path / "pantry"
    from breadwinner.config import settings
    monkeypatch.setattr(settings, "pantry_dir", pantry_dir)

    pm = PantryManager(pantry_dir)
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Systems Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud",
                role="Senior Systems Engineer",
                bullets=["Engineered distributed storage platform."]
            )
        ]
    )
    pm.save_pantry(profile)

    # 1. Get profile
    p_data = breadwinner_profile(action="get", section="all")
    assert p_data["full_name"] == "Alex Taylor"

    # 2. Patch basics
    patch_res = breadwinner_profile(
        action="patch",
        section="basics",
        payload={"title": "Principal Distributed Systems Engineer"}
    )
    assert patch_res["status"] == "SUCCESS"
    assert patch_res["snapshot_id"] is not None

    # Check updated profile
    updated_profile = pm.load_profile()
    assert updated_profile.title == "Principal Distributed Systems Engineer"

    # 3. Dossier tools
    save_dossier_res = breadwinner_dossier(
        action="save",
        rel_path="architectures/consensus_engine.md",
        content="# Consensus Engine Architecture\nDetails on Raft consensus."
    )
    assert save_dossier_res["status"] == "SUCCESS"

    list_res = breadwinner_dossier(action="list")
    assert "architectures/consensus_engine.md" in list_res["dossiers"]

    get_res = breadwinner_dossier(action="get", rel_path="architectures/consensus_engine.md")
    assert "Raft consensus" in get_res["content"]


def test_breadwinner_personas_tool(tmp_path: Path, monkeypatch):
    """Verify breadwinner_personas tool list, get, and set actions."""
    user_personas_dir = tmp_path / "personas"
    user_personas_dir.mkdir(parents=True)
    from breadwinner.config import settings
    monkeypatch.setattr(settings, "user_personas_dir", user_personas_dir)

    # List personas
    list_res = breadwinner_personas(action="list")
    assert isinstance(list_res["personas"], list)

    # Set custom persona
    custom_p = {
        "name": "Fintech Distributed Systems Lead",
        "slug": "fintech_lead",
        "description": "High-throughput financial ledger architect",
        "tone": "Quantitative, latency-focused",
        "system_directives": "Preserve hard financial throughput metrics.",
        "cover_letter_directives": "Highlight low latency and compliance.",
        "market": "London",
        "archetype": "Lead",
        "banned_words": ["synergy"]
    }
    set_res = breadwinner_personas(action="set", slug="fintech_lead", persona_data=custom_p)
    assert set_res["status"] == "SUCCESS"

    # Get custom persona
    get_res = breadwinner_personas(action="get", slug="fintech_lead")
    assert get_res["name"] == "Fintech Distributed Systems Lead"
    assert get_res["slug"] == "fintech_lead"


def test_breadwinner_tailor_tool(tmp_path: Path, monkeypatch):
    """Verify breadwinner_tailor generates resume.md, resume.html, and cover_letter.md."""
    pantry_dir = tmp_path / "pantry"
    from breadwinner.config import settings
    monkeypatch.setattr(settings, "pantry_dir", pantry_dir)

    pm = PantryManager(pantry_dir)
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Distributed Systems Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud",
                role="Distributed Systems Engineer",
                bullets=["Engineered event streaming platform in Go processing 10M events/day."]
            )
        ]
    )
    pm.save_pantry(profile)

    app_dir = tmp_path / "apps" / "uber"
    app_dir.mkdir(parents=True)
    contract = JobContract(
        metadata=ContractMetadata(company="Uber", role="Staff Software Engineer"),
        evaluation_criteria=EvaluationCriteria(core_domains=["Distributed Systems", "Go"])
    )
    c_path = app_dir / "job.json"
    c_path.write_text(contract.to_json(), encoding="utf-8")

    tailor_res = breadwinner_tailor(
        contract_path=str(c_path),
        target_folder=str(app_dir),
        template="jakes"
    )

    assert tailor_res["status"] == "SUCCESS"
    assert (app_dir / "resume.md").exists()
    assert (app_dir / "resume.html").exists()
    assert (app_dir / "cover_letter.md").exists()


def test_cli_mcp_command_help():
    """Verify breadwinner mcp --help exposes CLI options."""
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "FastMCP server" in result.output
    assert "--transport" in result.output
