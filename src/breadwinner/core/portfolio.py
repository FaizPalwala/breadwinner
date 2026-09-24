"""Abstract profile ingestion layer supporting Astro portfolios, JSON Resume, and Markdown directories."""

import re
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)


class BaseProfileSource(ABC):
    """Abstract base class for all personal context / portfolio sources."""

    @abstractmethod
    def load_profile(self) -> CandidateProfile:
        """Load and return a structured CandidateProfile."""
        pass


class AstroPortfolioAdapter(BaseProfileSource):
    """Adapter for Astro / Keystatic portfolios."""

    def __init__(self, portfolio_path: Path):
        self.path = Path(portfolio_path)

    def load_profile(self) -> CandidateProfile:
        about_file = self.path / "src" / "pages" / "about.astro"
        if not about_file.exists():
            # Try root about.astro
            about_file = self.path / "pages" / "about.astro"

        experiences: List[WorkExperience] = []
        education: List[Education] = []
        projects: List[Project] = []
        skills: List[SkillCategory] = []
        full_name = "Candidate"
        title = "Software Engineer"
        summary = ""

        if about_file.exists():
            content = about_file.read_text(encoding="utf-8")
            # Parse HTML / Astro body after frontmatter
            parts = content.split("---")
            body = parts[2] if len(parts) >= 3 else content
            soup = BeautifulSoup(body, "html.parser")

            # Extract name and summary
            name_span = soup.find("span", class_=lambda c: c and "font-bold" in c and "text-text-base" in c)
            if name_span:
                full_name = name_span.get_text().strip()

            summary_p = soup.find("p", class_="text-lg")
            if summary_p:
                summary = " ".join(summary_p.get_text().split())

            # Extract Experiences
            exp_section = soup.find(lambda tag: tag.name == "h2" and "Experience" in tag.get_text())
            if exp_section and exp_section.parent:
                exp_container = exp_section.parent
                # Find the container holding the jobs (e.g. space-y-6)
                job_container = exp_container.find("div", class_="space-y-6") or exp_container
                job_divs = job_container.find_all("div", recursive=False)

                for job in job_divs:
                    h3 = job.find("h3")
                    if not h3:
                        continue
                    company_span = h3.find("span")
                    company_raw = company_span.get_text().strip() if company_span else ""
                    company = company_raw.replace("@", "").strip() if company_raw else "Company"
                    
                    # Role is h3 text without company
                    role = h3.get_text().replace(company_raw, "").strip()

                    # Date & location
                    date_p = job.find("p", class_=lambda c: c and "text-text-muted" in c)
                    start_date, end_date, location = "2020", "Present", None
                    if date_p:
                        text = date_p.get_text().strip()
                        if "|" in text:
                            dates_part, loc_part = text.split("|", 1)
                            location = loc_part.strip()
                            text = dates_part.strip()
                        if "-" in text:
                            d_parts = text.split("-")
                            start_date = d_parts[0].strip()
                            end_date = d_parts[1].strip()
                        else:
                            start_date = text

                    bullets = []
                    ul = job.find("ul")
                    if ul:
                        for li in ul.find_all("li"):
                            bullets.append(" ".join(li.get_text().split()))

                    experiences.append(WorkExperience(
                        company=company,
                        role=role,
                        location=location,
                        start_date=start_date,
                        end_date=end_date,
                        is_current="present" in end_date.lower(),
                        bullets=bullets
                    ))

            # Extract Education
            edu_section = soup.find(lambda tag: tag.name == "h2" and "Education" in tag.get_text())
            if edu_section and edu_section.parent:
                edu_container = edu_section.parent
                inner = edu_container.find("div", class_="space-y-4") or edu_container
                for edu_div in inner.find_all("div", recursive=False):
                    h3 = edu_div.find("h3")
                    if not h3:
                        continue
                    degree = h3.get_text().strip()
                    inst_p = edu_div.find("p", class_=lambda c: c and "text-text-muted" in c)
                    institution = "University"
                    dates = ""
                    if inst_p:
                        text = inst_p.get_text().strip()
                        if "|" in text:
                            i_part, d_part = text.split("|", 1)
                            institution = i_part.strip()
                            dates = d_part.strip()
                        else:
                            institution = text

                    coursework = []
                    course_p = edu_div.find_all("p")
                    for cp in course_p:
                        if "coursework" in cp.get_text().lower():
                            raw = cp.get_text().split("Coursework:")[-1].strip()
                            coursework = [c.strip() for c in raw.split(",") if c.strip()]

                    education.append(Education(
                        institution=institution,
                        degree=degree,
                        start_date=dates.split("-")[0].strip() if "-" in dates else dates,
                        end_date=dates.split("-")[1].strip() if "-" in dates else None,
                        coursework=coursework
                    ))

            # Extract Technical Arsenal
            skills_section = soup.find(lambda tag: tag.name == "h2" and "Technical Arsenal" in tag.get_text())
            if skills_section and skills_section.parent:
                ul = skills_section.parent.find("ul")
                if ul:
                    for li in ul.find_all("li"):
                        text = li.get_text().replace(">", "").strip()
                        if "/" in text:
                            items = [s.strip() for s in text.split("/") if s.strip()]
                            skills.append(SkillCategory(category="Core", skills=items))
                        else:
                            skills.append(SkillCategory(category="Core", skills=[text]))

        # Read Projects from src/content/projects/
        projects_dir = self.path / "src" / "content" / "projects"
        if projects_dir.exists():
            for p_file in sorted(projects_dir.glob("*.*")):
                if p_file.suffix in [".md", ".mdx"]:
                    proj = self._parse_markdown_project(p_file)
                    if proj:
                        projects.append(proj)

        # Context nuggets from career coach or PartTime prompts if present
        raw_context: Dict[str, Any] = {}
        coach_file = self.path / "CAREER_COACH_PROMPT.md"
        if coach_file.exists():
            raw_context["career_coach_context"] = coach_file.read_text(encoding="utf-8")

        github_url = None
        portfolio_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "github.com" in href and not github_url:
                github_url = href
            elif href.startswith("http") and not portfolio_url and "github.com" not in href:
                portfolio_url = href

        return CandidateProfile(
            full_name=full_name or "Candidate Name",
            title=title or "Software Engineer",
            summary=summary,
            location=location or "United Kingdom",
            github_url=github_url,
            portfolio_url=portfolio_url,
            experiences=experiences,
            education=education,
            projects=projects,
            skills=skills,
            raw_context=raw_context
        )


    def _parse_markdown_project(self, file_path: Path) -> Optional[Project]:
        try:
            import yaml
            content = file_path.read_text(encoding="utf-8")
            title = file_path.stem
            tech_stack = []
            description = ""
            highlights = []
            url = None
            github_url = None

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    title = meta.get("title", title)
                    description = meta.get("description", "")
                    tech_stack = meta.get("techStack", [])
                    url = meta.get("demoLink")
                    github_url = meta.get("githubUrl")
                    
                    body = parts[2].strip()
                    for line in body.splitlines():
                        line_s = line.strip()
                        if line_s.startswith("- ") or line_s.startswith("* "):
                            cleaned = line_s[2:].strip().replace("**", "")
                            if len(cleaned) > 10:
                                highlights.append(cleaned)

            return Project(
                name=title,
                description=description or f"Project developed by candidate ({title})",
                tech_stack=tech_stack if isinstance(tech_stack, list) else [str(tech_stack)],
                url=url,
                github_url=github_url,
                highlights=highlights[:4]
            )
        except Exception:
            return None


class JsonResumeAdapter(BaseProfileSource):
    """Adapter for standard JSON Resume files (resume.json) or parsed dicts."""

    def __init__(self, json_source: Any):
        if isinstance(json_source, dict):
            self.data = json_source
            self.path = None
        else:
            self.path = Path(json_source)
            self.data = None

    def load_profile(self) -> CandidateProfile:
        if self.data is not None:
            data = self.data
        else:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        basics = data.get("basics", {})
        
        experiences = [
            WorkExperience(
                company=w.get("name", "Company"),
                role=w.get("position", "Role"),
                location=w.get("location"),
                start_date=w.get("startDate", ""),
                end_date=w.get("endDate", "Present"),
                bullets=w.get("highlights", []) or ([w.get("summary")] if w.get("summary") else [])
            )
            for w in data.get("work", [])
        ]

        education = [
            Education(
                institution=e.get("institution", "Institution"),
                degree=e.get("studyType", "Degree"),
                field_of_study=e.get("area"),
                start_date=e.get("startDate"),
                end_date=e.get("endDate"),
                grade=e.get("score"),
                coursework=e.get("courses", [])
            )
            for e in data.get("education", [])
        ]

        projects = [
            Project(
                name=p.get("name", "Project"),
                description=p.get("description", ""),
                tech_stack=p.get("keywords", []),
                url=p.get("url"),
                highlights=p.get("highlights", [])
            )
            for p in data.get("projects", [])
        ]

        skills = [
            SkillCategory(
                category=s.get("name", "Skills"),
                skills=s.get("keywords", [])
            )
            for s in data.get("skills", [])
        ]

        return CandidateProfile(
            full_name=basics.get("name", "Candidate"),
            title=basics.get("label", "Software Engineer"),
            email=basics.get("email"),
            phone=basics.get("phone"),
            location=basics.get("location", {}).get("city"),
            summary=basics.get("summary", ""),
            experiences=experiences,
            education=education,
            projects=projects,
            skills=skills
        )


class MarkdownDirectoryAdapter(BaseProfileSource):
    """Adapter for a generic folder of markdown files (experience.md, education.md, etc.)."""

    def __init__(self, dir_path: Path):
        self.path = Path(dir_path)

    def load_profile(self) -> CandidateProfile:
        profile = CandidateProfile(
            full_name="Candidate",
            title="Software Professional"
        )
        
        exp_file = self.path / "experience.md"
        if exp_file.exists():
            text = exp_file.read_text(encoding="utf-8")
            # Parse sections
            current_exp = None
            for line in text.splitlines():
                if line.startswith("## "):
                    if current_exp:
                        profile.experiences.append(current_exp)
                    current_exp = WorkExperience(
                        company=line.replace("##", "").strip(),
                        role="Software Engineer",
                        start_date="2020",
                        end_date="Present"
                    )
                elif line.strip().startswith("- ") and current_exp:
                    current_exp.bullets.append(line.strip()[2:].strip())
            if current_exp:
                profile.experiences.append(current_exp)

        return profile


def get_profile_source(path: Optional[Path] = None) -> BaseProfileSource:
    """Factory function that returns the appropriate adapter for the given path.
    Prioritizes the canonical Pantry if available."""
    from breadwinner.config import settings
    p = Path(path) if path else Path(settings.portfolio_path)

    # Check Pantry first if default path
    pantry_dir = Path(settings.pantry_dir)
    if (pantry_dir / "profile.json").exists() and (not path or p == Path(settings.portfolio_path)):
        return JsonResumeAdapter(pantry_dir / "profile.json")

    if p.is_file() and p.suffix == ".json":
        return JsonResumeAdapter(p)
    elif (p / "resume.json").exists():
        return JsonResumeAdapter(p / "resume.json")
    elif (p / "src" / "pages" / "about.astro").exists() or (p / "pages" / "about.astro").exists() or (p / "astro.config.mjs").exists():
        return AstroPortfolioAdapter(p)
    else:
        return MarkdownDirectoryAdapter(p)
