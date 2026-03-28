# W Flag

A Raspberry Pi Zero app that monitors the Chicago Cubs schedule and displays the W flag on a 64×32 RGB LED matrix panel when the Cubs win.

![W Flag](w_flag_source.png)

---

## Hardware

| Component | Details |
|---|---|
| Single-board computer | Raspberry Pi Zero (any revision) |
| Display | 64×32 P6 RGB LED matrix panel |
| Interface | HUB75 |
| Scan rate | 1/16 |

Standard HUB75 wiring to the Pi GPIO header. If the display flickers, set `gpio_slowdown = 2` in `display.py`.

## How it works

1. A local SQLite database holds the full Cubs regular-season schedule (fetched once from the free MLB Stats API — no key required).
2. At startup the daemon checks whether the Cubs play today. If so, it schedules a result check **3.5 hours after first pitch** — enough time to cover a typical game without hammering the API all day.
3. Once the check fires, it polls the MLB live feed every 5 minutes until the game is marked `Final`.
4. **Cubs win** → W flag image is rendered on the LED matrix. **Cubs lose** → display stays dark.
5. The display clears at midnight and the cycle repeats.

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/egelnoteagle/w-flag.git
cd w-flag
```

### 2. Run the installer (as root)

```bash
sudo bash install.sh
```

This will:
- Install system dependencies
- Build and install the [`rpi-rgb-led-matrix`](https://github.com/hzeller/rpi-rgb-led-matrix) C library from source
- Create a Python virtual environment and install pip dependencies
- Resize the W flag image to 64×32 px
- Fetch the 2026 Cubs schedule into `schedule.db`
- Install and start the `w-flag` systemd service (auto-starts on boot)

### 3. Verify it's running

```bash
sudo systemctl status w-flag
sudo journalctl -u w-flag -f
```

## Manual operation

```bash
# Re-fetch the schedule (e.g. after a rainout reschedule)
python3 -m wflag.setup_schedule

# Re-process the flag image after swapping assets/w_flag_source.png
python3 -m wflag.prepare_image

# Run the daemon directly
sudo python3 -m wflag.main
```

## Configuration

All tuneable values are near the top of their respective files:

| Setting | File | Default | Notes |
|---|---|---|---|
| `GAME_BUFFER_HOURS` | `main.py` | `3.5` | Hours after first pitch before checking result |
| `RETRY_INTERVAL_MIN` | `main.py` | `5` | Minutes between retries while game is in progress |
| `MAX_RETRY_UNTIL_HOUR` | `main.py` | `23` | Stop retrying after this hour (11 PM) |
| `options.brightness` | `display.py` | `80` | LED brightness, 0–100 |
| `options.gpio_slowdown` | `display.py` | `1` | Increase to `2` if display flickers |

## Dependencies

- Python 3.11+
- [`rpi-rgb-led-matrix`](https://github.com/hzeller/rpi-rgb-led-matrix) — built from source by `install.sh`
- `requests`, `schedule`, `Pillow` — installed via pip

## MLB Stats API

This project uses the free, unauthenticated MLB Stats API (`statsapi.mlb.com`). No account or API key is needed. Cubs team ID = `112`.
