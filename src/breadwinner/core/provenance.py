"""Anti-hallucination provenance and metric verification engine."""

import re
from typing import Dict, Any, List, Set, Optional
from pydantic import BaseModel, Field

from breadwinner.core.models import CandidateProfile, TailoredApplication
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


class ProvenanceReport(BaseModel):
    is_valid: bool = True
    verified_metrics: List[str] = Field(default_factory=list)
    unverified_metrics: List[str] = Field(default_factory=list)
    banned_words_found: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProvenanceValidator:
    """Validates that tailored applications do not invent metrics or use banned AI fluff words."""

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
                # Also check if numeric core is substring of any source metric
                numeric_core = re.sub(r"[^\d.]", "", m)
                if numeric_core and any(numeric_core in sm for sm in source_metrics):
                    verified.append(m)
                else:
                    unverified.append(m)
                    warnings.append(f"Unverified metric '{m}' not found in candidate pantry.")

        # Check banned words
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
