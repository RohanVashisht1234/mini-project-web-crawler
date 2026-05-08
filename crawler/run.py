#!/usr/bin/env python3
"""
crawler/run.py
──────────────
Entry point for the web crawler.

Usage
─────
  # Run with default config (edit crawler/config.py first):
  python crawler/run.py

  # Pass custom seeds and page limit:
  python crawler/run.py --seeds https://example.com https://python.org --max 50

  # Resume a previous crawl (frontier state is persisted in database.sqlite):
  python crawler/run.py
"""

import argparse
import sys
import os

# Allow running as  python crawler/run.py  from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.crawler import Crawler
from crawler import config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PythonSearchBot — web crawler"
    )
    p.add_argument(
        "--seeds", nargs="*",
        help="One or more seed URLs (overrides config.SEED_URLS)",
    )
    p.add_argument(
        "--max", type=int, default=None,
        help=f"Max pages to crawl (default: {config.MAX_PAGES})",
    )
    return p.parse_args()


def main() -> None:
    args  = parse_args()
    seeds = args.seeds or config.SEED_URLS
    max_p = args.max   or config.MAX_PAGES

    print("=" * 60)
    print("  PythonSearchBot — Web Crawler")
    print("=" * 60)
    print(f"  Seed URLs : {seeds}")
    print(f"  Max pages : {max_p}")
    print(f"  Max depth : {config.MAX_DEPTH}")
    print(f"  Rate limit: {config.RATE_LIMIT_SECONDS}s per domain")
    print(f"  Robots.txt: {'respected' if config.RESPECT_ROBOTS_TXT else 'ignored'}")
    print("=" * 60)
    print()

    crawler = Crawler()
    try:
        crawler.run(seed_urls=seeds, max_pages=max_p)
    except KeyboardInterrupt:
        print("\n\nInterrupted — progress is saved in database.sqlite")
        sys.exit(0)


if __name__ == "__main__":
    main()
