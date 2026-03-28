#!/usr/bin/env python3
"""
Query the MLB Stats API for the result of a specific Cubs game.
Returns True if the Cubs won, False if they lost, None if the game is not yet final.
"""

from __future__ import annotations

import logging
import sqlite3
import zoneinfo
from datetime import date, datetime

import requests

log = logging.getLogger(__name__)

CUBS_TEAM_ID = 112
DB_PATH = "schedule.db"
CHICAGO_TZ = zoneinfo.ZoneInfo("America/Chicago")

MLB_LINESCORE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
MLB_FEED_URL = (
    "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    "?fields=gameData,status,abstractGameState,detailedState,teams,home,away,team,id,linescore,teams,runs,wins,losses"
)


def get_todays_game(today: date | None = None) -> dict | None:
    """Return the scheduled Cubs game row for today, or None if no game."""
    if today is None:
        today = datetime.now(CHICAGO_TZ).date()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM games WHERE game_date = ? AND status != 'postponed'",
        (today.isoformat(),),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def cubs_won(game_pk: int) -> bool | None:
    """
    Check the live feed for a game.
    Returns:
        True   — Cubs won (game is Final)
        False  — Cubs lost (game is Final)
        None   — game not yet final (in progress / not started / suspended)
    """
    url = MLB_FEED_URL.format(game_pk=game_pk)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("MLB API request failed: %s", exc)
        return None

    game_data = data.get("gameData", {})
    status = game_data.get("status", {})
    abstract_state = status.get("abstractGameState", "")  # Preview / Live / Final

    if abstract_state != "Final":
        log.info("Game %s state: %s — not final yet", game_pk, abstract_state)
        return None

    # Determine which side (home or away) is the Cubs
    teams = game_data.get("teams", {})
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")

    linescore = data.get("linescore", {})
    home_runs = linescore.get("teams", {}).get("home", {}).get("runs", 0)
    away_runs = linescore.get("teams", {}).get("away", {}).get("runs", 0)

    if home_id == CUBS_TEAM_ID:
        cubs_runs, opp_runs = home_runs, away_runs
    elif away_id == CUBS_TEAM_ID:
        cubs_runs, opp_runs = away_runs, home_runs
    else:
        log.error("Cubs not found in game %s teams!", game_pk)
        return False

    log.info(
        "Game %s final — Cubs %d, Opponent %d", game_pk, cubs_runs, opp_runs
    )
    return cubs_runs > opp_runs


def update_game_status(game_pk: int, status: str) -> None:
    """Persist a game status update to the local DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE games SET status = ? WHERE game_pk = ?", (status, game_pk)
    )
    conn.commit()
    conn.close()
