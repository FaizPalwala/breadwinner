"""Interactive Baker's Interview loop for discovering qualitative career context and guardrails."""

from typing import Dict, Any, Optional
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
