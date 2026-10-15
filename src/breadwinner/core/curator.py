"""Anti-Hallucination Career Curation & Relevance Engine for Breadwinner.

Intelligently scores and curates candidate experiences, projects, and skills
against a target job description to prevent context bloat and token waste,
while strictly preserving verified metrics and adhering to 1-page resume budgets.
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

from breadwinner.core.models import CandidateProfile, WorkExperience, Project, JobPosting


STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "role", "job", "experience", "looking", "team",
    "work", "skills", "ability", "responsibilities", "requirements", "years"
}


@dataclass
class CuratedProfileResult:
    """The result of career curation against a target job."""
    curated_profile: CandidateProfile
    total_experiences_in_pantry: int
    selected_experiences_count: int
    omitted_experiences_count: int
    matched_keywords: List[str]
    missing_keywords: List[str]
    relevance_scores: Dict[str, float]
    curation_summary: str


class CareerCurator:
    """Intelligently curates candidate profiles against target roles."""

    @staticmethod
    def extract_keywords(text: str) -> Set[str]:
        """Extract clean alphanumeric keywords, skills, and technologies."""
        words = re.findall(r"\b[A-Za-z0-9+#.-]{2,}\b", text.lower())
        return {w for w in words if w not in STOP_WORDS and not w.isdigit()}

    @classmethod
    def score_bullet(cls, bullet: str, job_keywords: Set[str]) -> Tuple[float, int]:
        """Score an individual bullet for keyword overlap and quantifiable metric density."""
        bullet_lower = bullet.lower()
        bullet_words = cls.extract_keywords(bullet)
        overlap = len(bullet_words.intersection(job_keywords))

        # Check for numbers, percentages, currency, and scale (XYZ formula markers)
        metric_matches = re.findall(r"\b\d+[%kKmMbBxX]?\b|\$\d+|\b\d+\.\d+\b", bullet)
        metric_score = len(metric_matches)

        # Composite score
        total_score = (overlap * 1.5) + (metric_score * 1.0)
        return total_score, overlap

    @classmethod
    def score_experience(
        cls,
        exp: WorkExperience,
        job_keywords: Set[str],
        recency_index: int
    ) -> float:
        """Scores an entire work experience for relevance and recency."""
        exp_text = f"{exp.company} {exp.role} " + " ".join(exp.bullets)
        exp_words = cls.extract_keywords(exp_text)
        keyword_matches = len(exp_words.intersection(job_keywords))

        # Recency discount: index 0 is most recent, subsequent roles decay slightly
        recency_weight = max(0.5, 1.0 - (recency_index * 0.12))

        # Metric density across all bullets
        all_bullets_text = " ".join(exp.bullets)
        metrics_count = len(re.findall(r"\b\d+[%kKmMbBxX]?\b|\$\d+|\b\d+\.\d+\b", all_bullets_text))

        final_score = (keyword_matches * 2.0 + metrics_count * 1.0) * recency_weight
        return round(final_score, 2)

    @classmethod
    def score_project(cls, project: Project, job_keywords: Set[str]) -> float:
        """Scores a project based on tech stack and description overlap."""
        proj_text = f"{project.name} {project.description} " + " ".join(project.tech_stack)
        proj_words = cls.extract_keywords(proj_text)
        overlap = len(proj_words.intersection(job_keywords))

        # Bonus for tech stack keyword matches
        stack_overlap = sum(1 for t in project.tech_stack if t.lower() in job_keywords)
        return round(overlap * 1.5 + stack_overlap * 2.0, 2)

    @classmethod
    def curate(
        cls,
        profile: CandidateProfile,
        job: JobPosting,
        max_experiences: int = 4,
        max_bullets_per_exp: int = 4,
        max_projects: int = 3
    ) -> CuratedProfileResult:
        """Curates the candidate profile into an impactful, budget-conscious subset.
        
        Strict Anti-Hallucination Invariant:
        Only selects and re-orders verified items existing in the candidate's pantry.
        Never fabricates new metrics, projects, or experiences.
        """
        job_text = f"{job.title} {job.company} {job.raw_text}"
        job_keywords = cls.extract_keywords(job_text)

        # 1. Score and rank work experiences
        scored_experiences: List[Tuple[WorkExperience, float]] = []
        for idx, exp in enumerate(profile.experiences):
            score = cls.score_experience(exp, job_keywords, recency_index=idx)
            scored_experiences.append((exp, score))

        # If we have more than max_experiences, sort by score descending, but keep top recent role
        if len(scored_experiences) > max_experiences:
            # Sort all roles by relevance score
            scored_experiences.sort(key=lambda x: x[1], reverse=True)
            selected_exp_tuples = scored_experiences[:max_experiences]
        else:
            selected_exp_tuples = scored_experiences

        # Curate individual bullets within each selected experience
        curated_experiences: List[WorkExperience] = []
        exp_score_map: Dict[str, float] = {}

        for exp, exp_score in selected_exp_tuples:
            exp_key = f"{exp.role} @ {exp.company}"
            exp_score_map[exp_key] = exp_score

            # Score individual bullets
            scored_bullets: List[Tuple[str, float]] = []
            for b in exp.bullets:
                b_score, _ = cls.score_bullet(b, job_keywords)
                scored_bullets.append((b, b_score))

            # Sort bullets by relevance and take top K
            scored_bullets.sort(key=lambda x: x[1], reverse=True)
            selected_bullets = [b for b, _ in scored_bullets[:max_bullets_per_exp]]

            curated_experiences.append(
                WorkExperience(
                    company=exp.company,
                    role=exp.role,
                    location=exp.location,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    bullets=selected_bullets or exp.bullets[:max_bullets_per_exp]
                )
            )

        # 2. Score and rank projects
        scored_projects: List[Tuple[Project, float]] = []
        for proj in profile.projects:
            p_score = cls.score_project(proj, job_keywords)
            scored_projects.append((proj, p_score))

        scored_projects.sort(key=lambda x: x[1], reverse=True)
        curated_projects = [p for p, _ in scored_projects[:max_projects]]

        # 3. Match keyword analysis
        profile_all_text = " ".join([
            exp.role + " " + " ".join(exp.bullets) for exp in curated_experiences
        ]) + " " + " ".join([p.name + " " + p.description for p in curated_projects])
        profile_words = cls.extract_keywords(profile_all_text)

        matched = sorted(list(job_keywords.intersection(profile_words)))
        missing = sorted(list(job_keywords.difference(profile_words)))[:15]

        # 4. Construct Curated CandidateProfile
        curated_profile = CandidateProfile(
            full_name=profile.full_name,
            title=profile.title,
            email=profile.email,
            phone=profile.phone,
            location=profile.location,
            linkedin_url=profile.linkedin_url,
            github_url=profile.github_url,
            portfolio_url=profile.portfolio_url,
            summary=profile.summary,
            experiences=curated_experiences,
            education=profile.education,
            projects=curated_projects,
            skills=profile.skills,
            raw_context=profile.raw_context
        )

        total_exp = len(profile.experiences)
        selected_exp = len(curated_experiences)
        omitted_exp = total_exp - selected_exp

        summary = (
            f"Curated {selected_exp} of {total_exp} roles for '{job.company} - {job.title}'. "
            f"Prioritized top-match experiences ({', '.join(list(exp_score_map.keys())[:2])}) "
            f"and {len(curated_projects)} relevant projects to protect 1-page print budget."
        )

        return CuratedProfileResult(
            curated_profile=curated_profile,
            total_experiences_in_pantry=total_exp,
            selected_experiences_count=selected_exp,
            omitted_experiences_count=omitted_exp,
            matched_keywords=matched,
            missing_keywords=missing,
            relevance_scores=exp_score_map,
            curation_summary=summary
        )
