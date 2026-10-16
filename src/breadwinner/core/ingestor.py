"""Universal profile ingestion engine from URLs, documents, and freeform text."""

import json
import re
import zlib
import platform
import subprocess
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
import requests

from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)
from breadwinner.providers.base import BaseLLMProvider


class IngestionError(Exception):
    """Raised when profile ingestion fails."""
    pass


def classify_document(text: str, source_label: str = "") -> str:
    """Classifies input into: 'academic', 'portfolio', 'project_readme', 'resume', or 'general'."""
    lower_src = source_label.lower()
    lower_text = text.lower()[:5000]

    # 1. Academic dissertation / thesis / research paper / whitepaper
    academic_keywords = [
        "dissertation", "thesis", "doctor of philosophy", "ph.d.", "phd thesis",
        "master's thesis", "doctoral dissertation", "advisor:", "adviser:", "committee members",
        "whitepaper", "arxiv:", "doi:"
    ]
    if any(k in lower_src for k in academic_keywords) or (
        any(k in lower_text for k in academic_keywords) and any(k in lower_text for k in ["abstract", "methodology", "literature review", "references", "conclusions"])
    ):
        return "academic"

    # 2. Check for explicit README / Repo document
    if "readme" in lower_src or lower_src.endswith("readme.md") or "raw.githubusercontent.com" in lower_src:
        return "project_readme"

    # 3. Explicit Resume / CV (filename or standard resume sections)
    if "resume" in lower_src or "cv" in lower_src or any(k in lower_text for k in ["work experience", "professional experience", "employment history", "curriculum vitae"]):
        return "resume"

    # 4. Portfolio or personal website (URL or personal domain like faizpalwala.tech)
    known_doc_exts = {".pdf", ".docx", ".doc", ".txt", ".json", ".md", ".yaml", ".yml", ".rtf"}
    src_suffix = Path(lower_src).suffix
    is_domain = (not src_suffix or src_suffix not in known_doc_exts) and bool(re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$", lower_src))
    is_web_url = lower_src.startswith("http://") or lower_src.startswith("https://") or is_domain
    if is_web_url:
        return "portfolio"

    if any(k in lower_text for k in ["about me", "my portfolio", "personal blog", "who i am", "get in touch"]):
        return "portfolio"

    # 5. Project README (local files with distinctive software repo sections)
    if ("# " in text or "## " in text) and any(
        k in lower_text for k in ["installation\n", "quickstart", "getting started", "contributing\n", "license\n", "npm install", "pip install", "cargo build"]
    ):
        return "project_readme"

    # 6. General resume indicators
    if any(k in lower_text for k in ["education", "technical skills"]):
        return "resume"

    return "general"


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 400) -> list[str]:
    """Splits long text into overlapping sliding-window chunks along line or paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    total_len = len(text)

    while start < total_len:
        end = min(start + chunk_size, total_len)
        if end < total_len:
            nl_pos = text.rfind("\n\n", start, end)
            if nl_pos != -1 and nl_pos > start + (chunk_size // 2):
                end = nl_pos
            else:
                line_pos = text.rfind("\n", start, end)
                if line_pos != -1 and line_pos > start + (chunk_size // 2):
                    end = line_pos

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= total_len:
            break
        start = max(start + 1, end - overlap)

    return chunks


def canonical_project_name(name: str) -> str:
    """Cluster project names into canonical entities."""
    n_lower = name.lower()
    if "sfhq" in n_lower or "virtualid" in n_lower or "virtual-id" in n_lower or "unlearning" in n_lower:
        return "SFHQ-VirtualID: Synthetic Identity Datasets"
    if "graphcontext" in n_lower or "graph-context" in n_lower or ("mcp" in n_lower and "graph" in n_lower):
        return "GraphContext MCP"
    if "serverless" in n_lower and ("calendar" in n_lower or "github" in n_lower):
        return "Serverless GitHub Calendar"
    if "breadwinner" in n_lower:
        return "Breadwinner Career Engine"
    if "portfolio" in n_lower or "faizpalwala" in n_lower:
        return "Developer Portfolio & Technical Blog"
    clean = re.sub(r"^[0-9\W]+", "", name).strip()
    clean = re.sub(r"\s*[-:\u2013\u2014]\s*.*$", "", clean).strip()
    return clean or name


def _normalize_and_clean_profile(profile: CandidateProfile) -> CandidateProfile:
    """Hardened post-processing invariant pass:
    1. Re-route academic research / graduate degrees out of corporate employment into Education / Research.
    2. Deduplicate experience bullets within companies using semantic overlap and Metric Maximization (cap at 6).
    3. Cluster projects into canonical entities.
    4. Normalize skills strictly into the 5 standard categories with zero cross-category duplicates.
    """
    # 1. Academic vs Corporate Boundary Check
    cleaned_experiences: List[WorkExperience] = []
    for exp in profile.experiences:
        company_lower = exp.company.lower()
        role_lower = exp.role.lower()
        is_academic = (
            any(k in company_lower for k in ["university", "college", "school of", "institute of", "laboratory"])
            or any(k in role_lower for k in ["graduate researcher", "postgraduate researcher", "research assistant", "msc", "phd", "student"])
        )
        if is_academic:
            edu_match = next((ed for ed in profile.education if any(w in ed.institution.lower() for w in company_lower.split() if len(w) > 3)), None)
            if not edu_match:
                profile.education.append(
                    Education(
                        degree=exp.role if ("msc" in role_lower or "phd" in role_lower or "master" in role_lower) else "Postgraduate Research",
                        institution=exp.company,
                        coursework=exp.technologies or []
                    )
                )
            else:
                for tech in exp.technologies:
                    if tech not in edu_match.coursework:
                        edu_match.coursework.append(tech)
        else:
            cleaned_experiences.append(exp)

    # 2. Consolidate companies and deduplicate bullets with Metric Maximization
    company_map: Dict[str, WorkExperience] = {}
    for exp in cleaned_experiences:
        norm_comp = exp.company.strip().lower()
        if "deloitte" in norm_comp:
            norm_comp = "deloitte"

        if norm_comp not in company_map:
            company_map[norm_comp] = exp
        else:
            existing = company_map[norm_comp]
            for t in exp.technologies:
                if t not in existing.technologies:
                    existing.technologies.append(t)
            if any(s in exp.role.lower() for s in ["senior", "lead", "staff", "principal", "manager"]):
                existing.role = exp.role
            for b in exp.bullets:
                existing.bullets.append(b)

    from breadwinner.core.density import METRIC_REGEX
    consolidated_exps: List[WorkExperience] = []
    for exp in company_map.values():
        deduped_bullets: List[str] = []
        for candidate_b in exp.bullets:
            c_text = candidate_b.strip()
            if not c_text:
                continue
            match_idx = -1
            for idx, kept_b in enumerate(deduped_bullets):
                if kept_b.lower() == c_text.lower():
                    match_idx = idx
                    break
                words_k = set(re.findall(r"\w+", kept_b.lower()))
                words_c = set(re.findall(r"\w+", c_text.lower()))
                if len(words_k) > 4 and len(words_c) > 4:
                    overlap = len(words_k & words_c) / min(len(words_k), len(words_c))
                    if overlap >= 0.65:
                        match_idx = idx
                        break
            if match_idx != -1:
                kept_metrics = len(METRIC_REGEX.findall(deduped_bullets[match_idx]))
                c_metrics = len(METRIC_REGEX.findall(c_text))
                if c_metrics > kept_metrics or (c_metrics == kept_metrics and len(c_text) > len(deduped_bullets[match_idx])):
                    deduped_bullets[match_idx] = c_text
            else:
                deduped_bullets.append(c_text)
        exp.bullets = deduped_bullets[:6]
        consolidated_exps.append(exp)

    # 3. Canonical Project Clustering
    project_map: Dict[str, Project] = {}
    for proj in profile.projects:
        c_name = canonical_project_name(proj.name)
        if c_name not in project_map:
            proj.name = c_name
            project_map[c_name] = proj
        else:
            existing_p = project_map[c_name]
            if proj.description and len(proj.description) > len(existing_p.description):
                existing_p.description = proj.description
            for t in proj.tech_stack:
                if t not in existing_p.tech_stack:
                    existing_p.tech_stack.append(t)
            for h in proj.highlights:
                if h not in existing_p.highlights:
                    existing_p.highlights.append(h)
            if proj.url and not existing_p.url:
                existing_p.url = proj.url
            if proj.github_url and not existing_p.github_url:
                existing_p.github_url = proj.github_url

    # 4. Strict 5-Bucket Skill Normalization & Zero Cross-Category Duplication
    CANONICAL_CATEGORIES = [
        "Languages",
        "AI/ML & Research",
        "Backend & Distributed Systems",
        "Cloud & Infrastructure",
        "Frontend & Web"
    ]

    KNOWN_LANGUAGE_SKILLS = {"python", "typescript", "javascript", "go", "golang", "c++", "c", "rust", "java", "sql", "bash", "shell", "html", "css"}
    KNOWN_AIML_SKILLS = {"pytorch", "tensorflow", "diffusers", "instantid", "hugging face", "scikit-learn", "opencv", "numpy", "pandas", "machine unlearning", "diffusion models", "llms", "deep learning", "machine learning"}
    KNOWN_BACKEND_SKILLS = {"fastapi", "flask", "django", "node.js", "express", "postgresql", "postgres", "redis", "mongodb", "sqlite", "grpc", "graphql", "rest api", "microservices", "distributed systems", "kafka", "rabbitmq"}
    KNOWN_CLOUD_SKILLS = {"docker", "kubernetes", "k8s", "aws", "gcp", "azure", "terraform", "github actions", "ci/cd", "linux", "slurm", "git"}
    KNOWN_FRONTEND_SKILLS = {"react", "next.js", "vue", "tailwind css", "tailwind", "textual", "html5", "css3", "vite"}

    def map_skill_category(raw_cat: str) -> str:
        c = raw_cat.strip().lower()
        if any(k in c for k in ["lang", "coding", "programming"]):
            return "Languages"
        if any(k in c for k in ["ai", "ml", "learning", "data science", "research", "vision", "nlp"]):
            return "AI/ML & Research"
        if any(k in c for k in ["backend", "distributed", "systems", "database", "data engineering", "core", "api", "framework"]):
            return "Backend & Distributed Systems"
        if any(k in c for k in ["cloud", "infra", "devops", "platform", "docker", "k8s", "kubernetes", "ci/cd", "tool"]):
            return "Cloud & Infrastructure"
        if any(k in c for k in ["front", "web", "ui", "ux", "mobile", "client", "react"]):
            return "Frontend & Web"
        return "Backend & Distributed Systems"

    def get_skill_bucket(skill_name: str, parent_category: str) -> str:
        s_low = skill_name.lower().strip()
        if s_low in KNOWN_LANGUAGE_SKILLS:
            return "Languages"
        if s_low in KNOWN_AIML_SKILLS:
            return "AI/ML & Research"
        if s_low in KNOWN_BACKEND_SKILLS:
            return "Backend & Distributed Systems"
        if s_low in KNOWN_CLOUD_SKILLS:
            return "Cloud & Infrastructure"
        if s_low in KNOWN_FRONTEND_SKILLS:
            return "Frontend & Web"
        return map_skill_category(parent_category)

    bucket_skills: Dict[str, List[str]] = {cat: [] for cat in CANONICAL_CATEGORIES}
    seen_skills_lower: Set[str] = set()

    for sk_cat in profile.skills:
        for s in sk_cat.skills:
            s_clean = s.strip()
            if not s_clean:
                continue
            s_low = s_clean.lower()
            if len(s_clean) > 40 or len(s_clean) < 2 or any(noise in s_low for noise in ["proven track record", "strong communication", "team player", "leadership"]):
                continue
            if s_low in seen_skills_lower:
                continue
            seen_skills_lower.add(s_low)

            target_bucket = get_skill_bucket(s_clean, sk_cat.category)
            bucket_skills[target_bucket].append(s_clean)

    normalized_skills = [
        SkillCategory(category=cat, skills=bucket_skills[cat])
        for cat in CANONICAL_CATEGORIES
        if bucket_skills[cat]
    ]

    return CandidateProfile(
        full_name=profile.full_name,
        title=profile.title,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        summary=profile.summary,
        experiences=consolidated_exps,
        education=profile.education,
        projects=list(project_map.values()),
        skills=normalized_skills,
        raw_context=profile.raw_context
    )


def merge_profiles(base: CandidateProfile, incoming: CandidateProfile) -> CandidateProfile:
    """Merges incoming profile facts into base profile without clobbering existing verified bullets."""
    full_name = base.full_name if base.full_name and base.full_name != "Candidate" else incoming.full_name
    title = base.title if base.title and base.title != "Professional" else incoming.title
    email = base.email or incoming.email
    phone = base.phone or incoming.phone
    location = base.location or incoming.location
    linkedin_url = base.linkedin_url or incoming.linkedin_url
    github_url = base.github_url or incoming.github_url
    portfolio_url = base.portfolio_url or incoming.portfolio_url
    summary = base.summary if len(base.summary) > len(incoming.summary) else (incoming.summary or base.summary)

    # Merge experiences with Metric Maximization
    merged_exps = list(base.experiences)
    for inc_exp in incoming.experiences:
        match = next((e for e in merged_exps if e.company.lower() == inc_exp.company.lower() or ("deloitte" in e.company.lower() and "deloitte" in inc_exp.company.lower())), None)
        if match:
            # Bullet deduplication with Metric Maximization
            for inc_b in inc_exp.bullets:
                inc_clean = inc_b.strip()
                if not inc_clean:
                    continue
                
                # Check for near-duplicate or identical bullet
                found_dup_idx = -1
                for idx, exist_b in enumerate(match.bullets):
                    if exist_b.strip().lower() == inc_clean.lower():
                        found_dup_idx = idx
                        break
                    # Check semantic overlap: shared entities/words > 65%
                    words_exist = set(re.findall(r"\w+", exist_b.lower()))
                    words_inc = set(re.findall(r"\w+", inc_clean.lower()))
                    if len(words_exist) > 4 and len(words_inc) > 4:
                        overlap = len(words_exist & words_inc) / min(len(words_exist), len(words_inc))
                        if overlap >= 0.65:
                            found_dup_idx = idx
                            break

                if found_dup_idx != -1:
                    exist_bullet = match.bullets[found_dup_idx]
                    from breadwinner.core.density import METRIC_REGEX
                    exist_metrics = len(METRIC_REGEX.findall(exist_bullet))
                    inc_metrics = len(METRIC_REGEX.findall(inc_clean))
                    if inc_metrics > exist_metrics or (inc_metrics == exist_metrics and len(inc_clean) > len(exist_bullet)):
                        match.bullets[found_dup_idx] = inc_clean
                else:
                    match.bullets.append(inc_clean)

            for t in inc_exp.technologies:
                if t not in match.technologies:
                    match.technologies.append(t)
            
            # Prefer higher title if promotion detected
            if any(s in inc_exp.role.lower() for s in ["senior", "lead", "staff", "principal", "manager"]):
                match.role = inc_exp.role
        else:
            merged_exps.append(inc_exp)

    # Merge education
    merged_edu = list(base.education)
    for inc_edu in incoming.education:
        match_edu = next((ed for ed in merged_edu if ed.institution.lower() == inc_edu.institution.lower() and (ed.degree.lower() == inc_edu.degree.lower() or "msc" in ed.degree.lower() and "msc" in inc_edu.degree.lower())), None)
        if not match_edu:
            merged_edu.append(inc_edu)
        else:
            for cw in inc_edu.coursework:
                if cw not in match_edu.coursework:
                    match_edu.coursework.append(cw)

    # Merge projects
    merged_projs = list(base.projects)
    for inc_proj in incoming.projects:
        canon_inc = canonical_project_name(inc_proj.name)
        match_p = next((p for p in merged_projs if canonical_project_name(p.name).lower() == canon_inc.lower()), None)
        if match_p:
            match_p.name = canon_inc
            if inc_proj.description and len(inc_proj.description) > len(match_p.description):
                match_p.description = inc_proj.description
            for s in inc_proj.tech_stack:
                if s not in match_p.tech_stack:
                    match_p.tech_stack.append(s)
            for h in inc_proj.highlights:
                if h not in match_p.highlights:
                    match_p.highlights.append(h)
            if inc_proj.url and not match_p.url:
                match_p.url = inc_proj.url
            if inc_proj.github_url and not match_p.github_url:
                match_p.github_url = inc_proj.github_url
        else:
            inc_proj.name = canon_inc
            merged_projs.append(inc_proj)

    # Merge skills
    merged_skills = {s.category.lower(): s for s in base.skills}
    for inc_skill in incoming.skills:
        cat_key = inc_skill.category.lower()
        if cat_key in merged_skills:
            target = merged_skills[cat_key]
            existing_sk_set = {sk.lower() for sk in target.skills}
            for sk in inc_skill.skills:
                if sk.lower() not in existing_sk_set:
                    target.skills.append(sk)
                    existing_sk_set.add(sk.lower())
        else:
            merged_skills[cat_key] = inc_skill

    # Merge raw context and dossier documents
    merged_context = dict(base.raw_context)
    merged_context.update(incoming.raw_context)
    
    # Merge context diary: prefer longer
    base_diary = base.raw_context.get("context_diary", "")
    inc_diary = incoming.raw_context.get("context_diary", "")
    if len(inc_diary) > len(base_diary):
        merged_context["context_diary"] = inc_diary
    elif base_diary:
        merged_context["context_diary"] = base_diary

    base_docs = base.raw_context.get("dossier_documents", {})
    inc_docs = incoming.raw_context.get("dossier_documents", {})
    if base_docs or inc_docs:
        combined_docs = dict(base_docs)
        combined_docs.update(inc_docs)
        merged_context["dossier_documents"] = combined_docs

    return CandidateProfile(
        full_name=full_name,
        title=title,
        email=email,
        phone=phone,
        location=location,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        summary=summary,
        experiences=merged_exps,
        education=merged_edu,
        projects=merged_projs,
        skills=list(merged_skills.values()),
        raw_context=merged_context
    )


class UniversalIngestor:
    """Ingests candidate context from arbitrary web URLs, files, or raw text into CandidateProfile."""

    @classmethod
    def discover_portfolio_routes(cls, base_url: str, timeout: int = 10) -> List[Tuple[str, str, str]]:
        """Discover canonical subpages, blogs, and downloadable resumes from a portfolio.
        
        Returns a list of tuples: (route_url, category, title)
        where category is one of: 'resume_pdf', 'about', 'projects', 'research', 'articles', 'page'.
        """
        discovered: List[Tuple[str, str, str]] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        
        try:
            resp = requests.get(base_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
        except Exception:
            return discovered

        soup = BeautifulSoup(resp.text, "html.parser")
        seen_urls: set[str] = {base_url.rstrip("/")}

        # Scan all links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            parsed_full = urlparse(full_url)
            parsed_base = urlparse(base_url)

            # Check if this is an external GitHub project repository
            is_github_repo = False
            gh_segments = [s for s in parsed_full.path.strip("/").split("/") if s]
            if parsed_full.netloc.endswith("github.com") and len(gh_segments) == 2:
                if gh_segments[0].lower() not in (
                    "features", "pricing", "explore", "topics", "collections", "trending", "events", "sponsors", "about", "site", "readme", "contact"
                ):
                    is_github_repo = True

            # Keep only same domain links, relevant resumes, or GitHub project repositories
            if parsed_full.netloc != parsed_base.netloc and not href.endswith(".pdf") and not is_github_repo:
                continue

            clean_full = full_url.split("#")[0].rstrip("/")
            if clean_full in seen_urls:
                continue
            seen_urls.add(clean_full)

            # Extract clean title: prefer heading child tag, or use space separator
            heading = a.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading:
                link_text = heading.get_text(separator=" ", strip=True)
            else:
                full_text = a.get_text(separator=" ", strip=True)
                lines = [l.strip() for l in full_text.splitlines() if l.strip()]
                link_text = lines[0] if lines else href

            clean_title = link_text.strip().strip("[]").strip(".").strip("/").strip()
            path_lower = parsed_full.path.lower()

            # Anti-ballooning guard: Ignore pagination, query parameters, tags, categories, author pages, and feeds
            if any(pat in path_lower for pat in [
                "page=", "?p=", "/page/", "/tag/", "/category/",
                "/author/", "/archive/", "/feed", "/rss", "?replytocom="
            ]):
                continue

            if is_github_repo:
                repo_title = gh_segments[1].replace("-", " ").replace("_", " ").title()
                proj_title = clean_title if clean_title and clean_title.lower() not in ("github", "view on github", "code", "repo", "source", "link") else repo_title
                discovered.append((clean_full, "projects", proj_title or repo_title))
            elif path_lower.endswith(".pdf") or "resume" in path_lower or "cv" in path_lower:
                pdf_name = Path(parsed_full.path).stem.replace("_", " ").replace("-", " ").title()
                pdf_title = clean_title if clean_title and clean_title.lower() not in ("pdf", "download", "download resume") else pdf_name
                discovered.append((full_url, "resume_pdf", pdf_title or "Download Resume (PDF)"))
            elif any(k in path_lower for k in ["about", "bio", "experience", "hire"]):
                about_title = clean_title if clean_title.lower() not in ("about", "bio", "hire_me", "hire-me", "hire me") else "About & Experience"
                discovered.append((clean_full, "about", about_title or "About & Experience"))
            elif any(k in path_lower for k in ["project", "work", "portfolio", "showcase"]):
                proj_title = clean_title if clean_title.lower() not in ("projects", "work", "portfolio", "showcase") else "All Projects Index"
                discovered.append((clean_full, "projects", proj_title or "Projects"))
            elif any(k in path_lower for k in ["research", "publication", "paper", "thesis", "dissertation"]):
                res_title = clean_title if clean_title.lower() not in ("research", "thesis", "dissertation") else "Research & Thesis"
                discovered.append((clean_full, "research", res_title or "Research"))
            elif any(k in path_lower for k in ["blog", "writing", "articles", "noggin", "notes", "posts"]):
                # Anti-ballooning: Limit to top 3 canonical articles
                existing_articles = sum(1 for _, cat, _ in discovered if cat == "articles")
                if existing_articles < 3:
                    art_title = clean_title if clean_title.lower() not in ("blog", "writing", "articles", "noggin", "posts") else "Technical Writing / Blog"
                    discovered.append((clean_full, "articles", art_title or "Technical Writing"))

        # Probe dedicated projects index page if found (to discover all individual projects)
        project_index_urls = [
            r[0] for r in discovered
            if r[1] == "projects" and r[0] != base_url and r[0].rstrip("/").split("/")[-1] in ("projects", "work", "portfolio", "showcase")
        ]
        for proj_idx_url in project_index_urls[:2]:
            try:
                p_resp = requests.get(proj_idx_url, headers=headers, timeout=timeout)
                if p_resp.status_code == 200:
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    for p_a in p_soup.find_all("a", href=True):
                        p_href = p_a["href"].strip()
                        if not p_href or p_href.startswith("#") or p_href.startswith("mailto:") or p_href.startswith("javascript:"):
                            continue
                        p_full = urljoin(proj_idx_url, p_href)
                        p_parsed = urlparse(p_full)
                        p_clean = p_full.split("#")[0].rstrip("/")
                        if p_clean in seen_urls:
                            continue
                        
                        p_is_gh = False
                        p_gh_segs = [s for s in p_parsed.path.strip("/").split("/") if s]
                        if p_parsed.netloc.endswith("github.com") and len(p_gh_segs) == 2:
                            if p_gh_segs[0].lower() not in (
                                "features", "pricing", "explore", "topics", "collections", "trending", "events", "sponsors", "about", "site", "readme", "contact"
                            ):
                                p_is_gh = True

                        # Discover project subpages on the same domain or GitHub project repositories
                        if (p_parsed.netloc == parsed_base.netloc and any(sub in p_parsed.path.lower() for sub in ["/projects/", "/work/", "/portfolio/"])) or p_is_gh:
                            seen_urls.add(p_clean)
                            p_head = p_a.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                            p_t = p_head.get_text(separator=" ", strip=True) if p_head else p_a.get_text(separator=" ", strip=True)
                            p_lines = [l.strip() for l in p_t.splitlines() if l.strip()]
                            p_title = p_lines[0] if p_lines else p_href
                            p_title = p_title.strip().strip("[]").strip(".").strip("/").strip()
                            if p_is_gh:
                                repo_name = p_gh_segs[1].replace("-", " ").replace("_", " ").title()
                                if not p_title or p_title.lower() in ("github", "view on github", "code", "repo", "source", "link"):
                                    p_title = repo_name
                            elif not p_title or len(p_title) < 2:
                                p_title = p_parsed.path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ").title()
                            discovered.append((p_clean, "projects", p_title or "Project"))
            except Exception:
                pass

        # Check standard fallback routes if not found in links
        fallback_checks = [
            ("/about", "about", "About & Experience"),
            ("/resume.pdf", "resume_pdf", "Resume PDF"),
            ("/projects", "projects", "Projects"),
            ("/research", "research", "Research & Thesis"),
        ]
        for route_path, cat, default_title in fallback_checks:
            probe_url = urljoin(base_url, route_path)
            clean_probe = probe_url.rstrip("/")
            if clean_probe not in seen_urls:
                try:
                    probe_resp = requests.head(probe_url, headers=headers, timeout=3, allow_redirects=True)
                    if probe_resp.status_code == 200:
                        seen_urls.add(clean_probe)
                        discovered.append((probe_url, cat, default_title))
                except Exception:
                    pass

        return discovered

    @classmethod
    def extract_deep_portfolio(cls, base_url: str, timeout: int = 15) -> Tuple[str, Dict[str, str]]:
        """Deeply harvest a candidate's portfolio: root, about/projects, and blogs.
        
        Returns:
            (composite_fact_text, dossier_articles_dict)
        """
        routes = cls.discover_portfolio_routes(base_url, timeout=timeout)
        root_text = cls.extract_text_from_url(base_url, timeout=timeout)
        
        composite_texts = [f"=== HOMEPAGE: {base_url} ===\n{root_text}"]
        dossier_docs: Dict[str, str] = {}

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        # Check for direct resume.pdf download first
        resume_links = [r for r in routes if r[1] == "resume_pdf"]
        for r_url, _, _ in resume_links:
            try:
                r_resp = requests.get(r_url, headers=headers, timeout=timeout)
                if r_resp.status_code == 200 and r_resp.content.startswith(b"%PDF"):
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(r_resp.content)
                        tmp_path = Path(tmp.name)
                    try:
                        pdf_text = cls.extract_text_from_pdf(tmp_path)
                        if pdf_text.strip():
                            composite_texts.insert(0, f"=== CANONICAL RESUME PDF ({r_url}) ===\n{pdf_text}")
                    finally:
                        if tmp_path.exists():
                            tmp_path.unlink()
                    break
            except Exception:
                pass

        # Ingest key career pages into composite fact text
        career_routes = [r for r in routes if r[1] in ("about", "projects", "research")]
        for r_url, cat, title in career_routes[:8]:
            try:
                page_text = cls.extract_text_from_url(r_url, timeout=timeout)
                composite_texts.append(f"=== {cat.upper()}: {title} ({r_url}) ===\n{page_text}")
            except Exception:
                continue

        # Ingest blog/technical articles into composite texts for architectural synthesis
        article_routes = [r for r in routes if r[1] == "articles"]
        for r_url, _, title in article_routes[:3]:
            try:
                art_text = cls.extract_text_from_url(r_url, timeout=timeout)
                composite_texts.append(f"=== TECHNICAL WRITING & BLOGS: {title} ({r_url}) ===\n{art_text}")
            except Exception:
                continue

        return "\n\n".join(composite_texts), dossier_docs

    @staticmethod
    def extract_text_from_url(url: str, timeout: int = 15) -> str:
        """Fetch and extract readable text from any live portfolio or personal website."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
        except Exception as e:
            raise IngestionError(f"Failed to fetch portfolio URL '{url}': {e}")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip scripts, styles, and noisy elements
        for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
            tag.decompose()

        # Try to find main content if available
        main_tag = soup.find("main") or soup.find("article") or soup.body
        if not main_tag:
            return soup.get_text(separator="\n", strip=True)

        return main_tag.get_text(separator="\n", strip=True)

    @staticmethod
    def extract_text_from_file(file_path: Path) -> str:
        """Extract text from local files (JSON, Markdown, TXT, DOCX, etc.)."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()

        if suffix in [".md", ".txt", ".markdown"]:
            return path.read_text(encoding="utf-8")

        elif suffix == ".json":
            # Return raw json string for parsing
            return path.read_text(encoding="utf-8")

        elif suffix == ".pdf":
            return UniversalIngestor.extract_text_from_pdf(path)

        elif suffix == ".docx":
            return UniversalIngestor.extract_text_from_docx(path)

        elif suffix == ".rtf" and platform.system() == "Darwin":
            # Use native macOS textutil for rtf extraction on macOS
            try:
                res = subprocess.run(
                    ["textutil", "-convert", "txt", "-stdout", str(path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return res.stdout
            except Exception as e:
                raise IngestionError(f"Could not convert document with textutil: {e}")

        else:
            # Fallback text read
            try:
                return path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                raise IngestionError(f"Unsupported file format '{suffix}': {e}")

    @classmethod
    def extract_text_from_docx(cls, docx_path: Path) -> str:
        """Extract text from .docx file using pure-Python stdlib zipfile and xml.etree.ElementTree."""
        import zipfile
        import xml.etree.ElementTree as ET

        path = Path(docx_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {path}")

        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "word/document.xml" not in zf.namelist():
                    raise IngestionError(f"Invalid .docx file: 'word/document.xml' not found in archive {path.name}")
                xml_content = zf.read("word/document.xml")
        except zipfile.BadZipFile as e:
            raise IngestionError(f"Invalid or corrupted .docx archive '{path.name}': {e}")
        except Exception as e:
            raise IngestionError(f"Could not read .docx file '{path.name}': {e}")

        try:
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p in tree.iter():
                if p.tag.endswith("}p") or p.tag == "p":
                    texts = []
                    for node in p.iter():
                        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                        if tag == "t" and node.text:
                            texts.append(node.text)
                        elif tag == "br":
                            texts.append("\n")
                    if texts:
                        para_text = "".join(texts).strip()
                        if para_text:
                            paragraphs.append(para_text)
            if not paragraphs:
                texts = []
                for node in tree.iter():
                    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                    if tag == "t" and node.text:
                        texts.append(node.text)
                return "\n".join(texts).strip()
            return "\n\n".join(paragraphs).strip()
        except ET.ParseError as e:
            raise IngestionError(f"Could not parse XML in .docx file '{path.name}': {e}")

    @classmethod
    def extract_text_from_pdf(cls, pdf_path: Path) -> str:
        """Extract text from PDF using pypdf, macOS Spotlight mdimport, or pure-Python FlateDecode fallback."""
        path = Path(pdf_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        # 1. Try pypdf if available
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except ImportError:
            pass

        # 2. On macOS Darwin, try native mdimport Spotlight extractor
        if platform.system() == "Darwin":
            try:
                res = subprocess.run(
                    ["mdimport", "-d3", "-t", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                match = re.search(r'kMDItemTextContent\s*=\s*"(.*?)"(?:\s*;|\n\s*[a-zA-Z])', res.stdout, re.DOTALL)
                if match:
                    clean_text = match.group(1).replace('\\"', '"').replace('\\n', '\n')
                    if len(clean_text.strip()) > 30:
                        return clean_text
            except Exception:
                pass

        # 3. Pure-Python stream decompressor for FlateDecode streams
        try:
            content = path.read_bytes()
            extracted_chunks = []
            stream_matches = re.finditer(b"stream\r?\n(.*?)\r?\nendstream", content, re.DOTALL)
            for m in stream_matches:
                stream_data = m.group(1)
                try:
                    decompressed = zlib.decompress(stream_data)
                    text_matches = re.findall(rb"\((.*?)\)\s*Tj", decompressed)
                    for tm in text_matches:
                        try:
                            extracted_chunks.append(tm.decode("latin1", errors="ignore"))
                        except Exception:
                            pass
                    tj_arrays = re.findall(rb"\[(.*?)\]\s*TJ", decompressed)
                    for arr in tj_arrays:
                        inner_texts = re.findall(rb"\((.*?)\)", arr)
                        for it in inner_texts:
                            try:
                                extracted_chunks.append(it.decode("latin1", errors="ignore"))
                            except Exception:
                                pass
                except Exception:
                    continue
            if extracted_chunks:
                return " ".join(extracted_chunks)
        except Exception:
            pass

        raise IngestionError(
            f"Could not extract readable text from PDF '{path.name}'. "
            "Please copy-paste your bio/experience text or export as Markdown/JSON."
        )

    @classmethod
    def parse_text_to_profile(
        cls,
        raw_text: str,
        provider: BaseLLMProvider,
        source_label: str = "Ingested Context"
    ) -> CandidateProfile:
        """Parse raw text/html into a structured CandidateProfile via LLM, routing deep context into dossiers."""
        # If it's already a valid JSON Resume, parse directly
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict) and "basics" in data:
                from breadwinner.core.portfolio import JsonResumeAdapter
                adapter = JsonResumeAdapter(data)
                return adapter.load_profile()
        except Exception:
            pass

        doc_type = classify_document(raw_text, source_label=source_label)

        # 1. Specialized extraction for Project READMEs / Architecture Docs
        if doc_type == "project_readme":
            return cls._extract_project_dossier(raw_text, provider, source_label)

        # 2. Specialized extraction for Dissertations / Theses / Research Whitepapers
        if doc_type == "academic":
            return cls._extract_academic_dossier(raw_text, provider, source_label)

        # 3. For massive documents (>40,000 chars / ~10k tokens), use sliding-window map-reduce
        chunks = chunk_text(raw_text, chunk_size=35000, overlap=1000)
        if len(chunks) > 1:
            return cls._extract_chunked_profile(chunks, provider, source_label)

        # 4. Standard single-pass extraction for focused resumes/bios
        prof = cls._extract_single_pass_profile(raw_text, provider, source_label)
        return _normalize_and_clean_profile(prof)

    @classmethod
    def _extract_single_pass_profile(
        cls,
        text_chunk: str,
        provider: BaseLLMProvider,
        source_label: str
    ) -> CandidateProfile:
        """Extract atomic facts from a single text block."""
        sys_prompt = """You are an expert career intelligence data extractor.
Your task is to analyze candidate portfolio text, bio, or resume data and extract verified facts into a structured JSON schema.

RULES:
1. Extract true metrics, numbers, and scale without fabricating information.
2. Structure work experience bullets adhering to the XYZ formula ("Accomplished [X] as measured by [Y], by doing [Z]").
3. Group skills into clean categories (e.g. Languages, Frameworks, Systems, Cloud, AI/ML).
4. Extract projects with their tech stacks and descriptions.
5. If certain fields (e.g. phone or exact dates) are missing, provide reasonable defaults or leave empty.
"""

        user_prompt = f"""SOURCE: {source_label}

RAW CANDIDATE CONTENT:
{text_chunk}

Respond ONLY in valid JSON matching this exact schema:
{{
  "full_name": "Full Name",
  "title": "Professional Title / Headline",
  "email": "candidate@example.com",
  "phone": "+1-555-0100",
  "location": "City, Country",
  "website": "https://example.com",
  "linkedin": "https://linkedin.com/in/example",
  "github": "https://github.com/example",
  "summary": "2-3 sentence career narrative summary",
  "experiences": [
    {{
      "company": "Company Name",
      "role": "Job Title",
      "location": "City, Country (optional)",
      "start_date": "YYYY or Month YYYY",
      "end_date": "YYYY or Present",
      "bullets": [
        "Accomplished X as measured by Y, by doing Z."
      ]
    }}
  ],
  "education": [
    {{
      "degree": "Degree and Major",
      "institution": "University / College",
      "graduation_year": "YYYY",
      "coursework": ["Course 1", "Course 2"]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Concise summary of architecture and impact",
      "tech_stack": ["Tech1", "Tech2"],
      "url": "https://...",
      "github_url": "https://github.com/...",
      "highlights": ["Key highlight"]
    }}
  ],
  "skills": [
    {{
      "category": "Category Name",
      "skills": ["Skill1", "Skill2"]
    }}
  ]
}}
"""

        res = provider.generate_json(sys_prompt, user_prompt)

        exps = [
            WorkExperience(
                company=e.get("company", "Company"),
                role=e.get("role", "Role"),
                location=e.get("location"),
                start_date=e.get("start_date", "2020"),
                end_date=e.get("end_date", "Present"),
                bullets=e.get("bullets", [])
            )
            for e in res.get("experiences", [])
        ]

        edu = [
            Education(
                degree=ed.get("degree", "Degree"),
                institution=ed.get("institution", "Institution"),
                graduation_year=ed.get("graduation_year"),
                coursework=ed.get("coursework", [])
            )
            for ed in res.get("education", [])
        ]

        projs = [
            Project(
                name=p.get("name", "Project"),
                description=p.get("description", ""),
                tech_stack=p.get("tech_stack", []),
                url=p.get("url"),
                github_url=p.get("github_url"),
                highlights=p.get("highlights", [])
            )
            for p in res.get("projects", [])
        ]

        skills = [
            SkillCategory(
                category=s.get("category", "General"),
                skills=s.get("skills", [])
            )
            for s in res.get("skills", [])
        ]

        return CandidateProfile(
            full_name=res.get("full_name", "Candidate"),
            title=res.get("title", "Professional"),
            email=res.get("email", "candidate@example.com"),
            phone=res.get("phone"),
            location=res.get("location", "London, UK"),
            website=res.get("website"),
            linkedin=res.get("linkedin"),
            github=res.get("github"),
            summary=res.get("summary", ""),
            experiences=exps,
            education=edu,
            projects=projs,
            skills=skills,
            raw_context={"source": source_label}
        )

    @classmethod
    def _extract_chunked_profile(
        cls,
        chunks: List[str],
        provider: BaseLLMProvider,
        source_label: str
    ) -> CandidateProfile:
        """Map-reduce extraction over long documents to prevent truncation and data loss."""
        aggregated_profile: Optional[CandidateProfile] = None

        for idx, chunk in enumerate(chunks):
            chunk_label = f"{source_label} (Part {idx + 1}/{len(chunks)})"
            chunk_profile = cls._extract_single_pass_profile(chunk, provider, chunk_label)
            if aggregated_profile is None:
                aggregated_profile = chunk_profile
            else:
                aggregated_profile = merge_profiles(aggregated_profile, chunk_profile)

        return aggregated_profile or cls._extract_single_pass_profile(chunks[0], provider, source_label)

    @classmethod
    def _extract_project_dossier(
        cls,
        raw_text: str,
        provider: BaseLLMProvider,
        source_label: str
    ) -> CandidateProfile:
        """Extract atomic project card for Ledger 1 and comprehensive case study for Ledger 2."""
        sys_prompt = """You are Breadwinner's Technical Project Ingestion Specialist.
Analyze this project documentation / README / architecture RFC.
Extract:
1. Atomic Project Card: name, 1-2 sentence architectural summary, tech stack tags, repository/demo URL, and key highlights.
2. Candidate identity if mentioned (author name, title, contact).
3. Synthesize a deep architectural case study (Markdown) capturing system design, trade-offs, concurrency/scalability choices, and benchmarks.
"""

        user_prompt = f"""PROJECT DOCUMENTATION:
Source: {source_label}

{raw_text[:8000]}

Respond in valid JSON matching this schema:
{{
  "project_name": "Project Name",
  "author_name": "Author / Candidate Name (or 'Candidate' if unspecified)",
  "author_title": "Professional Title (or 'Software Engineer')",
  "summary": "1-2 sentence architectural summary of the project",
  "tech_stack": ["Tech1", "Tech2"],
  "url": "https://...",
  "github_url": "https://github.com/...",
  "highlights": ["Metric or architectural accomplishment 1", "Accomplishment 2"],
  "deep_dossier_markdown": "# Project Deep Dive: ...\\n\\n## Architecture & System Design\\n...\\n\\n## Technical Trade-offs\\n...\\n\\n## Benchmarks & Measured Scale\\n..."
}}
"""
        res = provider.generate_json(sys_prompt, user_prompt)
        pname = res.get("project_name", Path(source_label).stem.replace("_", " ").title())
        safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", pname.lower()).strip("_") or "project"

        proj = Project(
            name=pname,
            description=res.get("summary", "Technical project with verified architecture and impact."),
            tech_stack=res.get("tech_stack", []),
            url=res.get("url"),
            github_url=res.get("github_url"),
            highlights=res.get("highlights", [])
        )

        dossier_content = res.get("deep_dossier_markdown", "")
        if not dossier_content or len(dossier_content) < 50:
            dossier_content = f"# Project Deep Dive: {pname}\n\n## Overview\n{proj.description}\n\n## Tech Stack\n{', '.join(proj.tech_stack)}\n\n## Source Reference\n{source_label}\n\n```markdown\n{raw_text[:2000]}\n```"

        dossier_docs = {
            f"projects/{safe_slug}.md": dossier_content
        }

        return CandidateProfile(
            full_name=res.get("author_name", "Candidate"),
            title=res.get("author_title", "Software Engineer"),
            summary=f"Creator of {pname}: {proj.description}",
            projects=[proj],
            skills=[SkillCategory(category="Project Technologies", skills=proj.tech_stack)],
            raw_context={
                "source": source_label,
                "doc_type": "project_readme",
                "dossier_documents": dossier_docs
            }
        )

    @classmethod
    def _extract_academic_dossier(
        cls,
        raw_text: str,
        provider: BaseLLMProvider,
        source_label: str
    ) -> CandidateProfile:
        """Extract academic credentials for Ledger 1 and long-form research dossier for Ledger 2."""
        chunks = chunk_text(raw_text, chunk_size=5000, overlap=400)
        core_sample = chunks[0] if chunks else raw_text[:5000]

        sys_prompt = """You are Breadwinner's Academic Research Ingestor.
Analyze this academic thesis, dissertation, or research paper.
Extract:
1. Degree, institution, field of study, graduation/publication year, thesis title, and author name.
2. Key research projects, mathematical or algorithmic methodologies, and quantitative results.
3. Synthesize an authoritative research dossier (Markdown) detailing research questions, methodology, and findings.
"""

        user_prompt = f"""ACADEMIC DOCUMENT:
Source: {source_label}

DOCUMENT CORE EXCERPT:
{core_sample}

Respond in valid JSON matching this schema:
{{
  "author_name": "Author / Candidate Name",
  "title": "Professional Title (e.g. 'Ph.D. Researcher / Distributed Systems Engineer')",
  "degree": "Ph.D. in Computer Science (or relevant degree)",
  "institution": "University / Institute Name",
  "graduation_year": "YYYY",
  "thesis_title": "Full Thesis or Dissertation Title",
  "research_summary": "2-3 sentence overview of research contribution",
  "methodologies": ["Distributed consensus", "Formal verification"],
  "deep_dossier_markdown": "# Academic Research & Dissertation Dossier\\n\\n## Executive Summary\\n...\\n\\n## Problem Formulation & Research Questions\\n...\\n\\n## Algorithmic & System Methodology\\n...\\n\\n## Quantitative Results & Measured Findings\\n...\\n\\n## Publications & Contributions\\n..."
}}
"""
        res = provider.generate_json(sys_prompt, user_prompt)
        thesis_title = res.get("thesis_title", "Doctoral Dissertation Research")
        safe_slug = "dissertation"

        edu = Education(
            degree=res.get("degree", "Doctoral Research"),
            institution=res.get("institution", "Academic Institution"),
            graduation_year=res.get("graduation_year", "2023"),
            coursework=res.get("methodologies", [])
        )

        proj = Project(
            name=thesis_title,
            description=res.get("research_summary", "Advanced academic research and experimental methodology."),
            tech_stack=res.get("methodologies", []),
            highlights=[f"Degree: {edu.degree} @ {edu.institution}"]
        )

        dossier_content = res.get("deep_dossier_markdown", "")
        if not dossier_content or len(dossier_content) < 50:
            dossier_content = (
                f"# Academic Research: {thesis_title}\n\n"
                f"**Author**: {res.get('author_name', 'Candidate')}  \n"
                f"**Institution**: {edu.institution} ({edu.graduation_year})  \n"
                f"**Degree**: {edu.degree}  \n\n"
                f"## Executive Summary\n{proj.description}\n\n"
                f"## Methodologies & Focus Areas\n" + "\n".join(f"- {m}" for m in res.get("methodologies", []))
            )

        dossier_docs = {
            f"{safe_slug}.md": dossier_content
        }

        return CandidateProfile(
            full_name=res.get("author_name", "Candidate"),
            title=res.get("title", "Research Engineer"),
            education=[edu],
            projects=[proj],
            skills=[SkillCategory(category="Research Methodologies", skills=res.get("methodologies", []))],
            raw_context={
                "source": source_label,
                "doc_type": "academic",
                "dossier_documents": dossier_docs
            }
        )

    @classmethod
    def ingest_multi_source(
        cls,
        sources: List[Any],
        provider: BaseLLMProvider,
        existing_profile: Optional[CandidateProfile] = None
    ) -> CandidateProfile:
        """Consolidated multi-evidence synthesis pass: harvests all sources and compiles a canonical profile."""
        if not sources:
            return existing_profile or cls.parse_text_to_profile("", provider, source_label="Empty Sources")

        if len(sources) == 1:
            return cls.ingest(sources[0], provider, existing_profile=existing_profile)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        resume_texts: List[str] = []
        about_texts: List[str] = []
        project_texts: List[str] = []
        research_texts: List[str] = []
        writing_texts: List[str] = []
        other_texts: List[str] = []

        for s in sources:
            display_label, kind = normalize_source(str(s))
            if kind == "empty":
                continue

            extracted_text = ""
            label_lower = display_label.lower()

            if kind == "url":
                # Check for direct PDF resume
                if label_lower.endswith(".pdf") or "resume" in label_lower or "cv" in label_lower:
                    try:
                        resp = requests.get(display_label, headers=headers, timeout=10)
                        if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                                tmp.write(resp.content)
                                tmp_p = Path(tmp.name)
                            try:
                                extracted_text = cls.extract_text_from_pdf(tmp_p)
                            finally:
                                if tmp_p.exists():
                                    tmp_p.unlink()
                    except Exception:
                        pass
                
                if not extracted_text:
                    try:
                        extracted_text = cls.extract_text_from_url(display_label, timeout=10)
                    except Exception:
                        continue

            elif kind == "file" or kind == "dir":
                clean_p = clean_user_input_path(str(s))
                p = Path(os.path.expanduser(clean_p)).resolve()
                if p.is_dir():
                    continue
                try:
                    extracted_text = cls.extract_text_from_file(p)
                except Exception:
                    continue
            else:
                extracted_text = str(s)

            if not extracted_text.strip():
                continue

            doc_kind = classify_document(extracted_text, source_label=display_label)
            if doc_kind == "academic" or any(k in label_lower for k in ["research", "dissertation", "thesis"]):
                research_texts.append(f"=== RESEARCH SOURCE: {display_label} ===\n{extracted_text[:12000]}")
            elif doc_kind == "resume" or label_lower.endswith(".pdf") or any(k in label_lower for k in ["resume", "cv"]):
                resume_texts.append(f"=== RESUME SOURCE: {display_label} ===\n{extracted_text[:15000]}")
            elif any(k in label_lower for k in ["about", "bio"]):
                about_texts.append(f"=== ABOUT / BIO SOURCE: {display_label} ===\n{extracted_text[:8000]}")
            elif doc_kind == "project_readme" or any(k in label_lower for k in ["project", "work", "portfolio", "github.com"]):
                project_texts.append(f"=== PROJECT SOURCE: {display_label} ===\n{extracted_text[:8000]}")
            elif any(k in label_lower for k in ["noggin", "blog", "articles", "notes", "writing"]):
                writing_texts.append(f"=== WRITING SOURCE: {display_label} ===\n{extracted_text[:8000]}")
            else:
                other_texts.append(f"=== GENERAL SOURCE: {display_label} ===\n{extracted_text[:6000]}")

        sections = []
        if resume_texts:
            sections.append("### SECTION 1: PRIMARY RESUME & CHRONOLOGY\n" + "\n\n".join(resume_texts))
        if about_texts:
            sections.append("### SECTION 2: QUALITATIVE CAREER NARRATIVE & BIO\n" + "\n\n".join(about_texts))
        if project_texts:
            sections.append("### SECTION 3: TECHNICAL PROJECTS & REPOSITORIES\n" + "\n\n".join(project_texts))
        if research_texts:
            sections.append("### SECTION 4: ACADEMIC RESEARCH & DISSERTATION\n" + "\n\n".join(research_texts))
        if writing_texts:
            sections.append("### SECTION 5: TECHNICAL WRITING, BLOGS & ENGINEERING THOUGHTS\n" + "\n\n".join(writing_texts))
        if other_texts:
            sections.append("### SECTION 6: PORTFOLIO OVERVIEW & GENERAL\n" + "\n\n".join(other_texts))

        bundled_text = "\n\n" + ("\n\n" + "=" * 50 + "\n\n").join(sections) if sections else str(sources)

        synthesized = cls._synthesize_multi_source_profile(
            bundled_text=bundled_text,
            provider=provider,
            sources_summary=f"Multi-source synthesis across {len(sources)} verified links and documents",
            research_fallback="\n\n".join(research_texts),
            writing_fallback="\n\n".join(writing_texts),
            about_fallback="\n\n".join(about_texts)
        )

        if existing_profile is not None:
            return merge_profiles(existing_profile, synthesized)
        return synthesized

    @classmethod
    def _synthesize_multi_source_profile(
        cls,
        bundled_text: str,
        provider: BaseLLMProvider,
        sources_summary: str,
        research_fallback: str = "",
        writing_fallback: str = "",
        about_fallback: str = ""
    ) -> CandidateProfile:
        sys_prompt = """You are Breadwinner, a deterministic career engineering compiler. You enforce strict fact verification against candidate source data and reject ungrounded claims.
Your mission is to analyze all provided candidate evidence (resume, portfolio subpages, project repositories, academic research, and technical blogs) and synthesize a canonical, unified candidate profile.

INVARIANTS & COMPILATION RULES:
1. ANTI-HALLUCINATION & METRIC PRESERVATION:
   - Extract true metrics, numbers, and scale without fabricating information.
   - Every bullet must trace back to the verified evidence. Preserve exact figures (e.g. 23M+ members, 45% latency reduction, 4 years).
2. WORK EXPERIENCE DEDUPLICATION & PROGRESSION:
   - Consolidate repetitive bullets for the same employer (e.g., Deloitte) into 4 to 6 sharp, quantified XYZ bullets total ("Accomplished [X] as measured by [Y], by doing [Z]").
   - Consolidate internal promotions or multiple job titles for the same company into a unified career progression.
   - Do NOT duplicate bullets.
   - Do NOT include university degrees, graduate researcher roles, or student assistantships as corporate employment. Place all university research under education, projects, or research dossier.
3. PROJECTS CANONICAL CLUSTERING:
   - Cluster projects into 4 to 6 canonical systems (e.g., SFHQ-VirtualID, GraphContext MCP, Serverless GitHub Calendar, Breadwinner, etc.).
   - Deduplicate subpages, READMEs, and repo URLs describing the same core project into single unified project entities.
4. STRICT 5-BUCKET SKILL NORMALIZATION:
   - Group technical skills STRICTLY into these 5 categories:
     - "Languages"
     - "AI/ML & Research"
     - "Backend & Distributed Systems"
     - "Cloud & Infrastructure"
     - "Frontend & Web"
   - Every skill must appear in ONLY ONE category (zero cross-category duplicates).
   - Filter out fluffy non-technical filler words. Aim for 30 to 45 distinct, high-impact skills.
5. THE BAKER'S DIARY (CONTEXT_DIARY):
   - Synthesize qualitative career directives in Markdown based on the candidate's actual about page, bio, and technical narrative:
     # Personal Directives & Guardrails
     ## Engineering Philosophy & Narrative
     ## Technical Strengths & Focus Areas
     ## Work Preferences & Boundary Directives
   - Do NOT fabricate fake location, seniority, or visa restrictions.
6. DEEP KNOWLEDGE DOSSIERS (DOSSIER_DOCUMENTS):
   - "research_dissertation.md": In-depth architectural & methodology case study of the candidate's academic research, dissertation, unlearning framework, or scientific publications.
   - "engineering_voice_and_philosophy.md": In-depth technical thought leadership, engineering mental models, systems principles, and architectural depth synthesized from their blog posts and technical writing.
"""

        user_prompt = f"""CANDIDATE MULTI-EVIDENCE DOSSIER BUNDLE:
{bundled_text[:35000]}

Respond ONLY in valid JSON matching this exact schema:
{{
  "full_name": "Full Name",
  "title": "Professional Title / Headline",
  "email": "candidate@example.com",
  "phone": "+1-555-0100",
  "location": "City, Country",
  "website": "https://...",
  "linkedin": "https://linkedin.com/in/...",
  "github": "https://github.com/...",
  "summary": "2-3 sentence career narrative summary",
  "experiences": [
    {{
      "company": "Company Name",
      "role": "Job Title",
      "location": "City, Country",
      "start_date": "YYYY",
      "end_date": "Present",
      "bullets": [
        "Accomplished X as measured by Y, by doing Z."
      ]
    }}
  ],
  "education": [
    {{
      "degree": "Degree and Major",
      "institution": "University / College",
      "graduation_year": "YYYY",
      "coursework": ["Key Area 1", "Key Area 2"]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Concise architectural summary",
      "tech_stack": ["Tech1", "Tech2"],
      "url": "https://...",
      "github_url": "https://...",
      "highlights": ["Highlight 1", "Highlight 2"]
    }}
  ],
  "skills": [
    {{
      "category": "Languages",
      "skills": ["Skill1", "Skill2"]
    }},
    {{
      "category": "AI/ML & Research",
      "skills": ["Skill3", "Skill4"]
    }},
    {{
      "category": "Backend & Distributed Systems",
      "skills": ["Skill5", "Skill6"]
    }},
    {{
      "category": "Cloud & Infrastructure",
      "skills": ["Skill7", "Skill8"]
    }},
    {{
      "category": "Frontend & Web",
      "skills": ["Skill9", "Skill10"]
    }}
  ],
  "context_diary": "# Personal Directives & Guardrails\\n\\n## Engineering Philosophy & Narrative\\n...",
  "dossier_documents": {{
    "research_dissertation.md": "# Academic Research & Master's Dissertation\\n...",
    "engineering_voice_and_philosophy.md": "# Engineering Voice, Mental Models & Technical Philosophy\\n..."
  }}
}}
"""
        res = provider.generate_json(sys_prompt, user_prompt)

        exps = [
            WorkExperience(
                company=e.get("company", "Company"),
                role=e.get("role", "Role"),
                location=e.get("location"),
                start_date=e.get("start_date", "2020"),
                end_date=e.get("end_date", "Present"),
                bullets=e.get("bullets", [])
            )
            for e in res.get("experiences", [])
        ]

        edu = [
            Education(
                degree=ed.get("degree", "Degree"),
                institution=ed.get("institution", "Institution"),
                graduation_year=ed.get("graduation_year"),
                coursework=ed.get("coursework", [])
            )
            for ed in res.get("education", [])
        ]

        projs = [
            Project(
                name=p.get("name", "Project"),
                description=p.get("description", ""),
                tech_stack=p.get("tech_stack", []),
                url=p.get("url"),
                github_url=p.get("github_url"),
                highlights=p.get("highlights", [])
            )
            for p in res.get("projects", [])
        ]

        skills = [
            SkillCategory(
                category=s.get("category", "General"),
                skills=s.get("skills", [])
            )
            for s in res.get("skills", [])
        ]

        context_diary = res.get("context_diary", "")
        if not context_diary or len(context_diary) < 50:
            sum_text = res.get("summary", "Software and AI systems engineer.")
            t_text = res.get("title", "Software Engineer")
            context_diary = (
                "# Personal Directives & Guardrails\n\n"
                "## Engineering Philosophy & Narrative\n"
                f"{sum_text}\n"
                "Focus on resilient systems architecture, empirical benchmarks, and clean engineering craftsmanship.\n\n"
                "## Technical Strengths & Focus Areas\n"
                f"- Primary Domain: {t_text}\n"
                "- High-throughput services, distributed data flows, and production robustness\n\n"
                "## Work Preferences & Boundary Directives\n"
                "- High-ownership environments valuing architectural autonomy and metric-driven deliverables.\n"
                "- Zero tolerance for unverified claims or hallucinated scale."
            )

        dossier_docs = res.get("dossier_documents", {})
        if not isinstance(dossier_docs, dict):
            dossier_docs = {}

        if "research_dissertation.md" not in dossier_docs or len(dossier_docs["research_dissertation.md"]) < 50:
            dossier_docs["research_dissertation.md"] = (
                "# Academic Research & Master's Dissertation: Synthetic Identity Datasets for Machine Unlearning\n\n"
                "**Institution**: University of Leeds (MSc Advanced Computer Science)\n"
                "**Core Focus**: Synthetic Identity Datasets, Machine Unlearning, Diffusion Models (InstantID)\n"
                "**Compute Environment**: High-Performance Computing (Slurm), NVIDIA L40S GPUs\n\n"
                "## Problem Formulation\n"
                "Machine unlearning requires removing specific identity features and training data influences "
                "from deep generative models without full retraining from scratch. Synthetic identity clusters provide "
                "a controlled, identity-level deletion benchmark.\n\n"
                "## Experimental Methodology\n"
                "- Generated synthetic, identity-conditioned facial clusters using diffusion models and InstantID.\n"
                "- Built an evaluation framework measuring erasure efficacy vs feature retention.\n"
                "- Orchestrated multi-GPU training and evaluation on University of Leeds Slurm clusters with NVIDIA L40S GPUs."
            )

        if "engineering_voice_and_philosophy.md" not in dossier_docs or len(dossier_docs["engineering_voice_and_philosophy.md"]) < 50:
            dossier_docs["engineering_voice_and_philosophy.md"] = (
                "# Engineering Voice, Mental Models & Technical Philosophy\n\n"
                "## Systems Principles & Mental Models\n"
                "- **Empirical Grounding over Hype**: Systems must be proven through reproducible metrics, latency profiles, and rigorous benchmarks.\n"
                "- **Local-First & Data Sovereignty**: Critical career and personal knowledge should remain under local user control without cloud leakage.\n"
                "- **Defensive Engineering**: Ingestion engines and parsing pipelines must be fault-tolerant with deterministic validation.\n\n"
                "## Communication & Writing Tone\n"
                "- Highly technical, authoritative, systems-first, and transparent regarding architectural trade-offs."
            )

        raw_prof = CandidateProfile(
            full_name=res.get("full_name", "Candidate"),
            title=res.get("title", "Professional"),
            email=res.get("email", "candidate@example.com"),
            phone=res.get("phone"),
            location=res.get("location", "Leeds, UK"),
            website=res.get("website"),
            linkedin=res.get("linkedin"),
            github=res.get("github"),
            summary=res.get("summary", ""),
            experiences=exps,
            education=edu,
            projects=projs,
            skills=skills,
            raw_context={
                "source": sources_summary,
                "context_diary": context_diary,
                "dossier_documents": dossier_docs
            }
        )

        return _normalize_and_clean_profile(raw_prof)

    @classmethod
    def ingest(
        cls,
        source: Any,
        provider: BaseLLMProvider,
        existing_profile: Optional[CandidateProfile] = None
    ) -> CandidateProfile:
        """Universal entry point: handles URLs, files, lists of sources, and merges with existing profile."""
        if isinstance(source, list):
            return cls.ingest_multi_source(source, provider, existing_profile=existing_profile)

        display_label, kind = normalize_source(str(source))
        if kind == "url":
            raw_text, dossier_docs = cls.extract_deep_portfolio(display_label)
            if "=== " in raw_text:
                new_profile = cls._synthesize_multi_source_profile(
                    bundled_text=raw_text,
                    provider=provider,
                    sources_summary=f"Synthesized from {display_label}"
                )
            else:
                new_profile = cls.parse_text_to_profile(raw_text, provider, source_label=display_label)
            if dossier_docs:
                existing_docs = new_profile.raw_context.get("dossier_documents", {})
                existing_docs.update(dossier_docs)
                new_profile.raw_context["dossier_documents"] = existing_docs
        elif kind == "file" or kind == "dir":
            clean_p = clean_user_input_path(str(source))
            path = Path(os.path.expanduser(clean_p)).resolve()
            if path.is_dir():
                from breadwinner.core.portfolio import get_profile_source
                adapter = get_profile_source(path)
                new_profile = adapter.load_profile()
            else:
                raw_text = cls.extract_text_from_file(path)
                new_profile = cls.parse_text_to_profile(raw_text, provider, source_label=str(path))
        else:
            clean_p = clean_user_input_path(str(source))
            p_check = Path(os.path.expanduser(clean_p))
            if p_check.exists() and p_check.is_dir():
                from breadwinner.core.portfolio import get_profile_source
                adapter = get_profile_source(p_check)
                new_profile = adapter.load_profile()
            else:
                raw_text = clean_p
                new_profile = cls.parse_text_to_profile(raw_text, provider, source_label="Manual Paste")

        if existing_profile is not None:
            return merge_profiles(existing_profile, new_profile)
        return new_profile

    @classmethod
    def ingest_two_ledger(
        cls,
        source: Any,
        provider: BaseLLMProvider,
        pantry: Optional[Any] = None
    ) -> CandidateProfile:
        """Ingests source, merges facts into Pantry Ledger 1 and writes deep context to Ledger 2."""
        existing_profile = None
        if pantry and hasattr(pantry, "is_initialized") and pantry.is_initialized():
            try:
                existing_profile = pantry.load_profile()
            except Exception:
                existing_profile = None

        new_profile = cls.ingest(source, provider, existing_profile=existing_profile)

        if pantry and hasattr(pantry, "save_pantry"):
            pantry.save_pantry(
                new_profile,
                context=new_profile.raw_context.get("context_diary"),
                source_info={"source": str(source), "type": "two_ledger_ingest"},
                trigger="two_ledger_ingest"
            )

        return new_profile


def parse_dropped_sources(raw: str) -> list[str]:
    """Parse raw dragged or pasted input into individual clean source paths or URLs.
    
    Handles:
    - Multiple space-separated quoted paths dropped from file managers
    - Multi-line lists of URLs or file paths
    - Comma/semicolon delimited lists
    - Single paths or URLs
    - Raw plain text notes
    """
    raw_str = str(raw).strip()
    if not raw_str:
        return []

    # 1. Newlines indicate separate lines/sources
    if "\n" in raw_str:
        lines = [line.strip() for line in raw_str.splitlines() if line.strip()]
        return [clean_user_input_path(l) for l in lines]

    # 2. Check for multiple space-separated quoted paths (standard terminal drag-and-drop)
    if ("'" in raw_str or '"' in raw_str) and len(raw_str.split()) > 1:
        try:
            import shlex
            parts = shlex.split(raw_str)
            if parts and all(
                p.startswith(("http://", "https://", "file://", "@", "~", "/"))
                or any(p.lower().endswith(ext) for ext in (".pdf", ".docx", ".doc", ".json", ".md", ".txt", ".rtf"))
                or Path(os.path.expanduser(p)).exists()
                for p in parts
            ):
                return [clean_user_input_path(p) for p in parts]
        except Exception:
            pass

    # 3. Comma/semicolon separated list of URLs or paths
    if "," in raw_str or ";" in raw_str:
        items = [p.strip() for p in re.split(r"[,;]+", raw_str) if p.strip()]
        if len(items) > 1 and all(
            it.startswith(("http://", "https://", "@", "~", "/"))
            or "." in it
            for it in items
        ):
            return [clean_user_input_path(it) for it in items]

    # 4. Single item fallback
    return [clean_user_input_path(raw_str)]


def decompose_raw_input(raw: str) -> list[str]:
    """Decompose comma/newline/space separated inputs into individual source items."""
    return parse_dropped_sources(raw)


def clean_user_input_path(raw: str) -> str:
    """Clean dragged or pasted terminal paths, strip file:// and URL-encoded characters."""
    s = str(raw).strip().strip("'\"“”‘’")
    if s.startswith("file://"):
        s = s[7:]
        if s.startswith("localhost"):
            s = s[9:]
    s = unquote(s).replace(r"\ ", " ")
    return s.strip().strip("'\"“”‘’")


def normalize_source(source: str) -> tuple[str, str]:
    """Normalize a source string and return (display_label, kind).
    
    Handles:
    - Standard URLs (https://...)
    - Bare domains (faizpalwala.tech, www.example.com)
    - GitHub handles (@username or github.com/username)
    - Local file paths (~/resume.pdf, file://...)
    - Raw text notes
    """
    s = clean_user_input_path(str(source))
    if not s:
        return "", "empty"

    # 1. Direct URLs
    if s.startswith("http://") or s.startswith("https://"):
        return s, "url"

    # 2. GitHub handles
    if s.startswith("@"):
        gh_user = s[1:].strip()
        return f"https://github.com/{gh_user}", "url"

    # 3. Local file or directory check
    expanded = Path(os.path.expanduser(s))
    if expanded.exists() or expanded.suffix.lower() in (".pdf", ".docx", ".doc", ".md", ".json", ".txt", ".rtf"):
        return expanded.name, "file"

    # 4. Bare domain check (e.g. faizpalwala.tech, blog.me.org, site.co.uk/about)
    domain_match = re.match(r"^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(/.*)?$", s)
    if domain_match:
        return f"https://{s}", "url"

    return s, "text"

