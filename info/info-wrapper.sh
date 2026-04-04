#!/bin/bash
# Information services wrapper — systemd socket activation.
# The -u flag (unbuffered stdout) is CRITICAL for socket I/O.
# Edit INSTALL_DIR to match your installation path.

INSTALL_DIR="/opt/linbpq/services/info"
/usr/bin/python3 -u "$INSTALL_DIR/info.py"
