"""
crawler/indexer.py
──────────────────
Stores a parsed document in the `documents` table and updates the
`inverted_index` table inside database.sqlite.

Both writes happen in a single transaction for consistency.
"""

import json
import time
from collections import defaultdict

from crawler.db import get_connection
from crawler.tokenizer import Tokenizer


class Indexer:

    def __init__(self):
        self._tokenizer = Tokenizer()

    # ── Public ─────────────────────────────────────────────────────────

    def index(self, doc: dict) -> int:
        """
        Persist *doc* and update the inverted index.
        Returns the assigned doc_id.

        *doc* must contain:
            url, title, description, content, links (list of str)
        """
        tokens    = self._tokenizer.tokenize(doc["content"])
        tf, pos   = self._term_stats(tokens)
        word_cnt  = len(tokens)

        conn = get_connection()
        try:
            # ── Upsert document ───────────────────────────────────────
            conn.execute(
                """
                INSERT INTO documents
                    (url, title, description, content, word_count, last_crawled, links)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title        = excluded.title,
                    description  = excluded.description,
                    content      = excluded.content,
                    word_count   = excluded.word_count,
                    last_crawled = excluded.last_crawled,
                    links        = excluded.links
                """,
                (
                    doc["url"],
                    doc.get("title", ""),
                    doc.get("description", ""),
                    doc.get("content", ""),
                    word_cnt,
                    time.time(),
                    json.dumps(doc.get("links", [])),
                ),
            )

            # Retrieve the assigned doc_id (new or existing)
            doc_id = conn.execute(
                "SELECT doc_id FROM documents WHERE url = ?", (doc["url"],)
            ).fetchone()["doc_id"]

            # ── Remove old index entries for this doc ─────────────────
            conn.execute(
                "DELETE FROM inverted_index WHERE doc_id = ?", (doc_id,)
            )

            # ── Insert new index entries ──────────────────────────────
            rows = [
                (term, doc_id, freq, json.dumps(pos[term]))
                for term, freq in tf.items()
            ]
            conn.executemany(
                """
                INSERT INTO inverted_index (term, doc_id, frequency, positions)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(term, doc_id) DO UPDATE SET
                    frequency = excluded.frequency,
                    positions = excluded.positions
                """,
                rows,
            )

            conn.commit()
            return doc_id

        finally:
            conn.close()

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _term_stats(tokens: list[str]):
        tf:  dict[str, int]       = defaultdict(int)
        pos: dict[str, list[int]] = defaultdict(list)
        for i, tok in enumerate(tokens):
            tf[tok]  += 1
            pos[tok].append(i)
        return tf, pos
