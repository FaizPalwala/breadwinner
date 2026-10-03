"""In-Text Screening Prompt Extractor (Vector 2 "Brown M&M" Stealth Prompts).

Detects explicit application instructions, writing prompts, and screening questions
buried within the body paragraphs of job descriptions.
"""

import re
from typing import List
from breadwinner.core.models import (
    ApplicationQuestion,
    QuestionType,
    QuestionSource
)


IN_TEXT_PROMPT_PATTERNS = [
    # "In your application / cover letter / note, please tell us / include / explain / describe..."
    r"(?:in\s+your\s+(?:application|cover\s+letter|note|submission)|when\s+applying)[^.!?\n]*?(?:please\s+)?(?:tell\s+us|include|explain|describe|share|mention|answer|state)[^.!?\n]+?[.!?\n]",
    # "To confirm you read this / To prove you are not a bot / To ensure you read..."
    r"(?:to\s+(?:confirm|ensure|prove|show)\s+(?:you\s+(?:have\s+)?read|you['’]re\s+not\s+a\s+bot|attention\s+to\s+detail))[^.!?\n]*?[.!?\n]",
    # "Please include / attach a link to your (github|portfolio|pr|code|writing)..."
    r"please\s+(?:include|attach|provide|share)\s+(?:a\s+link\s+to\s+your|your\s+favorite|an\s+example\s+of)[^.!?\n]+?[.!?\n]",
    # "Answer the following question(s): ..."
    r"(?:please\s+)?answer\s+(?:the\s+following|this)\s+(?:question|prompt)[^.!?\n]*?[:.!?\n]",
]


def extract_in_text_prompts(text: str) -> List[ApplicationQuestion]:
    """Scans job description markdown/text for in-text screening questions and secret test prompts."""
    if not text:
        return []

    found_prompts: List[ApplicationQuestion] = []
    seen_prompts = set()

    for pattern in IN_TEXT_PROMPT_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            prompt_str = m.group(0).strip()
            # Clean up leading/trailing punctuation and markdown bullets
            prompt_str = re.sub(r"^[-*#>\s]+", "", prompt_str).strip()
            prompt_str = re.sub(r"\s+", " ", prompt_str)

            # Avoid very short or generic sentences
            if len(prompt_str) < 25:
                continue

            # Deduplicate similar prompts
            normalized = prompt_str.lower()
            if any(normalized in s or s in normalized for s in seen_prompts):
                continue
            seen_prompts.add(normalized)

            # Determine likely question type
            q_type = QuestionType.TEXTAREA
            if any(k in normalized for k in ["link", "url", "github", "portfolio", "pr"]):
                q_type = QuestionType.TEXT
            elif any(k in normalized for k in ["word", "phrase", "code word"]):
                q_type = QuestionType.TEXT

            found_prompts.append(
                ApplicationQuestion(
                    id=f"in_text_{len(found_prompts) + 1}",
                    prompt=prompt_str,
                    required=True,  # In-text stealth prompts are almost always mandatory screening filters
                    question_type=q_type,
                    source=QuestionSource.IN_TEXT,
                    description="Screening instruction detected inside job description body text."
                )
            )

    return found_prompts
