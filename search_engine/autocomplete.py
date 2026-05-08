"""
search_engine/autocomplete.py
──────────────────────────────
Prefix-based autocomplete using a sorted in-memory list of all indexed terms.
Binary search gives O(log N) prefix lookup.
"""

import bisect

from search_engine.db import get_connection


class Autocomplete:

    def __init__(self):
        self._terms: list[str] | None = None

    def suggest(self, prefix: str, limit: int = 5) -> list[str]:
        prefix = prefix.lower().strip()
        if not prefix:
            return []

        terms = self._load_terms()
        idx   = bisect.bisect_left(terms, prefix)

        suggestions = []
        for i in range(idx, len(terms)):
            if terms[i].startswith(prefix):
                suggestions.append(terms[i])
                if len(suggestions) >= limit:
                    break
            else:
                break   # Sorted list — no point continuing

        return suggestions

    # ── Helpers ────────────────────────────────────────────────────────

    def _load_terms(self) -> list[str]:
        if self._terms is None:
            conn = get_connection()
            rows = conn.execute(
                "SELECT DISTINCT term FROM inverted_index ORDER BY term"
            ).fetchall()
            conn.close()
            self._terms = [r["term"] for r in rows]
        return self._terms

    def reload(self) -> None:
        """Force a reload on next call (e.g. after new documents are indexed)."""
        self._terms = None
