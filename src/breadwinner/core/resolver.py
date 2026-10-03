"""Multi-hop URL resolution and tracking link unwrapper.

Resolves aggregators (LinkedIn, Glassdoor, Indeed, Bitly) to their canonical ATS destination.
"""

import urllib.parse
from urllib.parse import urlparse, parse_qs, urlunparse
import requests


class RedirectResolver:
    """Resolves redirect chains and unwraps aggregator tracking URLs."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "trk", "ref", "fbclid", "gclid", "source", "refId", "trackingId", "midToken"
    }

    @classmethod
    def resolve_canonical_url(cls, raw_url: str, timeout: int = 10) -> str:
        """Resolves redirects, unwraps nested target parameters, and strips tracking query tokens."""
        if not raw_url or not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            return raw_url

        url = raw_url.strip()

        # 1. Check for immediate nested URL params (e.g. ?url=https://... or ?dest=...)
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ["url", "dest", "target", "redirectUrl", "redirect"]:
            if key in qs and qs[key]:
                nested = qs[key][0]
                if nested.startswith("http://") or nested.startswith("https://"):
                    url = nested
                    break

        # 2. Perform lightweight HEAD/GET request to trace HTTP redirects
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            # First try HEAD for speed
            resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            final_url = resp.url
        except Exception:
            try:
                # Fallback to streaming GET with small chunk read
                resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
                final_url = resp.url
                resp.close()
            except Exception:
                final_url = url

        # 3. Strip tracking params from final URL
        return cls.strip_tracking_parameters(final_url)

    @classmethod
    def strip_tracking_parameters(cls, url: str) -> str:
        """Removes common marketing and tracking parameters while preserving functional parameters."""
        parsed = urlparse(url)
        if not parsed.query:
            return url

        qs = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in cls.TRACKING_PARAMS}
        new_query = urllib.parse.urlencode(cleaned_qs, doseq=True)

        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
