#!/usr/bin/env python3
"""
W Flag Daemon — main entry point.

Logic:
  1. At startup (and every day at 00:05 Chicago time) check the local schedule DB
     for today's Cubs game.
  2. If there is a game, schedule a check ~2h 38m after the listed start time
     (covers average MLB game length with buffer).
  3. At check time, call the MLB API. If the game is not yet Final, retry every
     5 minutes until it is (or until midnight).
  4. If Cubs won → display W flag. If they lost → clear the display.
  5. Clear the display at 23:59 each night to reset for the next day.

Run as root (required by the rpi-rgb-led-matrix library):
    sudo python3 -m wflag.main
"""

import logging
import signal
import sys
import time
import zoneinfo
from datetime import datetime, timedelta

import schedule  # pip install schedule

from wflag import check_game, display

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("w_flag.log"),
    ],
)
log = logging.getLogger(__name__)

CHICAGO_TZ = zoneinfo.ZoneInfo("America/Chicago")
GAME_BUFFER = timedelta(
    hours=2, minutes=38
)  # wait after scheduled start before first result check
RETRY_INTERVAL_MIN = 5  # minutes between retries while game is in progress
MAX_RETRY_UNTIL_HOUR = 23  # stop retrying after 11 PM


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def now_chicago() -> datetime:
    """Return the current datetime in Chicago local time."""
    return datetime.now(CHICAGO_TZ)


def check_and_display(game: dict) -> None:
    """
    Poll the MLB API until we have a final result for *game*, then act on it.
    Called from within the scheduler thread — will block until resolved or timeout.
    """
    game_pk = game["game_pk"]
    log.info(
        "Checking result for game %s: %s @ %s",
        game_pk,
        game["away_team"],
        game["home_team"],
    )

    while True:
        if now_chicago().hour >= MAX_RETRY_UNTIL_HOUR:
            log.warning(
                "Past %d:00 — giving up on game %s", MAX_RETRY_UNTIL_HOUR, game_pk
            )
            check_game.update_game_status(game_pk, "final")
            return

        result = check_game.cubs_won(game_pk)

        if result is True:
            log.info("Cubs WON game %s — displaying W flag!", game_pk)
            display.show_w_flag()
            check_game.update_game_status(game_pk, "final")
            return
        elif result is False:
            log.info("Cubs lost game %s — display stays off.", game_pk)
            display.clear()
            check_game.update_game_status(game_pk, "final")
            return
        else:
            log.info(
                "Game %s not final yet — retrying in %d min",
                game_pk,
                RETRY_INTERVAL_MIN,
            )
            time.sleep(RETRY_INTERVAL_MIN * 60)


def schedule_todays_check() -> None:
    """
    Look up today's game in the DB and, if one exists, schedule a result-check
    2h 38m after the listed start time.
    """
    today = now_chicago().date()
    game = check_game.get_todays_game(today)

    if game is None:
        log.info("%s — no Cubs game today, nothing to schedule.", today)
        return

    start_dt = datetime.strptime(
        f"{game['game_date']} {game['game_time']}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=CHICAGO_TZ)

    check_dt = start_dt + GAME_BUFFER
    now = now_chicago()

    log.info(
        "Game today: %s @ %s, starts %s — will check result at %s",
        game["away_team"],
        game["home_team"],
        start_dt.strftime("%H:%M"),
        check_dt.strftime("%H:%M"),
    )

    if check_dt <= now:
        log.info("Check time already passed — checking result immediately.")
        check_and_display(game)
    else:
        check_time_str = check_dt.strftime("%H:%M")
        log.info("Scheduled result check at %s", check_time_str)

        def _deferred_check():
            check_and_display(game)
            return schedule.CancelJob

        schedule.every().day.at(check_time_str).do(_deferred_check).tag("game_check")


def daily_reset() -> None:
    """Clear the display and cancel any leftover game_check jobs."""
    log.info("Daily reset — clearing display.")
    display.clear()
    schedule.clear("game_check")
    schedule_todays_check()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the W Flag daemon."""
    log.info("W Flag Daemon starting.")

    def _shutdown(signum, _frame):
        log.info("Received signal %s — shutting down.", signum)
        display.clear()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    schedule_todays_check()

    schedule.every().day.at("00:05").do(daily_reset)
    schedule.every().day.at("23:59").do(display.clear)

    log.info("Scheduler running. Press Ctrl-C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
