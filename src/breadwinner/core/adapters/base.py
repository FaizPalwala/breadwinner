"""Base class and common contracts for First-Class ATS Adapters."""

import re
from abc import ABC, abstractmethod
from typing import Optional, List
from bs4 import BeautifulSoup

from breadwinner.core.models import (
    IngestedJobResult,
    ApplicationQuestion,
    QuestionType,
    QuestionSource,
    CoverLetterRequirement,
    KnockoutLogistics
)


class BaseATSAdapter(ABC):
    """Abstract base adapter for querying public, unauthenticated ATS APIs."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the ATS platform (e.g. 'greenhouse', 'lever')."""
        pass

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Determines if this adapter handles the given URL."""
        pass

    @abstractmethod
    def extract(self, url: str) -> IngestedJobResult:
        """Extracts structured job posting data via public APIs."""
        pass

    @classmethod
    def html_to_markdown(cls, html_str: str) -> str:
        """Converts HTML text to clean Markdown, stripping scripts, styles, and empty lines."""
        if not html_str:
            return ""

        soup = BeautifulSoup(html_str, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # Replace headers
        for h1 in soup.find_all("h1"):
            h1.replace_with(f"\n\n# {h1.get_text().strip()}\n\n")
        for h2 in soup.find_all("h2"):
            h2.replace_with(f"\n\n## {h2.get_text().strip()}\n\n")
        for h3 in soup.find_all("h3"):
            h3.replace_with(f"\n\n### {h3.get_text().strip()}\n\n")
        for h4 in soup.find_all("h4"):
            h4.replace_with(f"\n\n#### {h4.get_text().strip()}\n\n")

        # Replace lists
        for li in soup.find_all("li"):
            li.replace_with(f"\n- {li.get_text().strip()}")

        # Replace paragraphs
        for p in soup.find_all("p"):
            p.replace_with(f"\n\n{p.get_text().strip()}\n\n")

        # Extract text and collapse excessive whitespace
        text = soup.get_text()
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text
