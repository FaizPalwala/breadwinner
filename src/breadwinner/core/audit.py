"""Breadwinner 6-Pillar Audit Engine.

Evaluates resume documents against JobContract specifications with zero network calls:
1. Immutable Truth & Provenance Gate (Binary PASS / FAIL)
2. Exact Title & Recruiter Search Alignment (0 - 100)
3. Domain Evidence Recall (0 - 100)
4. Google XYZ True-Impact Density (0 - 100)
5. Information Hierarchy & The Page 1 Rule (0 - 100)
6. ATS Structural Parseability & Page Budget Fill (Diagnostic)
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field

from breadwinner.core.contract import JobContract
from breadwinner.core.models import CandidateProfile
from breadwinner.core.provenance import ProvenanceValidator, DEFAULT_BANNED_WORDS
from breadwinner.core.curator import CareerCurator
from breadwinner.core.density import (
    extract_achievement_bullets,
    is_xyz_compliant_bullet,
    is_true_impact_metric,
    TRUE_IMPACT_PATTERNS
)


class AuditProvenanceGate(BaseModel):
    status: str = "PASS"  # PASS or FAIL
    flagged_entities: List[str] = Field(default_factory=list)
    unverified_metrics: List[str] = Field(default_factory=list)
    banned_words_found: List[str] = Field(default_factory=list)


class AuditAtsAlignment(BaseModel):
    ats_score: int = 100
    exact_title_match: bool = False
    domain_recall_score: int = 100
    matched_domains: List[str] = Field(default_factory=list)
    missing_domains: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)


class AuditQualityMetrics(BaseModel):
    total_achievement_bullets: int = 0
    xyz_compliant_bullets: int = 0
    xyz_score: float = 0.0
    page1_impact_ratio: float = 0.0


class AuditPageBudget(BaseModel):
    pages: int = 2
    fill_ratio: float = 0.85
    status: str = "OPTIMAL"  # OPTIMAL, OVERFLOW, UNDERFILL


class AuditReport(BaseModel):
    provenance_gate: AuditProvenanceGate
    ats_alignment: AuditAtsAlignment
    quality_metrics: AuditQualityMetrics
    page_budget: AuditPageBudget
    recommendations: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AuditEngine:
    """Unified 6-pillar deterministic evaluation engine."""

    @classmethod
    def load_resume_text(cls, resume_input: Union[str, Path]) -> str:
        """Read resume from file or raw string, stripping HTML markup if needed."""
        text = str(resume_input)
        p = Path(text)
        if p.exists() and p.is_file():
            text = p.read_text(encoding="utf-8")

        # Strip HTML tags for plain text analysis if HTML is detected
        if "<html" in text.lower() or "</div>" in text.lower() or "<body" in text.lower():
            # Strip style and script tag contents completely
            stripped_text = re.sub(r"<(?:style|script)[^>]*>[\s\S]*?</(?:style|script)>", "", text, flags=re.IGNORECASE)
            # Prefix list items with bullet character so achievement bullet extractor recognises them
            text_with_bullets = re.sub(r"<li[^>]*>", "\n- ", stripped_text, flags=re.IGNORECASE)
            # Keep line breaks for block elements
            text_with_breaks = re.sub(r"<(?:p|div|h[1-6]|tr)[^>]*>", "\n", text_with_bullets, flags=re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", text_with_breaks)
            clean_text = re.sub(r"&nbsp;", " ", clean_text)
            clean_text = re.sub(r"&amp;", "&", clean_text)
            clean_text = re.sub(r"\n\s*\n+", "\n\n", clean_text)
            return clean_text.strip()
        return text

    @classmethod
    def audit(
        cls,
        resume_input: Union[str, Path],
        contract_input: Union[JobContract, Path, str],
        profile: Optional[CandidateProfile] = None
    ) -> AuditReport:
        """Run the complete 6-pillar audit deterministically."""
        resume_text = cls.load_resume_text(resume_input)

        # 1. Resolve JobContract
        if isinstance(contract_input, JobContract):
            contract = contract_input
        else:
            cp = Path(str(contract_input))
            if cp.exists() and cp.is_file():
                contract = JobContract.load(cp)
            else:
                contract = JobContract.from_json(str(contract_input))

        # 2. Resolve CandidateProfile if not supplied
        if profile is None:
            try:
                from breadwinner.core.pantry import PantryManager
                pm = PantryManager()
                if pm.is_initialized():
                    profile = pm.load_profile()
            except Exception:
                profile = None

        # --- PILLAR 1: Immutable Truth & Provenance Gate ---
        flagged_entities: List[str] = []
        unverified_metrics: List[str] = []
        banned_words_found: List[str] = []

        # Check banned buzzwords
        resume_lower = resume_text.lower()
        for b_word in sorted(DEFAULT_BANNED_WORDS):
            pattern = rf"\b{re.escape(b_word)}\b"
            if re.search(pattern, resume_lower):
                banned_words_found.append(b_word)

        if profile:
            # Check institutions
            verified_institutions = {edu.institution.lower().strip() for edu in (profile.education or []) if edu.institution}
            # Generically extract parenthetical names/acronyms (e.g. "Full Name (ACRONYM)")
            expanded_verified = set(verified_institutions)
            for vi in verified_institutions:
                parts = re.findall(r"([^(]+)(?:\(([^)]+)\))?", vi)
                for full, paren in parts:
                    if full.strip():
                        expanded_verified.add(full.strip())
                    if paren.strip():
                        expanded_verified.add(paren.strip())
            
            raw_found = re.findall(r"\b(?:University[^\S\r\n]+of[^\S\r\n]+[A-Za-z]+|[A-Za-z]+[^\S\r\n]+University|[A-Za-z]+[^\S\r\n]+Institute[^\S\r\n]+of[^\S\r\n]+Technology|[A-Za-z]+[^\S\r\n]+College)\b", resume_text, re.IGNORECASE)
            found_institutions = {inst.strip() for inst in raw_found if inst.lower().strip() not in {"the university", "a university", "the college"}}
            for inst in sorted(found_institutions):
                inst_lower = inst.lower().strip()
                if not any(inst_lower in vi or vi in inst_lower for vi in expanded_verified):
                    flagged_entities.append(f"Unverified institution: '{inst}' not found in candidate pantry.")

            # Check metrics
            source_metrics = ProvenanceValidator.extract_source_facts(profile)
            tailored_metrics = ProvenanceValidator.extract_metrics(resume_text)
            for m in sorted(tailored_metrics):
                if m not in source_metrics:
                    numeric_core = re.sub(r"[^\d.]", "", m)
                    if not (numeric_core and any(
                        numeric_core == re.sub(r"[^\d.]", "", sm)
                        and (("%" in m) == ("%" in sm))
                        and (("$" in m) == ("$" in sm))
                        for sm in source_metrics
                    )):
                        unverified_metrics.append(m)

        prov_status = "PASS" if (len(flagged_entities) == 0 and len(unverified_metrics) == 0 and len(banned_words_found) == 0) else "FAIL"
        provenance_gate = AuditProvenanceGate(
            status=prov_status,
            flagged_entities=flagged_entities,
            unverified_metrics=unverified_metrics,
            banned_words_found=banned_words_found
        )

        # --- PILLAR 2: Exact Title & Recruiter Search Alignment ---
        target_role = (contract.metadata.role if contract.metadata and contract.metadata.role else "").strip()
        role_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9+#]+", target_role) if len(t) > 2]

        # Extract top 3 sentences / header area
        lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
        header_text = " ".join(lines[:6]).lower()

        exact_title_match = False
        title_score = 0

        if target_role and target_role.lower() in header_text:
            exact_title_match = True
            title_score = 100
        elif role_tokens:
            matched_tokens = sum(1 for tok in role_tokens if tok in header_text)
            token_ratio = matched_tokens / len(role_tokens)
            if token_ratio >= 0.75:
                title_score = 80
            elif token_ratio >= 0.5:
                title_score = 50
            else:
                title_score = 25
        else:
            title_score = 100

        # --- PILLAR 3: Domain Evidence Recall ---
        core_domains = contract.evaluation_criteria.core_domains if contract.evaluation_criteria else []
        recall_score, matched_domains, missing_domains = CareerCurator.calculate_domain_evidence_recall(
            resume_text, core_domains
        )

        # Secondary keywords
        missing_keywords: List[str] = []
        if contract.evaluation_criteria:
            target_kws = list(getattr(contract.evaluation_criteria, "essential_keywords", []) or []) + list(getattr(contract.evaluation_criteria, "preferred_keywords", []) or [])
            for kw in target_kws:
                if kw.lower() not in resume_lower:
                    missing_keywords.append(kw)

        # Composite ATS Score: 30% title alignment + 70% domain evidence recall
        ats_score = int(round((title_score * 0.3) + (recall_score * 0.7)))
        ats_alignment = AuditAtsAlignment(
            ats_score=ats_score,
            exact_title_match=exact_title_match,
            domain_recall_score=int(round(recall_score)),
            matched_domains=matched_domains,
            missing_domains=missing_domains,
            missing_keywords=missing_keywords
        )

        # --- PILLAR 4: Google XYZ True-Impact Density ---
        achievement_bullets = extract_achievement_bullets(resume_text)
        xyz_compliant_count = 0
        for b in achievement_bullets:
            is_comp, _, _ = is_xyz_compliant_bullet(b)
            if is_comp:
                xyz_compliant_count += 1

        total_bullets = len(achievement_bullets)
        xyz_score = round((xyz_compliant_count / max(total_bullets, 1)) * 100.0, 1) if total_bullets > 0 else 0.0

        # --- PILLAR 5: Information Hierarchy (Page 1 Rule) ---
        # Front-loaded recruiter magnet: >= 65% of impact metrics on Page 1
        # Divide document into Page 1 and remaining content
        if len(lines) <= 50:
            page1_text = resume_text
        elif "---" in resume_text:
            pages_content = resume_text.split("---", 1)
            page1_text = pages_content[0]
        else:
            # First 60% of lines represent Page 1 of a multi-page document
            split_idx = max(int(len(lines) * 0.60), 1)
            page1_text = "\n".join(lines[:split_idx])

        # Count true impact metrics on Page 1 vs total
        page1_metrics = 0
        total_impact_metrics = 0
        for p in TRUE_IMPACT_PATTERNS:
            page1_metrics += len(p.findall(page1_text))
            total_impact_metrics += len(p.findall(resume_text))

        page1_impact_ratio = round((page1_metrics / max(total_impact_metrics, 1)) * 100.0, 1) if total_impact_metrics > 0 else 100.0

        quality_metrics = AuditQualityMetrics(
            total_achievement_bullets=total_bullets,
            xyz_compliant_bullets=xyz_compliant_count,
            xyz_score=xyz_score,
            page1_impact_ratio=page1_impact_ratio
        )

        # --- PILLAR 6: ATS Structural Parseability & Page Budget ---
        expected_budget = contract.metadata.page_budget if contract.metadata and contract.metadata.page_budget else 2
        # Estimate page fill based on line count (approx 65-75 lines per printed page)
        line_count = len(lines)
        estimated_pages = max(1, int(round(line_count / 65)))
        fill_ratio = round(min(0.95, line_count / (expected_budget * 65.0)), 2)

        if estimated_pages == expected_budget and fill_ratio >= 0.70:
            budget_status = "OPTIMAL"
        elif estimated_pages > expected_budget or fill_ratio > 0.95:
            budget_status = "OVERFLOW"
        else:
            budget_status = "UNDERFILL"

        page_budget = AuditPageBudget(
            pages=estimated_pages,
            fill_ratio=fill_ratio,
            status=budget_status
        )

        # Recommendations
        recommendations: List[str] = []
        if not exact_title_match and target_role:
            recommendations.append(f"Include exact target title '{target_role}' in header or first sentence of summary to satisfy recruiter Boolean search filters.")
        if missing_domains:
            recommendations.append(f"Add evidence bullets for missing JD domain(s): {', '.join(missing_domains)}.")
        if missing_keywords:
            recommendations.append(f"Incorporate missing secondary keywords: {', '.join(missing_keywords[:3])}.")
        if xyz_score < 75.0:
            recommendations.append("Strengthen accomplishment bullets using the Google XYZ formula: [Accomplished X] as measured by [Y], by doing [Z].")
        if page1_impact_ratio < 65.0:
            recommendations.append("Apply the Page 1 Rule: front-load at least 65% of verified scale and throughput metrics into the top half of the resume.")
        if budget_status == "OVERFLOW":
            recommendations.append(f"Document exceeds the {expected_budget}-page budget; tighten bullet lengths or remove low-relevance items.")
        if flagged_entities:
            recommendations.append(f"Remove unverified entities not present in candidate pantry: {', '.join(flagged_entities)}.")
        if banned_words_found:
            recommendations.append(f"Purge AI buzzwords from text: {', '.join(banned_words_found)}.")

        return AuditReport(
            provenance_gate=provenance_gate,
            ats_alignment=ats_alignment,
            quality_metrics=quality_metrics,
            page_budget=page_budget,
            recommendations=recommendations
        )
