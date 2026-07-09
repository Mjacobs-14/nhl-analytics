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

Run this AFTER pull_nhl_data.py has populated your `players` table
(Edge ETL reads player IDs from there rather than re-discovering them).

SETUP: same SUPABASE_URL / SUPABASE_KEY environment variables as
pull_nhl_data.py. Also run sql/003_edge_schema.sql in Supabase first.

USAGE:
    python pull_edge_data.py
    python pull_edge_data.py --seasons 20232024,20242025,20252026
    python pull_edge_data.py --seasons 20252026 --limit 20   # quick test
"""

import os
import sys
import argparse
import time
import threading

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"
GAME_TYPES = {"2": "regular", "3": "playoff"}

DEFAULT_SEASONS = ["20232024", "20242025", "20252026"]

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
    global _cooldown_until
    with _cooldown_lock:
        _cooldown_until = max(_cooldown_until, time.time() + seconds)


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


def get_players(sb, limit=None):
    """Pulls player_id + position from the players table already populated
    by pull_nhl_data.py. Paged — an unpaginated select silently caps at
    PostgREST's 1000-row default, which quietly dropped players."""
    if limit:
        return sb.table("players").select("player_id, position, full_name").limit(limit).execute().data

    players = []
    page_size = 1000
    offset = 0
    while True:
        rows = (
            sb.table("players")
            .select("player_id, position, full_name")
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        if not rows:
            break
        players.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return players


def get_existing_edge_keys(sb):
    """Returns a set of (player_id, season, game_type) already pulled,
    so reruns skip what's already there instead of redoing everything."""
    existing = set()
    page_size = 1000
    offset = 0
    while True:
        result = (
            sb.table("player_season_edge_stats")
            .select("player_id, season, game_type")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data
        if not rows:
            break
        existing.update((r["player_id"], r["season"], r["game_type"]) for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return existing


def pull_edge_for_player(sb, player, season, game_type_code, game_type_label):
    player_id = player["player_id"]
    is_goalie = (player.get("position") == "G")

    if is_goalie:
        url = f"{NHL_API_BASE}/edge/goalie-detail/{player_id}/{season}/{game_type_code}"
    else:
        url = f"{NHL_API_BASE}/edge/skater-detail/{player_id}/{season}/{game_type_code}"

    payload = fetch_json(url)
    if not payload:
        return False  # no data for this player/season/game-type combo — common, not an error

    fields = {} if is_goalie else extract_skater_fields(payload)

    row = {
        "player_id": player_id,
        "season": season,
        "game_type": game_type_label,
        "raw_json": payload,
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
                         help="Only process the first N players (useful for a quick test run)")
    parser.add_argument("--force", action="store_true",
                         help="Re-fetch even if already in the database (default: skip existing)")
    args = parser.parse_args()

    seasons = args.seasons.split(",")
    sb = get_supabase_client()

    players = get_players(sb, limit=args.limit)
    print(f"Found {len(players)} players in the database.")

    existing_keys = set() if args.force else get_existing_edge_keys(sb)
    if existing_keys:
        print(f"Found {len(existing_keys)} player/season/game-type combos already pulled — will skip those.")

    total_pulled = 0
    total_skipped_no_data = 0
    total_skipped_existing = 0

    for season in seasons:
        for game_type_code, game_type_label in GAME_TYPES.items():
            print(f"\n=== Season {season} — {game_type_label} ===")
            for i, player in enumerate(players, 1):
                key = (player["player_id"], season, game_type_label)
                if key in existing_keys:
                    total_skipped_existing += 1
                else:
                    try:
                        got_data = pull_edge_for_player(
                            sb, player, season, game_type_code, game_type_label
                        )
                        if got_data:
                            total_pulled += 1
                        else:
                            total_skipped_no_data += 1
                    except Exception as e:
                        print(f"  ! Error on player {player['player_id']} ({player.get('full_name')}): {e}")

                if i % 25 == 0:
                    print(f"  ...{i}/{len(players)} players processed")

                time.sleep(0.5)  # be polite to the API

    print(f"\nDone. Rows pulled: {total_pulled}, "
          f"skipped (no data): {total_skipped_no_data}, "
          f"skipped (already had it): {total_skipped_existing}")


if __name__ == "__main__":
    main()
