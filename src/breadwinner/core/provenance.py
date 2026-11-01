"""Anti-hallucination provenance, metric verification, and deterministic auto-healing engine."""

import re
from typing import Dict, Any, List, Set, Optional, Tuple, Union
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup

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
    "testament",
    "testament to",
    "pivotal",
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
    "testament": "demonstration",
    "testament to": "demonstration of",
    "pivotal": "critical",
    "elevate": "improve",
    "groundbreaking": "high-impact",
    "game-changer": "key improvement",
    "transformative": "strategic"
}


class ProvenanceAuditError(Exception):
    """Raised when rendered experience headers drift from canonical pantry facts."""

    def __init__(
        self,
        company_or_message: str,
        field: str = "",
        expected: str = "",
        rendered: str = "",
        message: Optional[str] = None
    ):
        if field and expected and rendered:
            self.company = company_or_message
            self.field = field
            self.expected = expected
            self.rendered = rendered
            self.delta = {
                "company": self.company,
                "field": self.field,
                "expected": self.expected,
                "rendered": self.rendered,
                "resolution": "Restore the canonical pantry value exactly. Do not alter dates or locations."
            }
            msg = message or (
                f"Experience header drift detected in {self.company}.\n"
                f"  • Field: {self.field}\n"
                f'  • Expected (pantry/profile.yaml): "{self.expected}"\n'
                f'  • Rendered (generated resume):    "{self.rendered}"\n'
                f"  • Resolution: Restore the canonical pantry value exactly. Do not alter dates or locations."
            )
        else:
            self.company = ""
            self.field = field
            self.expected = expected
            self.rendered = rendered
            self.delta = {
                "company": self.company,
                "field": self.field,
                "expected": self.expected,
                "rendered": self.rendered,
                "resolution": "Restore the canonical pantry value exactly. Do not alter dates or locations."
            }
            msg = company_or_message
        super().__init__(msg)


MONTH_NAME_TO_NUM = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}


def _parse_year_month(d: str) -> Optional[Tuple[int, Optional[int]]]:
    """Parse date string into (year, optional_month_num)."""
    s = d.strip().lower()
    if not s:
        return None
    m = re.match(r"^(\d{4})[-/](\d{1,2})$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^([a-z]+)\s+(\d{4})$", s)
    if m:
        month_num = MONTH_NAME_TO_NUM.get(m.group(1))
        if month_num:
            return int(m.group(2)), month_num
    m = re.match(r"^(\d{4})\s+([a-z]+)$", s)
    if m:
        month_num = MONTH_NAME_TO_NUM.get(m.group(2))
        if month_num:
            return int(m.group(1)), month_num
    m = re.match(r"^(\d{4})$", s)
    if m:
        return int(m.group(1)), None
    return None


def _dates_equivalent(d1: str, d2: str) -> bool:
    """Compare two date representations for equivalence."""
    s1 = d1.strip().lower()
    s2 = d2.strip().lower()
    if s1 == s2:
        return True
    norm1 = re.sub(r"[\s\u2013\u2014-]+", "-", s1)
    norm2 = re.sub(r"[\s\u2013\u2014-]+", "-", s2)
    if norm1 == norm2:
        return True
    ym1 = _parse_year_month(s1)
    ym2 = _parse_year_month(s2)
    if ym1 and ym2 and ym1 == ym2:
        return True
    return False


def _split_dates(raw_date: str) -> Tuple[str, str]:
    """Split date range string into start_date and end_date."""
    if not raw_date:
        return "", ""
    if "|" in raw_date:
        raw_date = raw_date.split("|")[0].strip()
    normalized = re.sub(r"[\s\u2013\u2014]+", " - ", raw_date)
    normalized = re.sub(r"\s*--\s*", " - ", normalized)
    parts = re.split(r"\s+-\s+|\s+to\s+", normalized, flags=re.IGNORECASE)
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1:
        return parts[0].strip(), ""
    return "", ""


def _parse_html_experience_headers(html_text: str) -> List[Dict[str, Any]]:
    """Extract experience entries from rendered HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    entries: List[Dict[str, Any]] = []

    entry_blocks = soup.find_all(class_=re.compile(r"\bentry\b"))
    for block in entry_blocks:
        comp_el = block.find(class_=re.compile(r"(company-name|entry-company|entry-subtitle|client-firm)"))
        role_el = block.find(class_=re.compile(r"(role-title|entry-title|entry-role)"))
        date_el = block.find(class_=re.compile(r"(date-badge|entry-date)"))
        loc_el = block.find(class_=re.compile(r"(loc-badge|entry-loc|entry-location)"))

        comp = ""
        role = ""
        if comp_el:
            comp = comp_el.get_text(strip=True).lstrip("@ ").strip()
        if role_el:
            role = role_el.get_text(strip=True)
            if comp and ("@" in role or comp in role):
                role = re.sub(rf"@\s*{re.escape(comp)}", "", role).strip()

        if not comp:
            continue

        date_text = date_el.get_text(strip=True) if date_el else ""
        loc = loc_el.get_text(strip=True) if loc_el else None

        if not loc and "|" in date_text:
            parts = date_text.split("|", 1)
            date_text = parts[0].strip()
            loc = parts[1].strip()

        start_date, end_date = _split_dates(date_text)
        entries.append({
            "company": comp,
            "title": role,
            "location": loc,
            "start_date": start_date,
            "end_date": end_date,
        })
    return entries


def _parse_markdown_experience_headers(md_text: str) -> List[Dict[str, Any]]:
    """Extract experience entries from rendered Markdown."""
    lines = md_text.splitlines()
    entries: List[Dict[str, Any]] = []
    in_exp = False

    has_sections = any(line.strip().startswith("## ") for line in lines)
    in_exp = not has_sections

    for idx, line in enumerate(lines):
        stripped = line.strip()
        upper = stripped.upper()
        if re.match(r"^##\s+(?:WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT\s+HISTORY|PROFESSIONAL\s+EXPERIENCE)", upper):
            in_exp = True
            continue
        elif stripped.startswith("## "):
            in_exp = False
            continue

        if in_exp and stripped.startswith("### "):
            heading = stripped[4:].strip()
            role, comp = "", ""
            if " - " in heading:
                parts = heading.split(" - ", 1)
                role, comp = parts[0].strip(), parts[1].strip()
            elif " @ " in heading:
                parts = heading.split(" @ ", 1)
                role, comp = parts[0].strip(), parts[1].strip()
            elif ", " in heading:
                parts = heading.split(", ", 1)
                role, comp = parts[0].strip(), parts[1].strip()
            else:
                role = heading

            dates = ""
            loc = None
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line.startswith("*") and next_line.endswith("*"):
                    meta = next_line.strip("*").strip()
                    if "|" in meta:
                        m_parts = meta.split("|", 1)
                        dates = m_parts[0].strip()
                        loc = m_parts[1].strip()
                    else:
                        dates = meta

            start_date, end_date = _split_dates(dates)
            entries.append({
                "company": comp,
                "title": role,
                "location": loc,
                "start_date": start_date,
                "end_date": end_date,
            })
    return entries


class ProvenanceReport(BaseModel):
    is_valid: bool = True
    status: str = "PASS"  # "PASS" or "FAIL"
    flagged_entities: List[str] = Field(default_factory=list)
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
    status: str = "PASS"  # "PASS" or "FAIL"
    flagged_entities: List[str] = Field(default_factory=list)
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
            clean.add(cleaned)
        return clean

    @classmethod
    def extract_source_facts(cls, profile: CandidateProfile) -> Set[str]:
        """Extract all verified numeric tokens from the candidate's verified profile."""
        source_texts = [
            profile.phone or "",
            profile.location or "",
            profile.summary or "",
            profile.raw_context.get("personal_context", "") if isinstance(profile.raw_context, dict) else ""
        ]
        for exp in profile.experiences or []:
            if exp.start_date:
                source_texts.append(str(exp.start_date))
            if exp.end_date:
                source_texts.append(str(exp.end_date))
            if exp.location:
                source_texts.append(str(exp.location))
            if exp.company:
                source_texts.append(str(exp.company))
            if exp.role:
                source_texts.append(str(exp.role))
            source_texts.extend(exp.bullets or [])
        for proj in profile.projects or []:
            source_texts.append(proj.description or "")
            source_texts.extend(proj.highlights or [])
            source_texts.extend(proj.tech_stack or [])
        for edu in profile.education or []:
            if edu.start_date:
                source_texts.append(str(edu.start_date))
            if edu.end_date:
                source_texts.append(str(edu.end_date))
            if edu.institution:
                source_texts.append(str(edu.institution))
            if edu.degree:
                source_texts.append(str(edu.degree))

        full_source = " ".join(source_texts)
        return cls.extract_metrics(full_source)

    @classmethod
    def parse_experience_headers(
        cls,
        rendered: Union[TailoredApplication, List[WorkExperience], List[Dict[str, Any]], str]
    ) -> List[Dict[str, Any]]:
        """Parse rendered experience entries into a structured schema:
        {company, title, location, start_date, end_date}
        """
        entries: List[Dict[str, Any]] = []
        if isinstance(rendered, TailoredApplication):
            for exp in rendered.tailored_experiences or []:
                entries.append({
                    "company": exp.company or "",
                    "title": exp.role or "",
                    "location": exp.location,
                    "start_date": exp.start_date or "",
                    "end_date": exp.end_date or "",
                })
        elif isinstance(rendered, list):
            for item in rendered:
                if isinstance(item, WorkExperience):
                    entries.append({
                        "company": item.company or "",
                        "title": item.role or "",
                        "location": item.location,
                        "start_date": item.start_date or "",
                        "end_date": item.end_date or "",
                    })
                elif isinstance(item, dict):
                    entries.append({
                        "company": item.get("company", ""),
                        "title": item.get("title") or item.get("role", ""),
                        "location": item.get("location"),
                        "start_date": str(item.get("start_date", "")),
                        "end_date": str(item.get("end_date", "")),
                    })
        elif isinstance(rendered, str):
            if "<" in rendered and ">" in rendered:
                entries = _parse_html_experience_headers(rendered)
            else:
                entries = _parse_markdown_experience_headers(rendered)
        return entries

    @classmethod
    def validate_experience_headers(
        cls,
        rendered: Union[TailoredApplication, List[WorkExperience], List[Dict[str, Any]], str],
        profile: CandidateProfile
    ) -> List[Dict[str, Any]]:
        """Assert an exact 1:1 match against the canonical entries in pantry/profile.yaml.

        Raises ProvenanceAuditError on any detected tenure or location drift.
        Returns the parsed structured experience entries.
        """
        entries = cls.parse_experience_headers(rendered)

        for entry in entries:
            r_comp = entry.get("company", "").strip()
            if not r_comp:
                continue

            r_loc = (entry.get("location") or "").strip()
            r_start = str(entry.get("start_date") or "").strip()
            r_end = str(entry.get("end_date") or "").strip()

            # If all header metadata fields are unpopulated (e.g. bullet-only test fixture), skip
            if not r_loc and not r_start and not r_end:
                continue

            # Find matching canonical experience
            matching = None
            r_comp_lower = r_comp.lower()
            for can in profile.experiences or []:
                if not can.company:
                    continue
                can_comp_lower = can.company.strip().lower()
                if can_comp_lower == r_comp_lower or can_comp_lower in r_comp_lower or r_comp_lower in can_comp_lower:
                    matching = can
                    break

            if not matching:
                continue

            c_loc = (matching.location or "").strip()
            c_start = str(matching.start_date or "").strip()
            c_end = str(matching.end_date or "").strip()

            drifted_fields: List[str] = []

            # 1. Location drift
            if r_loc:
                if not c_loc or c_loc.lower() != r_loc.lower():
                    drifted_fields.append("location")
            elif c_loc and (r_start or r_end):
                drifted_fields.append("location")

            # 2. Tenure drift
            if r_start:
                if not c_start or not _dates_equivalent(c_start, r_start):
                    drifted_fields.append("start_date")
            elif c_start and (r_loc or r_end):
                drifted_fields.append("start_date")

            if r_end:
                if not c_end or not _dates_equivalent(c_end, r_end):
                    drifted_fields.append("end_date")
            elif c_end and (r_loc or r_start):
                drifted_fields.append("end_date")

            if drifted_fields:
                def format_hdr(loc: str, s: str, e: str) -> str:
                    parts = []
                    if loc:
                        parts.append(loc)
                    d_parts = []
                    if s:
                        d_parts.append(s)
                    if e:
                        d_parts.append(e)
                    if d_parts:
                        parts.append(" - ".join(d_parts))
                    return " | ".join(parts) if parts else "N/A"

                expected_str = format_hdr(c_loc, c_start, c_end)
                rendered_str = format_hdr(r_loc, r_start, r_end)

                raise ProvenanceAuditError(
                    company_or_message=matching.company,
                    field=", ".join(drifted_fields),
                    expected=expected_str,
                    rendered=rendered_str
                )

        return entries

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
        # 1. Structural experience header validation (tenure & location)
        cls.validate_experience_headers(app, profile)

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
                if numeric_core and any(
                    numeric_core == re.sub(r"[^\d.]", "", sm)
                    and (("%" in m) == ("%" in sm))
                    and (("$" in m) == ("$" in sm))
                    for sm in source_metrics
                ):
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

        # Binary check on institutions and employers
        flagged_entities = []
        verified_employers = {e.company.lower().strip() for e in (profile.experiences or []) if e.company}
        for exp in app.tailored_experiences or []:
            if exp.company:
                comp_lower = exp.company.lower().strip()
                if not any(comp_lower in ve or ve in comp_lower for ve in verified_employers):
                    flagged_entities.append(f"Unverified employer: '{exp.company}' not found in pantry.")
                    warnings.append(f"Unverified employer: '{exp.company}' not found in candidate pantry.")

        verified_institutions = {edu.institution.lower().strip() for edu in (profile.education or []) if edu.institution}
        inst_pattern = re.compile(r"\b(?:University\s+of\s+[A-Z][a-zA-Z]+|(?!From|At|In|The|A|Attended|To|And|Or|Graduated)[A-Z][a-zA-Z]+\s+(?:University|College|Institute(?:\s+of\s+Technology)?))\b")
        found_institutions = set(inst_pattern.findall(combined_tailored))
        for inst in sorted(found_institutions):
            inst_lower = inst.lower().strip()
            if not any(inst_lower in vi or vi in inst_lower for vi in verified_institutions):
                flagged_entities.append(f"Unverified institution: '{inst}' not found in pantry.")
                warnings.append(f"Unverified institution: '{inst}' not found in candidate pantry.")

        is_valid = len(unverified) == 0 and len(banned_found) == 0 and len(flagged_entities) == 0
        status = "PASS" if is_valid else "FAIL"

        return ProvenanceReport(
            is_valid=is_valid,
            status=status,
            flagged_entities=flagged_entities,
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
            if orig_exp:
                # Heal location drift
                if exp.location and orig_exp.location and exp.location.strip().lower() != orig_exp.location.strip().lower():
                    healing_log.append(
                        f"Healed location in {exp.company}: Reverted '{exp.location}' to canonical '{orig_exp.location}'."
                    )
                    exp.location = orig_exp.location
                # Heal start_date drift
                if exp.start_date and orig_exp.start_date and not _dates_equivalent(orig_exp.start_date, exp.start_date):
                    healing_log.append(
                        f"Healed start date in {exp.company}: Reverted '{exp.start_date}' to canonical '{orig_exp.start_date}'."
                    )
                    exp.start_date = orig_exp.start_date
                # Heal end_date drift
                if exp.end_date and orig_exp.end_date and not _dates_equivalent(orig_exp.end_date, exp.end_date):
                    healing_log.append(
                        f"Healed end date in {exp.company}: Reverted '{exp.end_date}' to canonical '{orig_exp.end_date}'."
                    )
                    exp.end_date = orig_exp.end_date

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
                        if not (numeric_core and any(
                            numeric_core == re.sub(r"[^\d.]", "", sm)
                            and (("%" in m) == ("%" in sm))
                            and (("$" in m) == ("$" in sm))
                            for sm in source_metrics
                        )):
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
            else f"{grounding_score}% Grounded | {len(final_report.unverified_metrics) + len(final_report.flagged_entities)} Pending Warnings"
        )

        cert = ProvenanceCertificate(
            grounding_score=grounding_score,
            is_valid=final_report.is_valid,
            status=final_report.status,
            flagged_entities=final_report.flagged_entities,
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
