"""
crawler/url_frontier.py
───────────────────────
SQLite-backed URL Frontier with per-domain politeness enforcement.

Design
──────
• Every URL is stored in the `frontier` table (status: pending → crawled/failed).
• Domain access timestamps live in `domain_access` so rate-limiting survives
  restarts and works across multiple workers.
• Priority: lower integer = higher priority (min-heap semantics).
  Seeds get priority 0; discovered links get 1+depth.
"""

import hashlib
import time
from urllib.parse import urlparse

from crawler.db import get_connection


class URLFrontier:

    # ── Public API ─────────────────────────────────────────────────────

    def add_url(self, url: str, depth: int = 0, priority: int = 1) -> bool:
        """
        Add *url* to the frontier.
        Returns True if the URL was new, False if already seen.
        """
        url_hash = self._hash(url)
        domain   = urlparse(url).netloc

        conn = get_connection()
        try:
            # Dedup check — one round-trip
            row = conn.execute(
                "SELECT 1 FROM url_seen WHERE url_hash = ?", (url_hash,)
            ).fetchone()
            if row:
                return False

            conn.execute(
                "INSERT OR IGNORE INTO url_seen (url_hash, url) VALUES (?, ?)",
                (url_hash, url),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO frontier
                    (url, priority, status, domain, depth, added_at)
                VALUES (?, ?, 'pending', ?, ?, ?)
                """,
                (url, priority, domain, depth, time.time()),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_next(self) -> dict | None:
        """
        Pop the highest-priority pending URL.
        Returns a row dict {id, url, domain, depth} or None if queue is empty.
        """
        conn = get_connection()
        try:
            row = conn.execute(
                """
                SELECT id, url, domain, depth
                FROM   frontier
                WHERE  status = 'pending'
                ORDER  BY priority ASC, id ASC
                LIMIT  1
                """
            ).fetchone()
            if row is None:
                return None
            # Reserve it immediately so another worker won't grab it
            conn.execute(
                "UPDATE frontier SET status = 'processing' WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            return dict(row)
        finally:
            conn.close()

    def mark_done(self, url: str, status: str = "crawled") -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE frontier SET status = ? WHERE url = ?", (status, url)
        )
        conn.commit()
        conn.close()

    def can_fetch_domain(self, domain: str, min_interval: float) -> bool:
        """True if enough time has passed since we last hit *domain*."""
        conn = get_connection()
        row = conn.execute(
            "SELECT last_access FROM domain_access WHERE domain = ?", (domain,)
        ).fetchone()
        conn.close()
        if row is None:
            return True
        return (time.time() - row["last_access"]) >= min_interval

    def update_domain_access(self, domain: str) -> None:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO domain_access (domain, last_access) VALUES (?, ?)
            ON CONFLICT(domain) DO UPDATE SET last_access = excluded.last_access
            """,
            (domain, time.time()),
        )
        conn.commit()
        conn.close()

    def pending_count(self) -> int:
        conn = get_connection()
        n = conn.execute(
            "SELECT COUNT(*) FROM frontier WHERE status = 'pending'"
        ).fetchone()[0]
        conn.close()
        return n

    def is_empty(self) -> bool:
        return self.pending_count() == 0

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()
