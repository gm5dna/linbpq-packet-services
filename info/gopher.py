"""
gopher.py -- Gopher browser sub-service for the packet node INFO menu.

A simple Gopher client using raw TCP sockets (stdlib).
Supports directory menus, text files, search, and basic navigation.
Default start: gopher.floodgap.com (the most reliable Gopher server).
"""

import socket
import textwrap

DEFAULT_HOST = "gopher.floodgap.com"
DEFAULT_PORT = 70

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 15
MAX_RESPONSE = 65536  # 64 KB cap
MAX_HISTORY = 20
MAX_MENU_ITEMS = 50
PAGE_SIZE = 20
LINE_WIDTH = 78

# Gopher item type labels for display.
TYPE_LABELS = {
    "0": "TXT",
    "1": "DIR",
    "7": "SRCH",
    "3": "ERR",
    "h": "HTML",
    "9": "BIN",
    "g": "GIF",
    "I": "IMG",
    "s": "SND",
    "d": "DOC",
}


# ---------------------------------------------------------------------------
# Gopher protocol
# ---------------------------------------------------------------------------

def _gopher_fetch(host, port, selector):
    """Fetch a Gopher resource. Returns raw bytes or None on error."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect((host, port))
        sock.sendall((selector + "\r\n").encode("ascii", errors="replace"))
        sock.settimeout(READ_TIMEOUT)

        data = bytearray()
        while len(data) < MAX_RESPONSE:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data.extend(chunk)

        sock.close()
        return bytes(data)
    except (socket.error, OSError):
        return None


def _parse_menu(data):
    """
    Parse a Gopher menu response into a list of item dicts.
    Each dict: type, display, selector, host, port.
    """
    text = data.decode("latin-1", errors="replace")
    items = []

    for line in text.splitlines():
        if line == ".":
            break
        if not line:
            continue

        item_type = line[0]
        rest = line[1:]
        parts = rest.split("\t")

        display = parts[0] if len(parts) > 0 else ""
        selector = parts[1] if len(parts) > 1 else ""
        host = parts[2] if len(parts) > 2 else ""
        try:
            port = int(parts[3]) if len(parts) > 3 else 70
        except ValueError:
            port = 70

        items.append({
            "type": item_type,
            "display": display,
            "selector": selector,
            "host": host,
            "port": port,
        })

    return items


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_menu(items, writeln):
    """
    Render a Gopher menu. Returns a dict mapping displayed number to item.
    Info lines (type 'i') are shown as plain text without a number.
    """
    nav_map = {}
    nav_num = 0
    shown = 0

    for item in items:
        if shown >= MAX_MENU_ITEMS and item["type"] != "i":
            writeln("  (Showing first {} navigable items)".format(MAX_MENU_ITEMS))
            break

        if item["type"] == "i":
            writeln("    {}".format(item["display"]))
        elif item["type"] == "3":
            writeln("    [ERR] {}".format(item["display"]))
        else:
            nav_num += 1
            shown += 1
            label = TYPE_LABELS.get(item["type"], "???")
            display = item["display"]
            prefix = "{:>3}  [{}] ".format(nav_num, label)
            max_disp = LINE_WIDTH - len(prefix)
            if len(display) > max_disp:
                display = display[:max_disp - 3] + "..."
            writeln("{}{}".format(prefix, display))
            nav_map[nav_num] = item

    return nav_map


def _display_text(data, writeln, read_line, write):
    """Display a Gopher text file with pagination."""
    text = data.decode("latin-1", errors="replace")
    if text.endswith("\r\n.\r\n"):
        text = text[:-5]
    elif text.endswith("\n.\n"):
        text = text[:-3]

    lines = []
    for line in text.splitlines():
        line = line.rstrip()
        if len(line) <= LINE_WIDTH:
            lines.append(line)
        else:
            lines.extend(textwrap.wrap(line, width=LINE_WIDTH))

    for i, line in enumerate(lines):
        writeln(line)
        if (i + 1) % PAGE_SIZE == 0 and i + 1 < len(lines):
            write("-- more (ENTER=next, Q=stop) -- ")
            resp = read_line()
            if resp is None:
                return
            if resp.strip().upper() == "Q":
                return


def _parse_address(addr):
    """
    Parse a user-entered Gopher address.
    Accepts: host, host:port, host:port/selector, host/selector
    Returns (host, port, selector).
    """
    addr = addr.strip()
    if addr.lower().startswith("gopher://"):
        addr = addr[9:]

    selector = ""
    port = 70

    if "/" in addr:
        host_part, selector = addr.split("/", 1)
        if len(selector) >= 2 and selector[0] in "01234579ghIs" and selector[1] == "/":
            selector = selector[2:]
        elif len(selector) >= 1 and selector[0] in "01234579ghIs":
            selector = selector[1:]
    else:
        host_part = addr

    if ":" in host_part:
        h, p = host_part.rsplit(":", 1)
        try:
            port = int(p)
            host_part = h
        except ValueError:
            pass

    return host_part, port, selector


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(writeln, read_line, write):
    """Entry point called from the main INFO menu."""
    writeln()
    writeln("=== Gopher Browser ===")
    writeln()
    writeln("Commands: number=navigate, U=back, A=address, blank=quit")

    host = DEFAULT_HOST
    port = DEFAULT_PORT
    selector = ""
    history = []

    while True:
        writeln()
        writeln("Connecting to {}...".format(host))

        data = _gopher_fetch(host, port, selector)

        if data is None:
            writeln("Cannot connect to {}:{}. Server may be offline.".format(
                host, port))
            if history:
                writeln("Press U to go back, or blank to quit.")
            else:
                writeln("Press A to try another address, or blank to quit.")
                writeln()
                write("> ")
                resp = read_line()
                if resp is None:
                    return
                resp = resp.strip().upper()
                if resp == "A":
                    write("Address: ")
                    addr = read_line()
                    if addr is None:
                        return
                    addr = addr.strip()
                    if addr:
                        host, port, selector = _parse_address(addr)
                    continue
                return
        elif not data:
            writeln("Server returned no data.")
        else:
            text_check = data[:512].decode("latin-1", errors="replace")
            is_menu = "\t" in text_check

            if is_menu:
                items = _parse_menu(data)
                writeln()
                nav_map = _display_menu(items, writeln)
            else:
                writeln()
                _display_text(data, writeln, read_line, write)
                writeln()
                writeln("(End of document)")
                if history:
                    host, port, selector = history.pop()
                    continue
                else:
                    return

        while True:
            writeln()
            write("> ")
            cmd = read_line()

            if cmd is None:
                return
            cmd = cmd.strip()

            if cmd == "":
                return

            if cmd.upper() == "U":
                if history:
                    host, port, selector = history.pop()
                    break
                else:
                    writeln("Already at the top level. Blank to quit.")
                    continue

            if cmd.upper() == "A":
                write("Address: ")
                addr = read_line()
                if addr is None:
                    return
                addr = addr.strip()
                if addr:
                    history.append((host, port, selector))
                    if len(history) > MAX_HISTORY:
                        history.pop(0)
                    host, port, selector = _parse_address(addr)
                    break
                continue

            try:
                num = int(cmd)
            except ValueError:
                writeln("Enter a number, U, A, or blank.")
                continue

            if not is_menu or num not in nav_map:
                writeln("Invalid choice.")
                continue

            item = nav_map[num]

            if item["type"] in ("0", "1", "7"):
                history.append((host, port, selector))
                if len(history) > MAX_HISTORY:
                    history.pop(0)

                if item["type"] == "7":
                    write("Search: ")
                    query = read_line()
                    if query is None:
                        return
                    query = query.strip()
                    if not query:
                        history.pop()
                        continue
                    selector = "{}\t{}".format(item["selector"], query)
                else:
                    selector = item["selector"]

                host = item["host"]
                port = item["port"]
                break
            else:
                writeln("Unsupported item type [{}].".format(
                    TYPE_LABELS.get(item["type"], item["type"])))
                continue
