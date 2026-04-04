# Packet Radio Information Services & Satellite Passes for LinBPQ

Two socket-activated services for LinBPQ packet radio nodes:

1. **Information Services** — weather, HF propagation, callsign lookup (QRZ),
   RSS news, Wikipedia, Gopher browser, fortune quotes, and ELIZA chatbot
2. **Satellite Pass Predictor** — amateur radio satellite pass predictions
   for any Maidenhead grid locator

Originally developed for GB7DNA by GM5DNA.

## What users see

### Information Services (SVC)

```
============================================================
   MYCALL Information Services      MYCALL - My Town
============================================================

Welcome to MYCALL Information Services.
Type a number to select a service, or Q to quit.

=== MYCALL Information Services ===

 1  Weather        - conditions & forecasts
 2  Propagation    - HF band conditions & solar data
 3  Callsign       - look up a callsign
 4  News           - RSS news reader
 5  Wikipedia      - search & browse articles
 6  Gopher         - browse gopherspace
 7  Fortune        - random quote
 8  ELIZA          - talk to a chatbot
 Q  Quit

Choice:
```

### Satellite Passes (SAT)

```
=== MYCALL Satellite Passes ===
Location: IO91WM (51.5N 0.1W) | 04/04/2026 14:30 UTC
Next 12h | Min elev: 10 deg

Satellite  AOS    Max  LOS    Rise  Set   Dur  Mode
---------  -----  ----  -----  ----  ----  ---  ----
ISS        15:23   54   15:32  SW    NE    9m   FM
SO-50      16:45   28   16:52  S     E     7m   FM
RS-44      18:10   19   18:22  W     N    12m   LIN

3 passes found.
```

## Architecture

Both services use the same pattern: systemd socket activation with no
background daemons. Zero resource usage when idle.

```
Packet user  ──►  LinBPQ
                    │
              APPLICATION ATTACH
                    │
                    ▼
            TCP 127.0.0.1:<port>
                    │
              *.socket
            (systemd, Accept=yes)
                    │
              *@.service
            (per-connection)
                    │
          info.py or satpass.py
```

## Prerequisites

- **Linux** with **systemd** (tested on Raspberry Pi OS / Debian)
- **LinBPQ** with ATTACH support
- **Python 3.6+**
- **curl** (for weather service and TLE downloads)

### Python packages

```bash
# Required for most info services (propagation, callsign, news, wikipedia)
pip3 install requests

# Required for satellite pass predictions
pip3 install skyfield maidenhead
```

## Quick start

### 1. Clone the repository

```bash
sudo mkdir -p /opt/linbpq/services
sudo chown linbpq:linbpq /opt/linbpq/services
git clone https://github.com/gm5dna/linbpq-packet-services.git /opt/linbpq/services
```

### 2. Configure

```bash
cd /opt/linbpq/services
cp config.example.py config.py
```

Edit `config.py` and set:

- `NODE_CALLSIGN` — your node callsign (e.g. `"GB7ABC"`)
- `SYSOP_CALLSIGN` — your personal callsign
- `LOCATION_NAME` — your town/city (used for weather and banners)
- `DEFAULT_GRID` — your Maidenhead grid locator (for satellite passes)
- `DEFAULT_LAT` / `DEFAULT_LON` — fallback coordinates
- Paths — adjust if not using `/opt/linbpq/services`

### 3. Set up QRZ callsign lookup (optional)

If you have a QRZ.com XML API subscription:

```bash
cp qrz.conf.example qrz.conf
chmod 640 qrz.conf
chown linbpq:linbpq qrz.conf
```

Edit `qrz.conf` with your QRZ credentials. If you skip this step, the
callsign lookup service will show an error but everything else works fine.

### 4. Download TLE data (for satellite passes)

```bash
chmod +x satpass/update-tle.sh
./satpass/update-tle.sh
```

Add a daily cron job to keep TLE data fresh:

```bash
# As the linbpq user:
crontab -e
# Add:
15 3 * * * /opt/linbpq/services/satpass/update-tle.sh >> /var/log/satpass-tle.log 2>&1
```

### 5. Install systemd units

```bash
sudo cp systemd/info.socket systemd/info@.service /etc/systemd/system/
sudo cp systemd/satpass.socket systemd/satpass@.service /etc/systemd/system/
```

Edit the paths in all four files if not using `/opt/linbpq/services`.

```bash
chmod +x info/info-wrapper.sh satpass/satpass-wrapper.sh
sudo systemctl daemon-reload
sudo systemctl enable --now info.socket satpass.socket
```

### 6. Test locally

```bash
nc 127.0.0.1 6499    # Info services
nc 127.0.0.1 6497    # Satellite passes
```

### 7. Add APPLICATION lines to LinBPQ

Add to `bpq32.cfg`:

```
APPLICATION 6,SVC,ATTACH 2 127.0.0.1 6499,MYCALL-12,ALIAS,0
APPLICATION 7,SAT,ATTACH 2 127.0.0.1 6497,MYCALL-14,ALIAS,0
```

Adjust the application numbers, SSIDs, and aliases to suit your node.
Restart LinBPQ to activate.

## Services

### Weather

Fetches compact weather from [wttr.in](https://wttr.in). Shows your
default location on entry, then lets the user query any location.

### HF Propagation

Solar flux, sunspot count, A/K indices, band conditions (day/night),
VHF E-skip and aurora data from [hamqsl.com](https://www.hamqsl.com/).
Cached for 30 minutes.

### Callsign Lookup

QRZ.com XML API lookup. Requires a paid QRZ subscription and credentials
in `qrz.conf`. Shows name, location, grid, country, QSL info.

### RSS News

Four feeds: RSGB, BBC News, ARRL, DX-World. Per-feed caching (15 min).
Select a headline number for the article summary.

### Wikipedia

Search and browse Wikipedia articles. Paginated display for packet
terminals. Extracts truncated at 4000 characters.

### Gopher

Browse gopherspace via a simple Gopher client. Supports directories,
text files, search items, and history navigation. Default start:
gopher.floodgap.com.

### Fortune

Random quote from `/usr/games/fortune` if installed, otherwise from a
built-in list of ham radio and computing quotes.

### ELIZA

Classic Rogerian psychotherapist chatbot (Weizenbaum, 1966). Pattern
matching with reflection. Type BYE to return to the menu.

### Satellite Passes

Predicts passes for 12 amateur radio satellites over the next 12 hours.
Uses [Skyfield](https://rhodesmill.org/skyfield/) for orbital mechanics
and TLE data from [CelesTrak](https://celestrak.org/). Users can enter
any Maidenhead grid locator for predictions from a different location.

## Adding a custom info service

1. Create a new Python file in `info/` with a `run(writeln, read_line, write)`
   function.

2. Import and add it to the `MENU` list in `info/info.py`:
   ```python
   import myservice
   # ...
   ("9", "MyService", "description here", myservice.run),
   ```

**Important:** Use only the `writeln`/`write`/`read_line` callables passed
to `run()`. Never use `print()` or `input()`.

## Troubleshooting

**"ModuleNotFoundError: No module named 'config'":**
Copy `config.example.py` to `config.py`. Check that wrapper scripts point
to the correct `INSTALL_DIR`.

**"ModuleNotFoundError: No module named 'requests'":**
Install it: `pip3 install requests`

**"ModuleNotFoundError: No module named 'skyfield'":**
Install satellite dependencies: `pip3 install skyfield maidenhead`

**Satellite service says "TLE data file not found":**
Run `satpass/update-tle.sh` to download TLE data. Check that `TLE_FILE`
in `config.py` points to the correct path.

**QRZ says "No QRZ credentials found":**
Create `qrz.conf` from `qrz.conf.example` and fill in your credentials.
This service is optional — skip it if you don't have a QRZ subscription.

**Nothing appears when connecting:**
Check that wrapper scripts use `-u` (unbuffered). Without it, Python
buffers stdout and the user sees nothing.

**Check logs:**
```bash
journalctl -u info@* -n 20
journalctl -u satpass@* -n 20
```

## Credits

Originally developed for the GB7DNA packet node in Inverness, Scotland
by GM5DNA.

Contributions and improvements are welcome — please open an issue or
pull request.
