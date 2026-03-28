# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Raspberry Pi Zero daemon that watches the 2026 Chicago Cubs schedule, polls the MLB Stats API after each game ends, and displays a W flag image on a 64×32 P6 HUB75 RGB LED matrix if the Cubs won.

## Setup (on the Pi)

```bash
sudo bash install.sh          # builds rpi-rgb-led-matrix, creates venv, seeds DB, installs systemd service
```

Manual steps if needed:

```bash
python3 setup_schedule.py     # (re-)fetch Cubs schedule → schedule.db
python3 prepare_image.py      # resize w_flag_source.png → w_flag_64x32.png
sudo venv/bin/python3 main.py # run the daemon (root required for GPIO)
```

Service management:

```bash
sudo systemctl status w-flag
sudo journalctl -u w-flag -f
```

## Architecture

```
main.py            — scheduler loop (runs as root)
  ├── check_game.py  — MLB Stats API queries + schedule.db reads/writes
  └── display.py     — rpi-rgb-led-matrix wrapper (stubs gracefully off-Pi)

setup_schedule.py  — one-shot: populate schedule.db from MLB API
prepare_image.py   — one-shot: produce w_flag_64x32.png from w_flag_source.png
```

**Data flow:**
1. `setup_schedule.py` writes the full season into `schedule.db` (SQLite, `games` table).
2. At startup and `00:05` daily, `main.py` queries the DB for today's game and schedules a result check 3.5 h after first pitch.
3. At check time, `check_game.cubs_won(game_pk)` hits `statsapi.mlb.com/api/v1.1/game/{pk}/feed/live`. Returns `True/False/None`; `None` triggers a 5-minute retry loop until 23:00.
4. Win → `display.show_w_flag()` renders `w_flag_64x32.png` via the matrix canvas. Loss → `display.clear()`.

## Key constants (all in their respective files)

| Constant | File | Default |
|---|---|---|
| `GAME_BUFFER_HOURS` | `main.py` | `3.5` — hours after start before first API check |
| `RETRY_INTERVAL_MIN` | `main.py` | `5` — minutes between in-progress retries |
| `MAX_RETRY_UNTIL_HOUR` | `main.py` | `23` — give up after 11 PM |
| `options.gpio_slowdown` | `display.py` | `1` — increase to `2` if Pi Zero flickers |
| `options.brightness` | `display.py` | `80` — 0–100 |

## Hardware notes

- `rpi-rgb-led-matrix` must be **built from source** (`/opt/rpi-rgb-led-matrix`); `install.sh` handles this. There is no pip package.
- The daemon must run as **root** for GPIO/DMA access.
- `display.py` detects the absence of `rgbmatrix` and falls back to log-only stubs, so all code except `display.py` can be tested on a non-Pi machine.

## MLB Stats API

Free, no API key. Cubs team ID = `112`. The `abstractGameState` field cycles through `Preview → Live → Final`; only `Final` is acted on.
