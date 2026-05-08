"""
search_engine/pagerank.py
─────────────────────────
Iterative PageRank computed from the link graph stored in `documents.links`.

The scores are cached in memory — call compute() once before searching.
"""

import json
import math

from search_engine.db import get_connection


class PageRankScorer:

    DAMPING    = 0.85
    ITERATIONS = 20
    EPSILON    = 1e-6

    def __init__(self):
        self._scores: dict[int, float] = {}
        self._computed = False

    # ── Public ─────────────────────────────────────────────────────────

    def ensure_computed(self) -> None:
        """Compute PageRank the first time; subsequent calls are no-ops."""
        if not self._computed:
            self.compute()
            self._computed = True

    def get_score(self, doc_id: int) -> float:
        return self._scores.get(doc_id, 0.0)

    def compute(self) -> None:
        conn = get_connection()
        rows = conn.execute("SELECT doc_id, url, links FROM documents").fetchall()
        conn.close()

        if not rows:
            return

        N           = len(rows)
        url_to_id   = {r["url"]: r["doc_id"] for r in rows}
        outlinks: dict[int, list[int]] = {}

        for r in rows:
            doc_id = r["doc_id"]
            try:
                links = json.loads(r["links"] or "[]")
            except (json.JSONDecodeError, TypeError):
                links = []
            outlinks[doc_id] = [url_to_id[l] for l in links if l in url_to_id]

        # Inlink index for O(1) lookup per node
        inlinks: dict[int, list[int]] = {r["doc_id"]: [] for r in rows}
        for src, targets in outlinks.items():
            for tgt in targets:
                inlinks.setdefault(tgt, []).append(src)

        # Initialise
        scores = {r["doc_id"]: 1.0 / N for r in rows}

        for _ in range(self.ITERATIONS):
            new_scores: dict[int, float] = {}
            dangling_mass = sum(
                scores[d] for d in scores if not outlinks.get(d)
            )
            for doc_id in scores:
                rank_sum = sum(
                    scores[src] / len(outlinks[src])
                    for src in inlinks.get(doc_id, [])
                    if outlinks.get(src)
                )
                new_scores[doc_id] = (
                    (1 - self.DAMPING) / N
                    + self.DAMPING * (rank_sum + dangling_mass / N)
                )

            # Check convergence
            delta = sum(abs(new_scores[d] - scores[d]) for d in scores)
            scores = new_scores
            if delta < self.EPSILON:
                break

        # Normalise to [0, 1]
        max_pr = max(scores.values()) or 1.0
        self._scores = {d: s / max_pr for d, s in scores.items()}
