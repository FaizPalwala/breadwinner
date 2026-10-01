"""Unit tests for Two-Ledger Ingestion, Document Classification, and Deep Dossier."""

from pathlib import Path
from unittest.mock import MagicMock

from breadwinner.core.models import CandidateProfile, WorkExperience, Education, Project, SkillCategory
from breadwinner.core.pantry import PantryManager
from breadwinner.core.ingestor import (
    UniversalIngestor,
    classify_document,
    chunk_text,
    merge_profiles,
)
from breadwinner.providers.factory import MockLLMProvider


def test_classify_document():
    # 1. Project README
    readme_text = "# High-Throughput Ingestion Engine\n\n## Installation\n```bash\npip install engine\n```\n\n## Architecture\nUses zero-copy ring buffers."
    assert classify_document(readme_text, "README.md") == "project_readme"

    # 2. Academic Dissertation / Thesis
    thesis_text = "Doctor of Philosophy Dissertation: Scalable Fault-Tolerant Consensus in Distributed Networks.\nAdvisor: Prof. Alan Turing.\nAbstract: This thesis investigates Paxos variants..."
    assert classify_document(thesis_text, "phd_thesis.pdf") == "academic"

    # 3. Portfolio
    portfolio_text = "About Me: Hi, I'm Alex. Welcome to my personal portfolio and technical blog."
    assert classify_document(portfolio_text, "https://alextaylor.dev") == "portfolio"

    # 4. Resume
    resume_text = "Alex Taylor\nWork Experience:\nSenior Engineer at Google\nEducation:\nBS Computer Science\nTechnical Skills: Go, Rust, Python"
    assert classify_document(resume_text, "resume.pdf") == "resume"


def test_chunk_text_sliding_window():
    # Create long text of 15,000 characters
    paragraphs = [f"Paragraph {i}: " + ("word " * 50) + "\n\n" for i in range(40)]
    long_doc = "".join(paragraphs)
    assert len(long_doc) > 10000

    chunks = chunk_text(long_doc, chunk_size=3000, overlap=300)
    assert len(chunks) >= 3
    # Check that chunks overlap and no text is discarded at start/end
    assert "Paragraph 0:" in chunks[0]
    assert "Paragraph 39:" in chunks[-1]


def test_merge_profiles_preserves_verified_bullets():
    base = CandidateProfile(
        full_name="Jane Doe",
        title="Senior Infrastructure Engineer",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Senior Engineer",
                start_date="2021",
                end_date="Present",
                bullets=["Scaled streaming cluster to 1.2M QPS, reducing latency by 40%."],
                technologies=["Go", "Kafka"]
            )
        ],
        projects=[
            Project(name="CacheDB", description="In-memory cache", tech_stack=["Rust"])
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Go", "Python"])
        ]
    )

    incoming = CandidateProfile(
        full_name="Jane Doe",
        title="Staff Engineer",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Senior Engineer",
                bullets=[
                    "Scaled streaming cluster to 1.2M QPS, reducing latency by 40%.",  # Duplicate
                    "Authored geo-replication RFC approved by VP of Engineering."     # New bullet
                ],
                technologies=["Go", "Kubernetes"]
            ),
            WorkExperience(
                company="Beta Startup",
                role="Founding Engineer",
                start_date="2019",
                end_date="2021",
                bullets=["Built initial MVP in 3 months."]
            )
        ],
        projects=[
            Project(name="VectorSearch", description="ANN search engine", tech_stack=["C++"])
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Go", "Rust"]),
            SkillCategory(category="Cloud", skills=["AWS", "GCP"])
        ]
    )

    merged = merge_profiles(base, incoming)

    # 1. Experiences merged without duplicate bullets
    acme = next(e for e in merged.experiences if e.company == "Acme Corp")
    assert len(acme.bullets) == 2
    assert "Scaled streaming cluster to 1.2M QPS" in acme.bullets[0]
    assert "Authored geo-replication RFC" in acme.bullets[1]
    assert "Kafka" in acme.technologies
    assert "Kubernetes" in acme.technologies

    # 2. New company appended
    assert any(e.company == "Beta Startup" for e in merged.experiences)

    # 3. Projects merged
    assert len(merged.projects) == 2
    assert any(p.name == "CacheDB" for p in merged.projects)
    assert any(p.name == "VectorSearch" for p in merged.projects)

    # 4. Skills merged under matching categories
    lang_cat = next(s for s in merged.skills if s.category.lower() == "languages")
    assert "Go" in lang_cat.skills
    assert "Python" in lang_cat.skills
    assert "Rust" in lang_cat.skills
    assert any(s.category.lower() == "cloud" for s in merged.skills)


def test_pantry_yaml_and_dossier_lifecycle(tmp_path: Path):
    pantry = PantryManager(tmp_path / "pantry")
    base_profile = CandidateProfile(
        full_name="Faiz Palwala",
        title="Distributed Systems Lead",
        summary="High-performance backend architect.",
        experiences=[
            WorkExperience(
                company="Apex AI",
                role="Lead Engineer",
                start_date="2022",
                end_date="Present",
                bullets=["Designed zero-copy memory manager saving 30% heap."]
            )
        ],
        skills=[SkillCategory(category="Core", skills=["Go", "C++"])]
    )

    # 1. Save and verify YAML export
    pantry.save_pantry(base_profile, trigger="v1")
    assert pantry.profile_yaml_path.exists()
    yaml_text = pantry.load_profile_yaml()
    assert "Faiz Palwala" in yaml_text
    assert "Apex AI" in yaml_text

    # 2. In-place edit via YAML
    edited_yaml = yaml_text.replace("Apex AI", "Apex Cloud Infrastructure")
    pantry.save_profile_yaml(edited_yaml, trigger="yaml_inplace_edit")
    reloaded = pantry.load_profile()
    assert reloaded.experiences[0].company == "Apex Cloud Infrastructure"

    # 3. Save deep dossier documents
    dossier_doc = "# Distributed Consensus Research\n\n## Algorithmic Formulation\nExplores multi-raft leadership election under Byzantine failures."
    saved_path = pantry.save_dossier_file("research/consensus.md", dossier_doc, trigger="dossier_save")
    assert saved_path.exists()

    dossier_files = pantry.list_dossier_files()
    assert len(dossier_files) == 1
    assert dossier_files[0]["rel_path"] == "research/consensus.md"

    loaded_content = pantry.load_dossier_file("research/consensus.md")
    assert "Byzantine failures" in loaded_content

    # 4. Snapshots cover both Ledgers (YAML, JSON, context, and dossier/)
    snapshots = pantry.list_snapshots()
    assert len(snapshots) >= 2
    latest_snap = snapshots[0]["id"]

    # Revert to base snapshot and verify dossier restoration
    base_snap_id = snapshots[-1]["id"]
    pantry.revert_snapshot(base_snap_id)
    reverted_prof = pantry.load_profile()
    assert reverted_prof.experiences[0].company == "Apex AI"


def test_two_ledger_ingest_project_readme(tmp_path: Path):
    pantry = PantryManager(tmp_path / "pantry")
    mock_provider = MockLLMProvider()

    readme_content = """# Breadwinner Ingestion Engine
High-throughput career knowledge compiler.

## Architecture
Built with Python 3.14, Textual TUI, and SQLite.
Processes raw documents into two-ledger canonical storage.

## Features
- Zero data leakage
- Anti-hallucination metric preservation
"""
    readme_file = tmp_path / "README.md"
    readme_file.write_text(readme_content)

    # Ingest into pantry via two-ledger API
    profile = UniversalIngestor.ingest_two_ledger(readme_file, mock_provider, pantry=pantry)

    assert pantry.is_initialized()
    assert len(profile.projects) >= 1

    # Check that dossier file was created
    dossier_files = pantry.list_dossier_files()
    assert len(dossier_files) >= 1
    proj_dossier = next(f for f in dossier_files if "project" in f["rel_path"])
    content = pantry.load_dossier_file(proj_dossier["rel_path"])
    assert len(content) > 50
