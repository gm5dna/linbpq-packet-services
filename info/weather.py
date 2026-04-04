"""
weather.py -- Weather sub-service for the packet node INFO menu.

Fetches compact weather data from wttr.in via curl.
Default location is read from config. User may query other locations.
Blank input returns to the main menu.
"""

import os
import sys
import subprocess

_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import config

DEFAULT_LOCATION = config.LOCATION_NAME


def fetch_weather(location):
    """
    Fetch compact weather from wttr.in for the given location.
    Returns the weather text on success, or None on error.
    """
    loc = location.strip().replace(" ", "+")
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "10",
             "wttr.in/{}?0ATn".format(loc)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = r.stdout.strip()
        if not out or "Unknown location" in out or "ERROR" in out:
            return None
        return out
    except Exception:
        return None


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
    writeln("=== Weather Service ===")
    writeln("Fetching {} weather, please wait...".format(DEFAULT_LOCATION))
    writeln()

    data = fetch_weather(DEFAULT_LOCATION)
    if data:
        for line in data.splitlines():
            writeln(line)
    else:
        writeln("Sorry, could not retrieve weather data.")

    writeln()
    writeln("Enter a place name for a different location,")
    writeln("or press ENTER to return to the menu.")

    while True:
        write("> ")
        line = read_line()

        if line is None:
            return

        if line == "":
            return

        writeln()
        writeln("Fetching weather for {}...".format(line))
        writeln()
        data = fetch_weather(line)
        if data:
            for row in data.splitlines():
                writeln(row)
        else:
            writeln("Sorry, no weather data found for '{}'.".format(line))

        writeln()
        writeln("Enter another location, or press ENTER to return.")
