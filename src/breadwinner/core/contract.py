"""Breadwinner Job Contract specification (job_contract.v1.json).

Defines the persistent machine-readable contract between job ingestion,
tailoring, visual baking, and provenance auditing.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from breadwinner.core.models import CandidateProfile, JobPosting, ApplicationQuestion


class ContractMetadata(BaseModel):
    company: str
    role: str
    portal_type: str = "general"
    source_url: Optional[str] = None
    seniority_level: str = "senior"
    page_budget: int = 2
    date_ingested: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ResumeDeliverable(BaseModel):
    required: bool = True
    template: str = "executive"
    target_pages: int = 2


class CoverLetterDeliverable(BaseModel):
    status: str = "optional"
    max_words: int = 250
    required_hooks: List[str] = Field(default_factory=list)


class PortfolioDeliverable(BaseModel):
    required: bool = False
    recommended_dossiers: List[str] = Field(default_factory=list)


class PortalQuestion(BaseModel):
    id: str
    prompt: str
    type: str = "text"
    required: bool = False
    options: List[str] = Field(default_factory=list)
    answer: str = ""


class ContractDeliverables(BaseModel):
    resume: ResumeDeliverable = Field(default_factory=ResumeDeliverable)
    cover_letter: CoverLetterDeliverable = Field(default_factory=CoverLetterDeliverable)
    portfolio_dossier: PortfolioDeliverable = Field(default_factory=PortfolioDeliverable)
    portal_questions: List[PortalQuestion] = Field(default_factory=list)


class KnockoutRules(BaseModel):
    min_experience_years: Optional[int] = None
    immediate_visa_sponsorship_needed: bool = False
    degree_level: Optional[str] = None
    work_authorization_required: bool = True


class EvaluationCriteria(BaseModel):
    core_domains: List[str] = Field(default_factory=list)
    essential_keywords: List[str] = Field(default_factory=list)
    preferred_keywords: List[str] = Field(default_factory=list)
    knockout_rules: KnockoutRules = Field(default_factory=KnockoutRules)


class JobContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_url: str = Field(
        default="https://breadwinner.tools/schemas/job_contract.v1.json",
        alias="$schema"
    )
    metadata: ContractMetadata
    deliverables: ContractDeliverables = Field(default_factory=ContractDeliverables)
    evaluation_criteria: EvaluationCriteria = Field(default_factory=EvaluationCriteria)

    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to serializable dict with $schema alias."""
        return self.model_dump(by_alias=True)

    def to_json(self, indent: int = 2) -> str:
        """Serialize contract to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> Path:
        """Write contract to target JSON file."""
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(indent=2) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path) -> "JobContract":
        """Load contract from target JSON file."""
        target = Path(path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"Job contract not found at: {target}")
        data = json.loads(target.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    @classmethod
    def create_contract_from_job(
        cls,
        job: JobPosting,
        template: Optional[str] = None,
        page_budget: Optional[int] = None,
        seniority_level: Optional[str] = None
    ) -> "JobContract":
        """Factory method to construct a JobContract from a parsed JobPosting."""
        title_low = job.title.lower()

        # 1. Infer seniority level
        if seniority_level:
            inferred_seniority = seniority_level
        elif any(k in title_low for k in ["staff", "principal", "distinguished", "architect", "lead", "director", "head", "vp"]):
            inferred_seniority = "senior"
        elif any(k in title_low for k in ["senior", "sr.", "sr ", "iii", "iv"]):
            inferred_seniority = "senior"
        elif any(k in title_low for k in ["intern", "junior", "jr.", "jr ", "graduate", "associate", "entry"]):
            inferred_seniority = "early"
        else:
            inferred_seniority = "mid_senior"

        # 2. Determine target page budget
        if page_budget is not None:
            pages = max(1, page_budget)
        elif inferred_seniority == "early":
            pages = 1
        else:
            pages = 2

        # 3. Deliverables
        active_template = template or ("compact_1page" if pages == 1 else "executive")
        portal_questions: List[PortalQuestion] = []
        for q in job.questions:
            q_type = "textarea" if (q.question_type and "area" in str(q.question_type).lower()) else "text"
            if q.options:
                q_type = "select"
            elif any(k in q.prompt.lower() for k in ["authorized", "sponsorship", "require", "are you", "do you", "will you"]):
                q_type = "boolean"
            portal_questions.append(PortalQuestion(
                id=q.id or f"q_{len(portal_questions)+1}",
                prompt=q.prompt,
                type=q_type,
                required=q.required,
                options=q.options,
                answer=q.answer or ""
            ))

        # 4. Evaluation Criteria: core domains & keywords
        core_domains = _cluster_job_domains(job)
        essential_keywords = [s.strip().lower() for s in job.extracted_skills if len(s.strip()) > 1]
        preferred_keywords = [t.strip().lower() for t in job.matched_technology_tags if t.strip().lower() not in essential_keywords]

        # 5. Knockout rules extraction
        min_years = None
        for txt in job.extracted_requirements + [job.cleaned_markdown, job.raw_text]:
            m = re.search(r"(\d+)\+?\s*years?(?:\s+of)?(?:\s+relevant)?\s+experience", txt, re.IGNORECASE)
            if m:
                try:
                    val = int(m.group(1))
                    if 1 <= val <= 25:
                        min_years = val if min_years is None else min(min_years, val)
                except ValueError:
                    pass

        metadata = ContractMetadata(
            company=job.company,
            role=job.title,
            portal_type=job.portal_type or "general",
            source_url=job.url,
            seniority_level=inferred_seniority,
            page_budget=pages,
            date_ingested=datetime.now(timezone.utc).isoformat()
        )

        deliverables = ContractDeliverables(
            resume=ResumeDeliverable(
                required=True,
                template=active_template,
                target_pages=pages
            ),
            cover_letter=CoverLetterDeliverable(
                status=str(job.cover_letter_status.value) if hasattr(job.cover_letter_status, "value") else "optional",
                max_words=250,
                required_hooks=core_domains[:3]
            ),
            portfolio_dossier=PortfolioDeliverable(required=False),
            portal_questions=portal_questions
        )

        evaluation_criteria = EvaluationCriteria(
            core_domains=core_domains,
            essential_keywords=essential_keywords[:25],
            preferred_keywords=preferred_keywords[:15],
            knockout_rules=KnockoutRules(
                min_experience_years=min_years,
                immediate_visa_sponsorship_needed=False,
                degree_level="bachelor_or_equivalent"
            )
        )

        return cls(
            schema_url="https://breadwinner.tools/schemas/job_contract.v1.json",
            metadata=metadata,
            deliverables=deliverables,
            evaluation_criteria=evaluation_criteria
        )


def _cluster_job_domains(job: JobPosting) -> List[str]:
    """Extract and cluster 4-6 high-salience technical domains from the job posting."""
    full_text = f"{job.title} {job.cleaned_markdown} {job.raw_text} {' '.join(job.extracted_skills)} {' '.join(job.extracted_requirements)}"
    t_lower = full_text.lower()

    DOMAIN_SIGNALS = [
        ("Large Language Models & Generative AI", ["llm", "large language model", "rag", "transformer", "diffusion", "genai", "prompt engineering", "langchain", "vllm", "mlx"]),
        ("Multi-Agent Orchestration & Systems", ["multi-agent", "agentic", "agent orchestration", "mcp", "model context protocol", "autogen", "crewai", "langgraph"]),
        ("Machine Learning & Deep Learning Systems", ["machine learning", "deep learning", "pytorch", "tensorflow", "fine-tuning", "model training", "cuda", "triton", "gpu"]),
        ("Distributed Systems & Microservices", ["distributed systems", "microservices", "event-driven", "kafka", "rabbitmq", "grpc", "message queue", "concurrency", "redis"]),
        ("Cloud Infrastructure & DevOps", ["cloud infrastructure", "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform", "ci/cd", "observability"]),
        ("Backend Engineering & API Design", ["backend", "rest api", "fastapi", "python", "golang", "go", "sql", "postgresql", "database architecture", "microservice"]),
        ("Frontend & UI Engineering", ["frontend", "react", "next.js", "typescript", "javascript", "tailwind", "ui/ux", "web applications"]),
        ("Data Engineering & Analytics", ["data engineering", "spark", "hadoop", "etl", "data pipeline", "snowflake", "bigquery", "data warehouse"])
    ]

    matched_domains: List[str] = []
    for domain_name, keywords in DOMAIN_SIGNALS:
        if any(re.search(r"\b" + re.escape(k) + r"\b", t_lower) for k in keywords):
            matched_domains.append(domain_name)
        if len(matched_domains) >= 6:
            break

    if not matched_domains:
        if job.extracted_skills:
            matched_domains = [s.title() for s in job.extracted_skills[:5]]
        else:
            matched_domains = ["Software Engineering & Architecture", "Systems Implementation"]

    return matched_domains


def generate_portal_answers_markdown(
    contract: JobContract,
    profile: Optional[CandidateProfile] = None,
    custom_qna: Optional[str] = None
) -> str:
    """Generate portal_answers.md containing logistical quick-fill data and screening question stubs."""
    meta = contract.metadata
    tech_tags = contract.evaluation_criteria.essential_keywords[:12]
    tags_str = ", ".join(f"`{t}`" for t in tech_tags) if tech_tags else "General Software Engineering"

    sections = [
        "# Application Logistics & Screening Answers",
        f"**Target Company:** {meta.company}",
        f"**Target Role:** {meta.role}",
        f"**Portal Type:** {meta.portal_type.capitalize()}",
        f"**Seniority Level:** {meta.seniority_level.capitalize()}",
        "",
        "## Quick-Fill Logistics",
        "- **Legally Authorized to Work:** Yes",
        "- **Require Visa Sponsorship:** No",
        "- **Work Authorization Status:** Authorized / Citizen / Permanent Resident",
        "- **Notice Period:** 1 Month / Immediate",
        "- **Earliest Start Date:** Immediate / Negotiable",
        "- **Compensation Expectation:** Competitive / Market Rate",
        "",
        "## Matched Technical Tags",
        tags_str,
        ""
    ]

    # Incorporate custom rendered QnA if available
    if custom_qna and custom_qna.strip():
        sections.append("## Screening Questions & Strategic Answers")
        sections.append(custom_qna.strip())
    elif contract.deliverables.portal_questions:
        sections.append("## Screening Questions & Strategic Answers")
        for idx, q in enumerate(contract.deliverables.portal_questions, 1):
            sections.append(f"### Q{idx}: {q.prompt}")
            if q.answer:
                sections.append(q.answer)
            elif q.type == "boolean":
                sections.append("**Answer:** Yes")
            else:
                sections.append("*Draft strategic response highlighting verified pantry accomplishments.*")
            sections.append("")
    else:
        sections.append("## Screening Questions & Strategic Answers")
        sections.append("*No dedicated screening questions identified in job posting. Ready for standard submission.*")

    return "\n".join(sections).strip() + "\n"


def save_application_contract_bundle(
    folder_path: Path,
    contract: JobContract,
    raw_job_text: str,
    portal_qna: Optional[str] = None,
    profile: Optional[CandidateProfile] = None
) -> Dict[str, Path]:
    """Atomically persist job_description.txt, job.json, and portal_answers.md into the application folder."""
    app_dir = Path(folder_path).resolve()
    app_dir.mkdir(parents=True, exist_ok=True)

    jd_path = app_dir / "job_description.txt"
    contract_path = app_dir / "job.json"
    answers_path = app_dir / "portal_answers.md"

    # 1. Persist unformatted job description text
    clean_text = raw_job_text.strip() if raw_job_text and raw_job_text.strip() else f"{contract.metadata.company} - {contract.metadata.role}"
    jd_path.write_text(clean_text + "\n", encoding="utf-8")

    # 2. Persist machine-readable evaluation contract
    contract.save(contract_path)

    # 3. Persist portal answers / logistics
    answers_content = generate_portal_answers_markdown(contract, profile=profile, custom_qna=portal_qna)
    answers_path.write_text(answers_content, encoding="utf-8")

    return {
        "job_description": jd_path,
        "job_contract": contract_path,
        "portal_answers": answers_path
    }
