"""
NHL Edge Data ETL Pipeline
==========================
Pulls season-level NHL Edge tracking stats (skating speed/distance,
shot speed, zone time) for players already in your `players` table,
for the last N seasons, split by game type (regular season vs.
playoffs — these are separate API calls, not a post-hoc filter).

This is a SEPARATE pipeline from pull_nhl_data.py because Edge data
is season-level, not per-game.

IMPORTANT: The Edge API is unofficial/reverse-engineered, so exact
field names in the response aren't fully documented. This script:
  1. Saves the FULL raw JSON response (in `raw_json`), so nothing
     is lost even if a field name guess below is wrong.
  2. Makes a best-effort attempt to extract common fields into
     dedicated columns for easy querying.

WHAT GETS FETCHED: only players who actually appeared in a game of that
season and game type (from player_game_stats), and of those only the ones
whose stored Edge row is missing or covers fewer games than they've played
(view `edge_pull_status_v`, sql/036). Edge stats are season-to-date, so this
keeps the season in progress fresh — each night it re-pulls whoever played,
and if Edge lags a day the row stays behind and is retried the next night.
It never asks about retired players or about playoffs before any exist.
(The old version requested every player in `players` x both game types —
~6,000 calls, nearly all 404s — and skipped anyone already pulled, so
in-season rows froze at whatever the first pull saw.)

Run this AFTER pull_nhl_data.py has populated `players` and
`player_game_stats` for the games in question.

SETUP: same SUPABASE_URL / SUPABASE_KEY environment variables as
pull_nhl_data.py. Also run sql/003_edge_schema.sql and sql/036 first.

USAGE:
    python pull_edge_data.py                       # season in progress
    python pull_edge_data.py --seasons 20232024,20242025,20252026
    python pull_edge_data.py --seasons 20252026 --limit 20   # quick test
    python pull_edge_data.py --force               # re-pull everyone who played
"""

import os
import sys
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"
GAME_TYPES = {"2": "regular", "3": "playoff"}

def _current_season():
    """Seasons roll over in August: July 2026 is still 20252026."""
    from datetime import date
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}{start + 1}"

DEFAULT_SEASONS = [_current_season()]  # daily runs track the season in progress

# Shared cooldown — same approach as pull_nhl_data.py: if any request gets
# rate-limited, every subsequent request waits until the cooldown clears,
# instead of each one backing off independently.
_cooldown_lock = threading.Lock()
_cooldown_until = 0.0


def _wait_for_cooldown():
    with _cooldown_lock:
        remaining = _cooldown_until - time.time()
    if remaining > 0:
        time.sleep(remaining)


def _set_cooldown(seconds):
    # Cap and announce — an uncapped Retry-After once put the whole run
    # into an invisible hours-long sleep that looked like a hang.
    global _cooldown_until
    seconds = min(seconds, 120)
    with _cooldown_lock:
        _cooldown_until = max(_cooldown_until, time.time() + seconds)
    if seconds >= 10:
        print(f"    ! Rate-limited — cooling down {seconds:.0f}s")


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL / SUPABASE_KEY environment variables.")
    return create_client(url, key)


def fetch_json(url, retries=6):
    last_error = None
    for attempt in range(retries):
        _wait_for_cooldown()
        try:
            resp = requests.get(url, timeout=15)
        except requests.exceptions.RequestException as e:
            last_error = e
            wait = min(3 * (attempt + 1), 30)
            print(f"    ! Network error ({e.__class__.__name__}), retrying in {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None  # player has no data for this season/game-type — normal, skip
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 0)) or min(2 ** attempt, 90)
            _set_cooldown(wait)
            _wait_for_cooldown()
            continue
        time.sleep(1.5 * (attempt + 1))
    if last_error:
        print(f"    ! Giving up after repeated network errors: {last_error}")
    return None


def db_execute(query_builder, retries=3, description=""):
    """Retries Supabase writes on transient connection drops."""
    last_error = None
    for attempt in range(retries):
        try:
            return query_builder.execute()
        except Exception as e:
            last_error = e
            wait = 2 * (attempt + 1)
            print(f"    ! DB write error{' on ' + description if description else ''} "
                  f"({e.__class__.__name__}), retrying in {wait}s...")
            time.sleep(wait)
    raise last_error


def safe_get(d, *keys, default=None):
    """Digs through nested dicts safely, returns default if any key is missing."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def extract_skater_fields(payload):
    """
    Extraction based on the CONFIRMED real response shape (verified from
    an actual pull, not just docs). Zone-time percentages are converted
    from 0-1 fractions to 0-100 for readability. Percentiles are kept as
    0-1 (i.e. 0.78 = 78th percentile vs. league average).
    """
    games_played = safe_get(payload, "player", "gamesPlayed")
    total_distance = safe_get(payload, "totalDistanceSkated", "imperial")

    # sogSummary is a list of shot-location breakdowns; "all" is the
    # overall summary across every location.
    shooting_pct = None
    for entry in (payload.get("sogSummary") or []):
        if entry.get("locationCode") == "all":
            shooting_pct = entry.get("shootingPctg")
            break

    return {
        "games_played": games_played,
        "top_skating_speed_mph": safe_get(payload, "skatingSpeed", "speedMax", "imperial"),
        "bursts_over_20mph": safe_get(payload, "skatingSpeed", "burstsOver20", "value"),
        "total_skating_distance_miles": total_distance,
        "avg_skating_distance_per_game": (
            round(total_distance / games_played, 3)
            if total_distance and games_played else None
        ),
        "top_shot_speed_mph": safe_get(payload, "topShotSpeed", "imperial"),
        "shooting_pct": shooting_pct,
        "offensive_zone_time_pct": _to_pct(safe_get(payload, "zoneTimeDetails", "offensiveZonePctg")),
        "neutral_zone_time_pct": _to_pct(safe_get(payload, "zoneTimeDetails", "neutralZonePctg")),
        "defensive_zone_time_pct": _to_pct(safe_get(payload, "zoneTimeDetails", "defensiveZonePctg")),
        "skating_speed_percentile": safe_get(payload, "skatingSpeed", "speedMax", "percentile"),
        "shot_speed_percentile": safe_get(payload, "topShotSpeed", "percentile"),
        "distance_skated_percentile": safe_get(payload, "totalDistanceSkated", "percentile"),
        "offensive_zone_percentile": safe_get(payload, "zoneTimeDetails", "offensiveZonePercentile"),
    }


def _to_pct(fraction):
    """Converts a 0-1 fraction to a 0-100 percentage, safely."""
    return round(fraction * 100, 2) if fraction is not None else None


def get_status(sb, season, game_type_label):
    """Everyone who appeared in a game of this season + game type, with games
    played (boxscore) vs games covered by their stored Edge row. Paged — an
    unpaginated select silently caps at PostgREST's 1000-row default."""
    rows = []
    page_size = 1000
    offset = 0
    while True:
        page = (
            sb.table("edge_pull_status_v")
            .select("player_id, position, full_name, actual_gp, edge_gp")
            .eq("season", season)
            .eq("game_type", game_type_label)
            .order("player_id")
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def needs_refresh(row):
    """Missing row, or Edge covers fewer games than the player has played."""
    return row["edge_gp"] is None or row["edge_gp"] < row["actual_gp"]


def fetch_edge_payload(player, season, game_type_code):
    """Fetch-only half of the pull, safe to run in a worker thread."""
    player_id = player["player_id"]
    is_goalie = (player.get("position") == "G")
    kind = "goalie-detail" if is_goalie else "skater-detail"
    payload = fetch_json(f"{NHL_API_BASE}/edge/{kind}/{player_id}/{season}/{game_type_code}")
    # The edge endpoints rate-limit harder than gamecenter — unpaced
    # threaded 404 sweeps got the whole run put in the penalty box.
    time.sleep(0.5)
    return payload


def upsert_edge_row(sb, player, season, game_type_label, payload):
    """Write half — main thread only, like the other ETLs."""
    player_id = player["player_id"]
    is_goalie = (player.get("position") == "G")

    if not payload:
        return False  # no data for this player/season/game-type combo — common, not an error

    # Goalies only get games_played extracted — it's what edge_pull_status_v
    # compares against, so without it every goalie would look stale forever.
    if is_goalie:
        fields = {"games_played": safe_get(payload, "player", "gamesPlayed")}
    else:
        fields = extract_skater_fields(payload)

    row = {
        "player_id": player_id,
        "season": season,
        "game_type": game_type_label,
        "raw_json": payload,
        # Upserts don't touch updated_at on their own; stamp it so you can see
        # when a row was last refreshed.
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }

    db_execute(
        sb.table("player_season_edge_stats").upsert(row, on_conflict="player_id,season,game_type"),
        description=f"player {player_id} edge stats"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Pull NHL Edge tracking data into Supabase.")
    parser.add_argument("--seasons", type=str, default=",".join(DEFAULT_SEASONS),
                         help="Comma-separated seasons, e.g. 20232024,20242025,20252026")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only fetch the first N players per season/game type (quick test run)")
    parser.add_argument("--force", action="store_true",
                         help="Re-fetch everyone who played, even if their Edge row is up to date")
    parser.add_argument("--workers", type=int, default=3,
                         help="Edge fetches in parallel (default 3 — NHL API rate-limits above this)")
    args = parser.parse_args()

    seasons = args.seasons.split(",")
    sb = get_supabase_client()

    total_pulled = 0
    total_no_data = 0
    total_current = 0

    for season in seasons:
        for game_type_code, game_type_label in GAME_TYPES.items():
            status = get_status(sb, season, game_type_label)
            if not status:
                # e.g. playoffs before they start — nothing to ask the API about
                print(f"\n=== Season {season} — {game_type_label}: no games played, skipping ===")
                continue

            todo = status if args.force else [r for r in status if needs_refresh(r)]
            if args.limit:
                todo = todo[:args.limit]
            total_current += len(status) - len(todo)
            print(f"\n=== Season {season} — {game_type_label} "
                  f"({len(status)} players appeared; {len(todo)} to fetch, "
                  f"{len(status) - len(todo)} already current) ===")

            done = 0
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(fetch_edge_payload, p, season, game_type_code): p
                    for p in todo
                }
                for future in as_completed(futures):
                    player = futures[future]
                    done += 1
                    try:
                        if upsert_edge_row(sb, player, season, game_type_label, future.result()):
                            total_pulled += 1
                        else:
                            # Played, but Edge has nothing (yet) — retried next run.
                            total_no_data += 1
                    except Exception as e:
                        print(f"  ! Error on player {player['player_id']} ({player.get('full_name')}): {e}")

                    if done % 100 == 0 or done == len(todo):
                        print(f"  ...{done}/{len(todo)} fetched")

    print(f"\nDone. Rows pulled: {total_pulled}, "
          f"no Edge data yet: {total_no_data}, "
          f"already current: {total_current}")


if __name__ == "__main__":
    main()
