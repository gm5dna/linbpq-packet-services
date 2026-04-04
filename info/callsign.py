"""
callsign.py -- Callsign lookup sub-service for the packet node INFO menu.

Uses the QRZ.com XML API (paid subscription, session-based auth).
Credentials are read from a config file (see config.py for the path).

Config file format (plain text, one key=value per line):
    qrz_username=YOURCALL
    qrz_password=yourpassword
"""

import os
import sys
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

QRZ_URL     = "https://xmldata.qrz.com/xml/current/"
QRZ_NS      = "{http://xmldata.qrz.com}"
CONF_FILE   = config.QRZ_CONF_FILE
PROGRAM_ID  = config.NODE_CALLSIGN


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_config():
    """Read credentials from CONF_FILE. Returns a dict."""
    try:
        with open(CONF_FILE, "r") as fh:
            lines = fh.readlines()
    except OSError:
        return {}

    cfg = {}
    for line in lines:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            cfg[key.strip().lower()] = val.strip()

    return cfg


# ---------------------------------------------------------------------------
# QRZ API helpers
# ---------------------------------------------------------------------------

def _qrz_get_session(username, password):
    """
    Authenticate with QRZ and return a session key string.
    Returns None on failure.
    """
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(
            QRZ_URL,
            params={"username": username, "password": password, "agent": PROGRAM_ID},
            timeout=15,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        session_el = root.find(QRZ_NS + "Session")
        if session_el is None:
            return None
        key_el = session_el.find(QRZ_NS + "Key")
        if key_el is not None and key_el.text:
            return key_el.text.strip()
        return None
    except Exception:
        return None


def _qrz_lookup(session_key, callsign):
    """
    Look up a callsign via QRZ XML API.
    Returns a result dict, "not_found", "session_error", or None.
    """
    if not REQUESTS_OK:
        return None
    callsign = callsign.upper().strip()
    try:
        r = requests.get(
            QRZ_URL,
            params={"s": session_key, "callsign": callsign},
            timeout=15,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:
        return None

    def _find(parent, tag):
        el = parent.find(QRZ_NS + tag)
        if el is not None and el.text:
            return el.text.strip()
        return ""

    session_el = root.find(QRZ_NS + "Session")
    if session_el is not None:
        err = _find(session_el, "Error")
        if err:
            msg = err.lower()
            if "not found" in msg:
                return "not_found"
            if "session" in msg or "invalid" in msg or "key" in msg:
                return "session_error"
            return None

    cs_el = root.find(QRZ_NS + "Callsign")
    if cs_el is None:
        return "not_found"

    fname = _find(cs_el, "fname")
    name = _find(cs_el, "name")
    display_name = " ".join(p for p in [fname, name] if p)

    addr2 = _find(cs_el, "addr2")
    state = _find(cs_el, "state")
    city = ", ".join(p for p in [addr2, state] if p)

    qslmgr = _find(cs_el, "qslmgr")
    qsl_parts = []
    if qslmgr:
        qsl_parts.append(qslmgr)
    else:
        lotw = _find(cs_el, "lotw")
        if lotw and lotw.upper() in ("Y", "YES", "1"):
            qsl_parts.append("LoTW")
        eqsl = _find(cs_el, "eqsl")
        if eqsl and eqsl.upper() in ("Y", "YES", "1"):
            qsl_parts.append("eQSL")

    return {
        "callsign": _find(cs_el, "call") or callsign,
        "name":     display_name,
        "country":  _find(cs_el, "country"),
        "city":     city,
        "grid":     _find(cs_el, "grid"),
        "qsl":      ", ".join(qsl_parts) if qsl_parts else "Unknown",
        "email":    _find(cs_el, "email"),
        "web":      _find(cs_el, "url"),
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_result(result, writeln):
    """Pretty-print a callsign lookup result dict."""
    cs      = result.get("callsign", "")
    name    = result.get("name", "")
    city    = result.get("city", "")
    country = result.get("country", "")
    grid    = result.get("grid", "")
    qsl     = result.get("qsl", "")
    email   = result.get("email", "")
    web     = result.get("web", "")

    header_parts = [cs]
    if name:
        loc_parts = [p for p in [name, city] if p]
        header_parts.append(", ".join(loc_parts))
    writeln("  " + " - ".join(header_parts))

    details = []
    if grid:
        details.append("Grid: " + grid)
    if country:
        details.append("Country: " + country)
    if details:
        writeln("  " + " | ".join(details))

    writeln("  QSL: " + qsl)

    if email:
        writeln("  Email: " + email)
    if web:
        writeln("  Web: " + web)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(writeln, read_line, write):
    """
    Entry point called from the main INFO menu.

    Parameters
    ----------
    writeln   : callable -- write a line followed by newline
    read_line : callable -- read one line from stdin (returns str or None)
    write     : callable -- write text with no trailing newline
    """
    writeln()
    writeln("=== Callsign Lookup (QRZ) ===")
    writeln()

    if not REQUESTS_OK:
        writeln("Error: 'requests' library not available.")
        writeln()
        return

    cfg = _load_config()
    qrz_user = cfg.get("qrz_username")
    qrz_pass = cfg.get("qrz_password")

    if not qrz_user or not qrz_pass:
        writeln("No QRZ credentials found.")
        writeln("Create {} with your QRZ.com credentials.".format(CONF_FILE))
        writeln("See qrz.conf.example for the format.")
        writeln()
        return

    qrz_session = _qrz_get_session(qrz_user, qrz_pass)
    if not qrz_session:
        writeln("QRZ login failed. Check credentials in {}".format(CONF_FILE))
        writeln()
        return

    writeln("Ready. Enter a callsign to look up.")
    writeln("Blank line returns to the menu.")
    writeln()

    while True:
        write("Callsign: ")
        line = read_line()

        if line is None:
            return

        callsign = line.strip().upper()
        if callsign == "":
            return

        write("Looking up {}...".format(callsign))
        result = _qrz_lookup(qrz_session, callsign)

        if result == "session_error":
            writeln("")
            writeln("Session expired, re-logging in...")
            qrz_session = _qrz_get_session(qrz_user, qrz_pass)
            if not qrz_session:
                writeln("Re-login failed. Returning to menu.")
                writeln()
                return
            result = _qrz_lookup(qrz_session, callsign)

        writeln("")

        if result is None:
            writeln("  Network error. Could not reach QRZ.")
        elif result == "not_found":
            writeln("  {} not found in QRZ database.".format(callsign))
        elif result == "session_error":
            writeln("  Session error. Please try again later.")
        else:
            _display_result(result, writeln)

        writeln()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    from io_helpers import writeln as _writeln, read_line as _rl, write as _write
    run(_writeln, _rl, _write)
