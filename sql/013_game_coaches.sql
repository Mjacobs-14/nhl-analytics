-- ============================================================
-- Game Coaches — head coach per team per game, from the same
-- gamecenter right-rail endpoint that already supplies referees
-- and linesmen (etl/backfill_game_details.py).
--
-- Foundation for coach-impact analysis: stints are derived from
-- contiguous runs of (team, coach) games, then offense/defense/
-- special-teams rates come from goal_events + shot_events.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

alter table games add column if not exists home_coach text;
alter table games add column if not exists away_coach text;
