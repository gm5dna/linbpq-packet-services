#!/bin/bash
# Download amateur radio TLEs from CelesTrak.
#
# Add to cron for daily updates, e.g.:
#   15 3 * * * /opt/linbpq/services/satpass/update-tle.sh >> /var/log/satpass-tle.log 2>&1
#
# Edit TLE_DIR to match your installation path.

TLE_DIR="/opt/linbpq/services/satpass"
TLE_FILE="$TLE_DIR/amateur.tle"
TLE_URL="https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"

mkdir -p "$TLE_DIR"

if curl -sf --max-time 30 -o "$TLE_FILE.tmp" "$TLE_URL"; then
    # Sanity check: file should be non-empty and contain TLE lines
    if grep -q "^1 " "$TLE_FILE.tmp"; then
        mv "$TLE_FILE.tmp" "$TLE_FILE"
        echo "$(date -u '+%Y-%m-%d %H:%M UTC') TLE update OK: $TLE_FILE"
    else
        echo "$(date -u '+%Y-%m-%d %H:%M UTC') TLE update FAILED: " \
             "downloaded file does not look like TLE data"
        rm -f "$TLE_FILE.tmp"
        exit 1
    fi
else
    echo "$(date -u '+%Y-%m-%d %H:%M UTC') TLE update FAILED: curl error"
    rm -f "$TLE_FILE.tmp"
    exit 1
fi
