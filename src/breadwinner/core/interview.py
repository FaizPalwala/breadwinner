import re
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


def synthesize_context(
    profile: CandidateProfile,
    answers: Dict[str, str],
    provider: BaseLLMProvider
) -> str:
    """Transform conversational interview answers into structured personal directives (context.md)."""
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
- Visa/work authorization status, location preferences, salary floors, and contract types.

Tone: Professional, direct, factual, zero fluff.
"""

    user_prompt = f"""CANDIDATE: {profile.full_name} ({profile.title})

INTERVIEW RESPONSES:
1. Target Roles & Boundaries:
{answers.get("target_roles", "None specified.")}

2. Hidden Wins & Impact Stories:
{answers.get("star_stories", "None specified.")}

3. Logistics & Guardrails:
{answers.get("logistics_guardrails", "None specified.")}

Compile into the structured Markdown format.
"""

    return provider.generate_text(sys_prompt, user_prompt, temperature=0.3).strip()


def generate_adaptive_questions(
    profile: CandidateProfile,
    provider: Optional[BaseLLMProvider] = None,
) -> List[Dict[str, str]]:
    """Generate adaptive interview questions based on candidate profile gaps, weak metrics, or technical projects."""
    questions: List[Dict[str, str]] = []

    # 1. Detect work experiences missing quantifiable metrics
    metric_pattern = re.compile(r"(\d+%?|\$\d+|\b[0-9]+[kKmMbB]?\b|reduced|increased|scaled|optimized)", re.IGNORECASE)
    for i, exp in enumerate(profile.experiences or []):
        has_metrics = any(bool(metric_pattern.search(b)) for b in (exp.bullets or []))
        if not has_metrics or len(exp.bullets or []) <= 1:
            company = exp.company or "your recent role"
            role = exp.role or "Engineer"
            questions.append({
                "id": f"metric_gap_{i}",
                "title": f"Quantifying Impact at {company}",
                "prompt": f"At {company} as {role}, what concrete metrics, scale, throughput, or revenue impact did you achieve?",
                "placeholder": f"e.g. Scaled system throughput to handle peak load at {company}, reducing p99 latency by 35%."
            })
            if len(questions) >= 3:
                break

    # 2. Deep dive into architectural tradeoffs for technical projects
    for j, proj in enumerate(profile.projects or []):
        pname = proj.name or f"Project #{j+1}"
        questions.append({
            "id": f"proj_arch_{j}",
            "title": f"Architecture & Tradeoffs in {pname}",
            "prompt": f"For {pname}, what were the critical architectural decisions, tradeoffs, or challenges you tackled?",
            "placeholder": f"e.g. Architected {pname} using event-driven streaming to achieve near-zero latency."
        })
        if len(questions) >= 5:
            break

    # 3. Ensure between 2 and 6 questions using baseline questions
    if len(questions) < 2:
        for q in INTERVIEW_QUESTIONS:
            if not any(existing["id"] == q["id"] for existing in questions):
                questions.append(q)
            if len(questions) >= 2:
                break

    return questions[:6]

