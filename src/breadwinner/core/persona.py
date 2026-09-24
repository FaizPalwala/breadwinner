"""Persona and narrative controller."""

from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from pydantic import BaseModel

from breadwinner.core.models import JobPosting
from breadwinner.providers.base import BaseLLMProvider


class Persona(BaseModel):
    name: str
    slug: str
    description: str
    tone: str
    system_directives: str
    cover_letter_directives: str


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
            "admin": "bridging_admin",
            "parttime": "bridging_admin",
            "service": "hospitality"
        }
        if persona_name in alias_map:
            return cls.load_persona(alias_map[persona_name], custom_dir)

        raise ValueError(f"Persona '{persona_name}' not found. Available: tech_ai, bridging_admin, hospitality")

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
    provider: Optional[BaseLLMProvider] = None
) -> List[Dict[str, str]]:
    """Generate 2-3 role-specific probing questions based on the ingested job."""
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
            "question": f"Which past project or verified achievement best proves you are the ideal {job.title} for this exact team?",
            "placeholder": "e.g., Scaling high-throughput data pipelines to 1M QPS; cutting latency by 40%..."
        },
        {
            "id": "tactics",
            "title": "Tactical Framing & Tone Nuances",
            "question": "Are there specific skills to downplay, gaps/career pivots to frame, or unique priorities for this role?",
            "placeholder": "e.g., Emphasize systems architecture over frontend; frame transition to tech lead..."
        }
    ]

    if not provider:
        return default_questions

    try:
        sys_prompt = (
            "You are Breadwinner's strategic career architect. "
            "Given a target job description, generate 3 sharp, tailored discovery questions "
            "for the candidate to answer before tailoring their application. "
            "Probe for: (1) company hook/alignment, (2) their strongest specific proof point for this role, "
            "and (3) tactical framing, tone, or gaps to address.\n"
            "Return JSON matching: {\"questions\": [{\"id\": \"hook\", \"title\": \"...\", \"question\": \"...\", \"placeholder\": \"...\"}]}"
        )
        user_prompt = f"TARGET JOB:\nCompany: {job.company}\nTitle: {job.title}\nJob Snippet:\n{job.raw_text[:1500]}"
        res = provider.generate_json(sys_prompt, user_prompt)
        raw_qs = res.get("questions", [])
        if isinstance(raw_qs, list) and len(raw_qs) >= 2:
            return raw_qs[:3]
    except Exception:
        pass

    return default_questions


def synthesize_job_directives(
    job: JobPosting,
    answers: Dict[str, str],
    provider: Optional[BaseLLMProvider] = None
) -> str:
    """Synthesize candidate answers into actionable, prioritized directives for tailoring."""
    clean_lines = []
    if answers.get("hook"):
        clean_lines.append(f"- STRATEGIC HOOK: Focus application on candidate's alignment with {job.company}: {answers['hook'].strip()}")
    if answers.get("proof"):
        clean_lines.append(f"- CORE PROOF POINT: Heavily prioritize and expand verified achievement: {answers['proof'].strip()}")
    if answers.get("tactics"):
        clean_lines.append(f"- TACTICAL FRAMING & CONSTRAINTS: {answers['tactics'].strip()}")

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

    directives = synthesize_job_directives(job, answers, provider)

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
                    cover_letter_directives=res.get("cover_letter_directives", "")
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
        cover_letter_directives=combined_cl
    )

