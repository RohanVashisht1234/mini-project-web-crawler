"""
search_engine/query_processor.py
─────────────────────────────────
Parses a raw query string into structured components.

Supported syntax:
  python web framework            → simple keywords
  "machine learning"              → phrase (treated as must-contain)
  python -django                  → exclude 'django'
  site:docs.python.org asyncio    → restrict to domain
"""

import re
from dataclasses import dataclass, field

from search_engine.tokenizer import Tokenizer


@dataclass
class ParsedQuery:
    raw:          str
    tokens:       list[str]        # All positive tokens (for retrieval)
    must_not:     list[str]        # Negative tokens (to exclude)
    site_filter:  str | None       # e.g. "docs.python.org"
    phrases:      list[str]        # Raw phrase strings (for snippet highlighting)


class QueryProcessor:

    def __init__(self):
        self._tok = Tokenizer()

    def process(self, raw: str) -> ParsedQuery:
        text       = raw.strip()
        site_filter = None
        phrases     = []
        must_not    = []
        remaining   = text

        # ── site: operator ─────────────────────────────────────────────
        m = re.search(r"site:(\S+)", remaining)
        if m:
            site_filter = m.group(1).lower()
            remaining   = remaining.replace(m.group(0), "").strip()

        # ── Quoted phrases ─────────────────────────────────────────────
        for phrase in re.findall(r'"([^"]+)"', remaining):
            phrases.append(phrase)
            remaining = remaining.replace(f'"{phrase}"', " ").strip()

        # ── Negative terms ─────────────────────────────────────────────
        for neg in re.findall(r"-(\w+)", remaining):
            must_not.extend(self._tok.tokenize(neg))
            remaining = re.sub(rf"-{neg}\b", "", remaining).strip()

        # ── Positive tokens ────────────────────────────────────────────
        pos_tokens = self._tok.tokenize(remaining)
        for phrase in phrases:
            pos_tokens.extend(self._tok.tokenize(phrase))

        # Deduplicate while preserving order
        seen, unique = set(), []
        for t in pos_tokens:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return ParsedQuery(
            raw=raw,
            tokens=unique,
            must_not=must_not,
            site_filter=site_filter,
            phrases=phrases,
        )
