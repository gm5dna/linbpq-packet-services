"""
news.py -- RSS news reader sub-service for the packet node INFO menu.

Fetches headlines from amateur radio and general news RSS feeds.
Uses xml.etree.ElementTree (stdlib) to parse RSS 2.0 XML.
Per-feed caching with 15-minute TTL.
"""

import json
import os
import re
import sys
import time
import textwrap
import xml.etree.ElementTree as ET

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

CACHE_DIR = config.CACHE_DIR
CACHE_MAX_AGE = 900  # 15 minutes

MAX_ITEMS = 15
LINE_WIDTH = 78

USER_AGENT = "{}/1.0".format(config.NODE_CALLSIGN)

# (key, label, description, feed_url)
FEEDS = [
    ("rsgb",    "RSGB",      "UK amateur radio",    "https://rsgb.org/main/feed/"),
    ("bbc",     "BBC News",  "top stories",         "https://feeds.bbci.co.uk/news/rss.xml"),
    ("arrl",    "ARRL",      "news & features",     "http://www.arrl.org/news/rss"),
    ("dxworld", "DX-World",  "DX news",             "https://www.dx-world.net/feed/"),
]


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
    "&#39;": "'", "&apos;": "'", "&nbsp;": " ", "&#8217;": "'",
    "&#8216;": "'", "&#8220;": '"', "&#8221;": '"', "&#8230;": "...",
}


def _strip_html(text):
    """Remove HTML tags and decode common entities."""
    text = _HTML_TAG_RE.sub("", text)
    for entity, char in _HTML_ENTITIES.items():
        text = text.replace(entity, char)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Feed fetching and parsing
# ---------------------------------------------------------------------------

def _fetch_feed(url):
    """Fetch raw XML from an RSS feed URL. Returns text or None."""
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _parse_rss(xml_text):
    """
    Parse RSS 2.0 XML and return a list of item dicts.
    Each dict has keys: title, desc, date.
    Returns up to MAX_ITEMS items, or an empty list on failure.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []

    channel = root.find("channel")
    if channel is not None:
        for item_el in channel.findall("item")[:MAX_ITEMS]:
            title = (item_el.findtext("title") or "").strip()
            desc = (item_el.findtext("description") or "").strip()
            date = (item_el.findtext("pubDate") or "").strip()
            if title:
                items.append({
                    "title": _strip_html(title),
                    "desc": _strip_html(desc),
                    "date": _format_date(date),
                })
        return items

    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry_el in root.findall("a:entry", ns)[:MAX_ITEMS]:
        title = (entry_el.findtext("a:title", namespaces=ns) or "").strip()
        desc = (entry_el.findtext("a:summary", namespaces=ns) or "").strip()
        date = (entry_el.findtext("a:updated", namespaces=ns) or "").strip()
        if title:
            items.append({
                "title": _strip_html(title),
                "desc": _strip_html(desc),
                "date": _format_date(date),
            })

    return items


def _format_date(date_str):
    """
    Parse an RFC 822 or ISO 8601 date and return 'DD Mon' format.
    Falls back to the first 10 characters of the raw string.
    """
    if not date_str:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%d %b")
    except Exception:
        pass
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b")
    except Exception:
        pass
    return date_str[:10]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(feed_key):
    return os.path.join(CACHE_DIR, "news_{}.json".format(feed_key))


def _load_cache(feed_key):
    """
    Load cached feed items.
    Returns (items_list, is_fresh, age_seconds) or (None, False, None).
    """
    try:
        with open(_cache_path(feed_key), "r") as fh:
            cached = json.load(fh)
        age = time.time() - cached.get("fetch_ts", 0)
        return cached.get("items", []), age < CACHE_MAX_AGE, age
    except (OSError, json.JSONDecodeError, KeyError):
        return None, False, None


def _save_cache(feed_key, items):
    """Save feed items to cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(feed_key), "w") as fh:
            json.dump({"fetch_ts": time.time(), "items": items}, fh)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _wrap_text(text, width=LINE_WIDTH):
    """Word-wrap text preserving paragraph breaks."""
    paragraphs = text.split("\n\n")
    wrapped = []
    for para in paragraphs:
        para = para.strip()
        if para:
            wrapped.append(textwrap.fill(para, width=width))
    return "\n\n".join(wrapped)


def _fmt_age(seconds):
    """Human-friendly staleness string."""
    if seconds is None:
        return "unknown age"
    mins = int(seconds / 60)
    if mins < 2:
        return "just now"
    if mins < 60:
        return "{} min old".format(mins)
    return "{} hr old".format(mins // 60)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(writeln, read_line, write):
    """
    Entry point called from the main INFO menu.
    """
    if not REQUESTS_OK:
        writeln()
        writeln("Error: 'requests' library not available.")
        writeln()
        return

    while True:
        writeln()
        writeln("=== RSS News Reader ===")
        writeln()
        writeln("Select a feed:")
        for i, (key, label, desc, url) in enumerate(FEEDS, 1):
            writeln(" {}  {:<12} - {}".format(i, label, desc))
        writeln()

        write("Feed (or blank to return): ")
        choice = read_line()

        if choice is None:
            return
        choice = choice.strip()
        if choice == "":
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(FEEDS):
                raise ValueError
        except ValueError:
            writeln("Invalid choice.")
            continue

        feed_key, feed_label, _, feed_url = FEEDS[idx]

        writeln()
        writeln("Fetching {}, please wait...".format(feed_label))

        cached_items, is_fresh, cache_age = _load_cache(feed_key)
        stale = False

        if is_fresh and cached_items:
            items = cached_items
        else:
            xml_text = _fetch_feed(feed_url)
            fresh_items = _parse_rss(xml_text) if xml_text else []

            if fresh_items:
                _save_cache(feed_key, fresh_items)
                items = fresh_items
            elif cached_items:
                items = cached_items
                stale = True
            else:
                writeln()
                writeln("Sorry, could not fetch this feed.")
                writeln("Please try again later.")
                continue

        writeln()
        if stale:
            writeln("** Cached data ({}) -- live fetch failed **".format(
                _fmt_age(cache_age)))
            writeln()
        writeln("=== {} ===".format(feed_label))
        writeln()

        for i, item in enumerate(items, 1):
            date_part = "[{}] ".format(item["date"]) if item["date"] else ""
            title = item["title"]
            prefix = "{:>2}  {}".format(i, date_part)
            max_title = LINE_WIDTH - len(prefix)
            if len(title) > max_title:
                title = title[:max_title - 3] + "..."
            writeln("{}{}".format(prefix, title))

        while True:
            writeln()
            write("Enter number for details, or blank to go back: ")
            pick = read_line()

            if pick is None:
                return
            pick = pick.strip()
            if pick == "":
                break

            try:
                art_idx = int(pick) - 1
                if art_idx < 0 or art_idx >= len(items):
                    raise ValueError
            except ValueError:
                writeln("Invalid choice. Enter 1-{} or blank.".format(len(items)))
                continue

            article = items[art_idx]
            writeln()
            writeln("--- {} ---".format(article["title"][:LINE_WIDTH - 8]))
            writeln()
            if article["desc"]:
                writeln(_wrap_text(article["desc"]))
            else:
                writeln("(No summary available for this article.)")
