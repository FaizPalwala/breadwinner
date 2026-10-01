"""Deterministic Job Description Deconstruction & Technical Entity Extraction Engine.

Extracts structured technical requirements, must-haves, nice-to-haves, scale constraints,
and domain architecture from raw job postings before tailoring to eliminate LLM drift.
"""

import re
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from breadwinner.core.models import JobPosting
from breadwinner.providers.base import BaseLLMProvider


class DeconstructedJob(BaseModel):
    """Structured, verifiable representation of a job description."""
    job_title: str
    company: str
    domain: str = "General Software & Systems"
    hard_must_haves: List[str] = Field(default_factory=list)
    nice_to_haves: List[str] = Field(default_factory=list)
    technical_stack: List[str] = Field(default_factory=list)
    scale_constraints: List[str] = Field(default_factory=list)
    core_responsibilities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class JDDeconstructor:
    """Deconstructs job postings into deterministic requirements and architectural constraints."""

    # Common technology keywords to look for deterministically
    TECH_PATTERNS = [
        "python", "go", "golang", "rust", "c\\+\\+", "c#", "java", "typescript", "javascript",
        "react", "next\\.js", "vue", "angular", "node\\.js", "django", "fastapi", "spring boot",
        "kubernetes", "docker", "terraform", "ansible", "aws", "gcp", "azure",
        "postgresql", "postgres", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
        "kafka", "rabbitmq", "pulsar", "sqs", "grpc", "graphql", "rest",
        "pytorch", "tensorflow", "scikit-learn", "llm", "rag", "transformers",
        "spark", "flink", "airflow", "snowflake", "databricks", "bigquery",
        "elasticsearch", "opensearch", "prometheus", "grafana", "datadog"
    ]

    SCALE_PATTERNS = [
        r"\b\d+[\+]?\s*(?:qps|tps|rps)\b",
        r"\b(?:sub|under)?-?\d+\s*ms\b",
        r"\b\d+[\+]?\s*(?:tb|pb|gb)\b",
        r"\b\d+[\+]?\s*(?:million|billion|k|m|b)\s*(?:users|events|records|requests|dau|mau)\b",
        r"\b99\.9[0-9]*%\s*(?:uptime|availability|sla)\b",
        r"\bhigh[- ]throughput\b",
        r"\blow[- ]latency\b",
        r"\bdistributed systems\b",
        r"\bpetabyte[- ]scale\b"
    ]

    @classmethod
    def deconstruct(
        cls,
        job: JobPosting,
        provider: Optional[BaseLLMProvider] = None
    ) -> DeconstructedJob:
        """Deconstruct job posting into structured technical entities and constraints."""
        clean_text = (job.raw_text or "").strip()
        if not clean_text:
            return DeconstructedJob(
                job_title=job.title,
                company=job.company,
                domain="Unspecified",
                keywords=[]
            )

        # 1. LLM Structured Extraction if provider is available
        if provider:
            try:
                sys_prompt = (
                    "You are Breadwinner's Deterministic Job Description Deconstructor. "
                    "Your role is to perform Stage 1 Technical Entity Extraction on a job description. "
                    "Extract ONLY verifiable technical entities, requirements, and constraints directly stated in the text. "
                    "Do NOT speculate, do NOT write resume bullets, and do NOT inject outside assumptions.\n\n"
                    "SCHEMA SPECIFICATION:\n"
                    "- 'job_title': Target role title.\n"
                    "- 'company': Company name.\n"
                    "- 'domain': Core engineering domain (e.g. 'Distributed Systems & Data Infrastructure', 'Applied AI & ML Platform', 'Fintech Payments').\n"
                    "- 'hard_must_haves': Non-negotiable requirements (e.g. '5+ years backend Go', 'Production Kubernetes cluster management').\n"
                    "- 'nice_to_haves': Optional qualifications or pluses.\n"
                    "- 'technical_stack': Exact tools, frameworks, and programming languages demanded.\n"
                    "- 'scale_constraints': Specific throughput, latency, concurrency, or data volume scale requirements.\n"
                    "- 'core_responsibilities': Top 3-5 primary engineering duties.\n"
                    "- 'keywords': High-value ATS keyword tokens for syntactic matching.\n\n"
                    "Respond strictly in valid JSON matching the schema."
                )

                user_prompt = (
                    f"COMPANY: {job.company}\n"
                    f"TITLE: {job.title}\n"
                    f"JOB POSTING TEXT:\n{clean_text[:4000]}"
                )

                res = provider.generate_json(sys_prompt, user_prompt)
                if isinstance(res, dict) and "hard_must_haves" in res:
                    return DeconstructedJob(
                        job_title=res.get("job_title", job.title),
                        company=res.get("company", job.company),
                        domain=res.get("domain", "General Engineering"),
                        hard_must_haves=res.get("hard_must_haves", []),
                        nice_to_haves=res.get("nice_to_haves", []),
                        technical_stack=res.get("technical_stack", []),
                        scale_constraints=res.get("scale_constraints", []),
                        core_responsibilities=res.get("core_responsibilities", []),
                        keywords=res.get("keywords", [])
                    )
            except Exception:
                pass

        # 2. Deterministic Heuristic Extraction Fallback
        return cls._heuristic_deconstruct(job)

    @classmethod
    def _heuristic_deconstruct(cls, job: JobPosting) -> DeconstructedJob:
        """Deterministic regex-based heuristic entity extractor when offline or without provider."""
        text = job.raw_text or ""
        text_lower = text.lower()

        # Extract technical stack
        found_tech: Set[str] = set()
        for pat in cls.TECH_PATTERNS:
            if re.search(r"\b" + pat + r"\b", text_lower):
                # Clean display name
                clean_name = pat.replace("\\.", ".").replace("\\+", "+")
                if clean_name == "golang":
                    clean_name = "Go"
                elif clean_name == "python":
                    clean_name = "Python"
                elif clean_name == "kubernetes":
                    clean_name = "Kubernetes"
                elif clean_name == "docker":
                    clean_name = "Docker"
                elif clean_name == "aws":
                    clean_name = "AWS"
                elif clean_name == "gcp":
                    clean_name = "GCP"
                else:
                    clean_name = clean_name.capitalize()
                found_tech.add(clean_name)

        # Extract scale constraints
        found_scale: Set[str] = set()
        for pat in cls.SCALE_PATTERNS:
            matches = re.findall(pat, text_lower)
            for m in matches:
                found_scale.add(m.strip())

        # Section-based requirement parsing
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        must_haves: List[str] = []
        nice_to_haves: List[str] = []
        responsibilities: List[str] = []

        current_section = "general"
        for line in lines:
            line_low = line.lower()
            if any(h in line_low for h in ["requirement", "qualification", "must have", "what you need", "what you'll bring"]):
                current_section = "requirements"
                continue
            elif any(h in line_low for h in ["nice to have", "bonus", "preferred", "plus"]):
                current_section = "nice_to_have"
                continue
            elif any(h in line_low for h in ["responsibilit", "what you'll do", "the role", "what you will do"]):
                current_section = "responsibilities"
                continue

            # Bullet detection
            if line.startswith(("-", "*", "•", "–")) or re.match(r"^\d+[\.\)]", line):
                clean_line = re.sub(r"^[-*•–\d\.\)\s]+", "", line).strip()
                if len(clean_line) > 10:
                    if current_section == "requirements":
                        if len(must_haves) < 6:
                            must_haves.append(clean_line)
                    elif current_section == "nice_to_have":
                        if len(nice_to_haves) < 4:
                            nice_to_haves.append(clean_line)
                    elif current_section == "responsibilities":
                        if len(responsibilities) < 5:
                            responsibilities.append(clean_line)

        # Fallback if no explicit section headers found
        if not must_haves and not responsibilities:
            for line in lines:
                if (line.startswith(("-", "*", "•")) and len(line) > 20) and len(must_haves) < 5:
                    clean_line = re.sub(r"^[-*•\s]+", "", line).strip()
                    must_haves.append(clean_line)

        # Determine domain
        domain = "General Software Engineering"
        if any(w in text_lower for w in ["machine learning", "deep learning", "nlp", "llm", "computer vision", "ai engineer"]):
            domain = "Applied AI & Machine Learning"
        elif any(w in text_lower for w in ["distributed systems", "platform", "infrastructure", "devops", "sre", "reliability"]):
            domain = "Platform & Distributed Systems"
        elif any(w in text_lower for w in ["frontend", "full stack", "react", "ui/ux", "web"]):
            domain = "Full Stack & Web Architecture"
        elif any(w in text_lower for w in ["security", "infosec", "appsec", "cryptography"]):
            domain = "Security & Systems Resilience"

        # Keywords set
        keywords = sorted(list(found_tech | {w.capitalize() for w in list(found_scale)[:5]}))

        return DeconstructedJob(
            job_title=job.title,
            company=job.company,
            domain=domain,
            hard_must_haves=must_haves,
            nice_to_haves=nice_to_haves,
            technical_stack=sorted(list(found_tech)),
            scale_constraints=sorted(list(found_scale)),
            core_responsibilities=responsibilities,
            keywords=keywords
        )
