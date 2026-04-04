#!/bin/bash
# Satellite pass predictor wrapper — systemd socket activation.
# The -u flag (unbuffered stdout) is CRITICAL for socket I/O.
# Edit INSTALL_DIR to match your installation path.

INSTALL_DIR="/opt/linbpq/services/satpass"
/usr/bin/python3 -u "$INSTALL_DIR/satpass.py"
