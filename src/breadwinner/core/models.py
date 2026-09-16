"""Data models for Breadwinner representing candidate profiles, jobs, and applications."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    start_date: str
    end_date: str
    is_current: bool = False
    bullets: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade: Optional[str] = None
    coursework: List[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: str
    tech_stack: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    github_url: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)


class SkillCategory(BaseModel):
    category: str
    skills: List[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    full_name: str
    title: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: str = ""
    experiences: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[SkillCategory] = Field(default_factory=list)
    raw_context: Dict[str, Any] = Field(default_factory=dict)

    def to_json_resume(self) -> Dict[str, Any]:
        """Export profile to standard JSON Resume schema for interoperability."""
        return {
            "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
            "basics": {
                "name": self.full_name,
                "label": self.title,
                "email": self.email or "",
                "phone": self.phone or "",
                "url": self.portfolio_url or "",
                "summary": self.summary,
                "location": {
                    "city": self.location or ""
                },
                "profiles": [
                    {"network": "GitHub", "url": self.github_url or ""},
                    {"network": "LinkedIn", "url": self.linkedin_url or ""}
                ]
            },
            "work": [
                {
                    "name": exp.company,
                    "position": exp.role,
                    "location": exp.location or "",
                    "startDate": exp.start_date,
                    "endDate": exp.end_date,
                    "summary": "; ".join(exp.bullets[:1]) if exp.bullets else "",
                    "highlights": exp.bullets
                }
                for exp in self.experiences
            ],
            "education": [
                {
                    "institution": edu.institution,
                    "area": edu.field_of_study or "",
                    "studyType": edu.degree,
                    "startDate": edu.start_date or "",
                    "endDate": edu.end_date or "",
                    "score": edu.grade or "",
                    "courses": edu.coursework
                }
                for edu in self.education
            ],
            "projects": [
                {
                    "name": proj.name,
                    "description": proj.description,
                    "highlights": proj.highlights or proj.tech_stack,
                    "keywords": proj.tech_stack,
                    "url": proj.url or proj.github_url or ""
                }
                for proj in self.projects
            ],
            "skills": [
                {
                    "name": sk.category,
                    "keywords": sk.skills
                }
                for sk in self.skills
            ]
        }


class JobPosting(BaseModel):
    id: str
    company: str
    title: str
    url: Optional[str] = None
    location: Optional[str] = None
    portal_type: str = "general"
    raw_text: str = ""
    extracted_skills: List[str] = Field(default_factory=list)
    extracted_responsibilities: List[str] = Field(default_factory=list)
    extracted_requirements: List[str] = Field(default_factory=list)


class MatchAnalysis(BaseModel):
    match_score: int
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    rationale: str = ""
    strategic_recommendations: List[str] = Field(default_factory=list)


class TailoredApplication(BaseModel):
    job: JobPosting
    persona: str
    match_analysis: MatchAnalysis
    tailored_summary: str
    tailored_experiences: List[WorkExperience] = Field(default_factory=list)
    tailored_projects: List[Project] = Field(default_factory=list)
    tailored_skills: List[SkillCategory] = Field(default_factory=list)
    cover_letter: str = ""
    portal_answers: Dict[str, str] = Field(default_factory=dict)
