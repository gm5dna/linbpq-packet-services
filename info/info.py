#!/usr/bin/env python3
"""
info.py -- Packet node information services main menu.

Socket-activated by systemd; invoked via info-wrapper.sh.
LinBPQ sends CR-only line endings; io_helpers.read_line() handles these.

https://github.com/gm5dna/linbpq-packet-services
Originally developed for GB7DNA by GM5DNA.
"""

import sys
import os

# Allow imports from the same directory regardless of cwd.
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# Allow imports from the parent directory (for config.py).
_PARENT = os.path.dirname(_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import config
from io_helpers import write, writeln, write_block, read_line, discard_callsign

# Sub-service modules.
import weather
import fortune
import eliza
import propagation
import callsign
import news
import wikipedia
import gopher


# ---------------------------------------------------------------------------
# Menu definition: (key, label, description, run_function)
# ---------------------------------------------------------------------------
MENU = [
    ("1", "Weather",     "conditions & forecasts",          weather.run),
    ("2", "Propagation", "HF band conditions & solar data", propagation.run),
    ("3", "Callsign",    "look up a callsign",               callsign.run),
    ("4", "News",        "RSS news reader",                  news.run),
    ("5", "Wikipedia",   "search & browse articles",         wikipedia.run),
    ("6", "Gopher",      "browse gopherspace",               gopher.run),
    ("7", "Fortune",     "random quote",                     fortune.run),
    ("8", "ELIZA",       "talk to a chatbot",                eliza.run),
]

BANNER = (
    "============================================================\n"
    "   {node} Information Services      {sysop} - {location}\n"
    "============================================================"
).format(
    node=config.NODE_CALLSIGN,
    sysop=config.SYSOP_CALLSIGN,
    location=config.LOCATION_NAME,
)

MENU_HEADER = "=== {} Information Services ===".format(config.NODE_CALLSIGN)


def show_menu():
    writeln()
    writeln(MENU_HEADER)
    writeln()
    for key, name, desc, _ in MENU:
        writeln(" {}  {:<14} - {}".format(key, name, desc))
    writeln(" Q  Quit")
    writeln()


def main():
    discard_callsign()

    writeln(BANNER)
    writeln()
    writeln("Welcome to {} Information Services.".format(config.NODE_CALLSIGN))
    writeln("Type a number to select a service, or Q to quit.")

    while True:
        show_menu()
        write("Choice: ")
        choice = read_line()

        if choice is None:
            break

        choice = choice.strip().upper()

        if choice == "Q" or choice == "":
            writeln()
            writeln("73 de {}. Goodbye!".format(config.NODE_CALLSIGN))
            writeln()
            break

        matched = None
        for key, name, desc, run_fn in MENU:
            if choice == key:
                matched = run_fn
                break

        if matched is None:
            writeln()
            writeln("Invalid choice. Please enter 1-8 or Q.")
            continue

        try:
            matched(writeln, read_line, write)
        except SystemExit:
            raise
        except Exception as exc:
            writeln()
            writeln("Service error: {}".format(exc))
            writeln()

    sys.exit(0)


if __name__ == "__main__":
    main()
