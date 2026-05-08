"""
search_engine/tfidf.py
──────────────────────
BM25-style TF-IDF scorer.

score(doc, query) = Σ_{term} TF(term,doc) × IDF(term)

  TF  = frequency_in_doc / doc_word_count
  IDF = log( (N+1) / (df+1) ) + 1        (add-one smoothed)
"""

import math

from search_engine.db import get_connection


class TFIDFScorer:

    def __init__(self):
        self._total_docs: int | None = None

    # ── Public ─────────────────────────────────────────────────────────

    def score(self, doc_id: int, query_tokens: list[str],
              doc_word_count: int) -> float:
        N = self._get_total_docs()
        if N == 0 or doc_word_count == 0:
            return 0.0

        conn = get_connection()
        total = 0.0
        try:
            for term in query_tokens:
                # TF for this term in this document
                row = conn.execute(
                    "SELECT frequency FROM inverted_index WHERE term=? AND doc_id=?",
                    (term, doc_id),
                ).fetchone()
                if row is None:
                    continue
                tf = row["frequency"] / doc_word_count

                # Document frequency
                df_row = conn.execute(
                    "SELECT COUNT(*) AS df FROM inverted_index WHERE term=?",
                    (term,),
                ).fetchone()
                df = df_row["df"] if df_row else 0

                idf   = math.log((N + 1) / (df + 1)) + 1
                total += tf * idf
        finally:
            conn.close()

        return total

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_total_docs(self) -> int:
        if self._total_docs is None:
            conn = get_connection()
            self._total_docs = conn.execute(
                "SELECT COUNT(*) FROM documents"
            ).fetchone()[0]
            conn.close()
        return self._total_docs
