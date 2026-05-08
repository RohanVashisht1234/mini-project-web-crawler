"""
crawler/parser.py
─────────────────
Parses raw HTML into a clean dict of:
  title       – page title (or first H1)
  description – meta description
  content     – clean visible body text (noise tags stripped)
  links       – list of normalised absolute URLs found on the page
"""

import re
from typing import Dict, List
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# Tags whose text is noise — remove before extracting body text
_NOISE_TAGS = {"script", "style", "noscript", "header", "footer",
               "nav", "aside", "form", "button", "iframe", "svg"}

_VALID_SCHEMES = {"http", "https"}


class ContentParser:

    def parse(self, html: str, base_url: str) -> Dict:
        soup = BeautifulSoup(html, "lxml")

        # Strip noise first so it doesn't pollute get_text()
        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        return {
            "title":       self._title(soup),
            "description": self._description(soup),
            "content":     self._body_text(soup),
            "links":       self._links(soup, base_url),
        }

    # ── Field extractors ───────────────────────────────────────────────

    def _title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()[:512]
        h1 = soup.find("h1")
        return h1.get_text(strip=True)[:512] if h1 else "Untitled"

    def _description(self, soup: BeautifulSoup) -> str:
        tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if tag:
            return tag.get("content", "")[:1024]
        return ""

    def _body_text(self, soup: BeautifulSoup) -> str:
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()

    def _links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        seen, links = set(), []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            absolute = urljoin(base_url, href)
            normalised = self._normalise(absolute)
            if normalised and normalised not in seen:
                seen.add(normalised)
                links.append(normalised)
        return links

    @staticmethod
    def _normalise(url: str):
        try:
            p = urlparse(url)
        except Exception:
            return None
        if p.scheme not in _VALID_SCHEMES:
            return None
        # Strip fragment; lowercase scheme + host
        p = p._replace(scheme=p.scheme.lower(),
                        netloc=p.netloc.lower(),
                        fragment="")
        return urlunparse(p)
