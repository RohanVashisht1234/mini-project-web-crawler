"""
crawler/db.py
─────────────
Creates database.sqlite at the project root and provides a connection helper.
The search_engine folder has its own identical copy so both programs are
fully self-contained — they just share the same database.sqlite file.
"""

import os
import sqlite3

# Resolve → .../project/database.sqlite  (one level above crawler/)
DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.sqlite")
)


def get_connection() -> sqlite3.Connection:
    """Open a WAL-mode SQLite connection with row-factory set."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables on first run. Safe to call on every startup."""
    conn = get_connection()
    conn.executescript("""
        -- ── Frontier & politeness ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS frontier (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT    UNIQUE NOT NULL,
            priority    INTEGER DEFAULT 0,
            status      TEXT    DEFAULT 'pending',
            domain      TEXT    NOT NULL DEFAULT '',
            depth       INTEGER DEFAULT 0,
            added_at    REAL    NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS domain_access (
            domain      TEXT PRIMARY KEY,
            last_access REAL NOT NULL DEFAULT 0
        );

        -- ── Deduplication ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS url_seen (
            url_hash     TEXT PRIMARY KEY,
            url          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS content_seen (
            content_hash TEXT PRIMARY KEY
        );

        -- ── Document store ─────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS documents (
            doc_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            url          TEXT UNIQUE NOT NULL,
            title        TEXT DEFAULT '',
            content      TEXT DEFAULT '',
            description  TEXT DEFAULT '',
            word_count   INTEGER DEFAULT 0,
            last_crawled REAL,
            links        TEXT DEFAULT '[]'
        );

        -- ── Inverted index ─────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS inverted_index (
            term      TEXT    NOT NULL,
            doc_id    INTEGER NOT NULL,
            frequency INTEGER NOT NULL DEFAULT 1,
            positions TEXT    DEFAULT '[]',
            PRIMARY KEY (term, doc_id)
        );

        -- ── Indexes for fast lookup ────────────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_ii_term      ON inverted_index (term);
        CREATE INDEX IF NOT EXISTS idx_doc_url      ON documents (url);
        CREATE INDEX IF NOT EXISTS idx_frontier_status ON frontier (status);
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Database ready → {DB_PATH}")
