"""
Game State ETL Pipeline
=======================
Pulls play-by-play data for games already in your `games` table and
derives the score situation (tied, up 1, down 2, etc.) at the moment
of every goal — something the boxscore data can't tell you, since it
only has final totals.

Reuses the same resilience patterns as pull_nhl_data.py: shared
rate-limit cooldown, network-error retries, DB write retries, and
skip-existing on rerun.

SETUP: run sql/007_game_state_schema.sql in Supabase first. Same
SUPABASE_URL / SUPABASE_KEY env vars as the other scripts.

USAGE:
    python pull_play_by_play.py                       # all games in DB
    python pull_play_by_play.py --season 20252026      # just one season
    python pull_play_by_play.py --limit 20             # quick test
"""

import os
import sys
import argparse
import time
import threading

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"

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


def game_state_label(diff):
    """Converts a goal differential into a readable state label."""
    if diff == 0:
        return "tied"
    elif diff >= 3:
        return "up_3_plus"
    elif diff > 0:
        return f"up_{diff}"
    elif diff <= -3:
        return "down_3_plus"
    else:
        return f"down_{abs(diff)}"


def get_games_to_process(sb, season=None, limit=None):
    if limit:
        query = sb.table("games").select("game_id, season")
        if season:
            query = query.eq("season", season)
        query = query.limit(limit)
        return query.execute().data

    # No limit requested — page through everything (PostgREST caps
    # unpaginated selects at 1000 rows, which silently truncated this
    # before).
    games = []
    page_size = 1000
    offset = 0
    while True:
        query = sb.table("games").select("game_id, season")
        if season:
            query = query.eq("season", season)
        query = query.range(offset, offset + page_size - 1)
        rows = query.execute().data
        if not rows:
            break
        games.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return games


def get_existing_pbp_game_ids(sb):
    """Games already processed for play-by-play, so reruns skip them."""
    existing = set()
    page_size = 1000
    offset = 0
    while True:
        result = (
            sb.table("goal_events")
            .select("game_id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data
        if not rows:
            break
        existing.update(r["game_id"] for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return existing


def process_game(sb, game_id):
    payload = fetch_json(f"{NHL_API_BASE}/gamecenter/{game_id}/play-by-play")
    if not payload:
        return 0

    home_team = payload.get("homeTeam", {})
    away_team = payload.get("awayTeam", {})
    home_numeric_id = home_team.get("id")
    away_numeric_id = away_team.get("id")
    home_abbrev = home_team.get("abbrev")
    away_abbrev = away_team.get("abbrev")

    goals_processed = 0

    for play in payload.get("plays", []):
        if play.get("typeDescKey") != "goal":
            continue

        details = play.get("details", {}) or {}
        event_id = play.get("eventId")
        home_score_after = details.get("homeScore")
        away_score_after = details.get("awayScore")
        scoring_numeric_team_id = details.get("eventOwnerTeamId")

        if event_id is None or home_score_after is None or away_score_after is None:
            continue  # incomplete data for this play — skip rather than guess

        if scoring_numeric_team_id == home_numeric_id:
            scoring_team_abbrev = home_abbrev
            scoring_before = home_score_after - 1
            opponent_before = away_score_after
        elif scoring_numeric_team_id == away_numeric_id:
            scoring_team_abbrev = away_abbrev
            scoring_before = away_score_after - 1
            opponent_before = home_score_after
        else:
            continue  # couldn't determine which team scored — skip rather than guess

        diff_before = scoring_before - opponent_before
        state_label = game_state_label(diff_before)

        db_execute(sb.table("goal_events").upsert({
            "game_id": game_id,
            "event_id": event_id,
            "period": play.get("periodDescriptor", {}).get("number"),
            "period_type": play.get("periodDescriptor", {}).get("periodType"),
            "time_in_period": play.get("timeInPeriod"),
            "scoring_team_id": scoring_team_abbrev,
            "home_score_after": home_score_after,
            "away_score_after": away_score_after,
            "scoring_team_diff_before": diff_before,
            "game_state_before": state_label,
            "raw_details": details,
        }, on_conflict="game_id,event_id"), description=f"goal_events {game_id}/{event_id}")

        # Attribute the goal + assists to individual players
        contributions = []
        if details.get("scoringPlayerId"):
            contributions.append((details["scoringPlayerId"], "goal"))
        if details.get("assist1PlayerId"):
            contributions.append((details["assist1PlayerId"], "assist"))
        if details.get("assist2PlayerId"):
            contributions.append((details["assist2PlayerId"], "assist"))

        for player_id, role in contributions:
            db_execute(sb.table("player_game_state_events").upsert({
                "game_id": game_id,
                "event_id": event_id,
                "player_id": player_id,
                "role": role,
                "team_id": scoring_team_abbrev,
                "game_state_before": state_label,
                "period": play.get("periodDescriptor", {}).get("number"),
            }, on_conflict="game_id,event_id,player_id"), description=f"contribution {game_id}/{event_id}/{player_id}")

        goals_processed += 1

    return goals_processed


def main():
    parser = argparse.ArgumentParser(description="Pull play-by-play game-state data into Supabase.")
    parser.add_argument("--season", type=str, default=None, help="Only process games from this season, e.g. 20252026")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N games (for testing)")
    parser.add_argument("--force", action="store_true", help="Re-process games even if already done")
    args = parser.parse_args()

    sb = get_supabase_client()

    games = get_games_to_process(sb, season=args.season, limit=args.limit)
    print(f"Found {len(games)} games in the database.")

    if not args.force:
        existing_ids = get_existing_pbp_game_ids(sb)
        before = len(games)
        games = [g for g in games if g["game_id"] not in existing_ids]
        print(f"  {before - len(games)} already processed — skipping those, "
              f"processing the remaining {len(games)}.")

    total_goals = 0
    for i, g in enumerate(games, 1):
        try:
            goals = process_game(sb, g["game_id"])
            total_goals += goals
        except Exception as e:
            print(f"  ! Error on game {g['game_id']}: {e}")

        if i % 25 == 0 or i == len(games):
            print(f"  ...{i}/{len(games)} games processed ({total_goals} goals so far)")

        time.sleep(0.3)

    print(f"\nDone. Processed {len(games)} games, {total_goals} goals total.")


if __name__ == "__main__":
    main()
