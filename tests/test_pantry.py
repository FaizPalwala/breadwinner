"""Unit tests for Pantry knowledge base manager and snapshot versioning."""

from pathlib import Path
from breadwinner.core.models import CandidateProfile, WorkExperience, Project, SkillCategory
from breadwinner.core.pantry import PantryManager


def make_sample_profile() -> CandidateProfile:
    return CandidateProfile(
        full_name="Alex Taylor",
        title="Software Engineer",
        email="alex@example.com",
        location="London, UK",
        summary="Distributed systems engineer.",
        experiences=[
            WorkExperience(
                company="Apex Systems",
                role="Software Engineer",
                start_date="2022",
                end_date="Present",
                bullets=["Built streaming pipeline reducing latency by 45%."]
            )
        ],
        projects=[
            Project(name="Task Scheduler", description="Go distributed queue")
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Go", "Python"])
        ]
    )


def test_pantry_save_and_load(tmp_path: Path):
    pantry = PantryManager(tmp_path / "pantry")
    assert not pantry.is_initialized()

    profile = make_sample_profile()
    pantry.save_pantry(profile, context="Targeting Senior Backend roles only.", trigger="initial_test")

    assert pantry.is_initialized()
    loaded = pantry.load_profile()
    assert loaded.full_name == "Alex Taylor"
    assert len(loaded.experiences) == 1
    assert "Targeting Senior Backend" in loaded.raw_context.get("personal_context", "")


def test_pantry_snapshot_and_revert(tmp_path: Path):
    pantry = PantryManager(tmp_path / "pantry")
    profile = make_sample_profile()
    pantry.save_pantry(profile, trigger="v1")

    # Update profile to v2
    v1_snapshots = pantry.list_snapshots()
    assert len(v1_snapshots) >= 1
    v1_id = v1_snapshots[0]["id"]

    profile.title = "Staff Systems Architect"
    profile.experiences[0].bullets.append("Authored RFC for multi-region replication.")
    pantry.save_pantry(profile, trigger="v2")

    assert pantry.load_profile().title == "Staff Systems Architect"

    # Revert to v1
    success = pantry.revert_snapshot(v1_id)
    assert success is True
    reverted = pantry.load_profile()
    assert reverted.title == "Software Engineer"
    assert len(reverted.experiences[0].bullets) == 1


def test_pantry_diff_computation(tmp_path: Path):
    pantry = PantryManager(tmp_path / "pantry")
    profile = make_sample_profile()
    pantry.save_pantry(profile, trigger="base")

    # Create new profile with 1 new experience and 1 new project
    updated_profile = make_sample_profile()
    updated_profile.experiences.append(WorkExperience(
        company="New Fintech Co",
        role="Lead Engineer",
        start_date="2024",
        end_date="Present",
        bullets=["Led 5 engineers."]
    ))
    updated_profile.projects.append(Project(
        name="AI Agent Engine",
        description="Autonomous workflow planner"
    ))

    diff = pantry.compute_diff(updated_profile)
    assert not diff["is_new"]
    assert len(diff["added_experiences"]) == 1
    assert "New Fintech Co" in diff["added_experiences"][0]
    assert "AI Agent Engine" in diff["added_projects"]
