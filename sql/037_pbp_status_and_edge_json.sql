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
from games g;

update public.player_season_edge_stats e
   set raw_json = null
  from public.players p
 where p.player_id = e.player_id and p.position <> 'G' and e.raw_json is not null;
