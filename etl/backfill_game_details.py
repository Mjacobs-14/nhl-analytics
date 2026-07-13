"""
Game Details ETL
================
Fills in four things the boxscore pipeline doesn't carry, for every
game already in the `games` table:

  1. player_game_stats.shifts     — from the shift-charts API
  2. games.referees / linesmen    — from the gamecenter right-rail endpoint
  3. games.attendance             — parsed from the NHL's HTML game summary
                                    (the JSON API stopped exposing attendance)
  4. games.home_coach / away_coach — head coaches, from the same right-rail
                                    gameInfo block as the officials

Skip-existing on rerun: games whose attendance, referees, AND coaches are
already set are skipped unless --force. Shifts are written for whichever
players already have a stat row for that game (never creates phantom rows).

--coaches-only is the fast path for backfilling coaches into games whose
other details are already filled: it fetches just the right-rail endpoint
(1 request/game instead of 3) and patches only the coach columns. It is
resume-aware — games that already have both coaches are skipped.

SETUP: run sql/010_shot_events_and_game_details.sql and
sql/013_game_coaches.sql in Supabase first. Same SUPABASE_URL /
SUPABASE_KEY env vars as the other scripts.

USAGE:
    python backfill_game_details.py                  # all games missing details
    python backfill_game_details.py --season 20182019
    python backfill_game_details.py --limit 20       # quick test
    python backfill_game_details.py --workers 3
    python backfill_game_details.py --coaches-only   # backfill coaches only
"""

import os
import re
import sys
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"
STATS_API_BASE = "https://api.nhle.com/stats/rest/en"
REPORTS_BASE = "https://www.nhl.com/scores/htmlreports"

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


def fetch(url, retries=6, as_json=True):
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
            return resp.json() if as_json else resp.text
        if resp.status_code == 404:
            return None
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


def get_games_to_process(sb, season=None, limit=None, force=False, coaches_only=False):
    """Games rows (id, date, season) still missing details, oldest first."""
    games = []
    page_size = 1000
    offset = 0
    while True:
        query = sb.table("games").select(
            "game_id, game_date, season, attendance, referees, home_coach, away_coach"
        )
        if season:
            query = query.eq("season", season)
        query = query.order("game_id").range(offset, offset + page_size - 1)
        rows = query.execute().data
        if not rows:
            break
        games.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    if not force:
        before = len(games)
        if coaches_only:
            games = [g for g in games
                     if g["home_coach"] is None or g["away_coach"] is None]
        else:
            games = [g for g in games
                     if g["attendance"] is None or g["referees"] is None
                     or g["home_coach"] is None or g["away_coach"] is None]
        print(f"  {before - len(games)} games already have details — skipping those.")

    if limit:
        games = games[:limit]
    return games


def get_stat_row_players(sb, game_ids):
    """(game_id, player_id) pairs that already have a stat row, so the
    shifts upsert never inserts skeleton rows for unknown players."""
    pairs = set()
    page_size = 1000
    offset = 0
    while True:
        rows = (
            sb.table("player_game_stats")
            .select("game_id, player_id")
            .in_("game_id", game_ids)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        if not rows:
            break
        pairs.update((r["game_id"], r["player_id"]) for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return pairs


def fetch_game_details(game, coaches_only=False):
    """Fetches shifts + officials + coaches + attendance for one game.
    With coaches_only, hits just the right-rail endpoint and patches only
    the coach columns. Returns (game, shifts_by_player, games_patch, error)."""
    game_id = game["game_id"]
    try:
        shifts_by_player = {}
        if not coaches_only:
            chart = fetch(f"{STATS_API_BASE}/shiftcharts?cayenneExp=gameId={game_id}")
            for row in (chart or {}).get("data", []):
                # Goal markers ride along in shift charts; real shifts have a
                # duration and no event description.
                if row.get("eventDescription") is None and row.get("duration"):
                    pid = row.get("playerId")
                    if pid:
                        shifts_by_player[pid] = shifts_by_player.get(pid, 0) + 1

        patch = {"game_id": game_id, "game_date": game["game_date"], "season": game["season"]}

        rail = fetch(f"{NHL_API_BASE}/gamecenter/{game_id}/right-rail")
        info = (rail or {}).get("gameInfo") or {}

        home_coach = ((info.get("homeTeam") or {}).get("headCoach") or {}).get("default")
        away_coach = ((info.get("awayTeam") or {}).get("headCoach") or {}).get("default")
        if home_coach:
            patch["home_coach"] = home_coach
        if away_coach:
            patch["away_coach"] = away_coach

        if coaches_only:
            # Nothing to write for games the API has no coach data for
            # (some preseason/special games) — don't churn the DB.
            if "home_coach" not in patch and "away_coach" not in patch:
                patch = None
            return game, shifts_by_player, patch, None

        refs = [r.get("default") for r in info.get("referees", []) if r.get("default")]
        lines = [l.get("default") for l in info.get("linesmen", []) if l.get("default")]
        if refs:
            patch["referees"] = refs
        if lines:
            patch["linesmen"] = lines

        # Attendance only exists in the HTML game summary, e.g.
        # "Attendance 18,354&nbsp;at&nbsp;T-Mobile Arena"
        report = fetch(f"{REPORTS_BASE}/{game['season']}/GS{str(game_id)[4:]}.HTM", as_json=False)
        if report:
            m = re.search(r"Attendance[^0-9]*([\d,]+)", report)
            if m:
                patch["attendance"] = int(m.group(1).replace(",", ""))

        return game, shifts_by_player, patch, None
    except Exception as e:
        return game, None, None, e


def main():
    parser = argparse.ArgumentParser(description="Backfill shifts, officials, and attendance.")
    parser.add_argument("--season", type=str, default=None, help="Only games from this season, e.g. 20182019")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N games (for testing)")
    parser.add_argument("--force", action="store_true", help="Re-fetch games that already have details")
    parser.add_argument("--coaches-only", action="store_true",
                        help="Backfill just games.home_coach/away_coach (right-rail fetch only, "
                             "1 request/game). Resume-aware: games with both coaches set are skipped.")
    parser.add_argument("--workers", type=int, default=3,
                        help="Games fetched in parallel (default 3 — NHL API rate-limits above this)")
    args = parser.parse_args()

    sb = get_supabase_client()

    games = get_games_to_process(sb, season=args.season, limit=args.limit,
                                 force=args.force, coaches_only=args.coaches_only)
    print(f"Processing {len(games)} games.")

    BATCH = 50
    processed = 0
    for start in range(0, len(games), BATCH):
        batch = games[start:start + BATCH]
        known_pairs = set() if args.coaches_only else get_stat_row_players(
            sb, [g["game_id"] for g in batch])

        shift_rows = []
        game_patches = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(fetch_game_details, g, args.coaches_only) for g in batch]
            for future in as_completed(futures):
                game, shifts_by_player, patch, err = future.result()
                processed += 1
                if err:
                    print(f"  ! Skipped game {game['game_id']} due to error: {err}")
                    continue
                if patch:
                    game_patches.append(patch)
                for pid, n in (shifts_by_player or {}).items():
                    if (game["game_id"], pid) in known_pairs:
                        shift_rows.append({
                            "game_id": game["game_id"],
                            "player_id": pid,
                            "shifts": n,
                        })

        if shift_rows:
            db_execute(
                sb.table("player_game_stats").upsert(shift_rows, on_conflict="game_id,player_id"),
                description=f"shifts batch @{start}",
            )
        if game_patches:
            db_execute(
                sb.table("games").upsert(game_patches, on_conflict="game_id"),
                description=f"game details batch @{start}",
            )

        print(f"  ...{processed}/{len(games)} games processed")

    print(f"\nDone. Processed {processed} games.")


if __name__ == "__main__":
    main()
