"""Unit tests for CareerDensityScorer."""

from breadwinner.core.density import CareerDensityScorer, DiscourseChunk


def test_chunk_text_markdown_and_bullets():
    raw = """# Header 1
Some intro paragraph about career and architecture.

- Architected streaming Kafka pipeline processing 10M events/day.
- Reduced p99 latency by 45ms across 3 AWS regions.

## Projects
Built a real-time analytics engine in Rust with 5000 QPS throughput.
"""
    chunks = CareerDensityScorer.chunk_text(raw)
    assert len(chunks) >= 4
    assert any("Kafka" in c for c in chunks)
    assert any("5000 QPS" in c for c in chunks)


def test_score_chunk_metrics_and_verbs():
    high_density = "Architected streaming Kafka pipeline processing 10M events/day, cutting latency by 45%."
    chunk = CareerDensityScorer.score_chunk(high_density)

    assert chunk.classification == "fact"
    assert chunk.metric_velocity > 0
    assert chunk.action_agency > 0
    assert chunk.composite_score > 5.0
    assert "architected" in chunk.matched_verbs
    assert any("10M" in m or "45%" in m for m in chunk.matched_metrics)


def test_score_chunk_fluff_tutorial_penalty():
    tutorial_junk = "In this tutorial we will learn how to install npm and run docker run step 1."
    chunk = CareerDensityScorer.score_chunk(tutorial_junk)

    assert chunk.classification == "fluff"
    assert chunk.fluff_penalty >= 4.0
    assert chunk.composite_score <= 0


def test_score_chunk_dissertation_boilerplate():
    thesis_junk = "This dissertation is submitted in partial fulfillment of the doctoral thesis requirements. Table of contents."
    chunk = CareerDensityScorer.score_chunk(thesis_junk)

    assert chunk.classification == "fluff"
    assert chunk.fluff_penalty >= 4.0


def test_distill_separates_fact_and_narrative_ledgers():
    mixed_content = """# About Me
I have spent the last 8 years passionate about distributed systems and building developer tooling.

## Experience
- Spearheaded migration of legacy monolith to Kubernetes, cutting cloud costs by $120,000 annually.
- Scaled Redis cluster to handle 50,000 QPS with 99.99% uptime.

## Blog Post: Weekend Thoughts
In this article I wanted to share some thoughts on coffee and my personal opinion on modern work.
Step 1 of making good coffee is grinding fresh beans.
"""
    fact_text, narrative_text, telemetry = CareerDensityScorer.distill(mixed_content)

    # Facts should have the high-metric bullet points
    assert "$120,000" in fact_text or "Kubernetes" in fact_text
    assert "50,000 QPS" in fact_text

    # Fluff should be pruned
    assert "coffee" not in fact_text
    assert "Step 1" not in fact_text
    assert telemetry["fluff_chunks_pruned"] >= 1
    assert telemetry["fact_chunks_retained"] >= 2
    assert telemetry["metrics_extracted_count"] >= 2
