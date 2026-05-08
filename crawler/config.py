"""
crawler/config.py
─────────────────
Edit these values before running the crawler.
"""

# ── Seeds ──────────────────────────────────────────────────────────────────
SEED_URLS = [
    "https://example.com",
    "https://en.wikipedia.org/wiki/Web_crawler",
]

# ── Crawl limits ───────────────────────────────────────────────────────────
MAX_PAGES  = 100   # Hard cap on pages crawled per run
MAX_DEPTH  = 3     # Max hop depth from a seed URL

# ── Politeness ─────────────────────────────────────────────────────────────
RATE_LIMIT_SECONDS = 1.5   # Min seconds between requests to the SAME domain
RESPECT_ROBOTS_TXT = True  # Honour robots.txt Disallow rules
REQUEST_TIMEOUT    = 15    # Per-request timeout in seconds

# ── Identity ───────────────────────────────────────────────────────────────
USER_AGENT = "PythonSearchBot/1.0 (+https://example.com/bot)"

# ── Content ────────────────────────────────────────────────────────────────
MAX_CONTENT_BYTES = 2 * 1024 * 1024  # Skip pages larger than 2 MB

# ── Text processing ────────────────────────────────────────────────────────
USE_STEMMING = True   # Apply Porter stemmer when building the index
