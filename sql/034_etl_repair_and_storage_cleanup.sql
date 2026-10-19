-- ============================================================
-- 034 — Daily-ETL repair + storage cleanup (applied live 2026-10)
--
-- Records schema changes already made in the live database so sql/ matches it.
-- Every statement is safe to re-run.
--
-- PART A — fix the daily ETL's failing last step.
--   refresh_player_career_regular_vs_playoff_stats() went through
--   player_season_totals_by_type_v (a count(DISTINCT) per season) and took
--   ~7.7s; the Supabase API path enforces an 8s statement_timeout, so the
--   daily "Refresh career regular-vs-playoff table" step failed every run from
--   2026-08-16 on. This version aggregates player_game_stats directly:
--   ~0.4s, output verified identical (3015 rows, 0 diffs).
--
-- PART B — storage cleanup that took the database from 1902 MB to 729 MB.
--   The row deletions themselves are data operations and are NOT repeated
--   here; for the record, play_events lost (1,981,150 rows):
--     * shot/miss/block/goal rows  — all already in shot_events / goal_events
--     * stoppage, period-start/end, game-end, shootout-complete rows
--       (NOTE: stoppage reasons — icing, offside, etc. — lived only here)
--     * every event from preseason and 'unknown' games (All-Star,
--       4 Nations 2025, Olympics 2026)
--   and the duplicated keys xCoord/yCoord/zoneCode/eventOwnerTeamId were
--   stripped from play_events.details (identical to real columns).
--   Any loader that writes play_events must skip those event/game types and
--   must not send an `id`, or the space comes straight back.
-- ============================================================

-- ---------------------------------------------------------------- PART A
create or replace function public.refresh_player_career_regular_vs_playoff_stats()
returns void language plpgsql as $function$
begin
  truncate table player_career_regular_vs_playoff_stats;
  insert into player_career_regular_vs_playoff_stats (
      player_id, full_name, position,
      regular_games_played, regular_points, regular_avg_ppg,
      playoff_games_played, playoff_points, playoff_avg_ppg,
      playoff_vs_regular_ppg_gap)
  select p.player_id, p.full_name, p.position,
    a.rgp, a.rpts, round(a.rpts::numeric / nullif(a.rgp,0), 2),
    a.pgp, a.ppts, round(a.ppts::numeric / nullif(a.pgp,0), 2),
    round((a.ppts::numeric / nullif(a.pgp,0)) - (a.rpts::numeric / nullif(a.rgp,0)), 2)
  from (
    -- (game_id, player_id) is unique in player_game_stats, so count(*) is the
    -- number of distinct games.
    select pgs.player_id,
      nullif(count(*) filter (where g.game_type = 'regular'), 0) as rgp,
      sum(pgs.points) filter (where g.game_type = 'regular')      as rpts,
      nullif(count(*) filter (where g.game_type = 'playoff'), 0) as pgp,
      sum(pgs.points) filter (where g.game_type = 'playoff')      as ppts
    from player_game_stats pgs
    join games g on g.game_id = pgs.game_id
    group by pgs.player_id
  ) a
  join players p on p.player_id = a.player_id
  where p.position != 'G';
end;
$function$;

-- ---------------------------------------------------------------- PART B
-- Unused or redundant indexes (0 scans since stats reset 2026-06-30, or
-- duplicated by the composite key).
drop index if exists public.play_events_details_gin;
drop index if exists public.play_events_game_idx;
drop index if exists public.play_events_fo_win_idx;
drop index if exists public.play_events_fo_lose_idx;
drop index if exists public.idx_shot_events_shooter;

-- Two fields that previously existed only in play_events, preserved on the
-- shot rows before those were removed from play_events.
alter table public.shot_events add column if not exists blocker_id bigint;
alter table public.shot_events add column if not exists miss_reason text;
comment on column public.shot_events.blocker_id is
  'Player who blocked the shot (blocked-shot rows). Copied from play_events before its shot rows were pruned, 2026-10.';
comment on column public.shot_events.miss_reason is
  'missed-shot: why it missed (wide-right, hit-crossbar, ...). blocked-shot: only teammate-blocked / other-block (NULL = ordinary opponent block).';

-- play_events: drop the unused surrogate key; (game_id, event_id) becomes the PK.
do $$
begin
  if exists (select 1 from information_schema.columns
             where table_schema = 'public' and table_name = 'play_events' and column_name = 'id') then
    alter table public.play_events drop constraint if exists play_events_pkey;
    alter table public.play_events drop column id;
    alter table public.play_events drop constraint if exists play_events_game_id_event_id_key;
    alter table public.play_events add constraint play_events_pkey primary key (game_id, event_id);
  end if;
end $$;
