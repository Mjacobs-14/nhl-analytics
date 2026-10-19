-- ============================================================
-- 035 — Get under the Supabase free plan's 500 MB (applied live 2026-10)
--
-- 746 MB -> 368 MB. Records the schema changes already made live so sql/
-- matches the database. Safe to re-run: every step is guarded.
--
-- 1. play_events ARCHIVED and dropped (~310 MB).
--    All 1,545,375 rows (faceoff, hit, giveaway, takeaway, penalty,
--    delayed-penalty, failed-shot-attempt; 2018-19..2025-26 regular+playoff)
--    were exported to gzipped CSV, one file per season
--    (archive/play_events/play_events_<year>.csv.gz, 26 MB total; columns:
--    game_id, event_id, sort_order, period, period_type, time_in_period,
--    type_code, type_desc_key, team_id, x_coord, y_coord, zone_code,
--    situation_code, details). Verified against the table before the drop:
--    row count, distinct games, sum(event_id), sum(x), sum(y), situation
--    chars, and total details-JSON chars all matched exactly.
--    Nothing in the app read play_events, and its loader was not in the daily
--    ETL (no 2026-27 rows existed).
--    Dropped with it: views pbp_faceoffs_v, pbp_hits_v, pbp_penalties_v,
--    pbp_turnovers_v. pbp_faceoff_mv and pbp_hit_grid_mv were converted to
--    plain tables of the same name (frozen, identical contents).
--    Replaced by two small summary tables built before the drop (below).
--
-- 2. goal_events: scorer/assists/goalie/shot type extracted from raw_details
--    into columns (71,499 rows, 0 mismatches); raw_details emptied (~33 MB).
--    The column is kept, empty, until no loader writes it; then drop it.
--
-- 3. Surrogate `id` keys replaced by the natural keys the ETL already upserts
--    on: goal_events (game_id, event_id), player_game_state_events
--    (game_id, event_id, player_id). player_game_stats keeps its `id` — the
--    app's drizzle schema maps it.
--
-- 4. Dropped indexes: idx_pgse_state (3 scans), idx_pgs_game (covered by
--    unique (game_id, player_id)). idx_shot_events_rush_done is deliberately
--    KEPT: etl/pull_play_by_play.py --refresh-shots resumes on that predicate.
-- ============================================================

-- ---------------------------------------------------------------- 1
-- Summary tables (built from play_events before it was dropped). The CTAS
-- only runs if play_events still exists, i.e. on a database that never had
-- this migration applied.
do $$
begin
  if to_regclass('public.play_events') is not null
     and to_regclass('public.pbp_player_season_stats') is null then
    execute $q$
      create table public.pbp_player_season_stats as
      with e as (
        select g.season, g.game_type, p.type_desc_key k, p.zone_code z, p.details d
        from play_events p join games g on g.game_id = p.game_id
      ),
      rows as (
        select (d->>'winningPlayerId')::bigint pid, season, game_type, 'fo_won' m, z from e where k='faceoff'
        union all
        select (d->>'losingPlayerId')::bigint, season, game_type, 'fo_lost',
               case z when 'O' then 'D' when 'D' then 'O' else z end from e where k='faceoff'
        union all select (d->>'hittingPlayerId')::bigint, season, game_type, 'hit', null from e where k='hit'
        union all select (d->>'hitteePlayerId')::bigint,  season, game_type, 'hit_taken', null from e where k='hit'
        union all select (d->>'committedByPlayerId')::bigint, season, game_type, 'pen_taken', (d->>'duration') from e where k='penalty'
        union all select (d->>'drawnByPlayerId')::bigint, season, game_type, 'pen_drawn', null from e where k='penalty'
        union all select (d->>'playerId')::bigint, season, game_type, 'giveaway', null from e where k='giveaway'
        union all select (d->>'playerId')::bigint, season, game_type, 'takeaway', null from e where k='takeaway'
      )
      select pid as player_id, season, game_type,
        count(*) filter (where m='fo_won') as fo_won,
        count(*) filter (where m='fo_lost') as fo_lost,
        count(*) filter (where m='fo_won'  and z='O') as fo_won_oz,
        count(*) filter (where m='fo_won'  and z='N') as fo_won_nz,
        count(*) filter (where m='fo_won'  and z='D') as fo_won_dz,
        count(*) filter (where m='fo_lost' and z='O') as fo_lost_oz,
        count(*) filter (where m='fo_lost' and z='N') as fo_lost_nz,
        count(*) filter (where m='fo_lost' and z='D') as fo_lost_dz,
        count(*) filter (where m='hit') as hits,
        count(*) filter (where m='hit_taken') as hits_taken,
        count(*) filter (where m='pen_taken') as penalties_taken,
        coalesce(sum(z::int) filter (where m='pen_taken'),0) as pim,
        count(*) filter (where m='pen_drawn') as penalties_drawn,
        count(*) filter (where m='giveaway') as giveaways,
        count(*) filter (where m='takeaway') as takeaways
      from rows where pid is not null
      group by pid, season, game_type
    $q$;
    alter table public.pbp_player_season_stats add primary key (player_id, season, game_type);

    execute $q$
      create table public.pbp_team_season_stats as
      with e as (
        select g.season, g.game_type, p.type_desc_key k, p.team_id t,
               case when p.team_id = g.home_team_id then g.away_team_id else g.home_team_id end opp,
               p.details d
        from play_events p join games g on g.game_id = p.game_id
        where p.team_id is not null and p.type_desc_key in ('faceoff','hit','penalty','giveaway','takeaway')
      ),
      rows as (
        select t team, season, game_type, k||'_for' m, d from e
        union all
        select opp, season, game_type, k||'_against', d from e
      )
      select team as team_id, season, game_type,
        count(*) filter (where m='faceoff_for') as fo_won,
        count(*) filter (where m='faceoff_against') as fo_lost,
        count(*) filter (where m='hit_for') as hits_for,
        count(*) filter (where m='hit_against') as hits_against,
        count(*) filter (where m='penalty_for') as penalties_taken,
        coalesce(sum((d->>'duration')::int) filter (where m='penalty_for'),0) as pim,
        count(*) filter (where m='penalty_against') as penalties_drawn,
        count(*) filter (where m='giveaway_for') as giveaways,
        count(*) filter (where m='takeaway_for') as takeaways
      from rows group by team, season, game_type
    $q$;
    alter table public.pbp_team_season_stats add primary key (team_id, season, game_type);
  end if;
end $$;

-- Freeze Ruston's two summaries as plain tables, then drop play_events.
-- Only acts if play_events still exists. Export it to archive/ first.
do $$
begin
  if to_regclass('public.play_events') is not null then
    create table public._fo_keep as select * from public.pbp_faceoff_mv;
    create table public._hg_keep as select * from public.pbp_hit_grid_mv;
    drop view if exists public.pbp_faceoffs_v;
    drop view if exists public.pbp_hits_v;
    drop view if exists public.pbp_penalties_v;
    drop view if exists public.pbp_turnovers_v;
    drop materialized view if exists public.pbp_faceoff_mv;
    drop materialized view if exists public.pbp_hit_grid_mv;
    drop table public.play_events;
    alter table public._fo_keep rename to pbp_faceoff_mv;
    alter table public._hg_keep rename to pbp_hit_grid_mv;
  end if;
end $$;

-- ---------------------------------------------------------------- 2
alter table public.goal_events add column if not exists scorer_id  bigint;
alter table public.goal_events add column if not exists assist1_id bigint;
alter table public.goal_events add column if not exists assist2_id bigint;
alter table public.goal_events add column if not exists goalie_id  bigint;
alter table public.goal_events add column if not exists shot_type  text;
update public.goal_events set
  scorer_id  = (raw_details->>'scoringPlayerId')::bigint,
  assist1_id = (raw_details->>'assist1PlayerId')::bigint,
  assist2_id = (raw_details->>'assist2PlayerId')::bigint,
  goalie_id  = (raw_details->>'goalieInNetId')::bigint,
  shot_type  = raw_details->>'shotType',
  raw_details = null
where raw_details is not null;

-- ---------------------------------------------------------------- 3
do $$
begin
  if exists (select 1 from information_schema.columns
             where table_schema='public' and table_name='goal_events' and column_name='id') then
    alter table public.goal_events drop column id;
    alter table public.goal_events drop constraint if exists goal_events_game_id_event_id_key;
    alter table public.goal_events add constraint goal_events_pkey primary key (game_id, event_id);
  end if;
  if exists (select 1 from information_schema.columns
             where table_schema='public' and table_name='player_game_state_events' and column_name='id') then
    alter table public.player_game_state_events drop column id;
    alter table public.player_game_state_events drop constraint if exists player_game_state_events_game_id_event_id_player_id_key;
    alter table public.player_game_state_events add constraint player_game_state_events_pkey primary key (game_id, event_id, player_id);
  end if;
end $$;

-- ---------------------------------------------------------------- 4
drop index if exists public.idx_pgse_state;
drop index if exists public.idx_pgs_game;
