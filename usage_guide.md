# Usage Guide

## Prerequisites

- Python 3.11 or newer
- `pip` for package installation
- An internet connection for the initial crawl (not needed for searching)

---

## Installation

Clone or unzip the project, then install the three required packages:

```bash
cd project/

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

`requirements.txt` contains only:

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

No NLTK data downloads are required. The tokeniser is fully self-contained.

---

## Part 1 — Running the Crawler

### Step 1: Configure your seeds

Open `crawler/config.py` and set the URLs you want to start crawling from:

```python
SEED_URLS = [
    "https://example.com",
    "https://en.wikipedia.org/wiki/Web_crawler",
]

MAX_PAGES = 100    # total pages to crawl
MAX_DEPTH = 3      # max hops from any seed
```

Key parameters to know:

| Parameter | What it controls |
|---|---|
| `SEED_URLS` | Where the crawl begins. Use specific article URLs to crawl a focused topic. |
| `MAX_PAGES` | The crawler stops after this many successfully indexed pages. |
| `MAX_DEPTH` | Pages 3 hops from a seed are crawled; pages 4 hops away are not. |
| `RATE_LIMIT_SECONDS` | How long to wait between requests to the same domain. Default 1.5s is safe for most sites. |
| `RESPECT_ROBOTS_TXT` | Leave this `True` unless you are crawling your own server. |

### Step 2: Run the crawler

Always run from the **project root** (the folder that contains both `crawler/` and `search_engine/`):

```bash
python crawler/run.py
```

You will see real-time progress:

```
============================================================
  PythonSearchBot — Web Crawler
============================================================
  Seed URLs : ['https://example.com', 'https://en.wikipedia.org/...']
  Max pages : 100
  Max depth : 3
  Rate limit: 1.5s per domain
  Robots.txt: respected
============================================================

[DB] Database ready → /path/to/project/database.sqlite
10:01:23 [INFO] Seeded 2 new URL(s). Max pages: 100
10:01:24 [INFO] [1/100] https://example.com
10:01:26 [INFO]   ✓ doc_id=1  title='Example Domain'
10:01:26 [INFO]     found 1 links
10:01:27 [INFO] [2/100] https://en.wikipedia.org/wiki/Web_crawler
10:01:29 [INFO]   ✓ doc_id=2  title='Web crawler - Wikipedia'
10:01:29 [INFO]     found 312 links
...

Crawl finished — crawled: 47, indexed: 47, skipped: 3
```

**Skipped** means the URL was disallowed by robots.txt, was a duplicate, had too little text (under 30 words), or returned a non-200 status.

### CLI options

You can override `config.py` values from the command line without editing the file:

```bash
# Different seeds
python crawler/run.py --seeds https://python.org https://docs.python.org

# Smaller crawl
python crawler/run.py --max 25

# Both at once
python crawler/run.py --seeds https://news.ycombinator.com --max 200
```

### Stopping and resuming

Press `Ctrl+C` at any time. The crawler saves progress to `database.sqlite` immediately and you will see:

```
Interrupted — progress is saved in database.sqlite
```

To resume, simply run the same command again. The URL frontier is persisted, so only pages not yet crawled will be fetched. Already-indexed pages are not re-fetched.

### Running multiple crawls on different topics

Each time you run `python crawler/run.py --seeds <url>`, new URLs are added to the existing frontier and new pages are appended to the index. To start completely fresh:

```bash
rm database.sqlite
python crawler/run.py
```

---

## Part 2 — Running the Search Engine

Once you have crawled at least a few pages, start the search REPL:

```bash
python search_engine/run.py
```

You will see:

```
──────────────────────────────────────────────────────────────────
  🔍  PythonSearchEngine
  Database: /path/to/project/database.sqlite
──────────────────────────────────────────────────────────────────
  Type a query to search. Type :help for commands.

  Search> _
```

On startup, the search engine computes PageRank over the crawled link graph. This takes less than a second for crawls up to ~5,000 pages.

---

## Search Query Syntax

### Basic keyword search

Type one or more words. The retriever first tries to find documents containing **all** of the terms (AND mode). If no results are found, it falls back to documents containing **any** of the terms (OR mode).

```
Search> web crawler python
```

### Phrase search

Wrap a phrase in double quotes. The query processor treats the entire phrase as a unit when tokenising.

```
Search> "web crawler" python
```

### Exclude a term

Prefix a word with `-` to exclude documents that contain it.

```
Search> python framework -django
Search> web scraping -javascript
```

### Restrict to a domain

Use `site:` to limit results to a specific domain or subdomain.

```
Search> site:docs.python.org asyncio
Search> site:en.wikipedia.org machine learning
```

### Paginate results

Append `--page N` (zero-indexed) to go to page N.

```
Search> python --page 0      (first page — default)
Search> python --page 1      (second page)
Search> python --page 2      (third page)
```

The results header shows the current page and total:

```
  42 result(s) for 'python'  [page 1/5]
```

### Combining operators

All operators can be combined in a single query:

```
Search> site:docs.python.org "asyncio event loop" -windows --page 0
```

---

## REPL Commands

| Command | What it does |
|---|---|
| `:help` | Show query syntax and command reference |
| `:stats` | Show database statistics (document count, term count, frontier status) |
| `:suggest <prefix>` | Show autocomplete suggestions for a prefix |
| `:quit` or `:q` | Exit the search engine |

### `:stats` example output

```
  Documents indexed : 47
  Unique terms      : 8,312
  Frontier pending  : 0
  Pages crawled     : 47
```

### `:suggest` example

```
Search> :suggest craw
  Suggestions: crawl, crawler, crawling, crawled
```

Autocomplete uses binary search on a sorted in-memory list of all indexed terms. Suggestions are stemmed tokens, so `craw` matches `crawl` (the stemmed form of `crawling`).

---

## Reading the Results

Each result shows four lines:

```
  1. Web crawler - Wikipedia
     https://en.wikipedia.org/wiki/Web_crawler
     A web crawler is an Internet bot that systematically browses the World Wide
     Web, typically for the purpose of web indexing …
     score=1.2847
```

| Field | Source |
|---|---|
| Title | `<title>` tag, or first `<h1>` if title is absent |
| URL | Final URL after redirects |
| Snippet | The sentence window in the body text with the highest query-term density, trimmed to 220 characters |
| Score | Blended score: `0.50 × TF-IDF + 0.35 × PageRank + 0.15 × Freshness` |

---

## Practical Crawl Recipes

### Crawl a documentation site

Set `MAX_DEPTH = 4` and use a deep entry point to get full coverage of a docs site:

```python
SEED_URLS = ["https://docs.python.org/3/library/"]
MAX_PAGES  = 500
MAX_DEPTH  = 4
```

### Crawl a Wikipedia topic

Start from a hub article. Wikipedia's dense interlinking means even depth 2 yields hundreds of related articles:

```python
SEED_URLS = [
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Deep_learning",
]
MAX_PAGES  = 300
MAX_DEPTH  = 2
```

### Crawl your own localhost site

To index a local Flask/Django development server:

```python
SEED_URLS          = ["http://localhost:8000/"]
RATE_LIMIT_SECONDS = 0.0     # No need to be polite to yourself
RESPECT_ROBOTS_TXT = False   # Your local server probably has no robots.txt
MAX_PAGES          = 1000
MAX_DEPTH          = 10
```

### Quick test crawl (5 pages)

For testing the pipeline end-to-end quickly:

```bash
python crawler/run.py --seeds https://example.com --max 5
```

---

## Inspecting the Database

`database.sqlite` is a standard SQLite file. You can open it with the `sqlite3` command-line tool or any SQLite GUI (DB Browser for SQLite, TablePlus, DBeaver, etc.):

```bash
sqlite3 database.sqlite
```

Useful queries:

```sql
-- How many pages are indexed?
SELECT COUNT(*) FROM documents;

-- What are the top 10 documents by word count?
SELECT title, word_count, url FROM documents ORDER BY word_count DESC LIMIT 10;

-- Which terms are most common across the index?
SELECT term, SUM(frequency) AS total
FROM inverted_index
GROUP BY term
ORDER BY total DESC
LIMIT 20;

-- What does the posting list for a term look like?
SELECT d.title, ii.frequency
FROM inverted_index ii
JOIN documents d ON d.doc_id = ii.doc_id
WHERE ii.term = 'crawl'
ORDER BY ii.frequency DESC;

-- How many URLs are still pending in the frontier?
SELECT status, COUNT(*) FROM frontier GROUP BY status;

-- Which domains were crawled?
SELECT domain, COUNT(*) AS pages
FROM frontier
WHERE status = 'crawled'
GROUP BY domain
ORDER BY pages DESC;
```

---

## Troubleshooting

**`database.sqlite not found`**

The search engine cannot find the database. Make sure you run the crawler first and that you are running both commands from the project root directory:

```bash
cd project/          # must be here
python crawler/run.py
python search_engine/run.py
```

**`No results` for a query you expect to find**

Check `:stats` to confirm pages were indexed. If `Documents indexed` is 0, the crawl may have skipped everything. Common causes:
- All seed URLs were blocked by robots.txt (set `RESPECT_ROBOTS_TXT = False` to debug)
- Pages had fewer than 30 words of visible text
- The site serves JavaScript-rendered content (see Limitations in `System_design.md`)

Try a simpler query: a single common word that definitely appears in your crawled content.

**Results have very low scores (near 0)**

This usually means very few pages were crawled, so TF-IDF and PageRank have almost no signal to work with. Crawl at least 20–30 pages on the same topic before expecting meaningful ranking.

**Crawl is very slow**

Each request waits `RATE_LIMIT_SECONDS` (default 1.5s) between requests to the same domain. A crawl of 100 pages from a single domain takes at least 2.5 minutes. To speed this up:
- Reduce `RATE_LIMIT_SECONDS` to `0.5` (be careful — some sites may rate-limit or block you)
- Add more seed URLs across different domains so requests interleave

**`Interrupted — progress is saved` but crawl doesn't resume**

URLs that were in `processing` status when the crawl was interrupted are not automatically retried. Reset them:

```bash
sqlite3 database.sqlite "UPDATE frontier SET status='pending' WHERE status='processing';"
python crawler/run.py
```

**Autocomplete returns stemmed tokens like `programm` instead of `programming`**

This is expected behaviour. The tokeniser applies Porter stemming, so `programming`, `programmer`, and `programmed` all become `programm` in the index. The search engine also stems your query, so searching for `programming` correctly matches `programm` entries. You only see the stemmed form in autocomplete suggestions.

**NLTK errors or `LookupError: Resource not found`**

The tokeniser does not use NLTK. If you see NLTK errors, an older version of `tokenizer.py` may still be present. Verify:

```bash
grep -n "nltk" crawler/tokenizer.py search_engine/tokenizer.py
```

Both files should return no matches. If they do, re-download the project zip.

---

## Resetting the Index

To wipe everything and start over:

```bash
rm database.sqlite
python crawler/run.py --seeds https://your-site.com
```

To wipe the index but keep the crawled pages (re-index without re-crawling):

```bash
sqlite3 database.sqlite "DELETE FROM inverted_index;"
sqlite3 database.sqlite "DELETE FROM documents;"
```

Then modify and re-run `crawler/run.py` — the frontier still has all the crawled URLs marked as `crawled`, so they won't be re-fetched. You would need to reset them too:

```bash
sqlite3 database.sqlite "UPDATE frontier SET status='pending';"
python crawler/run.py
```
