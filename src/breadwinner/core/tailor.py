"""Tailoring and match analysis orchestrator."""

import json
from typing import Dict, Any, List
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


class TailoringEngine:
    """Combines candidate source-of-truth, job description, and persona via LLM."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def analyze_and_tailor(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        persona: Persona
    ) -> TailoredApplication:
        """Run match analysis and generate tailored application packet."""

        # Prepare context payload
        candidate_summary = {
            "name": profile.full_name,
            "title": profile.title,
            "summary": profile.summary,
            "experiences": [
                {
                    "company": e.company,
                    "role": e.role,
                    "bullets": e.bullets,
                    "dates": f"{e.start_date} - {e.end_date}"
                }
                for e in profile.experiences
            ],
            "education": [
                {
                    "degree": ed.degree,
                    "institution": ed.institution,
                    "coursework": ed.coursework
                }
                for ed in profile.education
            ],
            "projects": [
                {
                    "name": p.name,
                    "description": p.description,
                    "tech_stack": p.tech_stack,
                    "highlights": p.highlights
                }
                for p in profile.projects
            ],
            "skills": [
                {"category": s.category, "skills": s.skills}
                for s in profile.skills
            ],
            "extra_context": profile.raw_context
        }

        personal_guardrails = profile.raw_context.get("personal_context", "")
        guardrails_block = f"\nCANDIDATE PERSONAL DIRECTIVES & GUARDRAILS (HIGH PRIORITY):\n{personal_guardrails}\n" if personal_guardrails else ""

        # Prompt for JSON match & tailoring
        system_prompt = f"""You are Breadwinner, an automated job application tailoring engine.
NARRATIVE PERSONA: {persona.name}
TONE: {persona.tone}

PERSONA DIRECTIVES:
{persona.system_directives}
{guardrails_block}
JOB TITLE: {job.title}
COMPANY: {job.company}
LOCATION: {job.location or 'Unspecified'}

TASK:
1. Analyze the match between candidate verified facts and the job description.
2. Produce an ATS Match Score (0-100) based on realistic keyword and semantic overlap.
3. Identify matched skills and missing skill gaps.
4. Tailor a compelling 2-3 sentence professional summary.
5. Tailor the candidate's work experience bullets adhering strictly to the XYZ formula ("Accomplished [X] as measured by [Y], by doing [Z]") without inventing false facts. Keep verified numbers, scale metrics, throughput, and award achievements intact.

6. Select the top 2-3 most relevant projects from candidate's portfolio.
7. Generate portal Q&A answers for standard questions ("Why this company?", "Key technical challenge solved").
"""

        user_prompt = f"""CANDIDATE SOURCE OF TRUTH:
{json.dumps(candidate_summary, indent=2)}

TARGET JOB DESCRIPTION:
Company: {job.company}
Title: {job.title}
Raw Job Details:
{job.raw_text[:4000]}

Respond ONLY in valid JSON with this exact schema:
{{
  "match_score": 85,
  "matched_skills": ["Skill 1", "Skill 2"],
  "missing_skills": ["Skill 3"],
  "rationale": "Why this score was awarded",
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
                # Match against original experience to keep metadata
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
        cover_letter = self._generate_cover_letter(profile, job, persona, match_analysis)

        return TailoredApplication(
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

    def _generate_cover_letter(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        persona: Persona,
        match: MatchAnalysis
    ) -> str:
        """Generate targeted 3-paragraph cover letter."""
        sys_prompt = f"""You are an expert cover letter copywriter for {profile.full_name}.
PERSONA: {persona.name}
{persona.cover_letter_directives}

COMPANY: {job.company}
ROLE: {job.title}
MATCHED STRENGTHS: {', '.join(match.matched_skills)}
"""

        # Dynamically compile verified proof points from candidate profile
        proof_points = []
        for exp in profile.experiences[:2]:
            b_sample = exp.bullets[0] if exp.bullets else ""
            proof_points.append(f"- {exp.role} @ {exp.company} ({exp.start_date} - {exp.end_date}): {b_sample}")
        for edu in profile.education[:1]:
            proof_points.append(f"- {edu.degree} @ {edu.institution}")

        user_prompt = f"""Write a tailored 3-paragraph cover letter (<220 words) for {profile.full_name} applying to {job.company} as {job.title}.

CANDIDATE VERIFIED FACTS:
{chr(10).join(proof_points)}

JOB CONTEXT:
{job.raw_text[:2000]}
"""

        return self.provider.generate_text(sys_prompt, user_prompt, temperature=0.3).strip()
