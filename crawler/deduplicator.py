"""
crawler/deduplicator.py
───────────────────────
Two-level deduplication backed by SQLite:
  1. URL-level  — SHA-256 of the normalised URL
  2. Content-level — SHA-256 of the raw HTML body

The frontier's url_seen table is the authoritative URL dedup store
(populated by URLFrontier.add_url). This class provides the content-level
check plus a lightweight in-memory URL cache.
"""

import hashlib
from crawler.db import get_connection


class Deduper:

    def __init__(self):
        # In-memory cache to avoid hitting SQLite on every URL check
        self._url_cache: set[str] = self._load_url_hashes()

    # ── URL dedup ──────────────────────────────────────────────────────

    def is_duplicate_url(self, url: str) -> bool:
        h = self._hash(url)
        return h in self._url_cache

    def add_url(self, url: str) -> None:
        h = self._hash(url)
        self._url_cache.add(h)
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO url_seen (url_hash, url) VALUES (?, ?)",
            (h, url),
        )
        conn.commit()
        conn.close()

    # ── Content dedup ──────────────────────────────────────────────────

    def is_duplicate_content(self, content: str) -> bool:
        h = self._hash(content)
        conn = get_connection()
        row = conn.execute(
            "SELECT 1 FROM content_seen WHERE content_hash = ?", (h,)
        ).fetchone()
        conn.close()
        return row is not None

    def add_content(self, content: str) -> None:
        h = self._hash(content)
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO content_seen (content_hash) VALUES (?)", (h,)
        )
        conn.commit()
        conn.close()

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def _load_url_hashes() -> set[str]:
        conn = get_connection()
        rows = conn.execute("SELECT url_hash FROM url_seen").fetchall()
        conn.close()
        return {r[0] for r in rows}
