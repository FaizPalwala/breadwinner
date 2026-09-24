"""Unit tests for CareerCurator (Relevance & Curation Engine)."""

import pytest
from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Project,
    Education,
    JobPosting
)
from breadwinner.core.curator import CareerCurator


@pytest.fixture
def sample_candidate_profile():
    return CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Software Engineer",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Backend Engineer",
                start_date="2022-01-01",
                end_date="Present",
                bullets=[
                    "Architected streaming Kafka pipeline processing 10M events/day, cutting latency by 45%.",
                    "Migrated monolithic Postgres to distributed CockroachDB across 3 AWS regions.",
                    "Mentored 4 junior engineers on distributed consensus and high-throughput systems."
                ]
            ),
            WorkExperience(
                company="Legacy Financial",
                role="Java Developer",
                start_date="2018-01-01",
                end_date="2021-12-31",
                bullets=[
                    "Maintained legacy SOAP banking endpoints.",
                    "Fixed compliance bugs in mainframe quarterly reports.",
                    "Attended weekly standups and wrote Jira tickets."
                ]
            ),
            WorkExperience(
                company="Nova Dynamics",
                role="Distributed Systems Engineer",
                start_date="2016-01-01",
                end_date="2017-12-31",
                bullets=[
                    "Engineered gRPC microservices reducing p99 latency by 60ms.",
                    "Implemented Redis cache cluster with 99.99% uptime."
                ]
            )
        ],
        projects=[
            Project(
                name="RaftEngine",
                description="Consensus protocol implementation in Go with 5000 QPS benchmark.",
                tech_stack=["Go", "Raft", "Distributed Systems"]
            ),
            Project(
                name="SimpleBlog",
                description="Basic static blog generator.",
                tech_stack=["PHP", "HTML"]
            )
        ]
    )


@pytest.fixture
def target_distributed_job():
    return JobPosting(
        id="job_dist_1",
        company="Datadog",
        title="Staff Distributed Systems Engineer",
        url="https://datadog.com/jobs/1",
        portal_type="greenhouse",
        raw_text="""
        Datadog is looking for a Staff Distributed Systems Engineer.
        Must have deep expertise in Kafka, streaming pipelines, high throughput, low latency,
        and distributed consensus protocols like Raft. Experience with Go, AWS, and caching is required.
        """
    )


def test_extract_keywords():
    text = "Looking for a Staff Engineer with Kafka, Go, and 5+ years experience!"
    keywords = CareerCurator.extract_keywords(text)
    assert "kafka" in keywords
    assert "go" in keywords
    assert "staff" in keywords
    assert "for" not in keywords
    assert "and" not in keywords


def test_score_bullet_with_metrics_and_keywords():
    job_keywords = {"kafka", "latency", "streaming"}
    bullet_with_metric = "Architected streaming Kafka pipeline, cutting latency by 45% across 10M events."
    score, overlap = CareerCurator.score_bullet(bullet_with_metric, job_keywords)

    assert overlap >= 3
    assert score > 5.0

    bullet_weak = "Attended meetings and resolved minor issues."
    weak_score, weak_overlap = CareerCurator.score_bullet(bullet_weak, job_keywords)
    assert weak_overlap == 0
    assert weak_score == 0.0


def test_curation_prioritizes_relevant_roles(sample_candidate_profile, target_distributed_job):
    result = CareerCurator.curate(
        profile=sample_candidate_profile,
        job=target_distributed_job,
        max_experiences=2,
        max_projects=1
    )

    curated = result.curated_profile
    assert len(curated.experiences) == 2

    # Apex Cloud (Kafka/streaming) and Nova Dynamics (Distributed systems) should be chosen over Legacy Financial (SOAP/mainframe)
    selected_companies = [e.company for e in curated.experiences]
    assert "Apex Cloud Systems" in selected_companies
    assert "Nova Dynamics" in selected_companies
    assert "Legacy Financial" not in selected_companies

    # Projects: RaftEngine should be chosen over SimpleBlog
    assert len(curated.projects) == 1
    assert curated.projects[0].name == "RaftEngine"

    # Verify summary metadata
    assert result.total_experiences_in_pantry == 3
    assert result.selected_experiences_count == 2
    assert result.omitted_experiences_count == 1
    assert "kafka" in result.matched_keywords
