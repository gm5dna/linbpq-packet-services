#!/usr/bin/env python3
"""
satpass.py - Satellite pass prediction service for LinBPQ packet nodes.

Runs as a systemd socket-activated TCP service. LinBPQ sends CR-only line
endings. Reads TLE data from local cache; no network access at runtime.

https://github.com/gm5dna/linbpq-packet-services
Originally developed for GB7DNA by GM5DNA.
"""

import sys
import os
import select
import math
from datetime import datetime, timezone, timedelta

# Allow imports from the parent directory (for config.py).
_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import config

# ---------------------------------------------------------------------------
# I/O helpers (binary, CR-tolerant)
# ---------------------------------------------------------------------------

def write(text):
    """Write text via os.write() for atomic output to the socket."""
    try:
        os.write(1, text.encode("ascii", errors="replace"))
    except (BrokenPipeError, OSError):
        sys.exit(0)


def writeln(text=""):
    write(text + "\n")


def write_block(lines):
    """Write multiple lines as a single TCP segment using TCP_CORK."""
    import socket
    data = ("\n".join(lines) + "\n").encode("ascii", errors="replace")
    try:
        sock = socket.fromfd(1, socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)
            sock.sendall(data)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)
        finally:
            sock.detach()
    except Exception:
        write("\n".join(lines) + "\n")


CR = b"\r"
LF = b"\n"


def read_line():
    buf = bytearray()
    while True:
        try:
            ch = os.read(0, 1)
        except OSError:
            return None
        if not ch:
            return None
        if ch == CR or ch == LF:
            return buf.decode("ascii", errors="replace").strip()
        buf.extend(ch)


def discard_callsign():
    """Consume the callsign that LinBPQ auto-sends on connect."""
    while True:
        try:
            ch = os.read(0, 1)
        except OSError:
            return
        if not ch:
            return
        if ch == CR or ch == LF:
            break
    try:
        r, _, _ = select.select([0], [], [], 0.1)
        if r:
            os.read(0, 1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CALLSIGN = config.NODE_CALLSIGN
TLE_PATH = config.TLE_FILE
DEFAULT_GRID = config.DEFAULT_GRID
DEFAULT_LAT = config.DEFAULT_LAT
DEFAULT_LON = config.DEFAULT_LON
MIN_ELEVATION = 10.0
WINDOW_HOURS = 12
TLE_MAX_AGE_DAYS = 3

# Satellite list: (TLE name pattern, display name, mode)
# TLE name matching uses 'startswith' or substring — CelesTrak names vary.
SATELLITES = [
    ("ISS (ZARYA)",          "ISS",     "FM"),
    ("SO-50",                "SO-50",   "FM"),
    ("AO-91",                "AO-91",   "FM*"),
    ("PO-101",               "PO-101",  "FM"),
    ("TEVEL-2",              "TEVEL-2", "FM"),
    ("RS-44",                "RS-44",   "LIN"),
    ("AO-73",                "AO-73",   "LIN"),
    ("JO-97",                "JO-97",   "LIN"),
    ("CAS-4A",               "CAS-4A",  "LIN"),
    ("CAS-4B",               "CAS-4B",  "LIN"),
    ("AO-7",                 "AO-7",    "LIN"),
    ("IO-117",               "IO-117",  "DIG"),
]


# ---------------------------------------------------------------------------
# Compass bearing helper
# ---------------------------------------------------------------------------

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def az_to_compass(az_deg):
    """Convert azimuth in degrees to 8-point compass string."""
    idx = int((az_deg + 22.5) / 45.0) % 8
    return COMPASS[idx]


# ---------------------------------------------------------------------------
# Grid locator validation and conversion
# ---------------------------------------------------------------------------

def validate_grid(grid):
    """Return True if grid is a plausible 4- or 6-char Maidenhead locator."""
    g = grid.upper()
    if len(g) not in (4, 6):
        return False
    if not (g[0].isalpha() and g[1].isalpha()):
        return False
    if not (g[2].isdigit() and g[3].isdigit()):
        return False
    if len(g) == 6:
        if not (g[4].isalpha() and g[5].isalpha()):
            return False
    return True


def grid_to_latlon(grid):
    """
    Convert Maidenhead grid locator to (lat, lon) using the maidenhead library.
    Returns (lat, lon) as floats, or raises ValueError.
    """
    try:
        import maidenhead
        lat, lon = maidenhead.to_location(grid, center=True)
        return float(lat), float(lon)
    except Exception as exc:
        raise ValueError("Cannot convert grid '{}': {}".format(grid, exc))


# ---------------------------------------------------------------------------
# TLE loading
# ---------------------------------------------------------------------------

def check_tle_age():
    """
    Return age of TLE file in days, or None if file does not exist.
    """
    try:
        mtime = os.path.getmtime(TLE_PATH)
    except OSError:
        return None
    age_days = (datetime.now(timezone.utc).timestamp() - mtime) / 86400.0
    return age_days


def load_tles():
    """
    Parse TLE file into a dict keyed by uppercased satellite name line.
    Returns {name: (line1, line2), ...}
    """
    tles = {}
    try:
        with open(TLE_PATH, "r") as fh:
            lines = [ln.rstrip("\r\n") for ln in fh if ln.strip()]
    except OSError as exc:
        return None, str(exc)

    i = 0
    while i + 2 < len(lines):
        name = lines[i].strip()
        l1 = lines[i + 1].strip()
        l2 = lines[i + 2].strip()
        if l1.startswith("1 ") and l2.startswith("2 "):
            tles[name.upper()] = (l1, l2)
            i += 3
        else:
            i += 1
    return tles, None


def find_tle(tles, pattern):
    """
    Find a TLE entry whose name starts with or contains 'pattern' (case-
    insensitive). Returns (name, line1, line2) or None.
    """
    pat = pattern.upper()
    for name, (l1, l2) in tles.items():
        if name.startswith(pat):
            return name, l1, l2
    for name, (l1, l2) in tles.items():
        if pat in name:
            return name, l1, l2
    return None


# ---------------------------------------------------------------------------
# Pass prediction
# ---------------------------------------------------------------------------

def predict_passes(tles, lat, lon, now_utc):
    """
    Predict passes for all configured satellites over the next WINDOW_HOURS
    hours. Returns a list of pass dicts sorted by AOS time.
    """
    from skyfield.api import load, EarthSatellite
    from skyfield.api import wgs84

    ts = load.timescale()
    station = wgs84.latlon(lat, lon)

    t0 = ts.from_datetime(now_utc)
    t1 = ts.from_datetime(now_utc + timedelta(hours=WINDOW_HOURS))

    passes = []

    for tle_pattern, display_name, mode in SATELLITES:
        result = find_tle(tles, tle_pattern)
        if result is None:
            continue
        tle_name, line1, line2 = result

        try:
            sat = EarthSatellite(line1, line2, tle_name, ts)
        except Exception:
            continue

        try:
            times, events = sat.find_events(
                station, t0, t1, altitude_degrees=MIN_ELEVATION
            )
        except Exception:
            continue

        pending = {}

        for t, ev in zip(times, events):
            ev = int(ev)
            if ev == 0:
                pending = {"aos_t": t}
            elif ev == 1:
                if "aos_t" not in pending:
                    pending["aos_t"] = t
                pending["peak_t"] = t
                diff = sat - station
                topo = diff.at(t)
                alt, az, _ = topo.altaz()
                pending["max_el"] = int(round(alt.degrees))
                pending["peak_az"] = az.degrees
            elif ev == 2:
                pending["los_t"] = t
                if "peak_t" not in pending:
                    pending["peak_t"] = t
                if "max_el" not in pending:
                    pending["max_el"] = int(MIN_ELEVATION)

                aos_t = pending.get("aos_t", t)
                diff = sat - station
                topo_aos = diff.at(aos_t)
                topo_los = diff.at(t)
                _, az_aos, _ = topo_aos.altaz()
                _, az_los, _ = topo_los.altaz()

                aos_dt = aos_t.utc_datetime()
                los_dt = t.utc_datetime()
                dur_min = int(round((los_dt - aos_dt).total_seconds() / 60.0))

                passes.append({
                    "name": display_name,
                    "mode": mode,
                    "aos_dt": aos_dt,
                    "los_dt": los_dt,
                    "max_el": pending["max_el"],
                    "az_rise": az_to_compass(az_aos.degrees),
                    "az_set": az_to_compass(az_los.degrees),
                    "dur_min": dur_min,
                })
                pending = {}

    passes.sort(key=lambda p: p["aos_dt"])
    return passes


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_passes(passes, grid, lat, lon, now_utc):
    """Format the pass table as a list of strings (each under 80 chars)."""
    lines = []
    lines.append("=== {} Satellite Passes ===".format(CALLSIGN))

    lat_str = "{:.1f}{}".format(abs(lat), "N" if lat >= 0 else "S")
    lon_str = "{:.1f}{}".format(abs(lon), "E" if lon >= 0 else "W")
    date_str = now_utc.strftime("%d/%m/%Y %H:%M UTC")
    lines.append(
        "Location: {} ({} {}) | {}".format(
            grid.upper(), lat_str, lon_str, date_str
        )
    )
    lines.append(
        "Next {}h | Min elev: {} deg".format(WINDOW_HOURS, int(MIN_ELEVATION))
    )
    lines.append("")

    if not passes:
        lines.append(
            "No passes above {} deg in next {} hours.".format(
                int(MIN_ELEVATION), WINDOW_HOURS
            )
        )
        return lines

    lines.append(
        "{:<9}  {:<5}  {:>4}  {:<5}  {:<4}  {:<4}  {:>3}  {}".format(
            "Satellite", "AOS", "Max", "LOS", "Rise", "Set", "Dur", "Mode"
        )
    )
    lines.append(
        "{:<9}  {:<5}  {:>4}  {:<5}  {:<4}  {:<4}  {:>3}  {}".format(
            "---------", "-----", "----", "-----",
            "----", "----", "---", "----"
        )
    )

    for p in passes:
        aos_s = p["aos_dt"].strftime("%H:%M")
        los_s = p["los_dt"].strftime("%H:%M")
        dur_s = "{}m".format(p["dur_min"])
        lines.append(
            "{:<9}  {:<5}  {:>3}   {:<5}  {:<4}  {:<4}  {:>3}  {}".format(
                p["name"],
                aos_s,
                p["max_el"],
                los_s,
                p["az_rise"],
                p["az_set"],
                dur_s,
                p["mode"],
            )
        )

    lines.append("")

    fm_star = any(p["mode"] == "FM*" for p in passes)
    if fm_star:
        lines.append("* = sunlit passes only (AO-91 requires sunlight)")
    lines.append("FM = FM repeater | LIN = linear transponder | DIG = digital")
    lines.append("")
    lines.append("{} pass{} found.".format(
        len(passes), "es" if len(passes) != 1 else ""
    ))
    return lines


# ---------------------------------------------------------------------------
# Main service loop
# ---------------------------------------------------------------------------

def run():
    discard_callsign()

    # Check TLE file
    age = check_tle_age()
    if age is None:
        writeln("ERROR: TLE data file not found: {}".format(TLE_PATH))
        writeln("Run update-tle.sh to download satellite data.")
        return

    tles, err = load_tles()
    if tles is None:
        writeln("ERROR: Cannot read TLE file: {}".format(err))
        return

    if age > TLE_MAX_AGE_DAYS:
        writeln(
            "WARNING: TLE data is {:.0f} days old - predictions may be "
            "less accurate.".format(age)
        )
        writeln("")

    # First pass: default location
    now_utc = datetime.now(timezone.utc)
    try:
        lat, lon = grid_to_latlon(DEFAULT_GRID)
    except ValueError:
        lat, lon = DEFAULT_LAT, DEFAULT_LON

    writeln("Calculating passes, please wait...")
    passes = predict_passes(tles, lat, lon, now_utc)
    write_block(format_passes(passes, DEFAULT_GRID, lat, lon, now_utc))

    # Interactive loop
    while True:
        writeln("")
        writeln("Enter grid locator (e.g. JO01), or blank to quit:")
        write("> ")

        raw = read_line()
        if raw is None:
            return
        grid = raw.strip()

        if grid == "":
            writeln("73 de {}".format(CALLSIGN))
            return

        if not validate_grid(grid):
            writeln(
                "Invalid grid locator '{}'. "
                "Use 4 or 6 characters, e.g. IO91wm or JO01.".format(grid)
            )
            continue

        try:
            lat, lon = grid_to_latlon(grid)
        except ValueError as exc:
            writeln("Error: {}".format(exc))
            continue

        writeln("")
        writeln("Calculating passes, please wait...")
        now_utc = datetime.now(timezone.utc)
        passes = predict_passes(tles, lat, lon, now_utc)
        write_block(format_passes(passes, grid, lat, lon, now_utc))


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass
    except Exception as exc:
        try:
            writeln("ERROR: {}".format(exc))
        except Exception:
            pass
        sys.exit(1)
