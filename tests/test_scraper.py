"""Unit tests for job scraper and portal detection."""

from breadwinner.core.scraper import JobScraper


def test_portal_detection():
    assert JobScraper.detect_portal_type("https://boards.greenhouse.io/monzo/jobs/123", "") == "greenhouse"
    assert JobScraper.detect_portal_type("https://jobs.lever.co/anthropic/456", "") == "lever"
    assert JobScraper.detect_portal_type("https://jobs.ashbyhq.com/synthesia/789", "") == "ashby"
    assert JobScraper.detect_portal_type("https://company.myworkdayjobs.com/careers/job/101", "") == "workday"
    assert JobScraper.detect_portal_type("https://example.com/careers", "") == "general"


def test_html_parsing_greenhouse():
    html = """
    <html>
      <head><title>Senior MLE at Monzo</title></head>
      <body>
        <div id="content">
          <h1>Senior Machine Learning Engineer</h1>
          <div class="location">London, UK (Hybrid)</div>
          <p>We are seeking a senior engineer to design and scale fraud detection models.</p>
          <p>Requirements include Python, distributed systems, and cloud experience.</p>
        </div>
      </body>
    </html>
    """
    company, title, location, text = JobScraper.parse_html_job(
        "https://boards.greenhouse.io/monzo/jobs/123",
        html,
        "greenhouse"
    )
    assert company == "Monzo"
    assert title == "Senior Machine Learning Engineer"
    assert "London" in location
    assert "fraud detection" in text
