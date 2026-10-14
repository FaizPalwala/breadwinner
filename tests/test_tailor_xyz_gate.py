import pytest
from breadwinner.core.models import CandidateProfile, WorkExperience, JobPosting
from breadwinner.core.tailor import TailoringEngine
from breadwinner.providers.factory import MockLLMProvider
from breadwinner.ui.editor import analyze_bullets_xyz


def test_tailor_verification_gate_heals_truncation():
    """Verify that the tailor verification gate heals truncated bullets and adds terminal punctuation."""
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)

    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Staff Engineer",
        email="jane@example.com",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Platform Lead",
                start_date="2020",
                end_date="Present",
                bullets=[
                    "Architected event processing pipeline handling 100,000 requests/sec with 99.99% uptime.",
                    "Optimized Redis cache layers, cutting p99 latency by 40% across 15 microservices."
                ]
            )
        ]
    )

    draft_experiences = [
        WorkExperience(
            company="Acme Corp",
            role="Platform Lead",
            start_date="2020",
            end_date="Present",
            bullets=[
                "Architected event processing pipeline handling 100,000 requests/sec with",  # truncated with dangling "with"
                "Optimized Redis cache layers, cutting p99 latency by 40% across 15 microservices,",  # trailing comma
                "Stabilized 12 microservices under peak traffic, mitigating 150 incidents"  # missing terminal period
            ]
        )
    ]

    healed = engine._verify_and_heal_tailored_bullets(draft_experiences, profile)
    bullets = healed[0].bullets

    assert len(bullets) == 3
    # First bullet restored from orig_bullets because it was truncated with dangling "with"
    assert "100,000 requests/sec" in bullets[0]
    assert bullets[0].endswith(".")

    # Second bullet trailing comma cleaned and closed with period
    assert bullets[1].endswith(".")
    assert not bullets[1].endswith(",.")
    assert "cutting p99 latency by 40%" in bullets[1]

    # Third bullet has terminal period added
    assert bullets[2].endswith(".")


def test_tailor_verification_gate_elevates_metric_score():
    """Verify that experiences with <80% metric score are elevated using verified metrics."""
    mock = MockLLMProvider()
    engine = TailoringEngine(mock)

    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Staff Engineer",
        email="jane@example.com",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Platform Lead",
                start_date="2020",
                end_date="Present",
                bullets=[
                    "Architected event processing pipeline handling 100,000 requests/sec with 99.99% uptime.",
                    "Optimized Redis cache layers, cutting p99 latency by 40% across 15 microservices.",
                    "Automated deployment workflows across 24 clusters, reducing cycle time by 50%."
                ]
            )
        ]
    )

    # Draft with only 1 quantified bullet out of 3 (33% < 80%)
    draft_experiences = [
        WorkExperience(
            company="Acme Corp",
            role="Platform Lead",
            start_date="2020",
            end_date="Present",
            bullets=[
                "Architected distributed event streaming backend for platform teams.",  # no metric
                "Collaborated with cross-functional stakeholders on architectural roadmaps.",  # no metric
                "Optimized database indices reducing latency by 45%."  # has metric
            ]
        )
    ]

    healed = engine._verify_and_heal_tailored_bullets(draft_experiences, profile)
    report = analyze_bullets_xyz("\n".join(f"- {b}" for b in healed[0].bullets), profile=profile)

    assert report.quantified_score >= 80


def test_tailor_prompt_invariants_contain_aligned_xyz_syntax():
    """Verify prompt contains strict XYZ syntax and anti-inversion rule."""
    from breadwinner.core.tailor import TailoringEngine
    import inspect

    src = inspect.getsource(TailoringEngine.analyze_and_tailor)
    assert 'Accomplished [X outcome] as measured by [Y metric], by doing [Z technical architecture/method]' in src
    assert 'Do NOT invert to Z-first' in src
