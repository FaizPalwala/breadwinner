"""Universal profile ingestion engine from URLs, documents, and freeform text."""

import json
import re
import zlib
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
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


class UniversalIngestor:
    """Ingests candidate context from arbitrary web URLs, files, or raw text into CandidateProfile."""

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

        elif suffix in [".docx", ".rtf"] and platform.system() == "Darwin":
            # Use native macOS textutil for zero-dependency docx extraction
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
        """Parse raw text/html into a structured CandidateProfile via LLM."""
        # If it's already a valid JSON Resume, parse directly
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict) and "basics" in data:
                from breadwinner.core.portfolio import JsonResumeAdapter
                adapter = JsonResumeAdapter(data)
                return adapter.load_profile()
        except Exception:
            pass

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
{raw_text[:7000]}

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

        # Build CandidateProfile models
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
    def ingest(
        cls,
        source: str,
        provider: BaseLLMProvider
    ) -> CandidateProfile:
        """Universal entry point: handles URLs, files, and text."""
        source_clean = source.strip()
        if source_clean.startswith("http://") or source_clean.startswith("https://"):
            raw_text = cls.extract_text_from_url(source_clean)
            return cls.parse_text_to_profile(raw_text, provider, source_label=source_clean)

        path = Path(source_clean)
        if path.exists() and path.is_file():
            raw_text = cls.extract_text_from_file(path)
            return cls.parse_text_to_profile(raw_text, provider, source_label=str(path))

        # Raw text / bio paste
        return cls.parse_text_to_profile(source_clean, provider, source_label="Manual Paste")
