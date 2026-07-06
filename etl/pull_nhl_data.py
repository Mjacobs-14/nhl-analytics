"""
NHL Data ETL Pipeline
=====================
Pulls schedule + boxscore data from the public NHL API and loads it
into Supabase (Postgres). Designed to be run daily via GitHub Actions,
or manually while you're testing.

SETUP (one-time):
1. Create a free project at https://supabase.com
2. Run sql/001_schema.sql and sql/002_derived_metrics_views.sql
   in Supabase's SQL Editor (Project > SQL Editor > New query > paste > Run)
3. Get your Project URL and "service_role" key from
   Project Settings > API
4. Set them as environment variables (locally in a .env file, or
   as GitHub Actions secrets — see .github/workflows/etl.yml):
       SUPABASE_URL=...
       SUPABASE_KEY=...
5. pip install -r requirements.txt
6. Run: python pull_nhl_data.py --date 2026-01-15
   (or --start-date / --end-date for a range, or no args for "yesterday")

You should not need to edit anything below this line to get started.
"""

import os
import sys
import argparse
import time
import threading
from datetime import date, timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"

# Shared cooldown state — when any thread hits a 429, every thread waits
# until this timestamp before making its next request, instead of each
# thread backing off independently while others keep hammering the API.
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

# ------------------------------------------------------------------
# Supabase client setup
# ------------------------------------------------------------------
def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit(
            "Missing SUPABASE_URL / SUPABASE_KEY environment variables.\n"
            "Set them locally (e.g. in a .env file + `export`) or as "
            "GitHub Actions secrets."
        )
    return create_client(url, key)


# ------------------------------------------------------------------
# NHL API helpers
# ------------------------------------------------------------------
def fetch_json(url, retries=8):
    last_error = None
    for attempt in range(retries):
        _wait_for_cooldown()
        try:
            resp = requests.get(url, timeout=15)
        except requests.exceptions.RequestException as e:
            # Transient network blips (DNS hiccups, dropped wifi, etc.) —
            # wait a bit and retry rather than crashing the whole run.
            last_error = e
            wait = min(3 * (attempt + 1), 30)
            print(f"    ! Network error ({e.__class__.__name__}), retrying in {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            # Rate-limited — set a shared cooldown so every thread pauses,
            # not just this one. Respects Retry-After if given (capped at 90s).
            wait = float(resp.headers.get("Retry-After", 0)) or min(2 ** attempt, 90)
            _set_cooldown(wait)
            _wait_for_cooldown()
            continue
        time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    resp.raise_for_status()


def get_schedule_for_date(day: date):
    """Returns list of game summaries for a given date."""
    url = f"{NHL_API_BASE}/schedule/{day.isoformat()}"
    data = fetch_json(url)
    games = []
    for week in data.get("gameWeek", []):
        if week.get("date") == day.isoformat():
            games.extend(week.get("games", []))
    return games


def get_boxscore(game_id: int):
    url = f"{NHL_API_BASE}/gamecenter/{game_id}/boxscore"
    return fetch_json(url)


def collect_games_in_range(start: date, end: date):
    """
    The /schedule/{date} endpoint returns an entire week per call, not just
    one day — so instead of calling it once per day (7x redundant calls),
    we step through by 7 days and grab every date in each response that
    falls inside our range. Big reduction in API calls for large ranges.
    """
    all_games = []
    seen_game_ids = set()
    current = start

    total_weeks = ((end - start).days // 7) + 1
    week_num = 0

    while current <= end:
        week_num += 1
        print(f"  Fetching schedule week {week_num}/{total_weeks} ({current.isoformat()})...")
        url = f"{NHL_API_BASE}/schedule/{current.isoformat()}"
        data = fetch_json(url)
        for week in data.get("gameWeek", []):
            week_date = datetime.strptime(week["date"], "%Y-%m-%d").date()
            if start <= week_date <= end:
                for g in week.get("games", []):
                    if g["id"] not in seen_game_ids:
                        seen_game_ids.add(g["id"])
                        all_games.append(g)
        current += timedelta(days=7)
        time.sleep(1.5)  # wider pause between schedule calls — the API appears to have a longer memory today

    return all_games


def db_execute(query_builder, retries=3, description=""):
    """Wraps a Supabase .execute() call with retries for transient
    connection drops (the API to Supabase can occasionally hiccup,
    same as any network call)."""
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


# ------------------------------------------------------------------
# Transform + load
# ------------------------------------------------------------------
def upsert_team(sb, team_id, team_name):
    if not team_id:
        return
    db_execute(sb.table("teams").upsert({
        "team_id": team_id,
        "team_name": team_name,
    }), description=f"team {team_id}")


def upsert_game(sb, game_json, boxscore_json):
    game_id = game_json["id"]
    home = game_json["homeTeam"]
    away = game_json["awayTeam"]

    upsert_team(sb, home.get("abbrev"), home.get("commonName", {}).get("default", home.get("abbrev")))
    upsert_team(sb, away.get("abbrev"), away.get("commonName", {}).get("default", away.get("abbrev")))

    db_execute(sb.table("games").upsert({
        "game_id": game_id,
        "game_date": game_json.get("gameDate", "")[:10] or game_json.get("startTimeUTC", "")[:10],
        "season": str(game_json.get("season", "")),
        "game_type": {1: "preseason", 2: "regular", 3: "playoff"}.get(game_json.get("gameType"), "unknown"),
        "home_team_id": home.get("abbrev"),
        "away_team_id": away.get("abbrev"),
        "home_score": boxscore_json.get("homeTeam", {}).get("score"),
        "away_score": boxscore_json.get("awayTeam", {}).get("score"),
        "venue": game_json.get("venue", {}).get("default"),
    }), description=f"game {game_id}")

    return game_id


def upsert_players_and_stats(sb, game_id, boxscore_json):
    """Loops through both teams' player stats in the boxscore payload."""
    player_stats = boxscore_json.get("playerByGameStats", {})

    for side in ["homeTeam", "awayTeam"]:
        team_id = boxscore_json.get(side, {}).get("abbrev") or boxscore_json.get(side, {}).get("abbreviation")
        side_data = player_stats.get(side, {})

        for group in ["forwards", "defense", "goalies"]:
            for p in side_data.get(group, []):
                player_id = p.get("playerId")
                if not player_id:
                    continue

                # Upsert player bio (partial — full bio comes from a separate
                # /player/{id}/landing call if you want more detail later)
                db_execute(sb.table("players").upsert({
                    "player_id": player_id,
                    "full_name": f"{p.get('name', {}).get('default', '')}".strip() or p.get("name", ""),
                    "position": p.get("position"),
                    "current_team_id": team_id,
                }), description=f"player {player_id}")

                # Upsert per-game stats
                db_execute(sb.table("player_game_stats").upsert({
                    "game_id": game_id,
                    "player_id": player_id,
                    "team_id": team_id,
                    "position": p.get("position"),
                    "goals": p.get("goals", 0),
                    "assists": p.get("assists", 0),
                    "shots": p.get("shots", 0),
                    "hits": p.get("hits", 0),
                    "blocked_shots": p.get("blockedShots", 0),
                    "penalty_minutes": p.get("pim", 0),
                    "plus_minus": p.get("plusMinus", 0),
                    "powerplay_goals": p.get("powerPlayGoals", 0),
                    "faceoff_wins": int(p.get("faceoffWins", 0) or 0),
                    "faceoff_losses": int(p.get("faceoffLosses", 0) or 0),
                    "toi_seconds": toi_to_seconds(p.get("toi", "0:00")),
                }, on_conflict="game_id,player_id"), description=f"player_game_stats {game_id}/{player_id}")


def toi_to_seconds(toi_str):
    """Converts 'MM:SS' time-on-ice string to seconds."""
    try:
        minutes, seconds = toi_str.split(":")
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return 0


def get_existing_game_ids(sb):
    """Pulls the set of game_ids already in the database, so reruns can
    skip anything already fetched instead of redoing everything."""
    existing = set()
    page_size = 1000
    offset = 0
    while True:
        result = sb.table("games").select("game_id").range(offset, offset + page_size - 1).execute()
        rows = result.data
        if not rows:
            break
        existing.update(r["game_id"] for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return existing


def run_for_date(sb, day: date):
    run_for_range(sb, day, day)


def _fetch_boxscore_task(g):
    """Runs in a worker thread — just the network call, no DB writes here
    (DB writes happen back on the main thread to keep Supabase calls simple)."""
    try:
        boxscore = get_boxscore(g["id"])
        return (g, boxscore, None)
    except Exception as e:
        return (g, None, e)


def run_for_range(sb, start: date, end: date, max_workers: int = 3, force: bool = False):
    print(f"Fetching schedule for {start.isoformat()} to {end.isoformat()}...")
    games = collect_games_in_range(start, end)
    print(f"  Found {len(games)} games total.")

    if not games:
        return

    if not force:
        existing_ids = get_existing_game_ids(sb)
        before = len(games)
        games = [g for g in games if g["id"] not in existing_ids]
        print(f"  {before - len(games)} already in the database — skipping those, "
              f"processing the remaining {len(games)}.")

    if not games:
        print("  Nothing new to fetch.")
        return

    processed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch_boxscore_task, g) for g in games]
        for future in as_completed(futures):
            g, boxscore, err = future.result()
            processed += 1

            if err:
                print(f"  ! Skipped game {g['id']} due to error: {err}")
                continue

            try:
                upsert_game(sb, g, boxscore)
                upsert_players_and_stats(sb, g["id"], boxscore)
            except Exception as e:
                print(f"  ! DB error on game {g['id']}: {e}")

            if processed % 25 == 0 or processed == len(games):
                print(f"  ...{processed}/{len(games)} games processed")


def main():
    parser = argparse.ArgumentParser(description="Pull NHL data into Supabase.")
    parser.add_argument("--date", type=str, help="Single date, YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, help="Start of range, YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, help="End of range, YYYY-MM-DD")
    parser.add_argument("--workers", type=int, default=3,
                         help="Number of games to fetch in parallel (default 3 — the NHL API rate-limits aggressively above this)")
    parser.add_argument("--force", action="store_true",
                         help="Re-fetch games even if already in the database (default: skip existing)")
    args = parser.parse_args()

    sb = get_supabase_client()

    if args.date:
        run_for_date(sb, datetime.strptime(args.date, "%Y-%m-%d").date())
    elif args.start_date and args.end_date:
        d0 = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        run_for_range(sb, d0, d1, max_workers=args.workers, force=args.force)
    else:
        # default: yesterday's games
        run_for_date(sb, date.today() - timedelta(days=1))

    print("Done.")


if __name__ == "__main__":
    main()