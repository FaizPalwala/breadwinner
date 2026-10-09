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
    1. Unquantified bullets lacking verified metrics or system scale (quotes bullet directly).
    2. Architectural tradeoffs or missing technical scope in projects.
    3. Missing market logistics (visa, notice period, location stance).
    """
    metric_pattern = re.compile(
        r"(\d+%\b|\$\d+|\b\d+[kKmMbB]\b|p99|p95|qps|tps|\b\d+\s*(?:ms|sec|min|users|req|members|clients|engineers|people|times|x\b)|\b\d{2,}\b)",
        re.IGNORECASE
    )

    # 1. Identify genuinely unquantified experiences (bullets lacking scale, numbers, or metrics)
    unquantified_exps = []
    for exp in (profile.experiences or []):
        vague_bullets = [b for b in (exp.bullets or []) if not metric_pattern.search(b)]
        if vague_bullets:
            unquantified_exps.append({
                "company": exp.company or "Recent Role",
                "role": exp.role or "Engineer",
                "vague_bullets": vague_bullets[:2]
            })

    # 2. Identify genuinely vague projects (short description, no highlights, no metrics)
    vague_projects = []
    for p in (profile.projects or []):
        has_highlights = bool(p.highlights and any(metric_pattern.search(h) or len(h) > 25 for h in p.highlights))
        has_desc_metric = bool(p.description and metric_pattern.search(p.description))
        is_rich_desc = bool(p.description and len(p.description.strip()) > 75 and p.tech_stack)
        if not (has_highlights or has_desc_metric or is_rich_desc):
            vague_projects.append({
                "name": p.name or "Project",
                "description": p.description or "",
                "tech": p.tech_stack or [],
                "highlights": p.highlights or []
            })

    # If the candidate has existing experiences/projects and nothing is vague, no questions needed!
    has_profile_content = bool(profile.experiences or profile.projects)
    if has_profile_content and not unquantified_exps and not vague_projects:
        return []

    # 3. LLM Proactive Audit if provider is available
    if provider and (unquantified_exps or vague_projects):
        try:
            sys_prompt = (
                "You are Breadwinner's Senior Career Strategist & Anti-Hallucination Ingestion Auditor. "
                "Audit the candidate's verified profile, projects, and dossier to uncover concrete metric gaps. "
                "CRITICAL INSTRUCTION: ONLY generate a question if a role bullet or project description is genuinely vague or lacks quantifiable metrics (XYZ formula: Y = measured metric, Z = technical method). "
                "If an accomplishment or project already specifies concrete metrics, scale, and technical architecture, DO NOT ask about it. "
                "If all items are already sufficiently detailed and quantified, return an empty list: {\"questions\": []}.\n"
                "Rules for questions:\n"
                "1. QUOTE EXACT STATEMENTS: Always quote the candidate's exact bullet or project description.\n"
                "2. PROBE FOR GOOGLE XYZ METRICS: Ask for missing Y (measured metric: % improvement, QPS, latency, volume, cost) and Z (technical method: algorithm, concurrency, architecture).\n"
                "3. ACADEMIC & RESEARCH: If a dissertation or thesis is mentioned, ask for empirical scale, dataset size, benchmark evaluation, or production applicability.\n"
                "4. Return JSON matching: {\"questions\": [{\"id\": \"gap_...\", \"title\": \"...\", \"prompt\": \"...\", \"placeholder\": \"...\"}]}"
            )
            user_prompt = (
                f"CANDIDATE: {profile.full_name} ({profile.title})\n"
                f"EXPERIENCES NEEDING QUANTIFICATION:\n{json.dumps(unquantified_exps[:3], indent=2)}\n"
                f"PROJECTS NEEDING SPECIFICS:\n{json.dumps(vague_projects[:3], indent=2)}\n"
            )
            if dossier_context:
                user_prompt += f"\nDEEP DOSSIER SNIPPET:\n{dossier_context[:1200]}"

            res = provider.generate_json(sys_prompt, user_prompt)
            raw_qs = res.get("questions", [])
            if isinstance(raw_qs, list):
                formatted = []
                for q in raw_qs[:4]:
                    formatted.append({
                        "id": q.get("id", f"gap_{len(formatted)}"),
                        "title": q.get("title", "Career Gap Clarification"),
                        "prompt": q.get("prompt", q.get("question", "")),
                        "placeholder": q.get("placeholder", "e.g., Scaled system to 100k QPS...")
                    })
                return formatted
        except Exception:
            pass

    # 4. Rule-based Heuristic Fallback for genuinely vague items
    questions: List[Dict[str, str]] = []

    for exp_item in unquantified_exps[:2]:
        company = exp_item["company"]
        role = exp_item["role"]
        for b_sample in exp_item["vague_bullets"][:2]:
            b_clean = b_sample.strip()
            if len(b_clean) > 75:
                b_clean = b_clean[:72] + "..."
            prompt_str = (
                f"At {company} as {role}, you mentioned: \"{b_clean}\". "
                f"What concrete scale or impact did this achieve? (e.g. latency reduction, request throughput, or user volume)?"
            )
            questions.append({
                "id": f"metric_gap_{len(questions)}",
                "title": f"Quantifying Impact at {company}",
                "prompt": prompt_str,
                "placeholder": f"e.g. Handled 50k peak QPS at {company}, reducing p99 latency by 35%."
            })
            if len(questions) >= 2:
                break
        if len(questions) >= 2:
            break

    for j, proj_item in enumerate(vague_projects[:2]):
        pname = proj_item["name"]
        desc = proj_item["description"].strip()
        if desc:
            d_sample = desc if len(desc) <= 75 else desc[:72] + "..."
            prompt_str = (
                f"For {pname} (\"{d_sample}\"), what were the critical architectural decisions, "
                f"tradeoffs, or measured throughput metrics?"
            )
        else:
            prompt_str = f"For {pname}, what were the critical architectural decisions, tradeoffs, or challenges you tackled?"

        questions.append({
            "id": f"proj_arch_{j}",
            "title": f"Architecture & Tradeoffs in {pname}",
            "prompt": prompt_str,
            "placeholder": f"e.g. Architected {pname} using event-driven streaming to achieve sub-10ms latency."
        })

    # Only fall back to baseline questions if the profile was completely blank
    if not has_profile_content and not questions:
        return INTERVIEW_QUESTIONS[:3]

    return questions[:4]


def generate_adaptive_questions(
    profile: CandidateProfile,
    provider: Optional[BaseLLMProvider] = None,
    dossier_context: Optional[str] = None
) -> List[Dict[str, str]]:
    """Backward-compatible wrapper for generating gap-filling interview questions."""
    return generate_gap_interview_questions(profile, provider=provider, dossier_context=dossier_context)


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
