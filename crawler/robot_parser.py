"""
crawler/robot_parser.py
───────────────────────
Caches parsed robots.txt entries per domain (TTL = 1 hour).
"""

import time
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from crawler import config


class RobotParser:

    _CACHE_TTL = 3600   # seconds

    def __init__(self):
        self._parsers: dict[str, RobotFileParser] = {}
        self._fetched_at: dict[str, float] = {}

    # ── Public ─────────────────────────────────────────────────────────

    def can_fetch(self, url: str) -> bool:
        """Return True if our crawler is allowed to fetch *url*."""
        if not config.RESPECT_ROBOTS_TXT:
            return True
        parser = self._get_parser(url)
        return parser.can_fetch(config.USER_AGENT, url) if parser else True

    def crawl_delay(self, url: str) -> float:
        """Return the Crawl-Delay directive for *url*'s domain, or 0."""
        parser = self._get_parser(url)
        if parser:
            delay = parser.crawl_delay(config.USER_AGENT)
            if delay is not None:
                return float(delay)
        return 0.0

    # ── Internal ───────────────────────────────────────────────────────

    def _get_parser(self, url: str) -> Optional[RobotFileParser]:
        domain = urlparse(url).netloc
        now    = time.time()

        # Return cached parser if still fresh
        if domain in self._parsers:
            if now - self._fetched_at.get(domain, 0) < self._CACHE_TTL:
                return self._parsers[domain]

        # Fetch and parse robots.txt
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            rp = None   # Can't reach robots.txt → allow everything

        self._parsers[domain]    = rp
        self._fetched_at[domain] = now
        return rp
