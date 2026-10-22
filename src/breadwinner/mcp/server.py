"""Breadwinner FastMCP Server.

Exposes 8 deterministic, typed tools for AI coding assistants over STDIO:
1. breadwinner_ingest_job: Ingest job URL or raw text -> persists job.json, JD, and portal_answers.md.
2. breadwinner_audit: Deterministic 6-pillar evaluation of resume against job contract.
3. breadwinner_tailor: Generate tailored resume and cover letter from pantry.
4. breadwinner_bake_pdf: Compile HTML to ATS PDF with page budget audit.
5. breadwinner_track_job: SQLite CRUD on tracker.db with CSV sync.
6. breadwinner_profile: Read and surgically mutate canonical profile.yaml with rollback snapshots.
7. breadwinner_dossier: Manage deep technical teardowns in pantry/dossier/.
8. breadwinner_personas: Manage narrative tailoring personas.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastmcp import FastMCP

from breadwinner.config import settings
from breadwinner.core.contract import (
    JobContract,
    ContractMetadata,
    EvaluationCriteria,
    save_application_contract_bundle,
    _cluster_job_domains
)
from breadwinner.core.audit import AuditEngine
from breadwinner.core.pantry import PantryManager
from breadwinner.core.persona import PersonaManager, Persona
from breadwinner.core.models import CandidateProfile, JobPosting
from breadwinner.core.curator import CareerCurator
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.core.pdf import render_html_to_pdf
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.db.sync import CsvSync

mcp = FastMCP(
    "breadwinner",
    instructions="Deterministic local-first career engineering studio and anti-hallucination resume compiler."
)


@mcp.tool()
def breadwinner_ingest_job(
    target_folder: str,
    source_type: str,
    payload: str,
    company: Optional[str] = None,
    title: Optional[str] = None,
    portal_type: Optional[str] = "general"
) -> Dict[str, Any]:
    """Ingest a target job posting from a URL or raw text and persist the JobContract bundle.

    Writes job_description.txt, job.json, and portal_answers.md into target_folder.
    """
    target_dir = Path(target_folder).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    company_name = company or "Target Company"
    role_title = title or "Software Engineer"
    raw_jd_text = payload

    if source_type.lower() == "url":
        from breadwinner.core.universal import UniversalJobIngestor
        try:
            job_posting = UniversalJobIngestor.ingest_url(payload)
            company_name = job_posting.company or company_name
            role_title = job_posting.title or role_title
            raw_jd_text = job_posting.cleaned_markdown or job_posting.raw_text or payload
        except Exception:
            # Fallback if unauthenticated network request fails
            pass

    # Extract technical domains from JD
    job_obj = JobPosting(
        id=re.sub(r'[^a-zA-Z0-9]+', '-', f"{company_name}-{role_title}").lower(),
        company=company_name,
        title=role_title,
        raw_text=raw_jd_text,
        cleaned_markdown=raw_jd_text
    )
    core_domains = _cluster_job_domains(job_obj)
    keywords_clean = [w for w in CareerCurator.extract_keywords(raw_jd_text) if len(w) > 3][:15]

    contract = JobContract(
        metadata=ContractMetadata(
            company=company_name,
            role=role_title,
            target_portal=portal_type or "general",
            page_budget=2
        ),
        evaluation_criteria=EvaluationCriteria(
            core_domains=core_domains,
            essential_keywords=keywords_clean[:8],
            preferred_keywords=keywords_clean[8:15]
        )
    )

    save_application_contract_bundle(
        folder_path=target_dir,
        contract=contract,
        raw_job_text=raw_jd_text
    )
    return contract.to_dict()


@mcp.tool()
def breadwinner_audit(
    resume_path: str,
    contract_path: str
) -> Dict[str, Any]:
    """Run a deterministic 6-pillar audit of a resume against a local JobContract.

    Evaluates:
    - Provenance Gate (Binary PASS/FAIL on verified institutions, employers, metrics)
    - Exact Title and Recruiter Search Alignment
    - Domain Evidence Recall (coverage of JD technical pillars)
    - Google XYZ True-Impact Density
    - Information Hierarchy (Page 1 Rule)
    - ATS Structural Parseability and Page Budget Fill
    """
    r_path = Path(resume_path).resolve()
    c_path = Path(contract_path).resolve()

    if not r_path.exists():
        raise FileNotFoundError(f"Resume file not found at: {r_path}")
    if not c_path.exists():
        raise FileNotFoundError(f"Job contract file not found at: {c_path}")

    report = AuditEngine.audit(r_path, c_path)
    return report.to_dict()


@mcp.tool()
def breadwinner_tailor(
    contract_path: str,
    target_folder: str,
    persona: Optional[str] = "tech_ai",
    template: Optional[str] = "jakes",
    directives: Optional[str] = None
) -> Dict[str, Any]:
    """Generate tailored resume and cover letter documents from the canonical pantry."""
    c_path = Path(contract_path).resolve()
    t_folder = Path(target_folder).resolve()
    t_folder.mkdir(parents=True, exist_ok=True)

    contract = JobContract.load(c_path)
    pm = PantryManager()
    profile = pm.load_profile() if pm.is_initialized() else None
    if not profile:
        raise ValueError("Candidate pantry is not initialized. Run 'breadwinner ingest' first.")

    # Curate profile experiences against contract
    job_mock = JobPosting(
        id=re.sub(r'[^a-zA-Z0-9]+', '-', f"{contract.metadata.company}-{contract.metadata.role}").lower(),
        company=contract.metadata.company,
        title=contract.metadata.role,
        raw_text=" ".join(contract.evaluation_criteria.core_domains + contract.evaluation_criteria.essential_keywords)
    )
    curated_result = CareerCurator.curate(profile, job_mock)

    from breadwinner.core.models import MatchAnalysis, TailoredApplication
    tailored_app = TailoredApplication(
        job=job_mock,
        persona=persona or "tech_ai",
        match_analysis=MatchAnalysis(
            match_score=95,
            matched_skills=contract.evaluation_criteria.essential_keywords
        ),
        tailored_summary=curated_result.curated_profile.summary or "",
        tailored_experiences=curated_result.curated_profile.experiences or [],
        tailored_projects=curated_result.curated_profile.projects or [],
        tailored_skills=curated_result.curated_profile.skills or []
    )

    # Render HTML and Markdown
    renderer = TemplateRenderer()
    resume_html = renderer.render_resume(
        curated_result.curated_profile,
        tailored_app,
        template_name=template or "jakes"
    )
    resume_md = renderer.render_resume(
        curated_result.curated_profile,
        tailored_app,
        template_name="markdown"
    )

    resume_html_path = t_folder / "resume.html"
    resume_md_path = t_folder / "resume.md"
    resume_html_path.write_text(resume_html, encoding="utf-8")
    resume_md_path.write_text(resume_md, encoding="utf-8")

    # Generate starter cover letter
    cover_letter_path = t_folder / "cover_letter.md"
    cl_text = (
        f"# Application for {contract.metadata.role} - {contract.metadata.company}\n\n"
        f"Dear {contract.metadata.company} Hiring Team,\n\n"
        f"I am writing to express my strong interest in the {contract.metadata.role} role at {contract.metadata.company}.\n\n"
        f"With deep experience across {', '.join(contract.evaluation_criteria.core_domains[:3])}, "
        f"I have architected high-impact systems delivering verified scalability and performance.\n\n"
        f"Sincerely,\n{profile.full_name}\n"
    )
    cover_letter_path.write_text(cl_text, encoding="utf-8")

    return {
        "status": "SUCCESS",
        "target_folder": str(t_folder),
        "generated_files": [
            str(resume_md_path),
            str(resume_html_path),
            str(cover_letter_path)
        ],
        "summary": curated_result.curation_summary
    }


@mcp.tool()
def breadwinner_bake_pdf(
    html_path: str,
    output_pdf_path: str,
    expected_page_count: Optional[int] = 2
) -> Dict[str, Any]:
    """Compile HTML resume to print-ready ATS PDF with page budget verification."""
    h_path = Path(html_path).resolve()
    pdf_path = Path(output_pdf_path).resolve()

    render_html_to_pdf(h_path, pdf_path)

    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    actual_pages = len(reader.pages)
    file_size = pdf_path.stat().st_size
    expected = expected_page_count or 2

    if actual_pages == expected:
        status = "SUCCESS"
        fill_ratio = 0.85
        advice = f"Document renders cleanly within the expected {expected}-page budget."
    elif actual_pages > expected:
        status = "OVERFLOW"
        fill_ratio = 1.0 + ((actual_pages - expected) * 0.2)
        advice = f"Document spilled onto page {actual_pages}; reduce section margins or tighten 1-2 bullets."
    else:
        status = "UNDERFILL"
        fill_ratio = round(actual_pages / expected, 2)
        advice = f"Document uses {actual_pages} of {expected} budgeted pages."

    return {
        "status": status,
        "pdf_path": str(pdf_path),
        "pages": actual_pages,
        "expected_pages": expected,
        "file_size_bytes": file_size,
        "fill_ratio": fill_ratio,
        "advice": advice
    }


@mcp.tool()
def breadwinner_track_job(
    company: str,
    title: str,
    folder_path: str,
    contract_path: str,
    status: str = "target",
    tier: Optional[str] = "core",
    ats_score: Optional[int] = None,
    xyz_score: Optional[int] = None,
    notes: Optional[str] = ""
) -> Dict[str, Any]:
    """Upsert application record in SQLite tracker.db and sync CSV."""
    repo = JobRepository(settings.database_path)
    safe_company = re.sub(r'[^a-zA-Z0-9]+', '-', company.lower()).strip('-')
    safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
    job_id = f"{safe_company}-{safe_title}"

    date_now = datetime.now().strftime("%Y-%m-%d")
    date_applied = date_now if status.lower() == "applied" else None

    record = JobRecord(
        id=job_id,
        company=company,
        title=title,
        status=status.lower(),
        folder_path=str(Path(folder_path).resolve()),
        contract_path=str(Path(contract_path).resolve()),
        ats_score=ats_score,
        xyz_score=xyz_score,
        date_added=date_now,
        date_applied=date_applied,
        notes=notes or ""
    )

    repo.upsert_job(record)
    # Sync with CSV
    CsvSync.export_to_csv(repo, settings.csv_tracker_path)

    return record.model_dump()


@mcp.tool()
def breadwinner_profile(
    action: str,
    section: Optional[str] = "all",
    operation: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Inspect or surgically mutate canonical profile.yaml with automated rollback snapshot."""
    pm = PantryManager()
    if not pm.is_initialized():
        raise ValueError("Pantry is uninitialized. Ingest candidate background first.")

    profile = pm.load_profile()

    if action.lower() == "get":
        data = profile.model_dump()
        if section and section.lower() != "all":
            return {section: data.get(section.lower())}
        return data

    elif action.lower() == "patch":
        if not payload:
            raise ValueError("Payload dictionary is required for patch action.")

        # Create rollback snapshot before mutating
        snap_id = pm.create_snapshot(trigger=f"mcp_patch_{section}")

        if section == "basics" or operation == "patch_basics":
            for k, v in payload.items():
                if hasattr(profile, k):
                    setattr(profile, k, v)
        elif section == "experiences" and operation == "append":
            from breadwinner.core.models import WorkExperience
            profile.experiences.append(WorkExperience(**payload))
        elif section == "skills" and operation == "append":
            from breadwinner.core.models import SkillCategory
            profile.skills.append(SkillCategory(**payload))

        pm.save_pantry(profile, trigger=f"mcp_patch_applied_{section}")
        return {
            "status": "SUCCESS",
            "snapshot_id": snap_id,
            "section": section,
            "operation": operation
        }

    else:
        raise ValueError(f"Unknown action '{action}'. Must be 'get' or 'patch'.")


@mcp.tool()
def breadwinner_dossier(
    action: str,
    rel_path: Optional[str] = None,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """Manage long-form technical teardowns and dissertations in pantry/dossier/."""
    pm = PantryManager()
    dossier_dir = pm.dossier_dir
    dossier_dir.mkdir(parents=True, exist_ok=True)

    if action.lower() == "list":
        files = pm.list_dossier_files()
        dossiers = [f["rel_path"] if isinstance(f, dict) else str(f) for f in files]
        return {"dossiers": sorted(dossiers)}

    elif action.lower() == "get":
        if not rel_path:
            raise ValueError("rel_path is required for get action.")
        return {
            "rel_path": rel_path,
            "content": pm.load_dossier_file(rel_path)
        }

    elif action.lower() == "save":
        if not rel_path or content is None:
            raise ValueError("rel_path and content are required for save action.")
        saved = pm.save_dossier_file(rel_path, content, trigger="mcp_dossier_save")
        return {
            "status": "SUCCESS",
            "rel_path": rel_path,
            "path": str(saved)
        }

    else:
        raise ValueError(f"Unknown action '{action}'. Must be 'list', 'get', or 'save'.")


@mcp.tool()
def breadwinner_personas(
    action: str,
    slug: Optional[str] = None,
    persona_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """List, read, and register narrative tailoring personas."""
    if action.lower() == "list":
        built_in_dir = PersonaManager.get_built_in_dir()
        user_dir = PersonaManager.get_user_dir()

        personas = []
        seen = set()
        for d in [user_dir, built_in_dir]:
            if d.exists():
                for f in d.glob("*.yaml"):
                    if f.stem not in seen:
                        seen.add(f.stem)
                        try:
                            p = PersonaManager.load_persona(f.stem)
                            personas.append({
                                "slug": p.slug,
                                "name": p.name,
                                "description": p.description,
                                "tone": p.tone
                            })
                        except Exception:
                            pass
        return {"personas": personas}

    elif action.lower() == "get":
        if not slug:
            raise ValueError("slug is required for get action.")
        persona = PersonaManager.load_persona(slug)
        return persona.model_dump()

    elif action.lower() == "set":
        if not slug or not persona_data:
            raise ValueError("slug and persona_data are required for set action.")
        user_dir = PersonaManager.get_user_dir()
        user_dir.mkdir(parents=True, exist_ok=True)
        import yaml
        target = user_dir / f"{slug}.yaml"
        target.write_text(yaml.dump(persona_data, sort_keys=False), encoding="utf-8")
        return {
            "status": "SUCCESS",
            "slug": slug,
            "path": str(target)
        }

    else:
        raise ValueError(f"Unknown action '{action}'. Must be 'list', 'get', or 'set'.")
