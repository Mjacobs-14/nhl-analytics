-- ============================================================
-- 037 — Daily-job timeout fix + Edge storage (applied live 2026-11)
--
-- 1. pbp_game_status_v: one row per game with flags for what
--    etl/pull_play_by_play.py has already loaded. The script used to build
--    its "already done" set by paging every shot_events row (~1,300 API
--    pages); the deep pages hit the 8s statement_timeout and failed the
--    daily job on 2026-11-02 and 11-16. Read keyset-paged on game_id:
--    ~1.4s per 1,000 games at any depth (OFFSET paging was ~14s deep).
--
--    Finished games only (home_score set), so a run during game night can't
--    store a few minutes of shots and then treat the game as done.
--
-- 2. player_season_edge_stats.raw_json emptied for skaters. Their useful
--    fields are already columns; the JSON (~16 MB) was rewritten for every
--    player who played, every night. Goalies keep theirs (nothing goalie-
--    specific is extracted). The ETL now writes NULL for skaters.
-- ============================================================

create or replace view public.pbp_game_status_v as
select g.game_id, g.season, g.game_type, g.game_date,
  exists (select 1 from shot_events s where s.game_id = g.game_id)                           as has_shots,
  exists (select 1 from shot_events s where s.game_id = g.game_id and s.is_rush is not null) as has_rush,
  exists (select 1 from goal_events e where e.game_id = g.game_id)                           as has_goals
from games g
where g.home_score is not null;   -- finished games only; unstarted/live rows have no score

update public.player_season_edge_stats e
   set raw_json = null
  from public.players p
 where p.player_id = e.player_id and p.position <> 'G' and e.raw_json is not null;

-- 3. Clean up dead rows sooner on the two big, append-heavy tables. Each
--    player_game_stats row is rewritten once (shift backfill); the default
--    20% threshold let tens of thousands of dead rows accumulate before
--    autovacuum made the space reusable.
alter table public.player_game_stats set (autovacuum_vacuum_scale_factor = 0.02, autovacuum_analyze_scale_factor = 0.02);
alter table public.shot_events       set (autovacuum_vacuum_scale_factor = 0.02, autovacuum_analyze_scale_factor = 0.02);

-- 4. Data repair (not repeated here): 2026-27 game dates. Schedule games carry
--    no local gameDate, so pull_nhl_data.py fell back to startTimeUTC, whose
--    date is the next day for any start at/after 00:00 UTC (7pm Eastern in
--    winter). 215 of 397 2026-27 games (and their player_game_stats rows)
--    were a day late; corrected 2026-11-18 from the NHL schedule's local
--    dates. Earlier seasons were checked against the schedule and are correct.
--    The script now uses the schedule week's local date.
--    A game-night test run then put 123 of those dates back: its weather step
--    read games before the repair and upserted them (with game_date) after.
--    Re-repaired 2026-11-18 against the schedule. 2026-27 weather was nulled
--    because it had been stamped for the wrong (UTC) day; the daily weather
--    step re-stamps it. backfill_weather.py now reads finished games only.
