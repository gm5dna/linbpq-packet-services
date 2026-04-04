"""
io_helpers.py -- Shared I/O helpers for packet node information services.

All output is plain ASCII. LinBPQ sends CR-only line endings; read_line()
accepts either CR or LF as a line terminator.
"""

import sys
import os
import select

CR = b"\r"
LF = b"\n"


def write(text):
    """Write text via os.write() for atomic output to the socket."""
    try:
        os.write(1, text.encode("ascii", errors="replace"))
    except (BrokenPipeError, OSError):
        sys.exit(0)


def writeln(text=""):
    """Write text followed by a newline."""
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


def read_line():
    """
    Read one line from stdin. CR or LF both act as line terminator.
    Returns the stripped string, or None on EOF / disconnection.
    """
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
    """
    Read and discard the first line that LinBPQ sends on connect
    (the connecting station's callsign), plus any trailing CR/LF.
    """
    while True:
        try:
            ch = os.read(0, 1)
        except OSError:
            return
        if not ch:
            return
        if ch == CR or ch == LF:
            break
    # Consume any immediately-following LF paired with the CR.
    try:
        r, _, _ = select.select([0], [], [], 0.1)
        if r:
            os.read(0, 1)
    except Exception:
        pass
