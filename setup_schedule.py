#!/usr/bin/env python3
"""
Fetch the 2026 Chicago Cubs schedule from the MLB Stats API and store it in a local SQLite database.
Run this once (or re-run to refresh) before starting the main daemon.

Cubs team ID: 112
MLB Stats API (free, no key required): https://statsapi.mlb.com/api/v1/
"""

import sqlite3
import requests
import sys
from datetime import datetime, timezone
import zoneinfo

DB_PATH = "schedule.db"
CUBS_TEAM_ID = 112
SEASON = 2026
MLB_SCHEDULE_URL = (
    f"https://statsapi.mlb.com/api/v1/schedule"
    f"?sportId=1&teamId={CUBS_TEAM_ID}&season={SEASON}"
    f"&gameType=R&fields=dates,date,games,gamePk,gameDate,status,abstractGameState,teams,home,away,team,id,name"
)

# MLB API returns times in UTC; games are played in various local zones but
# Chicago time (America/Chicago) is what we care about for "did they play today?"
CHICAGO_TZ = zoneinfo.ZoneInfo("America/Chicago")


def create_db(conn: sqlite3.Connection) -> None:
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
    print(f"Fetching {SEASON} Cubs schedule from MLB Stats API...")
    resp = requests.get(MLB_SCHEDULE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            game_pk = game["gamePk"]
            # gameDate is ISO-8601 UTC, e.g. "2026-04-09T17:05:00Z"
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
    conn = sqlite3.connect(DB_PATH)
    create_db(conn)
    games = fetch_schedule()
    if not games:
        print("No games returned — check the API URL or try again later.")
        sys.exit(1)
    upsert_games(conn, games)
    print(f"Stored {len(games)} games in {DB_PATH}")

    # Print first 5 games as a sanity check
    cur = conn.execute(
        "SELECT game_date, game_time, away_team, home_team FROM games ORDER BY game_date LIMIT 5"
    )
    print("\nFirst 5 games:")
    for row in cur:
        print(f"  {row[0]} {row[1]}  {row[2]} @ {row[3]}")

    conn.close()


if __name__ == "__main__":
    main()
