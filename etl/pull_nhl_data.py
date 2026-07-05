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
from datetime import date, timedelta, datetime

import requests
from supabase import create_client

NHL_API_BASE = "https://api-web.nhle.com/v1"

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
def fetch_json(url, retries=3):
    for attempt in range(retries):
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        time.sleep(1.5 * (attempt + 1))
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


# ------------------------------------------------------------------
# Transform + load
# ------------------------------------------------------------------
def upsert_team(sb, team_id, team_name):
    if not team_id:
        return
    sb.table("teams").upsert({
        "team_id": team_id,
        "team_name": team_name,
    }).execute()


def upsert_game(sb, game_json, boxscore_json):
    game_id = game_json["id"]
    home = game_json["homeTeam"]
    away = game_json["awayTeam"]

    upsert_team(sb, home.get("abbrev"), home.get("commonName", {}).get("default", home.get("abbrev")))
    upsert_team(sb, away.get("abbrev"), away.get("commonName", {}).get("default", away.get("abbrev")))

    sb.table("games").upsert({
        "game_id": game_id,
        "game_date": game_json.get("gameDate", "")[:10] or game_json.get("startTimeUTC", "")[:10],
        "season": game_json.get("season"),
        "game_type": {1: "preseason", 2: "regular", 3: "playoff"}.get(game_json.get("gameType"), "unknown"),
        "home_team_id": home.get("abbrev"),
        "away_team_id": away.get("abbrev"),
        "home_score": boxscore_json.get("homeTeam", {}).get("score"),
        "away_score": boxscore_json.get("awayTeam", {}).get("score"),
        "venue": game_json.get("venue", {}).get("default"),
    }).execute()

    return game_id


def upsert_players_and_stats(sb, game_id, boxscore_json, season=None, game_date=None):
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
                sb.table("players").upsert({
                    "player_id": player_id,
                    "full_name": f"{p.get('name', {}).get('default', '')}".strip() or p.get("name", ""),
                    "position": p.get("position"),
                    "current_team_id": team_id,
                }).execute()

                # Upsert per-game stats
                sb.table("player_game_stats").upsert({
                    "game_id": game_id,
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season,
                    "game_date": game_date,
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
                }, on_conflict="game_id,player_id").execute()


def toi_to_seconds(toi_str):
    """Converts 'MM:SS' time-on-ice string to seconds."""
    try:
        minutes, seconds = toi_str.split(":")
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return 0


def run_for_date(sb, day: date):
    print(f"Fetching schedule for {day.isoformat()}...")
    games = get_schedule_for_date(day)
    print(f"  Found {len(games)} games.")

    for g in games:
        game_id = g["id"]
        print(f"  Processing game {game_id} ({g['awayTeam']['abbrev']} @ {g['homeTeam']['abbrev']})...")
        try:
            boxscore = get_boxscore(game_id)
            upsert_game(sb, g, boxscore)
            upsert_players_and_stats(
                sb, game_id, boxscore,
                season=g.get("season"),
                game_date=(g.get("gameDate", "") or g.get("startTimeUTC", ""))[:10] or None,
            )
        except Exception as e:
            print(f"    ! Skipped game {game_id} due to error: {e}")
        time.sleep(0.5)  # be polite to the API


def main():
    parser = argparse.ArgumentParser(description="Pull NHL data into Supabase.")
    parser.add_argument("--date", type=str, help="Single date, YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, help="Start of range, YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, help="End of range, YYYY-MM-DD")
    args = parser.parse_args()

    sb = get_supabase_client()

    if args.date:
        run_for_date(sb, datetime.strptime(args.date, "%Y-%m-%d").date())
    elif args.start_date and args.end_date:
        d0 = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        current = d0
        while current <= d1:
            run_for_date(sb, current)
            current += timedelta(days=1)
    else:
        # default: yesterday's games
        run_for_date(sb, date.today() - timedelta(days=1))

    print("Done.")


if __name__ == "__main__":
    main()