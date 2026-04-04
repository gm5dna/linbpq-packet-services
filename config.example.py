# config.py — Site-specific settings for your packet information services.
#
# Copy this file to config.py and edit it for your station:
#   cp config.example.py config.py
#
# config.py is gitignored so your local settings won't be overwritten
# by updates, and credentials won't accidentally be committed.

# ---------------------------------------------------------------------------
# Station identity
# ---------------------------------------------------------------------------

# Your node callsign — used in banners, titles, and User-Agent strings.
NODE_CALLSIGN = "MYCALL"

# Sysop callsign — shown in the info services banner.
SYSOP_CALLSIGN = "MYCALL"

# Station location — used as the default weather location and in banners.
LOCATION_NAME = "My Town"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Base installation directory.
INSTALL_DIR = "/opt/linbpq/services"

# Info services directory (where info.py and sub-modules live).
INFO_DIR = "/opt/linbpq/services/info"

# Satellite pass predictor directory.
SATPASS_DIR = "/opt/linbpq/services/satpass"

# Cache directory for propagation and news data.
CACHE_DIR = "/opt/linbpq/services/info/cache"

# ---------------------------------------------------------------------------
# QRZ callsign lookup (optional)
# ---------------------------------------------------------------------------

# Path to the QRZ credentials file.  If this file does not exist or
# lacks credentials, the callsign lookup service will show an error
# but everything else will work fine.
#
# Create qrz.conf from qrz.conf.example and fill in your QRZ.com
# XML API credentials (requires a paid QRZ subscription).
QRZ_CONF_FILE = "/opt/linbpq/services/qrz.conf"

# ---------------------------------------------------------------------------
# Satellite pass predictor
# ---------------------------------------------------------------------------

# Your Maidenhead grid locator — used as the default location for
# satellite pass predictions.  Users can enter a different locator
# at the interactive prompt.
DEFAULT_GRID = "IO91wm"

# Fallback latitude/longitude if the maidenhead library is unavailable.
DEFAULT_LAT = 51.50
DEFAULT_LON = -0.12

# Path to the TLE data file (downloaded by update-tle.sh).
TLE_FILE = "/opt/linbpq/services/satpass/amateur.tle"
