"""
search_engine/searcher.py
─────────────────────────
Orchestrates: query parsing → retrieval → ranking → snippet generation → pagination.
"""

import re
import textwrap

from search_engine.db import get_connection
from search_engine.query_processor import QueryProcessor, ParsedQuery
from search_engine.retriever import Retriever
from search_engine.ranker import Ranker


class Searcher:

    def __init__(self):
        self._qproc    = QueryProcessor()
        self._retriever = Retriever()
        self._ranker   = Ranker()

    # ── Public ─────────────────────────────────────────────────────────

    def search(
        self,
        raw_query: str,
        page: int = 0,
        page_size: int = 10,
    ) -> dict:
        """
        Full search pipeline.

        Returns
        ───────
        {
          query:         str,
          total_results: int,
          page:          int,
          page_size:     int,
          results:       [ {doc_id, url, title, snippet, score}, ... ]
        }
        """
        pq = self._qproc.process(raw_query)

        if not pq.tokens:
            return self._empty(raw_query, page, page_size)

        # 1. Retrieve candidates
        candidates = self._retriever.retrieve(pq.tokens)

        # 2. Apply site: filter
        if pq.site_filter:
            candidates = self._filter_site(candidates, pq.site_filter)

        # 3. Apply must_not filter
        if pq.must_not:
            candidates = self._filter_must_not(candidates, pq.must_not)

        if not candidates:
            return self._empty(raw_query, page, page_size)

        # 4. Rank
        ranked = self._ranker.rank(candidates, pq.tokens)

        # 5. Paginate
        start     = page * page_size
        paginated = ranked[start : start + page_size]

        # 6. Format
        results = [
            self._format(doc_id, score, pq)
            for doc_id, score in paginated
        ]

        return {
            "query":         raw_query,
            "total_results": len(ranked),
            "page":          page,
            "page_size":     page_size,
            "results":       results,
        }

    # ── Formatting ─────────────────────────────────────────────────────

    def _format(self, doc_id: int, score: float, pq: ParsedQuery) -> dict:
        conn = get_connection()
        row  = conn.execute(
            "SELECT url, title, content, description FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        conn.close()

        if not row:
            return {}

        snippet = self._snippet(
            row["description"] or row["content"],
            pq.tokens,
        )
        return {
            "doc_id":  doc_id,
            "url":     row["url"],
            "title":   row["title"] or row["url"],
            "snippet": snippet,
            "score":   round(score, 6),
        }

    @staticmethod
    def _snippet(text: str, tokens: list[str], length: int = 220) -> str:
        """Find the sentence/region richest in query tokens and return it."""
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        token_set = set(tokens)

        best_score, best_text = -1, text[:length]
        for i, sent in enumerate(sentences):
            words = set(re.findall(r"\b[a-z]+\b", sent.lower()))
            score = len(words & token_set)
            if score > best_score:
                best_score = score
                window = " ".join(sentences[max(0, i-1) : i+2])
                best_text = window

        snip = best_text.strip()
        if len(snip) > length:
            snip = snip[:length].rsplit(" ", 1)[0] + " …"
        return snip

    # ── Filters ────────────────────────────────────────────────────────

    def _filter_site(self, candidates: dict, domain: str) -> dict:
        conn = get_connection()
        ids  = list(candidates.keys())
        ph   = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT doc_id, url FROM documents WHERE doc_id IN ({ph})", ids
        ).fetchall()
        conn.close()
        keep = {r["doc_id"] for r in rows if domain in r["url"]}
        return {k: v for k, v in candidates.items() if k in keep}

    def _filter_must_not(self, candidates: dict, must_not: list[str]) -> dict:
        """Remove docs that contain any of the must_not tokens."""
        conn  = get_connection()
        ids   = list(candidates.keys())
        ph    = ",".join("?" * len(ids))
        ph2   = ",".join("?" * len(must_not))
        rows  = conn.execute(
            f"""
            SELECT DISTINCT doc_id FROM inverted_index
            WHERE  doc_id IN ({ph}) AND term IN ({ph2})
            """,
            ids + must_not,
        ).fetchall()
        conn.close()
        excluded = {r["doc_id"] for r in rows}
        return {k: v for k, v in candidates.items() if k not in excluded}

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _empty(query: str, page: int, page_size: int) -> dict:
        return {
            "query":         query,
            "total_results": 0,
            "page":          page,
            "page_size":     page_size,
            "results":       [],
        }
