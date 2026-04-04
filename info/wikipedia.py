"""
wikipedia.py -- Wikipedia search & browse sub-service for the packet node
INFO menu.

Uses the MediaWiki API at en.wikipedia.org to search for articles and
display plain-text extracts. Paginated output for packet radio terminals.
"""

import json
import os
import re
import sys
import textwrap

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import config

API_URL = "https://en.wikipedia.org/w/api.php"
MAX_RESULTS = 10
MAX_EXTRACT_CHARS = 4000
PAGE_SIZE = 20
LINE_WIDTH = 78

USER_AGENT = "{}/1.0".format(config.NODE_CALLSIGN)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _search(term):
    """
    Search Wikipedia for articles matching the term.
    Returns a list of {"title": str, "snippet": str} dicts (max MAX_RESULTS),
    or None on network error.
    """
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(API_URL, params={
            "action": "query",
            "list": "search",
            "srsearch": term,
            "srlimit": MAX_RESULTS,
            "format": "json",
        }, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("query", {}).get("search", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": _strip_html(item.get("snippet", "")),
            })
        return results
    except Exception:
        return None


def _fetch_extract(title):
    """
    Fetch the plain-text extract for a Wikipedia article.
    Returns the text string, or None on error.
    """
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(API_URL, params={
            "action": "query",
            "prop": "extracts",
            "explaintext": "true",
            "titles": title,
            "format": "json",
            "exsectionformat": "plain",
        }, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract:
                return extract
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text):
    """Remove HTML tags from search snippets."""
    return _HTML_TAG_RE.sub("", text).strip()


def _wrap_text(text, width=LINE_WIDTH):
    """Word-wrap text, preserving paragraph breaks and section headings."""
    lines = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip()
        if not paragraph:
            lines.append("")
        elif paragraph.startswith("=="):
            lines.append(paragraph)
        elif len(paragraph) <= width:
            lines.append(paragraph)
        else:
            lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def _truncate(text, max_chars=MAX_EXTRACT_CHARS):
    """Truncate text at a word boundary if it exceeds max_chars."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rfind(" ")
    if cut < 0:
        cut = max_chars
    return text[:cut] + "\n\n[...article truncated]"


def _paginate(lines, writeln, read_line, write, page_size=PAGE_SIZE):
    """
    Display lines in pages. Returns True if all shown, False if user quit.
    """
    for i, line in enumerate(lines):
        writeln(line)
        if (i + 1) % page_size == 0 and i + 1 < len(lines):
            write("-- more (ENTER=next, Q=stop) -- ")
            resp = read_line()
            if resp is None:
                return False
            if resp.strip().upper() == "Q":
                return False
    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(writeln, read_line, write):
    """Entry point called from the main INFO menu."""
    if not REQUESTS_OK:
        writeln()
        writeln("Error: 'requests' library not available.")
        writeln()
        return

    writeln()
    writeln("=== Wikipedia ===")
    writeln()
    writeln("Enter a search term, or blank to return.")

    while True:
        writeln()
        write("Search: ")
        term = read_line()

        if term is None:
            return
        term = term.strip()
        if term == "":
            return

        writeln()
        writeln("Searching, please wait...")

        results = _search(term)

        if results is None:
            writeln("Sorry, could not reach Wikipedia. Please try later.")
            continue

        if not results:
            writeln("No results found for '{}'. Try a different search.".format(term))
            continue

        writeln()
        for i, item in enumerate(results, 1):
            title = item["title"]
            if len(title) > LINE_WIDTH - 5:
                title = title[:LINE_WIDTH - 8] + "..."
            writeln("{:>2}  {}".format(i, title))

        while True:
            writeln()
            write("Enter number to read, or blank to search again: ")
            pick = read_line()

            if pick is None:
                return
            pick = pick.strip()
            if pick == "":
                break

            try:
                idx = int(pick) - 1
                if idx < 0 or idx >= len(results):
                    raise ValueError
            except ValueError:
                writeln("Invalid choice. Enter 1-{} or blank.".format(len(results)))
                continue

            title = results[idx]["title"]
            writeln()
            writeln("Fetching \"{}\", please wait...".format(title))

            extract = _fetch_extract(title)

            if not extract:
                writeln("Sorry, could not fetch this article.")
                continue

            extract = _truncate(extract)
            lines = _wrap_text(extract)

            writeln()
            writeln("--- {} ---".format(title[:LINE_WIDTH - 8]))
            writeln()
            _paginate(lines, writeln, read_line, write)
