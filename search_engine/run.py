#!/usr/bin/env python3
"""
search_engine/run.py
────────────────────
Interactive command-line search REPL.

Usage
─────
  python search_engine/run.py

Commands inside the REPL
─────────────────────────
  <query>             → search
  <query> --page N    → show page N of results (0-indexed)
  :suggest <prefix>   → autocomplete suggestions
  :stats              → database statistics
  :help               → show syntax help
  :quit  /  Ctrl-C    → exit
"""

import os
import sys
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.searcher import Searcher
from search_engine.autocomplete import Autocomplete
from search_engine.db import get_connection, DB_PATH

# ── ANSI colours (disabled on Windows without ANSI support) ───────────────
_USE_COLOUR = sys.stdout.isatty() and os.name != "nt"

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

BOLD  = lambda t: _c(t, "1")
DIM   = lambda t: _c(t, "2")
GREEN = lambda t: _c(t, "32")
CYAN  = lambda t: _c(t, "36")
YELLOW= lambda t: _c(t, "33")
RED   = lambda t: _c(t, "31")

# ── Width ─────────────────────────────────────────────────────────────────
_W = min(os.get_terminal_size().columns if _USE_COLOUR else 100, 100)


def print_header() -> None:
    bar = "─" * _W
    print(GREEN(bar))
    print(GREEN("  🔍  PythonSearchEngine"))
    print(GREEN(f"  Database: {DB_PATH}"))
    print(GREEN(bar))
    print(DIM("  Type a query to search. Type :help for commands.\n"))


def print_help() -> None:
    print(CYAN(textwrap.dedent("""
    ┌─────────────────────────────────────────────────────────────┐
    │  Query syntax                                               │
    │  ─────────────────────────────────────────────────────────  │
    │  python web framework        → keyword search              │
    │  "machine learning"          → phrase search               │
    │  python -snake               → exclude 'snake'             │
    │  site:docs.python.org async  → restrict to domain          │
    │                                                             │
    │  Commands                                                   │
    │  ─────────────────────────────────────────────────────────  │
    │  :suggest <prefix>           → autocomplete                │
    │  :stats                      → database stats              │
    │  :help                       → this message                │
    │  :quit                       → exit                        │
    └─────────────────────────────────────────────────────────────┘
    """)))


def print_stats() -> None:
    try:
        conn = get_connection()
        doc_count  = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        term_count = conn.execute(
            "SELECT COUNT(DISTINCT term) FROM inverted_index"
        ).fetchone()[0]
        pending    = conn.execute(
            "SELECT COUNT(*) FROM frontier WHERE status='pending'"
        ).fetchone()[0]
        crawled    = conn.execute(
            "SELECT COUNT(*) FROM frontier WHERE status='crawled'"
        ).fetchone()[0]
        conn.close()

        print(CYAN(f"\n  Documents indexed : {doc_count:,}"))
        print(CYAN(f"  Unique terms      : {term_count:,}"))
        print(CYAN(f"  Frontier pending  : {pending:,}"))
        print(CYAN(f"  Pages crawled     : {crawled:,}\n"))
    except FileNotFoundError as e:
        print(RED(f"  {e}"))


def display_results(response: dict, page: int) -> None:
    total = response["total_results"]
    query = response["query"]
    items = response["results"]

    if total == 0:
        print(YELLOW(f'\n  No results for "{query}"\n'))
        return

    ps   = response["page_size"]
    pmax = (total - 1) // ps
    print(f"\n  {BOLD(str(total))} result(s) for {BOLD(repr(query))}"
          f"  [page {page+1}/{pmax+1}]\n")

    for i, r in enumerate(items, start=page * ps + 1):
        print(f"  {BOLD(str(i))}. {GREEN(r['title'])}")
        print(f"     {CYAN(r['url'])}")
        if r.get("snippet"):
            wrapped = textwrap.fill(r["snippet"], width=_W - 6,
                                    subsequent_indent="     ")
            print(f"     {DIM(wrapped)}")
        print(f"     {DIM(f'score={r["score"]:.4f}')}")
        print()

    # Pagination hint
    if pmax > 0:
        hint_parts = []
        if page > 0:
            hint_parts.append(f"  --page {page-1}  ← prev")
        if page < pmax:
            hint_parts.append(f"  --page {page+1}  → next")
        if hint_parts:
            print(DIM("  " + "    ".join(hint_parts)) + "\n")


def run_repl() -> None:
    print_header()

    try:
        from search_engine.db import get_connection as _gc
        _gc().close()   # Verify DB is accessible
    except FileNotFoundError as e:
        print(RED(f"\n  ERROR: {e}\n"))
        sys.exit(1)

    searcher     = Searcher()
    autocomplete = Autocomplete()
    page_size    = 10

    while True:
        try:
            raw = input(BOLD("  Search> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Goodbye!\n")
            break

        if not raw:
            continue

        # ── Commands ───────────────────────────────────────────────────
        if raw.lower() in (":quit", ":q", "exit", "quit"):
            print("\n  Goodbye!\n")
            break

        if raw.lower() == ":help":
            print_help()
            continue

        if raw.lower() == ":stats":
            print_stats()
            continue

        if raw.lower().startswith(":suggest "):
            prefix = raw[9:].strip()
            suggestions = autocomplete.suggest(prefix, limit=8)
            if suggestions:
                print(CYAN("  Suggestions: " + ", ".join(suggestions) + "\n"))
            else:
                print(DIM("  No suggestions found.\n"))
            continue

        # ── Parse --page N ─────────────────────────────────────────────
        page = 0
        query = raw
        if "--page" in raw:
            parts = raw.split("--page")
            query = parts[0].strip()
            try:
                page = int(parts[1].strip().split()[0])
            except (IndexError, ValueError):
                page = 0

        # ── Search ─────────────────────────────────────────────────────
        t0       = time.perf_counter()
        response = searcher.search(query, page=page, page_size=page_size)
        elapsed  = time.perf_counter() - t0

        display_results(response, page)
        print(DIM(f"  Query time: {elapsed*1000:.1f} ms"))
        print()


if __name__ == "__main__":
    run_repl()
