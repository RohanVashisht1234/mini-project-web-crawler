"""
search_engine/retriever.py
──────────────────────────
Retrieves candidate documents from the inverted index.

Strategy
────────
• AND mode  – all query tokens must appear in the document (strict).
• OR mode   – at least one token must appear (recall-oriented).

We start with AND; if no results, fall back to OR automatically.
"""

from search_engine.db import get_connection


class Retriever:

    def retrieve(self, query_tokens: list[str]) -> dict[int, dict]:
        """
        Return {doc_id: {word_count, freq_sum}} for matching documents.
        Empty dict if nothing matches.
        """
        if not query_tokens:
            return {}

        results = self._and_retrieve(query_tokens)
        if not results:
            results = self._or_retrieve(query_tokens)
        return results

    # ── Retrieval modes ────────────────────────────────────────────────

    def _and_retrieve(self, tokens: list[str]) -> dict[int, dict]:
        """Intersection of posting lists (all tokens must be present)."""
        conn     = get_connection()
        sets     = []
        try:
            for term in tokens:
                rows = conn.execute(
                    "SELECT doc_id, frequency FROM inverted_index WHERE term=?",
                    (term,),
                ).fetchall()
                if not rows:
                    return {}    # Any missing token → no AND results
                sets.append({r["doc_id"]: r["frequency"] for r in rows})
        finally:
            conn.close()

        # Intersect all sets
        common = set(sets[0].keys())
        for s in sets[1:]:
            common &= set(s.keys())
        if not common:
            return {}

        return self._build_result(common, sets, tokens)

    def _or_retrieve(self, tokens: list[str]) -> dict[int, dict]:
        """Union of posting lists (any token match counts)."""
        conn = get_connection()
        try:
            placeholders = ",".join("?" * len(tokens))
            rows = conn.execute(
                f"""
                SELECT ii.doc_id, SUM(ii.frequency) AS freq_sum,
                       d.word_count
                FROM   inverted_index ii
                JOIN   documents d ON d.doc_id = ii.doc_id
                WHERE  ii.term IN ({placeholders})
                GROUP  BY ii.doc_id
                """,
                tokens,
            ).fetchall()
        finally:
            conn.close()

        return {
            r["doc_id"]: {"freq_sum": r["freq_sum"], "word_count": r["word_count"] or 1}
            for r in rows
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_result(
        self,
        doc_ids: set[int],
        freq_sets: list[dict[int, int]],
        tokens: list[str],
    ) -> dict[int, dict]:
        conn = get_connection()
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT doc_id, word_count FROM documents WHERE doc_id IN ({placeholders})",
            list(doc_ids),
        ).fetchall()
        conn.close()

        wc_map = {r["doc_id"]: r["word_count"] or 1 for r in rows}
        result = {}
        for doc_id in doc_ids:
            freq_sum = sum(fs.get(doc_id, 0) for fs in freq_sets)
            result[doc_id] = {
                "freq_sum":   freq_sum,
                "word_count": wc_map.get(doc_id, 1),
            }
        return result
