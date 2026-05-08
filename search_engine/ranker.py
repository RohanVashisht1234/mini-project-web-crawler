"""
search_engine/ranker.py
───────────────────────
Combines three signals into a final score:

  final = w_tfidf   × TF-IDF score
        + w_pagerank × PageRank score  (normalised 0-1)
        + w_fresh    × Freshness score (normalised 0-1)

Default weights follow the source project: 0.5 / 0.35 / 0.15.
"""

import math
import time

from search_engine.db import get_connection
from search_engine.tfidf import TFIDFScorer
from search_engine.pagerank import PageRankScorer

# ── Weights ────────────────────────────────────────────────────────────────
W_TFIDF    = 0.50
W_PAGERANK = 0.35
W_FRESH    = 0.15

# Freshness decay half-life (7 days)
_HALF_LIFE_SECONDS = 7 * 86400


class Ranker:

    def __init__(self):
        self._tfidf    = TFIDFScorer()
        self._pagerank = PageRankScorer()
        self._pagerank.ensure_computed()

    # ── Public ─────────────────────────────────────────────────────────

    def rank(
        self,
        candidates: dict[int, dict],   # {doc_id: {word_count, freq_sum}}
        query_tokens: list[str],
    ) -> list[tuple[int, float]]:
        """
        Score and sort candidates.
        Returns [(doc_id, score), ...] sorted descending.
        """
        now    = time.time()
        scored = []

        # Batch-fetch last_crawled for all candidates
        conn   = get_connection()
        ids    = list(candidates.keys())
        ph     = ",".join("?" * len(ids))
        rows   = conn.execute(
            f"SELECT doc_id, last_crawled FROM documents WHERE doc_id IN ({ph})",
            ids,
        ).fetchall()
        conn.close()
        last_crawled = {r["doc_id"]: r["last_crawled"] or 0 for r in rows}

        for doc_id, meta in candidates.items():
            wc     = meta.get("word_count", 1) or 1
            tfidf  = self._tfidf.score(doc_id, query_tokens, wc)
            pr     = self._pagerank.get_score(doc_id)
            fresh  = self._freshness(last_crawled.get(doc_id, 0), now)

            final  = W_TFIDF * tfidf + W_PAGERANK * pr + W_FRESH * fresh
            scored.append((doc_id, final))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _freshness(last_crawled: float, now: float) -> float:
        """Exponential decay: 1.0 if just crawled, ~0.5 after 7 days."""
        age = now - last_crawled
        return math.exp(-age / _HALF_LIFE_SECONDS)
