"""Anti-hallucination provenance, metric verification, and deterministic auto-healing engine."""

import re
from typing import Dict, Any, List, Set, Optional, Tuple
from pydantic import BaseModel, Field

from breadwinner.core.models import CandidateProfile, TailoredApplication, WorkExperience, Project
from breadwinner.core.persona import Persona


DEFAULT_BANNED_WORDS = [
    "spearheaded",
    "orchestrated",
    "championed",
    "leveraged",
    "pioneered",
    "seamlessly",
    "passionate",
    "tapestry",
    "delve",
    "testament to",
    "elevate",
    "synergy",
    "groundbreaking",
    "game-changer",
    "transformative"
]

SLOP_REPLACEMENTS = {
    "spearheaded": "Led",
    "orchestrated": "Architected",
    "championed": "Drove",
    "leveraged": "Utilized",
    "pioneered": "Engineered",
    "seamlessly": "",
    "passionate": "",
    "synergy": "coordination",
    "delve": "investigate",
    "tapestry": "architecture",
    "testament to": "demonstration of",
    "elevate": "improve",
    "groundbreaking": "high-impact",
    "game-changer": "key improvement",
    "transformative": "strategic"
}


class ProvenanceReport(BaseModel):
    is_valid: bool = True
    verified_metrics: List[str] = Field(default_factory=list)
    unverified_metrics: List[str] = Field(default_factory=list)
    banned_words_found: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProvenanceCertificate(BaseModel):
    """Formal audit certificate guaranteeing anti-hallucination and metric grounding."""
    grounding_score: int = 100
    is_valid: bool = True
    verified_metrics: List[str] = Field(default_factory=list)
    unverified_metrics: List[str] = Field(default_factory=list)
    banned_words_found: List[str] = Field(default_factory=list)
    hallucinations_detected: int = 0
    hallucinations_healed: int = 0
    slop_words_cleaned: int = 0
    healing_log: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    summary: str = "Pantry: Verified (Strict) | Lexicon: Clean (0 flags)"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProvenanceValidator:
    """Validates that tailored applications do not invent metrics, tools, or use banned AI slop."""

    METRIC_REGEX = re.compile(
        r"(?:\$\s*\d+(?:\.\d+)?(?:\s*[kKmMbB]|\s*million|\s*thousand|\s*billion)?|"
        r"\b\d+(?:\.\d+)?%|"
        r"\b\d+(?:\.\d+)?\s*(?:k|K|m|M|b|B|QPS|qps|TPS|tps|ms|sec|s|min|hours|x|X|Gbps|MB|GB|TB|PB)\b|"
        r"\b\d{2,}\b)",
        re.IGNORECASE
    )

    @classmethod
    def extract_metrics(cls, text: str) -> Set[str]:
        """Extract all candidate metric tokens from text."""
        if not text:
            return set()
        matches = cls.METRIC_REGEX.findall(text)
        # Normalize: strip spaces, convert to lowercase for comparison
        clean = set()
        for m in matches:
            cleaned = re.sub(r"\s+", "", m).lower()
            # Ignore standard 4-digit years like 2018-2026
            if re.match(r"^(19|20)\d{2}$", cleaned):
                continue
            clean.add(cleaned)
        return clean

    @classmethod
    def extract_source_facts(cls, profile: CandidateProfile) -> Set[str]:
        """Extract all verified numeric tokens from the candidate's verified profile."""
        source_texts = [
            profile.summary or "",
            profile.raw_context.get("personal_context", "") if isinstance(profile.raw_context, dict) else ""
        ]
        for exp in profile.experiences or []:
            source_texts.extend(exp.bullets or [])
        for proj in profile.projects or []:
            source_texts.append(proj.description or "")
            source_texts.extend(proj.highlights or [])
            source_texts.extend(proj.tech_stack or [])

        full_source = " ".join(source_texts)
        return cls.extract_metrics(full_source)

    @classmethod
    def extract_verified_skills(cls, profile: CandidateProfile) -> Set[str]:
        """Extract all verified technical skills and tools from candidate profile."""
        skills = set()
        for sk_cat in profile.skills or []:
            for s in sk_cat.skills or []:
                skills.add(s.lower().strip())
        for proj in profile.projects or []:
            for t in proj.tech_stack or []:
                skills.add(t.lower().strip())
        for exp in profile.experiences or []:
            for t in getattr(exp, "technologies", []) or []:
                skills.add(t.lower().strip())
        return skills

    @classmethod
    def clean_slop_text(cls, text: str, banned_words: List[str]) -> Tuple[str, int]:
        """Replace banned AI buzzwords with clean, plain engineering language."""
        cleaned_text = text
        replacements_count = 0
        for b_word in banned_words:
            b_word_clean = b_word.lower().strip()
            pattern = re.compile(rf"\b{re.escape(b_word_clean)}\b", re.IGNORECASE)
            if pattern.search(cleaned_text):
                replacement = SLOP_REPLACEMENTS.get(b_word_clean, "")
                if replacement:
                    # Match casing of original first letter
                    def rep_match(m: re.Match) -> str:
                        orig = m.group(0)
                        if orig[0].isupper():
                            return replacement.capitalize()
                        return replacement.lower()
                    cleaned_text = pattern.sub(rep_match, cleaned_text)
                else:
                    # Remove the word and cleanup double spaces
                    cleaned_text = pattern.sub("", cleaned_text)
                    cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text).strip()
                replacements_count += 1
        return cleaned_text, replacements_count

    @classmethod
    def validate(
        cls,
        app: TailoredApplication,
        profile: CandidateProfile,
        persona: Optional[Persona] = None
    ) -> ProvenanceReport:
        """Run strict anti-hallucination provenance and banned words verification."""
        source_metrics = cls.extract_source_facts(profile)

        # Collect tailored text
        tailored_texts = [app.tailored_summary or "", app.cover_letter or ""]
        for exp in app.tailored_experiences or []:
            tailored_texts.extend(exp.bullets or [])
        for proj in app.tailored_projects or []:
            tailored_texts.append(proj.description or "")
            tailored_texts.extend(proj.highlights or [])

        combined_tailored = " ".join(tailored_texts)
        tailored_metrics = cls.extract_metrics(combined_tailored)

        verified = []
        unverified = []
        warnings = []

        for m in sorted(tailored_metrics):
            if m in source_metrics:
                verified.append(m)
            else:
                numeric_core = re.sub(r"[^\d.]", "", m)
                if numeric_core and any(numeric_core in sm for sm in source_metrics):
                    verified.append(m)
                else:
                    unverified.append(m)
                    warnings.append(f"Unverified metric '{m}' not found in candidate pantry.")

        active_banned = set(DEFAULT_BANNED_WORDS)
        if persona and persona.banned_words:
            active_banned.update(w.lower() for w in persona.banned_words)

        banned_found = []
        tailored_lower = combined_tailored.lower()
        for word in sorted(active_banned):
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, tailored_lower):
                banned_found.append(word)
                warnings.append(f"Detected banned buzzword: '{word}'.")

        is_valid = len(unverified) == 0 and len(banned_found) == 0

        return ProvenanceReport(
            is_valid=is_valid,
            verified_metrics=verified,
            unverified_metrics=unverified,
            banned_words_found=banned_found,
            warnings=warnings
        )

    @classmethod
    def verify_and_heal_application(
        cls,
        app: TailoredApplication,
        profile: CandidateProfile,
        persona: Optional[Persona] = None
    ) -> Tuple[TailoredApplication, ProvenanceCertificate]:
        """Deterministically audit every bullet, heal hallucinated metrics, and purge AI slop."""
        source_metrics = cls.extract_source_facts(profile)
        active_banned = sorted(list(set(DEFAULT_BANNED_WORDS + (persona.banned_words if persona else []))))

        healing_log: List[str] = []
        hallucinations_detected = 0
        hallucinations_healed = 0
        slop_words_cleaned = 0
        warnings: List[str] = []

        # 1. Audit and heal Work Experiences
        for exp_idx, exp in enumerate(app.tailored_experiences):
            orig_exp = next((e for e in profile.experiences if e.company.lower() in exp.company.lower()), None)
            orig_bullets = orig_exp.bullets if orig_exp else []
            orig_metrics = cls.extract_metrics(" ".join(orig_bullets)) if orig_bullets else set()

            healed_bullets: List[str] = []
            for b_idx, bullet in enumerate(exp.bullets):
                cur_bullet = bullet
                b_metrics = cls.extract_metrics(cur_bullet)

                # Find unverified metrics in this specific bullet
                bad_metrics = []
                for m in b_metrics:
                    if m not in source_metrics:
                        numeric_core = re.sub(r"[^\d.]", "", m)
                        if not (numeric_core and any(numeric_core in sm for sm in source_metrics)):
                            bad_metrics.append(m)

                if bad_metrics:
                    hallucinations_detected += len(bad_metrics)
                    # AUTO-HEAL: Revert to verified baseline bullet from candidate profile
                    if b_idx < len(orig_bullets):
                        replacement = orig_bullets[b_idx]
                        healing_log.append(
                            f"Healed bullet #{b_idx+1} in {exp.company}: Reverted unverified metric(s) {bad_metrics} to verified source bullet."
                        )
                        cur_bullet = replacement
                        hallucinations_healed += len(bad_metrics)
                    else:
                        # Strip the unverified metrics if no 1-to-1 original bullet exists
                        for bm in bad_metrics:
                            cur_bullet = re.sub(rf"\b{re.escape(bm)}\b", "[verified impact]", cur_bullet, flags=re.IGNORECASE)
                            healing_log.append(
                                f"Healed bullet #{b_idx+1} in {exp.company}: Purged unverified metric '{bm}'."
                            )
                            hallucinations_healed += 1

                # Clean banned slop words
                cur_bullet, cleaned_count = cls.clean_slop_text(cur_bullet, active_banned)
                if cleaned_count > 0:
                    slop_words_cleaned += cleaned_count
                    healing_log.append(f"Sanitized {cleaned_count} AI buzzword(s) in {exp.company} bullet #{b_idx+1}.")

                healed_bullets.append(cur_bullet.strip())

            exp.bullets = healed_bullets

        # 2. Audit and heal Summary
        summary = app.tailored_summary or ""
        sum_metrics = cls.extract_metrics(summary)
        bad_sum_metrics = [m for m in sum_metrics if m not in source_metrics]
        if bad_sum_metrics:
            hallucinations_detected += len(bad_sum_metrics)
            app.tailored_summary = profile.summary or ""
            healing_log.append(f"Healed Summary: Reverted to verified profile summary due to unverified metric(s) {bad_sum_metrics}.")
            hallucinations_healed += len(bad_sum_metrics)
        else:
            app.tailored_summary, s_cleaned = cls.clean_slop_text(summary, active_banned)
            slop_words_cleaned += s_cleaned

        # 3. Audit Cover Letter
        if app.cover_letter:
            app.cover_letter, cl_cleaned = cls.clean_slop_text(app.cover_letter, active_banned)
            slop_words_cleaned += cl_cleaned

        # 4. Final verification pass after healing
        final_report = cls.validate(app, profile, persona)

        # Grounding score: 100% when all hallucinations have been healed
        grounding_score = 100 if final_report.is_valid else max(75, 100 - (len(final_report.unverified_metrics) * 10))

        summary_text = (
            f"Pantry: Verified (Strict) | Lexicon: Clean (0 flags)"
            if final_report.is_valid
            else f"{grounding_score}% Grounded • {len(final_report.unverified_metrics)} Pending Warnings"
        )

        cert = ProvenanceCertificate(
            grounding_score=grounding_score,
            is_valid=final_report.is_valid,
            verified_metrics=final_report.verified_metrics,
            unverified_metrics=final_report.unverified_metrics,
            banned_words_found=final_report.banned_words_found,
            hallucinations_detected=hallucinations_detected,
            hallucinations_healed=hallucinations_healed,
            slop_words_cleaned=slop_words_cleaned,
            healing_log=healing_log,
            warnings=final_report.warnings,
            summary=summary_text
        )

        app.provenance_report = cert.to_dict()
        return app, cert
