"""Persona and narrative controller."""

from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import yaml
from pydantic import BaseModel

from breadwinner.core.models import JobPosting, CandidateProfile
from breadwinner.providers.base import BaseLLMProvider


class Persona(BaseModel):
    name: str
    slug: str
    description: str
    tone: str
    system_directives: str
    cover_letter_directives: str
    market: str = "Global"
    logistics: Dict[str, Any] = {}
    archetype: str = "Generalist"
    banned_words: List[str] = []


class PersonaManager:
    """Manages loading, resolving, and persisting narrative personas."""

    @classmethod
    def get_built_in_dir(cls) -> Path:
        return Path(__file__).parent.parent / "personas"

    @classmethod
    def get_user_dir(cls) -> Path:
        return Path("user_personas")

    @classmethod
    def load_persona(cls, persona_name: str, custom_dir: Optional[Path] = None) -> Persona:
        """Load persona by name (checking user_personas first, then built-in)."""
        # 1. If path directly given
        p_path = Path(persona_name)
        if p_path.is_file():
            return cls._load_file(p_path)

        # 2. Check custom dir if provided
        if custom_dir and (custom_dir / f"{persona_name}.yaml").is_file():
            return cls._load_file(custom_dir / f"{persona_name}.yaml")

        # 3. Check local user_personas directory
        user_file = cls.get_user_dir() / f"{persona_name}.yaml"
        if user_file.is_file():
            return cls._load_file(user_file)

        # 4. Check built-in personas
        built_in = cls.get_built_in_dir() / f"{persona_name}.yaml"
        if built_in.is_file():
            return cls._load_file(built_in)

        # Fallback aliases
        alias_map = {
            "tech": "tech_ai",
            "ai": "tech_ai",
            "sde": "tech_ai",
            "uk": "uk_eu_tech",
            "uk_tech": "uk_eu_tech",
            "eu": "uk_eu_tech",
            "india": "india_tech",
            "in": "india_tech",
            "c2c": "us_remote_c2c",
            "us_remote": "us_remote_c2c",
            "contractor": "us_remote_c2c",
            "staff": "staff_architect",
            "architect": "staff_architect",
            "principal": "staff_architect",
            "founding": "founding_engineer",
            "startup": "founding_engineer",
            "admin": "bridging_admin",
            "parttime": "bridging_admin",
            "service": "hospitality"
        }
        if persona_name in alias_map:
            return cls.load_persona(alias_map[persona_name], custom_dir)

        available = ", ".join(sorted(cls.list_personas().keys())) or "tech_ai, bridging_admin, hospitality"
        raise ValueError(f"Persona '{persona_name}' not found. Available: {available}")

    @classmethod
    def _load_file(cls, path: Path) -> Persona:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Persona(**data)

    @classmethod
    def list_personas(cls) -> Dict[str, str]:
        """Return dict of available personas (user custom personas override built-in)."""
        result = {}
        # Built-in first
        for p_file in cls.get_built_in_dir().glob("*.yaml"):
            try:
                p = cls._load_file(p_file)
                result[p.slug] = p.description
            except Exception:
                pass

        # User custom personas override or add
        if cls.get_user_dir().exists():
            for p_file in cls.get_user_dir().glob("*.yaml"):
                try:
                    p = cls._load_file(p_file)
                    result[p.slug] = f"{p.description} [bold green](Customized)[/bold green]"
                except Exception:
                    pass

        return result

    @classmethod
    def save_persona(cls, persona: Persona, custom_dir: Optional[Path] = None) -> Path:
        """Persist a persona definition to user_personas/<slug>.yaml."""
        target_dir = custom_dir or cls.get_user_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{persona.slug}.yaml"
        data = persona.model_dump()
        file_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return file_path

    @classmethod
    def delete_persona(cls, persona_slug: str, custom_dir: Optional[Path] = None) -> bool:
        """Delete custom persona from user_personas (built-in personas are immutable)."""
        target_dir = custom_dir or cls.get_user_dir()
        file_path = target_dir / f"{persona_slug}.yaml"
        if file_path.is_file():
            file_path.unlink()
            return True
        return False


def generate_job_strategy_questions(
    job: JobPosting,
    profile: Optional[Any] = None,
    persona: Optional[Persona] = None,
    provider: Optional[BaseLLMProvider] = None,
    personal_context: Optional[str] = None
) -> List[Dict[str, str]]:
    """Proactively probe for strategic alignment, technical bridges, and logistical stance between JD, Pantry, and Persona."""
    # Support positional call: generate_job_strategy_questions(job, provider)
    if isinstance(profile, BaseLLMProvider) and provider is None:
        provider = profile
        profile = None

    # 1. Proactive LLM Strategy Discovery if provider is available
    if provider:
        try:
            sys_prompt = (
                "You are Breadwinner's Proactive Career Architect & Tailoring Problem-Solver. "
                "Compare the Target Job Description against the Candidate's Verified Profile, Active Application Class Persona, and Personal Context. "
                "Instead of generic interview questions, proactively discover 2 to 3 sharp, problem-solving discovery questions to resolve tailoring friction: "
                "1. ADJACENT SKILL OR ARCHITECTURAL BRIDGES: Identify where the role requires a technology or pattern adjacent to the candidate's verified stack (e.g. Kafka vs RabbitMQ, Nomad vs K8s). Probe how they want that bridge framed. "
                "2. HERO PROJECT & IMPACT ANCHOR: Identify which verified project or achievement best anchors the narrative for this specific role and probe for the primary technical proof point. "
                "3. LOGISTICAL & MARKET FIT: Address any friction between the role requirements (hybrid schedule, location, seniority level) and candidate's persona/guardrails. "
                "Return JSON matching: {\"questions\": [{\"id\": \"hook\", \"title\": \"...\", \"question\": \"...\", \"placeholder\": \"...\"}]}"
            )

            candidate_summary_bits = []
            if profile and isinstance(profile, CandidateProfile):
                candidate_summary_bits.append(f"Candidate: {profile.full_name} ({profile.title})")
                if profile.projects:
                    proj_names = ", ".join(p.name for p in profile.projects[:3])
                    candidate_summary_bits.append(f"Top Projects: {proj_names}")
                if profile.skills:
                    skill_summary = ", ".join(f"{s.category}: {', '.join(s.skills[:4])}" for s in profile.skills[:3])
                    candidate_summary_bits.append(f"Skills: {skill_summary}")
            if persona:
                candidate_summary_bits.append(f"Application Class Persona: {persona.name} (Market: {persona.market}, Archetype: {persona.archetype})")
                if persona.logistics:
                    candidate_summary_bits.append(f"Persona Logistics: {persona.logistics}")
            if personal_context:
                candidate_summary_bits.append(f"Personal Guardrails: {personal_context[:400]}")

            candidate_block = "\n".join(candidate_summary_bits) if candidate_summary_bits else "General Technical Profile"

            user_prompt = (
                f"TARGET JOB:\nCompany: {job.company}\nTitle: {job.title}\nLocation: {job.location or 'Unspecified'}\nJob Snippet:\n{job.raw_text[:1800]}\n\n"
                f"CANDIDATE SOURCE & STANCE:\n{candidate_block}"
            )

            res = provider.generate_json(sys_prompt, user_prompt)
            raw_qs = res.get("questions", [])
            if isinstance(raw_qs, list) and len(raw_qs) >= 2:
                return raw_qs[:3]
        except Exception:
            pass

    # 2. Dynamic Heuristic / Contextual Fallback
    top_project_name = profile.projects[0].name if (profile and isinstance(profile, CandidateProfile) and profile.projects) else "your primary system"
    proof_prompt = f"Which past project (such as {top_project_name}) best proves you are the ideal {job.title} for {job.company}'s engineering challenges?"

    default_questions = [
        {
            "id": "hook",
            "title": "Strategic Hook & Mission Alignment",
            "question": f"What specific aspect of {job.company}'s product, team, or challenge resonates with you, and what connection should we lead with?",
            "placeholder": f"e.g., Excited by {job.company}'s developer tooling or recent infrastructure scale..."
        },
        {
            "id": "proof",
            "title": "Primary Superpower & Proof Point",
            "question": proof_prompt,
            "placeholder": f"e.g., Scaling {top_project_name} to 1M QPS; cutting p99 latency by 40%..."
        },
        {
            "id": "tactics",
            "title": "Tactical Framing & Skill Bridges",
            "question": f"Are there specific skills or architectural tools to bridge (e.g. adjacent technologies demanded in {job.company}'s stack), or unique constraints to highlight?",
            "placeholder": "e.g., Frame RabbitMQ experience as event-driven streaming equivalent to Kafka; emphasize systems architecture over frontend..."
        }
    ]

    return default_questions


def synthesize_job_directives(
    job: JobPosting,
    answers: Dict[str, str],
    profile: Optional[Any] = None,
    persona: Optional[Persona] = None,
    provider: Optional[BaseLLMProvider] = None
) -> str:
    """Synthesize candidate answers, persona application class, and job context into prioritized directives."""
    # Support positional call: synthesize_job_directives(job, answers, provider)
    if isinstance(profile, BaseLLMProvider) and provider is None:
        provider = profile
        profile = None
    clean_lines = []
    if answers.get("hook"):
        clean_lines.append(f"- STRATEGIC HOOK: Focus application on candidate's alignment with {job.company}: {answers['hook'].strip()}")
    if answers.get("proof"):
        clean_lines.append(f"- CORE PROOF POINT: Heavily prioritize and expand verified achievement: {answers['proof'].strip()}")
    if answers.get("tactics"):
        clean_lines.append(f"- TACTICAL FRAMING & SKILL BRIDGES: {answers['tactics'].strip()}")

    if persona:
        if persona.market != "Global":
            clean_lines.append(f"- MARKET STANCE ({persona.market}): Apply {persona.market} hiring norms and conventions.")
        if persona.logistics:
            clean_lines.append(f"- LOGISTICAL BOUNDS: {json.dumps(persona.logistics)}")

    default_directives = "\n".join(clean_lines) if clean_lines else "- TARGET ALIGNMENT: Maximize relevance to target job requirements without diluting verified metrics."

    if not provider:
        return default_directives

    try:
        sys_prompt = (
            f"You are Breadwinner's narrative strategist. Synthesize candidate strategic inputs for applying to {job.company} as {job.title} "
            "into a bulleted block of 3-5 high-priority directives for an automated resume and cover letter tailoring engine. "
            "Directives must be concise, authoritative, and direct."
        )
        user_prompt = f"TARGET ROLE: {job.title} at {job.company}\nCANDIDATE ANSWERS:\n" + "\n".join(f"{k}: {v}" for k, v in answers.items() if v)
        text = provider.generate_text(sys_prompt, user_prompt, temperature=0.2)
        if text and len(text.strip()) > 20:
            return text.strip()
    except Exception:
        pass

    return default_directives


def synthesize_job_persona(
    name: str,
    slug: str,
    job: JobPosting,
    answers: Dict[str, str],
    base_persona: Optional[Persona] = None,
    provider: Optional[BaseLLMProvider] = None
) -> Persona:
    """Synthesize a complete reusable Persona from the role context and strategy answers."""
    clean_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug.lower().strip()).strip("_")
    if not clean_slug:
        clean_slug = f"persona_{job.company.lower()}_{job.title.lower()}"
        clean_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in clean_slug).strip("_")

    directives = synthesize_job_directives(job, answers, persona=base_persona, provider=provider)

    market = base_persona.market if base_persona else "Global"
    logistics = base_persona.logistics if base_persona else {}
    archetype = base_persona.archetype if base_persona else "Target Role Strategist"
    banned_words = base_persona.banned_words if base_persona else []

    if provider:
        try:
            sys_prompt = (
                "You are an expert career architect. Generate a reusable narrative Persona configuration in JSON. "
                "The Persona should have:\n"
                "- name: string (e.g. 'Fintech Distributed Systems Lead')\n"
                "- slug: string (e.g. 'fintech_systems_lead')\n"
                "- description: string (summary of when to use this persona)\n"
                "- tone: string (e.g. 'Authoritative, systems-first, quantitative')\n"
                "- system_directives: string (detailed rules for tailoring resume and experiences)\n"
                "- cover_letter_directives: string (detailed 3-paragraph instructions for cover letter)\n"
            )
            user_prompt = (
                f"TARGET JOB: {job.title} at {job.company}\n"
                f"PERSONA NAME: {name}\n"
                f"PERSONA SLUG: {clean_slug}\n"
                f"BASE PERSONA: {base_persona.name if base_persona else 'General Technical'}\n"
                f"CANDIDATE DIRECTIVES:\n{directives}\n"
                f"JOB RAW TEXT:\n{job.raw_text[:1500]}"
            )
            res = provider.generate_json(sys_prompt, user_prompt)
            if all(k in res for k in ["name", "slug", "description", "tone", "system_directives", "cover_letter_directives"]):
                # Ensure the user's chosen name and clean_slug are preserved
                return Persona(
                    name=name or res["name"],
                    slug=clean_slug or res["slug"],
                    description=res.get("description", f"Tailored strategy for {job.title} at {job.company}."),
                    tone=res.get("tone", base_persona.tone if base_persona else "Authoritative, quantitative."),
                    system_directives=res.get("system_directives", ""),
                    cover_letter_directives=res.get("cover_letter_directives", ""),
                    market=market,
                    logistics=logistics,
                    archetype=archetype,
                    banned_words=banned_words
                )
        except Exception:
            pass

    # Heuristic fallback
    base_sys = base_persona.system_directives if base_persona else (
        "CORE RULES:\n"
        "1. PRESERVE HARD METRICS: Never dilute, round down, or remove verified metrics.\n"
        "2. STRICT XYZ FORMULA: Structure all bullet points as 'Accomplished [X] as measured by [Y], by doing [Z]'.\n"
        "3. ATS ALIGNMENT: Mirror exact technical vocabulary and architectural patterns from target role."
    )
    base_cl = base_persona.cover_letter_directives if base_persona else (
        "Write a concise 3-paragraph letter (<220 words total):\n"
        "- Paragraph 1: Hook the hiring manager with immediate alignment to their specific mission.\n"
        "- Paragraph 2: Provide two concrete proof points detailing architecture, system scale, and quantitative outcomes.\n"
        "- Paragraph 3: Direct call to action and availability."
    )

    combined_sys = f"{base_sys}\n\nJOB-SPECIFIC STRATEGY DIRECTIVES:\n{directives}"
    combined_cl = f"{base_cl}\n\nSTRATEGIC EMPHASIS:\n{directives}"

    return Persona(
        name=name or f"{job.company} {job.title} Strategist",
        slug=clean_slug,
        description=f"Tailored strategy for {job.title} at {job.company} and similar roles.",
        tone=base_persona.tone if base_persona else "Authoritative, highly quantitative, role-focused.",
        system_directives=combined_sys,
        cover_letter_directives=combined_cl,
        market=market,
        logistics=logistics,
        archetype=archetype,
        banned_words=banned_words
    )

