"""Unit tests for portfolio adapters and profile models."""

import json
from pathlib import Path
from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)
from breadwinner.core.portfolio import JsonResumeAdapter, MarkdownDirectoryAdapter


def test_candidate_profile_json_resume_export():
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="AI/ML Engineer",
        email="alex.taylor@example.com",
        location="London, UK",
        experiences=[
            WorkExperience(
                company="Tech Corp",
                role="SDE 2",
                start_date="2023",
                end_date="2024",
                bullets=["Built platform for 10M+ users."]
            )
        ],
        education=[
            Education(
                institution="University of Technology",
                degree="MSc Advanced Computer Science",
                start_date="2025",
                end_date="2026"
            )
        ],
        projects=[
            Project(
                name="Serverless Heatmap",
                description="GitHub calendar action",
                tech_stack=["TypeScript", "React"]
            )
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Python", "Java", "Go"])
        ]
    )

    json_data = profile.to_json_resume()
    assert json_data["basics"]["name"] == "Alex Taylor"
    assert len(json_data["work"]) == 1
    assert json_data["work"][0]["name"] == "Tech Corp"
    assert len(json_data["education"]) == 1
    assert len(json_data["projects"]) == 1
    assert json_data["skills"][0]["name"] == "Languages"



def test_json_resume_adapter(tmp_path: Path):
    sample_resume = {
        "basics": {
            "name": "Jane Doe",
            "label": "Data Scientist",
            "email": "jane@example.com"
        },
        "work": [
            {
                "name": "Acme Corp",
                "position": "Data Scientist",
                "startDate": "2021",
                "endDate": "2023",
                "highlights": ["Trained XGBoost models."]
            }
        ],
        "education": [],
        "projects": [],
        "skills": []
    }
    json_file = tmp_path / "resume.json"
    json_file.write_text(json.dumps(sample_resume), encoding="utf-8")

    adapter = JsonResumeAdapter(json_file)
    profile = adapter.load_profile()
    assert profile.full_name == "Jane Doe"
    assert profile.title == "Data Scientist"
    assert len(profile.experiences) == 1
    assert profile.experiences[0].company == "Acme Corp"


def test_markdown_directory_adapter(tmp_path: Path):
    exp_file = tmp_path / "experience.md"
    exp_file.write_text("""## Tech Co
- Developed core payment gateway.
- Reduced latency by 35%.
""", encoding="utf-8")

    adapter = MarkdownDirectoryAdapter(tmp_path)
    profile = adapter.load_profile()
    assert len(profile.experiences) == 1
    assert profile.experiences[0].company == "Tech Co"
    assert len(profile.experiences[0].bullets) == 2


def test_pantry_profile_adapter(tmp_path: Path, monkeypatch):
    from breadwinner.core.portfolio import get_profile_source
    pantry_dir = tmp_path / "pantry"
    pantry_dir.mkdir()
    (pantry_dir / "profile.json").write_text(json.dumps({
        "basics": {"name": "Jordan Lee", "label": "DevOps Engineer"}
    }), encoding="utf-8")
    (pantry_dir / "context.md").write_text("## Boundaries\n- Remote only", encoding="utf-8")

    monkeypatch.setattr("breadwinner.config.settings.pantry_dir", pantry_dir)
    adapter = get_profile_source()
    profile = adapter.load_profile()
    assert profile.full_name == "Jordan Lee"
    assert "Remote only" in profile.raw_context.get("personal_context", "")

