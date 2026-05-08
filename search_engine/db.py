"""
search_engine/db.py
───────────────────
Read-only database access for the search engine.
Points to the same database.sqlite created by the crawler.
"""

import os
import sqlite3

# One level up from search_engine/ → project root
DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.sqlite")
)


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"database.sqlite not found at {DB_PATH}\n"
            "Run the crawler first:  python crawler/run.py"
        )
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
