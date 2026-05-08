"""
crawler/fetcher.py
──────────────────
Synchronous HTTP fetcher with retry / exponential back-off.
Only fetches text/html content; skips images, PDFs, etc.
"""

import time
from typing import Optional

import requests
from requests.exceptions import RequestException

from crawler import config

# Content-type prefixes we are willing to index
_ACCEPTED = {"text/html", "application/xhtml+xml"}


class PageFetcher:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

    def fetch(self, url: str, max_retries: int = 3) -> Optional[dict]:
        """
        Download *url* and return a result dict, or None on failure.

        Result dict keys:
            url          – final URL (after redirects)
            status_code  – HTTP status
            content      – decoded response body (str)
            content_type – content-type header value
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    timeout=config.REQUEST_TIMEOUT,
                    allow_redirects=True,
                    stream=True,          # stream so we can cap size
                )
                response.raise_for_status()

                # ── Content-type gate ──────────────────────────────────
                ctype = response.headers.get("Content-Type", "").split(";")[0].strip()
                if not any(ctype.startswith(a) for a in _ACCEPTED):
                    return None            # silently skip non-HTML

                # ── Size cap ──────────────────────────────────────────
                chunks, total = [], 0
                for chunk in response.iter_content(chunk_size=8192):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > config.MAX_CONTENT_BYTES:
                        break

                encoding = response.encoding or "utf-8"
                html = b"".join(chunks).decode(encoding, errors="replace")

                return {
                    "url":          str(response.url),
                    "status_code":  response.status_code,
                    "content":      html,
                    "content_type": ctype,
                }

            except RequestException:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)   # back-off: 1s, 2s, 4s
                continue

        return None
