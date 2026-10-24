"""Deterministic Career Density Scorer (CDS) for Breadwinner.

Chunks heterogeneous source documents (personal websites, blog posts, dissertations,
LinkedIn exports, portfolios, resumes) and evaluates them using:
- Metric Velocity (M): Quantifiable metrics, scale, throughput, financial impact.
- Action Agency (V): Google XYZ strong action verbs.
- Technical Entity Salience (E): Recognizable platforms, architectures, and stacks.
- Fluff Penalty (F): Pruning tutorial noise, academic boilerplate, and conversational filler.

Partitions content into:
1. Fact Ledger: High-density verified accomplishment nuggets (for profile.json).
2. Narrative Ledger: Qualitative career journey, philosophies, and superpowers (for context.md).
"""

import re
from typing import List, Dict, Tuple, Set, Any, Optional
from dataclasses import dataclass, field


# Google XYZ formula high-agency action verbs
ACTION_VERBS = {
    "architected", "engineered", "spearheaded", "designed", "scaled",
    "optimized", "optimised", "built", "implemented", "reduced", "increased",
    "decreased", "orchestrated", "migrated", "mentored", "automated", "authored",
    "founded", "delivered", "deployed", "transformed", "pioneered",
    "refactored", "standardized", "standardised", "negotiated", "secured", "eliminated",
    "accelerated", "boosted", "consolidated", "directed", "formulated",
    "integrated", "launched", "streamlined", "revamped", "unlocked",
    "developed", "achieved", "executed", "configured", "benchmarked",
    "evaluated", "trained", "quantized", "ablated", "finetuned", "fine-tuned",
    "curated", "stabilized", "stabilised", "reconciled", "resolved",
    "partitioned", "provisioned", "shipped", "modernised", "modernized",
    "redesigned", "rearchitected"
}

# Recognizable technical entities, tools, and architectures
TECHNICAL_ENTITIES = {
    "python", "typescript", "javascript", "golang", "go", "rust", "c++", "c#", "java", "sql",
    "aws", "gcp", "azure", "kubernetes", "k8s", "docker", "terraform", "linux", "unix",
    "postgres", "postgresql", "redis", "kafka", "cockroachdb", "mongodb", "mysql", "clickhouse",
    "snowflake", "bigquery", "cassandra", "dynamodb", "elasticsearch", "opensearch",
    "microservices", "event-driven", "distributed systems", "ci/cd", "graphql", "rest", "grpc",
    "fastapi", "django", "flask", "react", "next.js", "node.js", "vue", "angular", "tailwind",
    "pytorch", "tensorflow", "llm", "rag", "langchain", "transformers", "vector db",
    "raft", "paxos", "consensus", "high-availability", "low-latency", "concurrency", "qps",
    "vllm", "mlx", "metal", "triton", "apple mlx", "langgraph", "diffusers", "instantid",
    "huggingface", "onnx", "polars", "webrtc", "openmp", "cuda", "simd", "pydantic"
}

# Negative fluff patterns: Tutorials, personal blog filler, dissertation thesis boilerplate
FLUFF_PATTERNS = [
    r"\btutorial\b",
    r"\bhow to (?:install|build|create|set up|configure)\b",
    r"\bstep \d+\b",
    r"\bnpm install\b|\bpip install\b|\bgit clone\b|\bdocker run\b",
    r"\bgetting started with\b",
    r"\bin this article\b|\bin this post\b|\bin this tutorial\b|\bin this guide\b",
    r"\bclick (?:here|below|the link)\b",
    r"\bin my opinion\b|\bi believe that\b|\bcoffee\b|\bweekend\b|\bmusings\b",
    r"\bthis dissertation is submitted\b|\bin partial fulfillment\b",
    r"\bliterature review\b|\bchapter \d+\b|\btable of contents\b|\backnowledgements\b",
    r"\bdoctoral thesis\b|\bmaster(?:'s)? thesis\b|\bproceedings of\b",
    r"\bdisclaimer: views are (?:my own|personal)\b"
]

METRIC_REGEX = re.compile(
    r"\b\d+[%kKmMbBxX]?\b|\$\d+[\d,]*|\b\d+\.\d+\b|\b\d+\s*(?:ms|seconds|s|minutes|users|qps|rps|tps|gb|tb|pb|req/s|engineers|clients|members|stars|forks|downloads|weekly|monthly|annually)\b",
    re.IGNORECASE
)

# True impact metric patterns filtering out incidental calendar years and version strings
TRUE_IMPACT_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?%\+?", re.IGNORECASE),  # Percentages (45%, 90%+)
    re.compile(r"\b\d+x\b|\b\d+X\b"),  # Multipliers (10x)
    re.compile(r"[\$£€¥]\s*\d+[\d,.]*[kKmMbB]?", re.IGNORECASE),  # Currency ($100k, £500k)
    re.compile(r"\b\d+[\d,.]*\s*[kKmMbB]\b"),  # Large quantities (10M, 500k)
    re.compile(r"\b\d{1,3}(?:,\d{3})+\b"),  # Formatted numbers (75,000, 1,000,000)
    re.compile(r"\b\d+\s*gpu[- ]hours?\b", re.IGNORECASE),  # GPU hours
    re.compile(r"\b(?:auc|f1|accuracy|loss|precision|recall|perplexity)\b", re.IGNORECASE),  # Model metrics
    re.compile(r"\b\d+[bBmM]\s*(?:parameters|tokens|weights)\b", re.IGNORECASE),  # LLM scale
    re.compile(r"\b(?:sub-)?\d+\+?\s*(?:events|users|requests|qps|rps|tps|ms|seconds|minutes|hours|days|engineers|services|nodes|clusters)\b", re.IGNORECASE),
    re.compile(r"\b\d+\+?\s*(?:[a-zA-Z-]+\s+)?(?:records|anomalies|incidents|features|releases|cycles|microservices|claims|endpoints|tickets|prs|pipelines|portraits|members)\b", re.IGNORECASE),
    re.compile(r"\b(?:zero|single-digit)\s*(?:downtime|latency)\b", re.IGNORECASE),
    re.compile(r"\bp9[0-9]\b", re.IGNORECASE),  # p99, p95
    re.compile(r"\b9\d(?:\.\d+)?%\s*(?:uptime|availability)?\b", re.IGNORECASE)  # 99.999% uptime
]


def is_true_impact_metric(token: str) -> bool:
    """Check if token is a genuine accomplishment metric, filtering out calendar years and versions."""
    token = token.strip()
    # Reject 4-digit calendar years
    if re.fullmatch(r"(?:19|20)\d{2}", token):
        return False
    # Reject standalone software versions like 3.11, 2.0
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", token):
        return False
    return any(p.search(token) for p in TRUE_IMPACT_PATTERNS)


def extract_bullet_action_verb(bullet: str) -> Optional[str]:
    """Extract action verb from bullet, handling bold category lead-ins and markdown formatting."""
    clean = re.sub(r"^(?:[-*•]|\d+\.)\s+", "", bullet.strip()).strip()
    # Remove leading bold or italic category tags, e.g. **Enterprise Stabilization:** Action verb...
    clean = re.sub(r"^(?:\*\*.*?\*\*|\*.*?\*|\[.*?\])\s*:?\s*", "", clean).strip()
    match = re.findall(r"^[A-Za-z]+(?:-[A-Za-z]+)?", clean)
    if match and match[0].lower() in ACTION_VERBS:
        return match[0].lower()
    return None


def is_xyz_compliant_bullet(bullet: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Determine if a bullet satisfies Google XYZ formula [Accomplished X] as measured by [Y], by doing [Z]."""
    verb = extract_bullet_action_verb(bullet)
    # Search for true impact metrics in the bullet
    found_metric = None
    for pattern in TRUE_IMPACT_PATTERNS:
        match = pattern.search(bullet)
        if match:
            matched_str = match.group(0)
            if is_true_impact_metric(matched_str):
                found_metric = matched_str
                break

    is_compliant = bool(verb and found_metric)
    return is_compliant, verb, found_metric


def extract_achievement_bullets(text: str) -> List[str]:
    """Extract genuine achievement bullets from resume text, filtering out skill lists and degrees."""
    raw_bullets = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line):
            cleaned = re.sub(r"^(?:[-*•]|\d+\.)\s+", "", line).strip()
            # Skip short fragments or skills list lines like "Languages: Python, Go"
            if len(cleaned) < 20:
                continue
            if re.match(r"^(?:languages|technologies|tools|skills|frameworks|databases|certifications|education):", cleaned, re.IGNORECASE):
                continue
            # Skip degree lines
            if re.search(r"\b(?:bachelor|master|bsc|msc|phd|b\.s\.|m\.s\.|ba|ma)\b", cleaned, re.IGNORECASE) and not re.search(r"\b(?:architected|engineered|developed|built)\b", cleaned, re.IGNORECASE):
                continue
            raw_bullets.append(cleaned)
    return raw_bullets


@dataclass
class DiscourseChunk:
    """A scored semantic chunk from ingested text."""
    text: str
    kind: str  # 'bullet', 'paragraph', 'header', 'project', 'meta'
    metric_velocity: float
    action_agency: float
    entity_salience: float
    fluff_penalty: float
    composite_score: float
    classification: str  # 'fact', 'narrative', 'fluff'
    matched_metrics: List[str] = field(default_factory=list)
    matched_verbs: List[str] = field(default_factory=list)
    matched_entities: List[str] = field(default_factory=list)


class CareerDensityScorer:
    """Evaluates, ranks, and filters candidate discourse chunks for anti-hallucination ingestion."""

    @classmethod
    def chunk_text(cls, raw_text: str) -> List[str]:
        """Segment raw text into structured discourse units (headers, bullets, paragraphs)."""
        lines = [line.strip() for line in raw_text.splitlines()]
        chunks: List[str] = []
        current_chunk: List[str] = []

        for line in lines:
            if not line:
                if current_chunk:
                    joined = " ".join(current_chunk).strip()
                    if joined:
                        chunks.append(joined)
                    current_chunk = []
                continue

            # Header or section break
            if line.startswith("#") or line.startswith("===") or line.startswith("---"):
                if current_chunk:
                    joined = " ".join(current_chunk).strip()
                    if joined:
                        chunks.append(joined)
                    current_chunk = []
                chunks.append(line)
                continue

            # Bullet points: keep each distinct bullet as its own chunk
            if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line):
                if current_chunk:
                    joined = " ".join(current_chunk).strip()
                    if joined:
                        chunks.append(joined)
                    current_chunk = []
                clean_bullet = re.sub(r"^[-*•\d.]+\s*", "", line).strip()
                if clean_bullet:
                    chunks.append(clean_bullet)
                continue

            current_chunk.append(line)

        if current_chunk:
            joined = " ".join(current_chunk).strip()
            if joined:
                chunks.append(joined)

        return chunks

    @classmethod
    def score_chunk(cls, text: str) -> DiscourseChunk:
        """Score an individual chunk for metric velocity, agency, entity salience, and fluff penalty."""
        clean_lower = text.lower()
        words = set(re.findall(r"\b[a-zA-Z0-9+#.-]+\b", clean_lower))

        # 1. Metric Velocity (M)
        metric_matches = METRIC_REGEX.findall(text)
        metric_count = len(metric_matches)
        m_score = min(metric_count * 2.5, 10.0)

        # 2. Action Agency (V)
        found_verbs = [v for v in ACTION_VERBS if v in words]
        v_score = min(len(found_verbs) * 2.0, 6.0)

        # 3. Technical Entity Salience (E)
        found_entities = [e for e in TECHNICAL_ENTITIES if e in words]
        e_score = min(len(found_entities) * 1.5, 6.0)

        # 4. Fluff Penalty (F)
        fluff_hits = 0
        for pattern in FLUFF_PATTERNS:
            if re.search(pattern, clean_lower):
                fluff_hits += 1
        f_score = fluff_hits * 4.0

        # Structural kind detection
        kind = "paragraph"
        if text.startswith("#"):
            kind = "header"
        elif len(text.split()) < 30 and (metric_count > 0 or len(found_verbs) > 0):
            kind = "bullet"

        # Composite Density Score
        composite = (m_score * 1.5) + (v_score * 1.2) + (e_score * 1.0) - f_score

        # Classification
        if f_score >= 4.0 or composite <= 0:
            classification = "fluff"
        elif composite >= 3.5 or (metric_count > 0 and len(found_verbs) > 0):
            classification = "fact"
        else:
            classification = "narrative"

        return DiscourseChunk(
            text=text,
            kind=kind,
            metric_velocity=round(m_score, 2),
            action_agency=round(v_score, 2),
            entity_salience=round(e_score, 2),
            fluff_penalty=round(f_score, 2),
            composite_score=round(composite, 2),
            classification=classification,
            matched_metrics=metric_matches,
            matched_verbs=found_verbs,
            matched_entities=found_entities
        )

    @classmethod
    def distill(
        cls,
        raw_text: str,
        max_fact_chars: int = 16000,
        max_narrative_chars: int = 12000
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Distill raw ingested documents into high-fidelity Fact Ledger & Narrative Ledger.

        Returns:
            (fact_ledger_text, narrative_ledger_text, telemetry_dict)
        """
        raw_chunks = cls.chunk_text(raw_text)
        scored_chunks = [cls.score_chunk(c) for c in raw_chunks if len(c.strip()) > 15]

        facts: List[DiscourseChunk] = []
        narratives: List[DiscourseChunk] = []
        fluff_pruned: int = 0

        for sc in scored_chunks:
            if sc.classification == "fluff":
                fluff_pruned += 1
            elif sc.classification == "fact":
                facts.append(sc)
            else:
                narratives.append(sc)

        # Sort facts by highest composite density
        facts.sort(key=lambda x: x.composite_score, reverse=True)

        # Pack fact ledger within budget
        fact_lines: List[str] = []
        curr_fact_len = 0
        for f in facts:
            if curr_fact_len + len(f.text) > max_fact_chars:
                break
            fact_lines.append(f"- {f.text}")
            curr_fact_len += len(f.text)

        # Pack narrative ledger within budget
        narrative_lines: List[str] = []
        curr_narr_len = 0
        for n in narratives:
            if curr_narr_len + len(n.text) > max_narrative_chars:
                break
            narrative_lines.append(n.text)
            curr_narr_len += len(n.text)

        fact_text = "\n".join(fact_lines)
        narrative_text = "\n\n".join(narrative_lines)

        telemetry = {
            "total_chunks_scanned": len(scored_chunks),
            "fact_chunks_retained": len(fact_lines),
            "narrative_chunks_retained": len(narrative_lines),
            "fluff_chunks_pruned": fluff_pruned,
            "top_density_score": facts[0].composite_score if facts else 0.0,
            "metrics_extracted_count": sum(len(f.matched_metrics) for f in facts)
        }

        return fact_text, narrative_text, telemetry
