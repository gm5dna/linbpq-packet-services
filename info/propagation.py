"""
propagation.py -- HF propagation sub-service for the packet node INFO menu.

Fetches solar/band-condition data from the hamqsl.com XML feed.
Uses a 30-minute local cache to avoid hammering the upstream service.

CLI usage:
    python3 propagation.py        -- interactive (fetches or reads cache)
    python3 propagation.py -c     -- cache-refresh mode (fetch + save, no output)
"""

import json
import os
import sys
import time
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

XML_URL   = "https://www.hamqsl.com/solarxml.php"
CACHE_DIR = config.CACHE_DIR
CACHE_FILE = os.path.join(CACHE_DIR, "propagation.json")
CACHE_MAX_AGE = 1800  # 30 minutes in seconds

CALLSIGN = config.NODE_CALLSIGN

# HamQSL band names as they appear in the XML.
BAND_GROUPS = [
    ("80m-40m",  ["80m-40m"]),
    ("30m-20m",  ["30m-20m"]),
    ("17m-15m",  ["17m-15m"]),
    ("12m-10m",  ["12m-10m"]),
]


# ---------------------------------------------------------------------------
# Data fetching and parsing
# ---------------------------------------------------------------------------

def _fetch_xml():
    """Fetch raw XML from hamqsl.com. Returns text string or None."""
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(XML_URL, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _text(el, tag, default=""):
    """Return stripped text of a child element, or default if absent."""
    child = el.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _parse_xml(xml_text):
    """
    Parse hamqsl XML and return a flat dict of propagation data.
    Returns None if parsing fails.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    solar = root.find("solardata")
    if solar is None:
        return None

    data = {
        "sfi":         _text(solar, "solarflux"),
        "sunspots":    _text(solar, "sunspots"),
        "a_index":     _text(solar, "aindex"),
        "k_index":     _text(solar, "kindex"),
        "xray":        _text(solar, "xray"),
        "geofield":    _text(solar, "geomagfield"),
        "sig_noise":   _text(solar, "signalnoise"),
        "updated":     _text(solar, "updated"),
        "eski_eu":     "",
        "aurora":      _text(solar, "aurora"),
        "aurora_lat":  _text(solar, "latdegree"),
        "bands":       {},
        "fetch_ts":    time.time(),
    }

    calc = solar.find("calculatedconditions")
    if calc is not None:
        for band_el in calc.findall("band"):
            name      = band_el.get("name", "")
            period    = band_el.get("time", "")
            condition = (band_el.text or "").strip()
            if name not in data["bands"]:
                data["bands"][name] = {}
            data["bands"][name][period] = condition

    vhf = solar.find("calculatedvhfconditions")
    if vhf is not None:
        for ph in vhf.findall("phenomenon"):
            ph_name = ph.get("name", "")
            ph_loc  = ph.get("location", "")
            ph_val  = (ph.text or "").strip()
            if ph_name == "E-Skip" and ph_loc == "europe":
                data["eski_eu"] = ph_val
            elif ph_name == "vhf-aurora" and ph_loc == "northern_hemi":
                if not data["aurora"]:
                    data["aurora"] = ph_val

    return data


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache():
    """
    Load cached propagation data.
    Returns (data_dict, is_fresh, age_seconds) or (None, False, None).
    """
    try:
        with open(CACHE_FILE, "r") as fh:
            cached = json.load(fh)
        age = time.time() - cached.get("fetch_ts", 0)
        return cached, age < CACHE_MAX_AGE, age
    except (OSError, json.JSONDecodeError, KeyError):
        return None, False, None


def _save_cache(data):
    """Save propagation data dict to cache file."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as fh:
            json.dump(data, fh)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_age(seconds):
    """Return a human-friendly staleness string."""
    if seconds is None:
        return "unknown age"
    mins = int(seconds / 60)
    if mins < 2:
        return "just now"
    if mins < 60:
        return "{} min old".format(mins)
    hrs = mins // 60
    return "{} hr old".format(hrs)


def _band_condition_row(data, label, keys):
    """
    Return a formatted line for one band group.
    keys is a list of band names to look up (usually one entry).
    """
    day   = "N/A"
    night = "N/A"
    for k in keys:
        entry = data["bands"].get(k, {})
        if entry.get("day"):
            day   = entry["day"]
        if entry.get("night"):
            night = entry["night"]
    return "  {:8s}  {} / {}".format(label + ":", day, night)


def _format_output(data, stale=False, stale_age=None):
    """Return a list of display lines (plain ASCII) for the given data dict."""
    lines = []
    lines.append("=== HF Propagation - {} ===".format(CALLSIGN))
    lines.append("")

    if stale:
        lines.append("** Cached data ({}) -- live fetch failed **".format(
            _fmt_age(stale_age)))
        lines.append("")

    sfi       = data.get("sfi", "?")
    sunspots  = data.get("sunspots", "?")
    a_index   = data.get("a_index", "?")
    k_index   = data.get("k_index", "?")
    xray      = data.get("xray", "?")
    geofield  = data.get("geofield", "?")
    sig_noise = data.get("sig_noise", "?")

    lines.append("Solar: SFI {} | Sunspots {} | A-index {} | K-index {}".format(
        sfi, sunspots, a_index, k_index))
    lines.append("X-ray: {} | Geofield: {} | Sig Noise: {}".format(
        xray, geofield, sig_noise))
    lines.append("")
    lines.append("Band Conditions (Day / Night):")

    for label, keys in BAND_GROUPS:
        lines.append(_band_condition_row(data, label, keys))

    lines.append("")

    eski   = data.get("eski_eu") or "N/A"
    aurora = data.get("aurora") or "N/A"
    a_lat  = data.get("aurora_lat") or ""
    aurora_str = aurora
    if a_lat:
        aurora_str = "{} (lat {})".format(aurora, a_lat)
    lines.append("VHF: E-skip Europe: {} | Aurora: {}".format(eski, aurora_str))
    lines.append("")

    updated = data.get("updated", "unknown")
    lines.append("Updated: {}".format(updated))

    return lines


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(writeln, read_line, write):
    """
    Entry point called from the main INFO menu.

    Fetches (or reads from cache) solar/HF propagation data and displays it.
    Returns immediately after display -- no interactive loop needed.
    """
    writeln()
    writeln("Fetching HF propagation data, please wait...")
    writeln()

    data, is_fresh, cache_age = _load_cache()

    if is_fresh and data:
        stale = False
        stale_age = None
    else:
        xml_text = _fetch_xml()
        fresh_data = _parse_xml(xml_text) if xml_text else None

        if fresh_data:
            _save_cache(fresh_data)
            data = fresh_data
            stale = False
            stale_age = None
        elif data:
            stale = True
            stale_age = cache_age
        else:
            writeln("Sorry, HF propagation data is unavailable.")
            writeln("(Could not reach hamqsl.com and no cached data found.)")
            writeln()
            return

    output = "\n".join(_format_output(data, stale=stale, stale_age=stale_age))
    writeln(output)
    writeln()


# ---------------------------------------------------------------------------
# CLI entry point (cache-refresh mode)
# ---------------------------------------------------------------------------

def _cli_cache_refresh():
    """Fetch live data and save to cache. No display output."""
    xml_text = _fetch_xml()
    if not xml_text:
        sys.stderr.write("propagation: fetch failed\n")
        sys.exit(1)
    data = _parse_xml(xml_text)
    if not data:
        sys.stderr.write("propagation: XML parse failed\n")
        sys.exit(1)
    _save_cache(data)
    sys.stdout.write("propagation: cache updated\n")


if __name__ == "__main__":
    if "-c" in sys.argv:
        _cli_cache_refresh()
    else:
        sys.path.insert(0, os.path.dirname(__file__))
        from io_helpers import writeln as _writeln, read_line as _rl, write as _write
        run(_writeln, _rl, _write)
