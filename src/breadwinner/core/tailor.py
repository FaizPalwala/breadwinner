"""Tailoring, match analysis, and metric-frozen constrained generation orchestrator."""

import json
from typing import Dict, Any, List, Optional
from breadwinner.core.models import (
    CandidateProfile,
    JobPosting,
    MatchAnalysis,
    TailoredApplication,
    WorkExperience,
    Project,
    SkillCategory
)
from breadwinner.core.persona import Persona
from breadwinner.providers.base import BaseLLMProvider
from breadwinner.core.curator import CareerCurator
from breadwinner.core.deconstruct import JDDeconstructor, DeconstructedJob
from breadwinner.core.provenance import ProvenanceValidator, DEFAULT_BANNED_WORDS


class TailoringEngine:
    """Multi-stage deterministic career engineering studio and anti-hallucination tailoring engine."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def analyze_and_tailor(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        persona: Persona,
        job_directives: Optional[str] = None
    ) -> TailoredApplication:
        """Run match analysis and generate tailored application packet with metric freezing."""
        # STAGE 1: Deterministic Job Description Deconstruction
        deconstructed_job: DeconstructedJob = JDDeconstructor.deconstruct(job, self.provider)

        # STAGE 2: Assessment & Constrained Tailoring
        # Curate profile against target job to avoid context bloat and protect 1-page budget
        curated_res = CareerCurator.curate(profile, job)
        target_profile = curated_res.curated_profile

        # Extract verified metrics per experience for metric freezing
        verified_metrics_by_exp: Dict[str, List[str]] = {}
        for exp in target_profile.experiences:
            metrics = ProvenanceValidator.extract_metrics(" ".join(exp.bullets))
            verified_metrics_by_exp[exp.company] = sorted(list(metrics))

        candidate_summary = {
            "name": target_profile.full_name,
            "title": target_profile.title,
            "summary": target_profile.summary,
            "experiences": [
                {
                    "company": e.company,
                    "role": e.role,
                    "bullets": e.bullets,
                    "verified_metrics": verified_metrics_by_exp.get(e.company, []),
                    "dates": f"{e.start_date} - {e.end_date}"
                }
                for e in target_profile.experiences
            ],
            "education": [
                {
                    "degree": ed.degree,
                    "institution": ed.institution,
                    "coursework": ed.coursework
                }
                for ed in target_profile.education
            ],
            "projects": [
                {
                    "name": p.name,
                    "description": p.description,
                    "tech_stack": p.tech_stack,
                    "highlights": p.highlights
                }
                for p in target_profile.projects
            ],
            "skills": [
                {"category": s.category, "skills": s.skills}
                for s in target_profile.skills
            ],
            "extra_context": target_profile.raw_context
        }

        personal_guardrails = profile.raw_context.get("personal_context", "") if isinstance(profile.raw_context, dict) else ""
        guardrails_block = f"\nCANDIDATE PERSONAL DIRECTIVES & GUARDRAILS (HIGH PRIORITY):\n{personal_guardrails}\n" if personal_guardrails else ""
        job_directives_block = f"\nJOB-SPECIFIC STRATEGY DIRECTIVES (TOP PRIORITY OVERRIDE):\n{job_directives}\n" if job_directives else ""

        banned_words_list = sorted(list(set(DEFAULT_BANNED_WORDS + (persona.banned_words or []))))
        banned_words_str = ", ".join(f'"{w}"' for w in banned_words_list)

        # Constrained Prompt
        system_prompt = f"""You are Breadwinner, an automated career engineering studio and anti-hallucination resume tailoring engine.
NARRATIVE PERSONA: {persona.name} (Market: {persona.market}, Archetype: {persona.archetype})
TONE: {persona.tone}

PERSONA DIRECTIVES:
{persona.system_directives}
{guardrails_block}
{job_directives_block}
TARGET JOB: {job.title} at {job.company} (Domain: {deconstructed_job.domain})

CORE TAILORING INVARIANTS:
1. STRICT GOOGLE XYZ FORMULA: Structure all bullet points strictly as "Accomplished [X] as measured by [Y], by doing [Z]".
2. ACTION VERBS ONLY: Every bullet must lead with an authoritative, technical past-tense action verb (e.g., "Architected", "Engineered", "Implemented", "Scaled", "Automated"). NEVER use passive or weak verbs ("assisted", "helped", "worked on", "participated in", "responsible for").
3. METRIC FREEZING & IMMUTABILITY: You may ONLY use the exact verified metrics listed under 'verified_metrics' for each experience. NEVER invent, fabricate, inflate, or round up metrics, scale, throughput, or percentages. If an experience lacks a verified metric, describe the concrete technical mechanism, concurrency model, or architecture instead of inventing a number.
4. TECH STACK GROUNDING: Do NOT smuggle unverified technologies into a work experience that the candidate never used in that role.
5. FORBIDDEN AI SLOP BLACKLIST: Strictly DO NOT use any of the following banned AI buzzwords or fluff phrases:
   {banned_words_str}
6. RECRUITER SCANNING BOUNDS: Keep every bullet strictly 1.2 to 1.8 lines (maximum 2 lines). High density, zero fluff.
7. ATS ALIGNMENT: Accurately align candidate verified skills against the target job requirements.

TASK:
1. Produce an ATS Alignment Assessment (match_score 0-100, matched_skills, missing_skills, rationale).
2. Tailor a compelling 2-3 sentence professional summary.
3. Tailor candidate work experience bullets adhering strictly to the metric freezing and XYZ invariants.
4. Select the top 2-3 most relevant projects from candidate's portfolio.
5. Generate concise portal Q&A answers.
"""

        user_prompt = f"""DECONSTRUCTED JOB SPECIFICATION:
Must Haves: {json.dumps(deconstructed_job.hard_must_haves)}
Nice to Haves: {json.dumps(deconstructed_job.nice_to_haves)}
Technical Stack: {json.dumps(deconstructed_job.technical_stack)}
Scale Constraints: {json.dumps(deconstructed_job.scale_constraints)}

CANDIDATE VERIFIED SOURCE OF TRUTH:
{json.dumps(candidate_summary, indent=2)}

TARGET JOB DESCRIPTION:
Company: {job.company}
Title: {job.title}
Raw Job Details:
{job.raw_text[:3500]}

Respond ONLY in valid JSON with this exact schema:
{{
  "match_score": 85,
  "matched_skills": ["Skill 1", "Skill 2"],
  "missing_skills": ["Skill 3"],
  "rationale": "Why this alignment was determined",
  "strategic_recommendations": ["Recommendation 1", "Recommendation 2"],
  "tailored_summary": "2-3 punchy sentences",
  "tailored_experiences": [
    {{
      "company": "Company",
      "role": "Role",
      "bullets": ["Bullet 1", "Bullet 2"]
    }}
  ],
  "selected_projects": [
    {{
      "name": "Project Name",
      "description": "Short tailored description",
      "tech_stack": ["Tech 1", "Tech 2"],
      "highlights": ["Highlight 1"]
    }}
  ],
  "portal_answers": {{
    "why_company": "Why you want to work at this specific company",
    "technical_challenge": "Describe a difficult bug or complex engineering challenge solved",
    "availability": "Immediate unrestricted availability"
  }}
}}"""

        res = self.provider.generate_json(system_prompt, user_prompt)

        # Parse match analysis
        match_analysis = MatchAnalysis(
            match_score=res.get("match_score", 75),
            matched_skills=res.get("matched_skills", []),
            missing_skills=res.get("missing_skills", []),
            rationale=res.get("rationale", "Good alignment with candidate skills."),
            strategic_recommendations=res.get("strategic_recommendations", [])
        )

        # Parse tailored experiences
        tailored_exps = []
        raw_tailored_exps = res.get("tailored_experiences", [])
        if raw_tailored_exps:
            for t_exp in raw_tailored_exps:
                orig = next((e for e in profile.experiences if e.company.lower() in t_exp.get("company", "").lower()), None)
                tailored_exps.append(WorkExperience(
                    company=t_exp.get("company", orig.company if orig else "Company"),
                    role=t_exp.get("role", orig.role if orig else "Role"),
                    location=orig.location if orig else None,
                    start_date=orig.start_date if orig else "2020",
                    end_date=orig.end_date if orig else "Present",
                    bullets=t_exp.get("bullets", orig.bullets if orig else [])
                ))
        else:
            tailored_exps = profile.experiences

        # Parse selected projects
        tailored_projs = []
        raw_projs = res.get("selected_projects", [])
        if raw_projs:
            for p in raw_projs:
                orig_p = next((op for op in profile.projects if op.name.lower() in p.get("name", "").lower()), None)
                tailored_projs.append(Project(
                    name=p.get("name", "Project"),
                    description=p.get("description", orig_p.description if orig_p else ""),
                    tech_stack=p.get("tech_stack", orig_p.tech_stack if orig_p else []),
                    url=orig_p.url if orig_p else None,
                    github_url=orig_p.github_url if orig_p else None,
                    highlights=p.get("highlights", orig_p.highlights if orig_p else [])
                ))
        else:
            tailored_projs = profile.projects[:3]

        # Generate targeted cover letter
        cover_letter = self._generate_cover_letter(profile, job, persona, match_analysis, job_directives=job_directives)

        app = TailoredApplication(
            job=job,
            persona=persona.slug,
            match_analysis=match_analysis,
            tailored_summary=res.get("tailored_summary", profile.summary),
            tailored_experiences=tailored_exps,
            tailored_projects=tailored_projs,
            tailored_skills=profile.skills,
            cover_letter=cover_letter,
            portal_answers=res.get("portal_answers", {})
        )

        # STAGE 3: Deterministic Provenance Diff Auditor & Auto-Healer
        app, cert = ProvenanceValidator.verify_and_heal_application(app, profile, persona)
        return app

    def _generate_cover_letter(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        persona: Persona,
        match: MatchAnalysis,
        job_directives: Optional[str] = None
    ) -> str:
        """Generate targeted 3-paragraph cover letter adhering to word budgets and zero fluff."""
        directives_block = f"\nJOB-SPECIFIC DIRECTIVES (TOP PRIORITY):\n{job_directives}\n" if job_directives else ""
        sys_prompt = f"""You are an expert technical cover letter copywriter for {profile.full_name}.
PERSONA: {persona.name} (Market: {persona.market}, Archetype: {persona.archetype})
{persona.cover_letter_directives}
{directives_block}
COMPANY: {job.company}
ROLE: {job.title}
MATCHED STRENGTHS: {', '.join(match.matched_skills)}

INVARIANTS:
1. STRICT WORD BUDGET: Maximum 180 words total across exactly 3 paragraphs.
2. ZERO FILLER PLEASANTRIES: Absolutely no generic openers ("I am writing to express my enthusiastic interest...").
3. PARAGRAPH 1 (HOOK): Immediate technical hook aligning candidate experience with company's platform or stated engineering challenge.
4. PARAGRAPH 2 (PROOF): Exactly two verified technical accomplishments citing architecture, scale, and exact metrics.
5. PARAGRAPH 3 (LOGISTICS & CLOSE): State work authorization, notice period availability, and a direct interview call to action.
6. ZERO AI SLOP: Strictly avoid words like "spearheaded", "orchestrated", "championed", "passionate", "tapestry".
"""

        proof_points = []
        for exp in profile.experiences[:2]:
            b_sample = exp.bullets[0] if exp.bullets else ""
            proof_points.append(f"- {exp.role} @ {exp.company} ({exp.start_date} - {exp.end_date}): {b_sample}")
        for edu in profile.education[:1]:
            proof_points.append(f"- {edu.degree} @ {edu.institution}")

        user_prompt = f"""Write a tailored 3-paragraph cover letter (<180 words) for {profile.full_name} applying to {job.company} as {job.title}.

CANDIDATE VERIFIED FACTS:
{chr(10).join(proof_points)}

JOB CONTEXT:
{job.raw_text[:2000]}
"""

        return self.provider.generate_text(sys_prompt, user_prompt, temperature=0.1).strip()
