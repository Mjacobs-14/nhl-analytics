"""
Game State + Shot Location ETL Pipeline
========================================
Pulls play-by-play data for games already in your `games` table and
derives (1) the score situation (tied, up 1, down 2, etc.) at the
moment of every goal, and (2) a row per shot attempt (Corsi) with the
shooter's release coordinates, shot type, and strength state.

Reuses the same resilience patterns as pull_nhl_data.py: shared
rate-limit cooldown, network-error retries, DB write retries, and
skip-existing on rerun.

SETUP: run sql/007_game_state_schema.sql and sql/010_shot_events_and_game_details.sql
in Supabase first. Same SUPABASE_URL / SUPABASE_KEY env vars as the
other scripts.

USAGE:
    python pull_play_by_play.py                       # all games in DB
    python pull_play_by_play.py --season 20252026      # just one season
    python pull_play_by_play.py --limit 20             # quick test
    python pull_play_by_play.py --refresh-shots        # re-extract shots for
                                                       # every game (e.g. to
                                                       # backfill blocked shots)
"""

import os
import sys
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def get_existing_game_ids(sb, table):
    """Distinct game_ids already present in `table`, so reruns skip them."""
    existing = set()
    page_size = 1000
    offset = 0
    while True:
        result = (
            sb.table(table)
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


# All shot attempts (Corsi). shot-on-goal / missed-shot / goal carry the
# shooter's release coordinates; blocked-shot is included too (so Corsi and
# shot-suppression counts work), but its x/y/zone are nulled below because
# the API reports the *block* location, not the shot origin — keeping them
# would poison any coordinate- or distance-based metric (e.g. xG).
SHOT_EVENT_TYPES = {"goal", "shot-on-goal", "missed-shot", "blocked-shot"}


def extract_shot_events(payload, game_id, team_abbrev_by_id):
    """Builds shot_events rows from a play-by-play payload."""
    rows = []
    for play in payload.get("plays", []):
        event_type = play.get("typeDescKey")
        if event_type not in SHOT_EVENT_TYPES:
            continue
        details = play.get("details", {}) or {}
        event_id = play.get("eventId")
        if event_id is None:
            continue
        # Blocked-shot coordinates are where the block happened, not where
        # the shot was taken — null them so they don't masquerade as shot
        # locations. The row still counts as a shot attempt (Corsi), with
        # the shooter and team preserved.
        is_blocked = event_type == "blocked-shot"
        rows.append({
            "game_id": game_id,
            "event_id": event_id,
            "period": play.get("periodDescriptor", {}).get("number"),
            "period_type": play.get("periodDescriptor", {}).get("periodType"),
            "time_in_period": play.get("timeInPeriod"),
            "team_id": team_abbrev_by_id.get(details.get("eventOwnerTeamId")),
            "shooter_id": details.get("shootingPlayerId") or details.get("scoringPlayerId"),
            "goalie_id": details.get("goalieInNetId"),
            "event_type": event_type,
            "shot_type": details.get("shotType"),
            "x_coord": None if is_blocked else details.get("xCoord"),
            "y_coord": None if is_blocked else details.get("yCoord"),
            "zone_code": None if is_blocked else details.get("zoneCode"),
            "situation_code": play.get("situationCode"),
        })
    return rows


def process_game(sb, game_id, payload, do_goals=True, do_shots=True):
    """Extracts and writes goal/shot events from an already-fetched
    play-by-play payload (fetches are threaded; DB writes stay in the
    main thread, mirroring pull_nhl_data.py)."""
    if not payload:
        return 0, 0

    home_team = payload.get("homeTeam", {})
    away_team = payload.get("awayTeam", {})
    home_numeric_id = home_team.get("id")
    away_numeric_id = away_team.get("id")
    home_abbrev = home_team.get("abbrev")
    away_abbrev = away_team.get("abbrev")

    shots_processed = 0
    if do_shots:
        shot_rows = extract_shot_events(payload, game_id, {
            home_numeric_id: home_abbrev,
            away_numeric_id: away_abbrev,
        })
        if shot_rows:
            db_execute(
                sb.table("shot_events").upsert(shot_rows, on_conflict="game_id,event_id"),
                description=f"shot_events {game_id}",
            )
        shots_processed = len(shot_rows)

    goals_processed = 0
    if not do_goals:
        return 0, shots_processed

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

    return goals_processed, shots_processed


def main():
    parser = argparse.ArgumentParser(description="Pull play-by-play game-state data into Supabase.")
    parser.add_argument("--season", type=str, default=None, help="Only process games from this season, e.g. 20252026")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N games (for testing)")
    parser.add_argument("--force", action="store_true", help="Re-process games even if already done")
    parser.add_argument("--refresh-shots", action="store_true",
                        help="Re-extract shots for every game even if already done (goals still skip "
                             "already-done games). Use to backfill after shot-extraction logic changes, "
                             "e.g. adding blocked shots — upserts are idempotent, so existing rows are unharmed.")
    parser.add_argument("--workers", type=int, default=3,
                        help="Play-by-play fetches in parallel (default 3 — NHL API rate-limits above this)")
    args = parser.parse_args()

    sb = get_supabase_client()

    games = get_games_to_process(sb, season=args.season, limit=args.limit)
    print(f"Found {len(games)} games in the database.")

    # Goals and shots are tracked separately so games processed before
    # shot_events existed still get their shots extracted on rerun.
    done_goals = set() if args.force else get_existing_game_ids(sb, "goal_events")
    done_shots = set() if (args.force or args.refresh_shots) else get_existing_game_ids(sb, "shot_events")
    before = len(games)
    games = [g for g in games
             if g["game_id"] not in done_goals or g["game_id"] not in done_shots]
    if before - len(games):
        print(f"  {before - len(games)} already processed — skipping those, "
              f"processing the remaining {len(games)}.")

    total_goals = 0
    total_shots = 0
    processed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_json, f"{NHL_API_BASE}/gamecenter/{g['game_id']}/play-by-play"): g
            for g in games
        }
        for future in as_completed(futures):
            g = futures[future]
            processed += 1
            try:
                goals, shots = process_game(
                    sb, g["game_id"], future.result(),
                    do_goals=g["game_id"] not in done_goals,
                    do_shots=g["game_id"] not in done_shots,
                )
                total_goals += goals
                total_shots += shots
            except Exception as e:
                print(f"  ! Error on game {g['game_id']}: {e}")

            if processed % 25 == 0 or processed == len(games):
                print(f"  ...{processed}/{len(games)} games processed "
                      f"({total_goals} goals, {total_shots} shots so far)")

    print(f"\nDone. Processed {processed} games, {total_goals} goals, {total_shots} shots.")


if __name__ == "__main__":
    main()
