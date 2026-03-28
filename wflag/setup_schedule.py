#!/usr/bin/env python3
"""
Fetch the 2026 Chicago Cubs schedule from the MLB Stats API and store it in a local SQLite database.
Run this once (or re-run to refresh) before starting the main daemon.

Cubs team ID: 112
MLB Stats API (free, no key required): https://statsapi.mlb.com/api/v1/
"""

import sqlite3
import sys
import zoneinfo
from datetime import datetime
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent.parent / "schedule.db"
CUBS_TEAM_ID = 112
SEASON = 2026
MLB_SCHEDULE_URL = (
    f"https://statsapi.mlb.com/api/v1/schedule"
    f"?sportId=1&teamId={CUBS_TEAM_ID}&season={SEASON}"
    f"&gameType=R&fields=dates,date,games,gamePk,gameDate,status,abstractGameState,teams,home,away,team,id,name"
)

CHICAGO_TZ = zoneinfo.ZoneInfo("America/Chicago")


def create_db(conn: sqlite3.Connection) -> None:
    """Create the games table if it does not already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_pk     INTEGER PRIMARY KEY,
            game_date   TEXT NOT NULL,          -- YYYY-MM-DD in Chicago local time
            game_time   TEXT NOT NULL,          -- HH:MM in Chicago local time (24h)
            home_team   TEXT NOT NULL,
            away_team   TEXT NOT NULL,
            home_id     INTEGER NOT NULL,
            away_id     INTEGER NOT NULL,
            status      TEXT DEFAULT 'scheduled' -- scheduled | final | in_progress | postponed
        )
    """)
    conn.commit()


def fetch_schedule() -> list[dict]:
    """Fetch the full Cubs regular-season schedule from the MLB Stats API."""
    print(f"Fetching {SEASON} Cubs schedule from MLB Stats API...")
    resp = requests.get(MLB_SCHEDULE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            game_pk = game["gamePk"]
            game_date_utc = datetime.fromisoformat(
                game["gameDate"].replace("Z", "+00:00")
            )
            game_date_chicago = game_date_utc.astimezone(CHICAGO_TZ)

            home = game["teams"]["home"]["team"]
            away = game["teams"]["away"]["team"]

            games.append({
                "game_pk": game_pk,
                "game_date": game_date_chicago.strftime("%Y-%m-%d"),
                "game_time": game_date_chicago.strftime("%H:%M"),
                "home_team": home["name"],
                "away_team": away["name"],
                "home_id": home["id"],
                "away_id": away["id"],
                "status": "scheduled",
            })

    return games


def upsert_games(conn: sqlite3.Connection, games: list[dict]) -> None:
    """Insert or update game rows in the database."""
    conn.executemany(
        """
        INSERT INTO games (game_pk, game_date, game_time, home_team, away_team, home_id, away_id, status)
        VALUES (:game_pk, :game_date, :game_time, :home_team, :away_team, :home_id, :away_id, :status)
        ON CONFLICT(game_pk) DO UPDATE SET
            game_date  = excluded.game_date,
            game_time  = excluded.game_time,
            home_team  = excluded.home_team,
            away_team  = excluded.away_team,
            home_id    = excluded.home_id,
            away_id    = excluded.away_id
        """,
        games,
    )
    conn.commit()


def main() -> None:
    """Fetch the Cubs schedule and store it in the local database."""
    conn = sqlite3.connect(DB_PATH)
    create_db(conn)
    games = fetch_schedule()
    if not games:
        print("No games returned — check the API URL or try again later.")
        sys.exit(1)
    upsert_games(conn, games)
    print(f"Stored {len(games)} games in {DB_PATH}")

    cur = conn.execute(
        "SELECT game_date, game_time, away_team, home_team FROM games ORDER BY game_date LIMIT 5"
    )
    print("\nFirst 5 games:")
    for row in cur:
        print(f"  {row[0]} {row[1]}  {row[2]} @ {row[3]}")

    conn.close()


if __name__ == "__main__":
    main()
