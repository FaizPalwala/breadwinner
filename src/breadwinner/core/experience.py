"""Mathematical experience duration calculator for CandidateProfiles.

Calculates cumulative production experience in years for specific technologies,
preventing automated ATS knockout rejections.
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from breadwinner.core.models import CandidateProfile, WorkExperience


def _parse_date_to_months(date_str: str, is_end: bool = False) -> Optional[int]:
    """Converts diverse date strings into an absolute integer month count (year * 12 + month)."""
    if not date_str:
        return None
    
    clean = date_str.strip().lower()
    if clean in ["present", "current", "now"]:
        now = datetime.now()
        return now.year * 12 + now.month

    # Match YYYY-MM
    m_ym = re.search(r"\b(19\d\d|20\d\d)[-/.](0?[1-9]|1[0-2])\b", clean)
    if m_ym:
        year = int(m_ym.group(1))
        month = int(m_ym.group(2))
        return year * 12 + month

    # Match Month YYYY (e.g. "March 2021", "Jan 2019")
    months_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    m_my = re.search(r"\b([a-z]+)\s+(19\d\d|20\d\d)\b", clean)
    if m_my:
        m_name = m_my.group(1)
        year = int(m_my.group(2))
        if m_name in months_map:
            return year * 12 + months_map[m_name]

    # Match standalone YYYY
    m_y = re.search(r"\b(19\d\d|20\d\d)\b", clean)
    if m_y:
        year = int(m_y.group(1))
        # Default start to Jan, end to Dec
        return year * 12 + (12 if is_end else 1)

    return None


def calculate_experience_years(profile: CandidateProfile, technology: str) -> int:
    """Calculates non-overlapping cumulative years of experience for a technology."""
    tech_clean = technology.strip().lower()
    if not tech_clean or not profile.experiences:
        return 0

    # Word boundary regex for exact tech token matching (e.g. "go" should not match "good")
    tech_pattern = rf"\b{re.escape(tech_clean)}\b"

    matching_intervals: List[Tuple[int, int]] = []

    for exp in profile.experiences:
        has_tech = False
        
        # 1. Check tagged technologies list
        if any(tech_clean == t.strip().lower() for t in exp.technologies):
            has_tech = True
        
        # 2. Check role title
        if not has_tech and re.search(tech_pattern, exp.role.lower()):
            has_tech = True

        # 3. Check achievement bullets
        if not has_tech:
            for bullet in exp.bullets:
                if re.search(tech_pattern, bullet.lower()):
                    has_tech = True
                    break

        if has_tech:
            start_m = _parse_date_to_months(exp.start_date, is_end=False)
            if exp.is_current:
                now = datetime.now()
                end_m = now.year * 12 + now.month
            else:
                end_m = _parse_date_to_months(exp.end_date, is_end=True)

            if start_m is not None:
                if end_m is None or end_m < start_m:
                    end_m = start_m + 12  # fallback 1 year if missing end date
                matching_intervals.append((start_m, end_m))

    if not matching_intervals:
        return 0

    # Merge overlapping intervals to prevent double-counting simultaneous roles
    matching_intervals.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    for start, end in matching_intervals:
        if not merged:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

    total_months = sum(end - start for start, end in merged)
    years = round(total_months / 12.0)
    return max(1, years) if total_months >= 6 else 0


def calculate_skills_experience(
    profile: CandidateProfile,
    demanded_skills: List[str]
) -> Dict[str, int]:
    """Calculates experience duration for a set of demanded skills."""
    results: Dict[str, int] = {}
    for skill in demanded_skills:
        skill_clean = skill.strip()
        if not skill_clean:
            continue
        yrs = calculate_experience_years(profile, skill_clean)
        if yrs > 0:
            results[skill_clean] = yrs
    return results
