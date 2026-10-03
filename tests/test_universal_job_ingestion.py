"""Comprehensive tests for Universal Job Ingestion & Application Requirement Extraction (ADR 001)."""

import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    SkillCategory,
    CoverLetterRequirement,
    QuestionType,
    QuestionSource
)
from breadwinner.core.persona import Persona
from breadwinner.core.resolver import RedirectResolver
from breadwinner.core.experience import calculate_experience_years, calculate_skills_experience
from breadwinner.core.prompts_extractor import extract_in_text_prompts
from breadwinner.core.adapters.greenhouse import GreenhouseAdapter
from breadwinner.core.adapters.lever import LeverAdapter
from breadwinner.core.adapters.ashby import AshbyAdapter
from breadwinner.core.adapters.workable import WorkableAdapter
from breadwinner.core.adapters.smartrecruiters import SmartRecruitersAdapter
from breadwinner.core.adapters.workday import WorkdayAdapter
from breadwinner.core.adapters.linkedin import LinkedInGuestAdapter
from breadwinner.core.universal import UniversalJobIngestor
from breadwinner.core.dossier import render_application_dossier
from breadwinner.cli import main


def make_sample_profile() -> CandidateProfile:
    return CandidateProfile(
        full_name="Alex Mercer",
        title="Staff Distributed Systems Engineer",
        email="alex.mercer@example.com",
        phone="+44 7700 900999",
        location="London, UK",
        linkedin_url="https://linkedin.com/in/alexmercer",
        github_url="https://github.com/alexmercer",
        portfolio_url="https://alexmercer.dev",
        experiences=[
            WorkExperience(
                company="Monzo Bank",
                role="Senior Staff Backend Engineer",
                start_date="2021-01",
                end_date="2024-01",
                is_current=False,
                technologies=["Go", "Kubernetes", "Kafka", "AWS"],
                bullets=["Architected real-time transaction pipeline in Go scaling to 45k QPS."]
            ),
            WorkExperience(
                company="Deliveroo",
                role="Senior Distributed Systems Engineer",
                start_date="2018-01",
                end_date="2020-12",
                is_current=False,
                technologies=["Go", "Python", "PostgreSQL", "Docker"],
                bullets=["Engineered high-throughput dispatch engine in Go and Python."]
            )
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Go", "Python", "SQL"]),
            SkillCategory(category="Infrastructure", skills=["Kubernetes", "Docker", "Kafka", "AWS"])
        ]
    )


def test_redirect_resolver_unwrapping():
    """Verify RedirectResolver unwraps tracking URLs and query parameters."""
    raw = "https://www.linkedin.com/jobs/view/externalApply/12345?url=https%3A%2F%2Fboards.greenhouse.io%2Fmonzo%2Fjobs%2F5239102&utm_source=linkedin&trk=job_view"
    cleaned = RedirectResolver.strip_tracking_parameters(raw)
    assert "utm_source" not in cleaned
    assert "trk" not in cleaned

    # Direct canonical unwrapping test
    with patch("requests.head") as mock_head:
        mock_head.return_value.url = "https://boards.greenhouse.io/monzo/jobs/5239102?utm_campaign=spring"
        res = RedirectResolver.resolve_canonical_url("https://bit.ly/monzo-job")
        assert res == "https://boards.greenhouse.io/monzo/jobs/5239102"


def test_greenhouse_adapter():
    """Verify Greenhouse adapter extracts structured questions and cover letter status."""
    adapter = GreenhouseAdapter()
    assert adapter.matches("https://boards.greenhouse.io/monzo/jobs/5239102")
    assert adapter.matches("https://job-boards.greenhouse.io/stripe/jobs/123")
    assert adapter.matches("https://careers.company.com/apply?gh_jid=998877")

    mock_payload = {
        "title": "Staff Platform Engineer",
        "content": "&lt;p&gt;We are seeking a staff engineer to scale our distributed ledger.&lt;/p&gt;&lt;h2&gt;Requirements&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;5+ years Go&lt;/li&gt;&lt;/ul&gt;",
        "location": {"name": "London, UK (Hybrid)"},
        "questions": [
            {
                "name": "first_name",
                "label": "First Name",
                "required": True,
                "fields": [{"type": "input_text"}]
            },
            {
                "name": "cover_letter",
                "label": "Cover Letter",
                "required": True,
                "fields": [{"type": "input_file"}]
            },
            {
                "name": "question_101",
                "label": "Describe a production outage in a distributed system you mitigated.",
                "required": True,
                "fields": [{"type": "textarea"}]
            },
            {
                "name": "question_102",
                "label": "Do you require visa sponsorship to work in the UK?",
                "required": True,
                "fields": [
                    {
                        "type": "multi_value_single_select",
                        "values": [{"label": "Yes"}, {"label": "No"}]
                    }
                ]
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_payload

        result = adapter.extract("https://boards.greenhouse.io/monzo/jobs/5239102")

        assert result.title == "Staff Platform Engineer"
        assert result.company == "Monzo"
        assert "London" in (result.location or "")
        assert result.cover_letter_status == CoverLetterRequirement.MANDATORY
        assert "5+ years Go" in result.cleaned_markdown

        # 2 questions (excluding first_name and cover_letter)
        assert len(result.questions) == 2
        q1 = result.questions[0]
        assert "production outage" in q1.prompt
        assert q1.question_type == QuestionType.TEXTAREA
        assert q1.required is True

        q2 = result.questions[1]
        assert "visa sponsorship" in q2.prompt
        assert q2.question_type == QuestionType.DROPDOWN
        assert q2.options == ["Yes", "No"]


def test_lever_adapter():
    """Verify Lever adapter extracts customQuestions and markdown lists."""
    adapter = LeverAdapter()
    assert adapter.matches("https://jobs.lever.co/anthropic/e3b0c442")

    mock_payload = {
        "text": "Research Infrastructure Engineer",
        "categories": {
            "commitment": "Full time",
            "location": "San Francisco, CA"
        },
        "content": {
            "description": "<p>Build high-scale GPU clusters.</p>",
            "lists": [
                {"text": "Key Responsibilities", "content": "<li>Manage 10,000 GPUs</li><li>Optimize p99 latency</li>"}
            ]
        },
        "customQuestions": [
            {
                "text": "Link to your published research or GitHub",
                "required": True,
                "type": "text"
            },
            {
                "text": "Why Anthropic?",
                "required": False,
                "type": "textarea"
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_payload

        result = adapter.extract("https://jobs.lever.co/anthropic/e3b0c442")
        assert result.title == "Research Infrastructure Engineer"
        assert result.company == "Anthropic"
        assert len(result.questions) == 2
        assert result.questions[0].prompt == "Link to your published research or GitHub"
        assert result.questions[0].required is True
        assert result.questions[1].question_type == QuestionType.TEXTAREA
        assert result.cover_letter_status == CoverLetterRequirement.OPTIONAL


def test_ashby_adapter():
    """Verify Ashby adapter parses __NEXT_DATA__ server-rendered payload."""
    adapter = AshbyAdapter()
    assert adapter.matches("https://jobs.ashbyhq.com/synthesia/8b9a0c")

    next_data = {
        "props": {
            "pageProps": {
                "jobPosting": {
                    "title": "Senior AI Video Pipeline Engineer",
                    "locationName": "London, UK",
                    "descriptionHtml": "<p>Scaling real-time generative video.</p>"
                },
                "applicationForm": {
                    "fields": [
                        {
                            "id": "f_1",
                            "title": "Full Name",
                            "path": "_systemfield_name",
                            "isRequired": True
                        },
                        {
                            "id": "f_2",
                            "title": "Cover Letter",
                            "path": "_systemfield_coverletter",
                            "isRequired": False
                        },
                        {
                            "id": "f_3",
                            "title": "What is the most challenging streaming pipeline you built?",
                            "path": "custom_question_1",
                            "type": "LongAnswer",
                            "isRequired": True
                        }
                    ]
                }
            }
        }
    }

    html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></body></html>'

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = html

        result = adapter.extract("https://jobs.ashbyhq.com/synthesia/8b9a0c")
        assert result.title == "Senior AI Video Pipeline Engineer"
        assert result.company == "Synthesia"
        assert result.cover_letter_status == CoverLetterRequirement.OPTIONAL
        assert len(result.questions) == 1
        assert "challenging streaming pipeline" in result.questions[0].prompt
        assert result.questions[0].question_type == QuestionType.TEXTAREA
        assert result.questions[0].required is True


def test_workable_adapter():
    """Verify Workable adapter parses application form questions and cover letter enum."""
    adapter = WorkableAdapter()
    assert adapter.matches("https://apply.workable.com/deliveroo/j/AB12CD34/")

    mock_payload = {
        "title": "Lead Backend Architect",
        "location": {"city": "London"},
        "description": "<p>Architect our hyper-growth food delivery platform.</p>",
        "requirements": "<li>10+ years microservices</li>",
        "application_form": {
            "cover_letter": "required",
            "questions": [
                {
                    "id": "q_workable_1",
                    "body": "Are you legally authorized to work in the UK?",
                    "required": True,
                    "type": "boolean"
                }
            ]
        }
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_payload

        result = adapter.extract("https://apply.workable.com/deliveroo/j/AB12CD34/")
        assert result.title == "Lead Backend Architect"
        assert result.company == "Deliveroo"
        assert result.cover_letter_status == CoverLetterRequirement.MANDATORY
        assert len(result.questions) == 1
        assert result.questions[0].question_type == QuestionType.BOOLEAN


def test_smartrecruiters_adapter():
    """Verify SmartRecruiters adapter extracts job sections and screening questions."""
    adapter = SmartRecruitersAdapter()
    assert adapter.matches("https://jobs.smartrecruiters.com/Visa/7439999")

    mock_post = {
        "name": "Senior Staff Systems Engineer",
        "company": {"name": "Visa"},
        "location": {"city": "Foster City"},
        "jobAd": {
            "sections": {
                "jobDescription": {"title": "Company Description", "text": "<p>Global payment networks.</p>"},
                "qualifications": {"title": "Qualifications", "text": "<li>Distributed consensus</li>"}
            }
        }
    }
    mock_questions = {
        "questions": [
            {
                "id": "sr_q1",
                "label": "Expected base salary?",
                "required": True,
                "type": "number"
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = mock_post

        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = mock_questions

        mock_get.side_effect = [mock_resp1, mock_resp2]

        result = adapter.extract("https://jobs.smartrecruiters.com/Visa/7439999")
        assert result.title == "Senior Staff Systems Engineer"
        assert result.company == "Visa"
        assert len(result.questions) == 1
        assert result.questions[0].prompt == "Expected base salary?"
        assert result.questions[0].question_type == QuestionType.NUMBER


def test_workday_cxs_adapter():
    """Verify Workday CXS adapter parses Client Experience Service JSON."""
    adapter = WorkdayAdapter()
    assert adapter.matches("https://nvidia.wd3.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Austin-TX/Senior-CUDA-Architect_JR19482")

    mock_payload = {
        "jobPostingInfo": {
            "title": "Senior CUDA Systems Architect",
            "jobDescription": "<p>Build high-performance computing platforms.</p>",
            "location": "Austin, TX"
        }
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_payload

        result = adapter.extract("https://nvidia.wd3.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Austin-TX/Senior-CUDA-Architect_JR19482")
        assert result.title == "Senior CUDA Systems Architect"
        assert result.company == "Nvidia"
        assert "Austin" in (result.location or "")
        assert "high-performance computing" in result.cleaned_markdown


def test_linkedin_guest_adapter():
    """Verify LinkedIn Guest adapter extracts from unauthenticated public guest view."""
    adapter = LinkedInGuestAdapter()
    assert adapter.matches("https://www.linkedin.com/jobs/view/3920192847")

    mock_html = """
    <html>
      <body>
        <h2 class="topcard__title">Principal Distributed Systems Engineer</h2>
        <a class="topcard__org-name-link">Stripe</a>
        <span class="topcard__flavor--bullet">London, England, United Kingdom</span>
        <div class="show-more-less-html__markup">
          <p>Lead the core ledger and banking infrastructure at Stripe.</p>
        </div>
      </body>
    </html>
    """

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = mock_html

        result = adapter.extract("https://www.linkedin.com/jobs/view/3920192847")
        assert result.title == "Principal Distributed Systems Engineer"
        assert result.company == "Stripe"
        assert "London" in (result.location or "")
        assert "core ledger" in result.cleaned_markdown


def test_in_text_prompts_extraction():
    """Verify Vector 2 detection of buried screening prompts in JD text."""
    jd_text = """
    ## Staff Platform Engineer
    We are scaling our transaction network.

    In your application, please explain your experience scaling Kafka partitions to over 100k msgs/sec.
    Also, please provide a link to your favorite open source pull request.
    To confirm you read this job description, include the code word 'Boule' at the top of your cover letter.
    """

    prompts = extract_in_text_prompts(jd_text)
    assert len(prompts) >= 2
    prompt_texts = [p.prompt for p in prompts]
    assert any("experience scaling Kafka" in p for p in prompt_texts)
    assert any("favorite open source pull request" in p for p in prompt_texts)
    assert all(p.source == QuestionSource.IN_TEXT for p in prompts)


def test_mathematical_experience_duration_calculation():
    """Verify mathematical calculation of cumulative production experience from Career Pantry."""
    profile = make_sample_profile()

    # Go was used in Monzo (2021-01 to 2024-01: 3 yrs) AND Deliveroo (2018-01 to 2020-12: 3 yrs) -> 6 yrs
    years_go = calculate_experience_years(profile, "Go")
    assert years_go == 6

    # Kubernetes was used only at Monzo (2021-01 to 2024-01: 3 yrs)
    years_k8s = calculate_experience_years(profile, "Kubernetes")
    assert years_k8s == 3

    # Python was used only at Deliveroo (2018-01 to 2020-12: 3 yrs)
    years_python = calculate_experience_years(profile, "Python")
    assert years_python == 3

    # Rust was never in profile
    years_rust = calculate_experience_years(profile, "Rust")
    assert years_rust == 0

    skills_dict = calculate_skills_experience(profile, ["Go", "Kubernetes", "Rust", "AWS"])
    assert skills_dict == {"Go": 6, "Kubernetes": 3, "AWS": 3}


def test_application_dossier_rendering():
    """Verify Application Dossier formatting."""
    profile = make_sample_profile()
    persona = Persona(
        name="Staff Leader",
        slug="staff_leader",
        description="Hands-on distributed systems engineering leader",
        tone="authoritative",
        system_directives="Prioritize p99 latency and high-throughput scale.",
        cover_letter_directives="Highlight consensus algorithms and 45k QPS scale.",
        logistics={
            "compensation_floor": "£165,000",
            "notice_period": "1 month",
            "visa": "UK Citizen, no sponsorship needed for UK."
        }
    )

    sample_result = UniversalJobIngestor.ingest_text(
        text=(
            "### Staff Systems Engineer\n"
            "Requirements: Go, Kubernetes, Kafka, AWS.\n"
            "In your application, please describe your experience with zero-downtime database sharding.\n"
        ),
        company="Monzo",
        title="Staff Systems Engineer",
        profile=profile,
        persona=persona
    )

    dossier = render_application_dossier(sample_result, profile=profile, persona=persona)
    assert "# 🥐 BREADWINNER APPLICATION DOSSIER" in dossier
    assert "Alex Mercer" in dossier
    assert "**Work Authorized:** YES" in dossier
    assert "**Notice Period:** 1 month" in dossier
    assert "GBP 165,000" in dossier
    assert "6 Years" in dossier
    assert "zero-downtime database sharding" in dossier


def test_cli_job_inspect():
    """Verify CLI `breadwinner job inspect` prints summary card and detected prompts."""
    runner = CliRunner()
    text_content = (
        "## Senior Engineer\n"
        "Requirements: Go, Docker, Kubernetes.\n"
        "In your application, please describe how you handled a production Kubernetes outage.\n"
    )

    with runner.isolated_filesystem():
        with open("job.txt", "w") as f:
            f.write(text_content)

        result = runner.invoke(main, ["job", "inspect", "job.txt"])
        assert result.exit_code == 0
        assert "BREADWINNER UNIVERSAL JOB INSPECTOR" in result.output
        assert "Target Role" in result.output
        assert "production Kubernetes outage" in result.output
