"""
crawler/crawler.py
──────────────────
Orchestrates the full crawl loop:
  URL Frontier → Robots check → Fetch → Dedup → Parse → Index → Enqueue links
"""

import logging
import time
from urllib.parse import urlparse

from crawler import config
from crawler.db import init_db
from crawler.deduplicator import Deduper
from crawler.fetcher import PageFetcher
from crawler.indexer import Indexer
from crawler.parser import ContentParser
from crawler.robot_parser import RobotParser
from crawler.url_frontier import URLFrontier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crawler")


class Crawler:

    def __init__(self):
        # Bootstrap DB tables on every start (idempotent)
        init_db()

        self.frontier  = URLFrontier()
        self.robots    = RobotParser()
        self.fetcher   = PageFetcher()
        self.parser    = ContentParser()
        self.deduper   = Deduper()
        self.indexer   = Indexer()

        self._crawled  = 0
        self._indexed  = 0
        self._skipped  = 0

    # ── Public entry point ─────────────────────────────────────────────

    def run(self, seed_urls: list[str] | None = None,
            max_pages: int | None = None) -> None:
        """
        Start (or resume) a crawl.

        Parameters
        ──────────
        seed_urls : override the SEED_URLS in config
        max_pages : override MAX_PAGES in config
        """
        seeds     = seed_urls or config.SEED_URLS
        max_pages = max_pages or config.MAX_PAGES

        # Seed the frontier (skipped if URLs were already seen)
        seeded = 0
        for url in seeds:
            if self.frontier.add_url(url, depth=0, priority=0):
                seeded += 1
        log.info(f"Seeded {seeded} new URL(s). Max pages: {max_pages}")

        # ── Main loop ─────────────────────────────────────────────────
        while self._crawled < max_pages:
            job = self.frontier.get_next()
            if job is None:
                log.info("Frontier empty. Crawl complete.")
                break

            url    = job["url"]
            domain = job["domain"]
            depth  = job["depth"]

            try:
                self._process(url, domain, depth)
            except Exception as exc:
                log.warning(f"Unhandled error on {url}: {exc}")
                self.frontier.mark_done(url, status="failed")

        log.info(
            f"\nCrawl finished — crawled: {self._crawled}, "
            f"indexed: {self._indexed}, skipped: {self._skipped}"
        )

    # ── Per-URL processing ─────────────────────────────────────────────

    def _process(self, url: str, domain: str, depth: int) -> None:

        # 1. Robots.txt check
        if not self.robots.can_fetch(url):
            log.debug(f"robots.txt disallow → {url}")
            self.frontier.mark_done(url, "failed")
            self._skipped += 1
            return

        # 2. Rate limiting — wait if we hit this domain too recently
        extra_delay = self.robots.crawl_delay(url)
        min_interval = max(config.RATE_LIMIT_SECONDS, extra_delay)
        waited = 0
        while not self.frontier.can_fetch_domain(domain, min_interval):
            time.sleep(0.25)
            waited += 0.25
            if waited > 30:
                log.debug(f"Rate-limit wait exceeded for {domain}, skipping")
                self.frontier.add_url(url, depth=depth, priority=depth + 2)
                return

        # 3. Fetch
        self.frontier.update_domain_access(domain)
        log.info(f"[{self._crawled+1}/{config.MAX_PAGES}] {url}")
        result = self.fetcher.fetch(url)

        if result is None:
            log.warning(f"  ✗ Fetch failed")
            self.frontier.mark_done(url, "failed")
            self._skipped += 1
            return

        # 4. Content-level deduplication
        if self.deduper.is_duplicate_content(result["content"]):
            log.debug(f"  ✗ Duplicate content")
            self.frontier.mark_done(url, "failed")
            self._skipped += 1
            return

        # 5. Parse HTML
        parsed = self.parser.parse(result["content"], result["url"])

        if len(parsed["content"].split()) < 30:
            log.debug(f"  ✗ Too little text ({len(parsed['content'].split())} words)")
            self.frontier.mark_done(url, "failed")
            self._skipped += 1
            return

        # 6. Index document
        doc_id = self.indexer.index({
            "url":         result["url"],
            "title":       parsed["title"],
            "description": parsed["description"],
            "content":     parsed["content"],
            "links":       parsed["links"],
        })
        self.deduper.add_content(result["content"])
        self.frontier.mark_done(url, "crawled")

        self._crawled += 1
        self._indexed += 1
        log.info(f"  ✓ doc_id={doc_id}  title='{parsed['title'][:60]}'")
        log.info(f"    found {len(parsed['links'])} links")

        # 7. Enqueue discovered links
        if depth < config.MAX_DEPTH:
            enqueued = 0
            for link in parsed["links"]:
                if self.frontier.add_url(link, depth=depth + 1, priority=depth + 1):
                    enqueued += 1
            log.debug(f"    enqueued {enqueued} new links")
