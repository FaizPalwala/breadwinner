"""Candidate ingestion gap interview and personal context synthesis module."""

import re
import json
from typing import Dict, Any, Optional, List
from breadwinner.core.models import CandidateProfile
from breadwinner.providers.base import BaseLLMProvider


INTERVIEW_QUESTIONS = [
    {
        "id": "target_roles",
        "title": "Target Roles & Non-Negotiables",
        "prompt": "What specific job titles or engineering domains are you targeting? What roles or technologies do you want to avoid?",
        "placeholder": "e.g. Senior Backend / Distributed Systems Engineer. Avoid pure frontend or DevOps-only roles."
    },
    {
        "id": "star_stories",
        "title": "Hidden Wins & High-Impact Proof Points",
        "prompt": "What are 1 or 2 accomplishments or complex technical challenges you solved that resume bullets don't fully capture?",
        "placeholder": "e.g. Diagnosed a distributed race condition saving $50k/mo in cloud egress; built an internal agent tool used by 40 engineers."
    },
    {
        "id": "logistics_guardrails",
        "title": "Logistics, Work Setup & Guardrails",
        "prompt": "What are your practical constraints? (Visa/work status, hybrid vs remote, target salary, relocation)?",
        "placeholder": "e.g. UK citizen, no sponsorship needed. Remote or London hybrid. Minimum £95,000 base."
    }
]


def generate_gap_interview_questions(
    profile: CandidateProfile,
    provider: Optional[BaseLLMProvider] = None,
    dossier_context: Optional[str] = None
) -> List[Dict[str, str]]:
    """Proactively audit candidate profile and dossier to generate targeted gap-filling interview questions.

    Identifies:
    1. Unquantified bullets lacking verified metrics or system scale.
    2. Architectural tradeoffs or missing technical scope in projects.
    3. Missing market logistics (visa, notice period, location stance).
    """
    metric_pattern = re.compile(r"(\d+%?|\$\d+|\b[0-9]+[kKmMbB]?\b|p99|p95|qps|tps|\b[0-9]+\s*(?:ms|sec|min|users|req))", re.IGNORECASE)

    # 1. Collect unquantified or vague experiences
    unquantified_exps = []
    for exp in (profile.experiences or []):
        vague_bullets = [b for b in (exp.bullets or []) if not metric_pattern.search(b)]
        if vague_bullets or len(exp.bullets or []) <= 1:
            unquantified_exps.append({
                "company": exp.company,
                "role": exp.role,
                "bullets": exp.bullets[:2]
            })

    # 2. LLM Proactive Audit if provider is available
    if provider:
        try:
            sys_prompt = (
                "You are Breadwinner's Senior Career Strategist & Anti-Hallucination Ingestion Auditor. "
                "Audit the candidate's verified profile and dossier to uncover gaps, unquantified claims, missing architecture, and vague logistics. "
                "Generate 2 to 4 proactive, high-leverage probing questions. "
                "Rules:\n"
                "1. UNQUANTIFIED BULLETS: Target specific vague statements lacking numbers, throughput, latency, or scale. Probe for exact metrics.\n"
                "2. ARCHITECTURAL TRADEOFFS: Probe for distributed decisions, concurrency models, or database indexing in stated projects.\n"
                "3. MARKET LOGISTICS: Probe for work authorization, notice period, and hybrid/remote constraints if unstated.\n"
                "Return JSON matching: {\"questions\": [{\"id\": \"gap_...\", \"title\": \"...\", \"prompt\": \"...\", \"placeholder\": \"...\"}]}"
            )
            user_prompt = (
                f"CANDIDATE: {profile.full_name} ({profile.title})\n"
                f"EXPERIENCES NEEDING QUANTIFICATION:\n{json.dumps(unquantified_exps[:3], indent=2)}\n"
                f"PROJECTS:\n{json.dumps([{'name': p.name, 'tech': p.tech_stack} for p in (profile.projects or [])[:3]], indent=2)}\n"
            )
            if dossier_context:
                user_prompt += f"\nDEEP DOSSIER SNIPPET:\n{dossier_context[:1000]}"

            res = provider.generate_json(sys_prompt, user_prompt)
            raw_qs = res.get("questions", [])
            if isinstance(raw_qs, list) and len(raw_qs) >= 2:
                formatted = []
                for q in raw_qs[:4]:
                    formatted.append({
                        "id": q.get("id", f"gap_{len(formatted)}"),
                        "title": q.get("title", "Career Gap Clarification"),
                        "prompt": q.get("prompt", q.get("question", "")),
                        "placeholder": q.get("placeholder", "e.g., Scaled system to 100k QPS...")
                    })
                if len(formatted) >= 2:
                    return formatted
        except Exception:
            pass

    # 3. Rule-based Heuristic Fallback
    questions: List[Dict[str, str]] = []

    for i, exp in enumerate(profile.experiences or []):
        has_metrics = any(bool(metric_pattern.search(b)) for b in (exp.bullets or []))
        if not has_metrics or len(exp.bullets or []) <= 1:
            company = exp.company or "your recent role"
            role = exp.role or "Engineer"
            questions.append({
                "id": f"metric_gap_{i}",
                "title": f"Quantifying Impact at {company}",
                "prompt": f"At {company} as {role}, what concrete metrics, scale, throughput, or latency did you achieve?",
                "placeholder": f"e.g. Scaled system throughput to handle peak load at {company}, reducing p99 latency by 35%."
            })
            if len(questions) >= 2:
                break

    for j, proj in enumerate(profile.projects or []):
        pname = proj.name or f"Project #{j+1}"
        questions.append({
            "id": f"proj_arch_{j}",
            "title": f"Architecture & Tradeoffs in {pname}",
            "prompt": f"For {pname}, what were the critical architectural decisions, tradeoffs, or challenges you tackled?",
            "placeholder": f"e.g. Architected {pname} using event-driven streaming to achieve near-zero latency."
        })
        if len(questions) >= 4:
            break

    # Ensure baseline questions fill in if profile was sparse
    if len(questions) < 2:
        for q in INTERVIEW_QUESTIONS:
            if not any(existing["id"] == q["id"] for existing in questions):
                questions.append(q)
            if len(questions) >= 3:
                break

    return questions[:4]


def generate_adaptive_questions(
    profile: CandidateProfile,
    provider: Optional[BaseLLMProvider] = None,
) -> List[Dict[str, str]]:
    """Backward-compatible wrapper for generating gap-filling interview questions."""
    return generate_gap_interview_questions(profile, provider=provider)


def synthesize_context(
    profile: CandidateProfile,
    answers: Dict[str, str],
    provider: BaseLLMProvider
) -> str:
    """Transform conversational interview answers and gap resolutions into structured personal directives (context.md)."""
    sys_prompt = """You are Breadwinner's Career Strategy Director.
Your task is to synthesize conversational interview responses from a candidate into a clean, authoritative Markdown context document.
This document (context.md) acts as high-priority guardrails during automated resume tailoring and cover letter copywriting.

STRUCTURE REQUIREMENTS:
# Personal Directives & Career Guardrails

## Strategic Positioning & Role Targeting
- Bullet points summarizing ideal roles, seniority, and non-negotiable boundaries.

## Key Highlight Stories & Core Differentiators (STAR)
- Concrete technical stories, metrics, throughput, scale, or challenges solved that should be highlighted.

## Practical Guardrails & Work Logistics
- Visa/work authorization status, notice period availability, location preferences, salary floors, and contract types.

Tone: Professional, direct, factual, zero fluff.
"""

    user_prompt = f"""CANDIDATE: {profile.full_name} ({profile.title})

INTERVIEW RESPONSES & GAP RESOLUTIONS:
""" + "\n\n".join(f"{k.upper()}:\n{v}" for k, v in answers.items() if v.strip()) + "\n\nCompile into the structured Markdown format."

    return provider.generate_text(sys_prompt, user_prompt, temperature=0.1).strip()
