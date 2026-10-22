"""Unit tests for the 6-Pillar Metric Engine, Domain Evidence Recall, and Provenance Gate."""

import json
from pathlib import Path
import pytest

from breadwinner.core.models import CandidateProfile, WorkExperience, Education
from breadwinner.core.contract import JobContract, EvaluationCriteria, ContractMetadata
from breadwinner.core.density import (
    extract_bullet_action_verb,
    is_true_impact_metric,
    is_xyz_compliant_bullet,
    extract_achievement_bullets
)
from breadwinner.core.curator import CareerCurator
from breadwinner.core.provenance import ProvenanceValidator, DEFAULT_BANNED_WORDS
from breadwinner.core.models import TailoredApplication
from breadwinner.core.audit import AuditEngine, AuditReport


def test_true_impact_metric_filter():
    """Verify true impact metric filtering rejects calendar years and versions."""
    # Calendar years must be rejected
    assert not is_true_impact_metric("2024")
    assert not is_true_impact_metric("2019")
    assert not is_true_impact_metric("2026")

    # Isolated version numbers must be rejected
    assert not is_true_impact_metric("3.11")
    assert not is_true_impact_metric("2.0")

    # True scale, latency, throughput, percentages, and currencies must be accepted
    assert is_true_impact_metric("10M events")
    assert is_true_impact_metric("10M")
    assert is_true_impact_metric("99.999% uptime")
    assert is_true_impact_metric("sub-10ms")
    assert is_true_impact_metric("45%")
    assert is_true_impact_metric("5000 QPS")
    assert is_true_impact_metric("75,000")
    assert is_true_impact_metric("$100k")
    assert is_true_impact_metric("£500k")
    assert is_true_impact_metric("10x")
    assert is_true_impact_metric("p99")


def test_bold_lead_in_action_verb_extraction():
    """Verify action verb extraction works across bold prefixes and categories."""
    b1 = "**Enterprise Platform Stabilization:** Directed cross-functional team across 5 regions."
    assert extract_bullet_action_verb(b1) == "directed"

    b2 = "**Event Streaming:** Architected distributed pipeline processing 10M events/day."
    assert extract_bullet_action_verb(b2) == "architected"

    b3 = "*Consensus Layer:* Refactored Raft state machine reducing failover latency."
    assert extract_bullet_action_verb(b3) == "refactored"

    b4 = "[Infrastructure] Deployed Kubernetes clusters across 3 multi-zone regions."
    assert extract_bullet_action_verb(b4) == "deployed"

    b5 = "- Scaled backend services to 50,000 concurrent users."
    assert extract_bullet_action_verb(b5) == "scaled"


def test_xyz_bullet_compliance():
    """Verify Google XYZ formula adherence detection."""
    good_bullet = "**High-Throughput Streaming:** Engineered Kafka messaging tier in Go, achieving sub-10ms p99 latency across 10M daily events."
    is_comp, verb, metric = is_xyz_compliant_bullet(good_bullet)
    assert is_comp is True
    assert verb == "engineered"
    assert metric is not None

    weak_bullet = "Participated in weekly agile meetings with cross-functional product stakeholders."
    is_comp_weak, verb_weak, metric_weak = is_xyz_compliant_bullet(weak_bullet)
    assert is_comp_weak is False


def test_domain_evidence_recall():
    """Verify domain recall measures coverage of technical pillars without penalizing extra bullets."""
    core_domains = [
        "Distributed Systems",
        "Python/PyTorch",
        "Kafka/Microservices",
        "Cloud & Infrastructure",
        "Large Language Models"
    ]

    resume_text = """
    # Alex Taylor - Senior Distributed Systems Engineer
    Summary: Experienced backend engineer specializing in distributed systems, event-driven microservices, and Kafka.
    Experience:
    - Architected distributed event platform in Go and Python processing 10M events/day.
    - Optimized Kafka clusters and microservices reducing latency by 45%.
    - Deployed containerized workloads on Kubernetes and AWS cloud infrastructure.
    - Built evaluation pipelines using PyTorch and transformer models for LLM benchmarks.
    """

    score, matched, missing = CareerCurator.calculate_domain_evidence_recall(resume_text, core_domains)
    assert score == 100.0
    assert len(matched) == 5
    assert len(missing) == 0

    # Extra bullets should not degrade the score
    longer_resume = resume_text + "\n- Mentored 4 junior engineers on team best practices.\n- Authored technical RFCs."
    score_extra, matched_extra, _ = CareerCurator.calculate_domain_evidence_recall(longer_resume, core_domains)
    assert score_extra == 100.0
    assert len(matched_extra) == 5


def test_provenance_gate_hard_binary_verification():
    """Verify hard binary gate blocks unverified institutions, employers, or hallucinated metrics."""
    profile = CandidateProfile(
        full_name="Alex Taylor",
        title="Senior Distributed Systems Engineer",
        summary="Senior Distributed Systems Engineer at Apex Cloud Systems.",
        experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=["Architected streaming pipeline in Go processing 10M events/day."]
            )
        ],
        education=[
            Education(
                institution="University of Leeds",
                degree="BSc Computer Science"
            )
        ]
    )

    from breadwinner.core.models import JobPosting, MatchAnalysis
    job_mock = JobPosting(id="apex-1", company="Apex Cloud Systems", title="Senior Distributed Systems Engineer")
    match_mock = MatchAnalysis(match_score=95)

    # Valid application
    valid_app = TailoredApplication(
        job=job_mock,
        persona="tech_ai",
        match_analysis=match_mock,
        tailored_summary="Experienced distributed systems engineer from University of Leeds.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=["Architected streaming pipeline in Go processing 10M events/day."]
            )
        ]
    )
    report_valid = ProvenanceValidator.validate(valid_app, profile)
    assert report_valid.is_valid is True
    assert report_valid.status == "PASS"
    assert len(report_valid.flagged_entities) == 0

    # Application with unverified institution (hallucination)
    fake_inst_app = TailoredApplication(
        job=job_mock,
        persona="tech_ai",
        match_analysis=match_mock,
        tailored_summary="Graduated from Harvard University with honors.",
        tailored_experiences=[
            WorkExperience(
                company="Apex Cloud Systems",
                role="Senior Distributed Systems Engineer",
                bullets=["Architected streaming pipeline in Go processing 10M events/day."]
            )
        ]
    )
    report_fake_inst = ProvenanceValidator.validate(fake_inst_app, profile)
    assert report_fake_inst.is_valid is False
    assert report_fake_inst.status == "FAIL"
    assert any("Harvard University" in fe for fe in report_fake_inst.flagged_entities)

    # Application with unverified employer (hallucination)
    fake_emp_app = TailoredApplication(
        job=job_mock,
        persona="tech_ai",
        match_analysis=match_mock,
        tailored_summary="Staff Engineer at Apex Cloud Systems.",
        tailored_experiences=[
            WorkExperience(
                company="Google DeepMind",
                role="Staff Research Engineer",
                bullets=["Engineered large scale infrastructure."]
            )
        ]
    )
    report_fake_emp = ProvenanceValidator.validate(fake_emp_app, profile)
    assert report_fake_emp.is_valid is False
    assert report_fake_emp.status == "FAIL"
    assert any("Google DeepMind" in fe for fe in report_fake_emp.flagged_entities)


def test_audit_engine_end_to_end(tmp_path: Path):
    """Verify AuditEngine produces complete 6-pillar receipt matching RFC specification."""
    fixture_path = Path("tests/fixtures/golden_profile.json")
    profile = CandidateProfile.from_yaml(fixture_path.read_text(encoding="utf-8")) if fixture_path.name.endswith(".yaml") else CandidateProfile(**json.loads(fixture_path.read_text(encoding="utf-8")))

    contract = JobContract(
        metadata=ContractMetadata(
            company="Apex Systems",
            role="Senior Distributed Systems Engineer",
            page_budget=2
        ),
        evaluation_criteria=EvaluationCriteria(
            core_domains=["Distributed Systems", "Kafka", "PostgreSQL", "Go"],
            essential_keywords=["consensus", "redis"]
        )
    )

    resume_text = """
    # Alex Taylor
    ### Senior Distributed Systems Engineer - London, UK

    **Professional Summary**
    Senior Distributed Systems Engineer specializing in high-throughput event streaming, fault-tolerant consensus, and cloud infrastructure.

    **Work Experience**
    **Apex Cloud Systems** | Senior Distributed Systems Engineer
    - Architected distributed event streaming platform in Go processing 10M events/day with 99.999% uptime.
    - Optimized Kafka and Redis caching tiers, achieving sub-10ms p99 latency across all regional clusters.
    - Redesigned multi-tenant PostgreSQL storage layer resulting in a 45% cost reduction on cloud compute.

    **Education**
    **University of Leeds** | BSc Computer Science
    """

    report = AuditEngine.audit(resume_text, contract, profile=profile)

    assert isinstance(report, AuditReport)
    assert report.provenance_gate.status == "PASS"
    assert len(report.provenance_gate.flagged_entities) == 0
    assert report.ats_alignment.exact_title_match is True
    assert report.ats_alignment.domain_recall_score == 100
    assert report.ats_alignment.ats_score >= 90
    assert report.quality_metrics.total_achievement_bullets == 3
    assert report.quality_metrics.xyz_compliant_bullets == 3
    assert report.quality_metrics.xyz_score == 100.0
    assert report.quality_metrics.page1_impact_ratio >= 65.0
    assert report.page_budget.status in ["OPTIMAL", "UNDERFILL"]
