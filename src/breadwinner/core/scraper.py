"""Job ingestion and scraping engine supporting URLs, files, and pasted text."""

import re
import requests
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, Tuple
from bs4 import BeautifulSoup

from breadwinner.core.models import JobPosting


class JobScraper:
    """Scrapes and normalizes job descriptions from URLs or local text files."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    @classmethod
    def ingest_from_url(cls, url: str) -> JobPosting:
        """Fetch and extract job posting details from a web URL."""
        headers = {"User-Agent": cls.USER_AGENT}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html = response.text
        portal_type = cls.detect_portal_type(url, html)
        company, title, location, clean_text = cls.parse_html_job(url, html, portal_type)

        # Generate a slug id: company-role
        safe_company = re.sub(r'[^a-zA-Z0-9]+', '-', company.lower()).strip('-') or "unknown-company"
        safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-') or "role"
        job_id = f"{safe_company}-{safe_title}"

        return JobPosting(
            id=job_id,
            company=company,
            title=title,
            url=url,
            location=location,
            portal_type=portal_type,
            raw_text=clean_text
        )

    @classmethod
    def ingest_from_text(cls, text: str, company: str = "Target Company", title: str = "Target Role") -> JobPosting:
        """Ingest job posting from raw text or markdown."""
        safe_company = re.sub(r'[^a-zA-Z0-9]+', '-', company.lower()).strip('-') or "unknown-company"
        safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-') or "role"
        job_id = f"{safe_company}-{safe_title}"

        return JobPosting(
            id=job_id,
            company=company,
            title=title,
            portal_type="text",
            raw_text=text.strip()
        )

    @classmethod
    def detect_portal_type(cls, url: str, html: str) -> str:
        """Detect portal provider (Greenhouse, Lever, Ashby, Workday)."""
        domain = urlparse(url).netloc.lower()
        if "greenhouse.io" in domain or "gh_jid" in url:
            return "greenhouse"
        elif "lever.co" in domain:
            return "lever"
        elif "ashbyhq.com" in domain:
            return "ashby"
        elif "myworkdayjobs.com" in domain or "workday" in domain:
            return "workday"
        return "general"

    @classmethod
    def parse_html_job(cls, url: str, html: str, portal_type: str) -> Tuple[str, str, Optional[str], str]:
        """Extract company, title, location, and cleaned text from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Strip scripts, styles, nav, footer, headers
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()

        company = "Company"
        title = "Role"
        location = None

        domain = urlparse(url).netloc.lower()
        # Fallback company from domain: e.g. boards.greenhouse.io/monzo -> monzo
        path_parts = [p for p in urlparse(url).path.split("/") if p]

        if portal_type == "greenhouse":
            if path_parts:
                company = path_parts[0].capitalize()
            # Title is usually h1
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text().strip()
            loc_div = soup.find("div", class_=lambda c: c and "location" in c.lower())
            if loc_div:
                location = loc_div.get_text().strip()

        elif portal_type == "lever":
            # Lever has posting-headline
            headline = soup.find("div", class_="posting-headline")
            if headline:
                h2 = headline.find("h2")
                if h2:
                    title = h2.get_text().strip()
            if path_parts:
                company = path_parts[0].capitalize()
            categories = soup.find("div", class_="posting-categories")
            if categories:
                location = categories.get_text().strip()

        elif portal_type == "ashby":
            if path_parts:
                company = path_parts[0].capitalize()
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text().strip()

        else:
            # General fallback
            # Extract meta tags first
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title_content = og_title["content"]
                if " at " in title_content:
                    t, c = title_content.split(" at ", 1)
                    title, company = t.strip(), c.strip()
                elif " - " in title_content:
                    t, c = title_content.split(" - ", 1)
                    title, company = t.strip(), c.strip()
                else:
                    title = title_content.strip()
            elif soup.title:
                t_text = soup.title.get_text().strip()
                title = t_text

            if company == "Company" and domain:
                parts = domain.split(".")
                company = parts[-2].capitalize() if len(parts) >= 2 else domain

        # Clean text
        text_lines = []
        for p in soup.find_all(["p", "li", "h1", "h2", "h3", "h4"]):
            t = p.get_text().strip()
            if len(t) > 20 and not any(skip in t.lower() for skip in ["cookie", "privacy policy", "all rights reserved"]):
                text_lines.append(t)

        clean_text = "\n\n".join(text_lines)
        return company, title, location, clean_text
