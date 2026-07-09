-- ============================================================
-- Live-Database Repair — bring the pre-merge database up to the
-- unified schema in sql/001_schema.sql.
--
-- Background: PR #1 unified the two codebases on one schema, but the
-- live Supabase database was created from the ORIGINAL 001 and never
-- migrated. 001 is all `create table if not exists`, so re-running it
-- cannot add columns to tables that already exist — this file does.
--
-- Idempotent: every step is add-if-missing / guarded, so it is safe
-- on the live DB, on a fresh DB (where it's a no-op after 001), and
-- on re-runs. Run via `npm run db:apply` or paste into the SQL Editor.
-- ============================================================

-- teams: logo used by the app -----------------------------------
alter table teams add column if not exists logo_url text;

-- players: name split + display fields (roster ingest fills these;
-- backfill below gives daily-ETL-created rows a usable split too) ---
alter table players add column if not exists first_name text;
alter table players add column if not exists last_name  text;
alter table players add column if not exists sweater_number int;
alter table players add column if not exists headshot_url text;

update players
set first_name = split_part(full_name, ' ', 1),
    last_name  = nullif(btrim(substr(full_name, length(split_part(full_name, ' ', 1)) + 2)), '')
where first_name is null
  and full_name is not null;

-- player_game_stats: columns the unified pipelines write ----------
alter table player_game_stats add column if not exists season int;
alter table player_game_stats add column if not exists game_date date;
alter table player_game_stats add column if not exists opponent_abbrev text;
alter table player_game_stats add column if not exists home_road text;
alter table player_game_stats add column if not exists shifts int;

-- games.season: text -> int (the app and ingest compare it as a number).
-- Postgres refuses to retype a column any view touches, and the live DB
-- has views that were never committed to git — so this saves EVERY public
-- view's definition, drops them, retypes, and recreates them verbatim
-- (retrying to satisfy view-on-view dependencies). Skipped entirely once
-- the column is already an int.
do $$
declare
    r         record;
    remaining int;
    prev      int := -1;
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'games'
          and column_name = 'season' and data_type = 'text'
    ) then
        create temp table _saved_views as
        select viewname,
               pg_get_viewdef(format('%I.%I', schemaname, viewname)::regclass, true) as def
        from pg_views
        where schemaname = 'public';

        for r in select viewname from _saved_views loop
            execute format('drop view if exists public.%I cascade', r.viewname);
        end loop;

        alter table games alter column season type int using season::int;

        loop
            select count(*) into remaining from _saved_views;
            exit when remaining = 0 or remaining = prev;
            prev := remaining;
            for r in select viewname, def from _saved_views loop
                begin
                    execute format('create view public.%I as %s', r.viewname, r.def);
                    delete from _saved_views where viewname = r.viewname;
                exception when others then
                    -- depends on a view not recreated yet; retry next pass
                    null;
                end;
            end loop;
        end loop;

        select count(*) into remaining from _saved_views;
        if remaining > 0 then
            raise exception 'could not recreate % view(s) after retyping games.season', remaining;
        end if;

        drop table _saved_views;
    end if;
end $$;

-- Backfill the new player_game_stats columns from games (the daily
-- ETL fills them for new rows from here on) -----------------------
update player_game_stats pgs
set season    = g.season,
    game_date = g.game_date
from games g
where g.game_id = pgs.game_id
  and (pgs.season is null or pgs.game_date is null);

-- Tables the unified schema adds (verbatim from 001) --------------
create table if not exists season_totals (
    player_id         bigint not null references players(player_id),
    season            int not null,        -- e.g. 20252026
    team_name         text,
    games_played      int not null,
    goals             int not null,
    assists           int not null,
    points            int not null,
    shots             int,
    shooting_pctg     double precision,
    avg_toi_seconds   int,
    plus_minus        int,
    pim               int,
    power_play_points int,
    primary key (player_id, season)
);

create table if not exists cooked_scores (
    player_id            bigint primary key references players(player_id),
    season               int not null,
    score                double precision,   -- 0..100, null when not enough data
    label                text not null,      -- Fresh ... Cooked / Too Fresh to Judge
    status               text not null,      -- scored | not_enough_data | goalie
    games_played         int,
    points_per_game      double precision,
    peak_points_per_game double precision,
    signals              text,               -- JSON breakdown for the UI
    computed_at          text not null
);

create index if not exists idx_st_season on season_totals(season);

-- player_game_rates_v selects pgs.*, whose column list just grew —
-- `create or replace` can't insert columns mid-view, so drop first
-- and recreate with the definition from 002 ------------------------
drop view if exists player_game_rates_v;
create view player_game_rates_v as
select
    pgs.*,
    case when pgs.toi_seconds > 0
         then round((pgs.points::numeric / pgs.toi_seconds) * 3600, 2)
         else null end as points_per_60,
    case when pgs.shots > 0
         then round(pgs.goals::numeric / pgs.shots, 3)
         else null end as shooting_pct,
    case when (pgs.faceoff_wins + pgs.faceoff_losses) > 0
         then round(pgs.faceoff_wins::numeric / (pgs.faceoff_wins + pgs.faceoff_losses), 3)
         else null end as faceoff_win_pct
from player_game_stats pgs;

-- cooked_scores exists now, so 002's leaderboard view can too ------
create or replace view cooked_leaderboard_v as
select
    cs.player_id,
    p.full_name,
    p.position,
    p.current_team_id as team_id,
    cs.season,
    cs.score,
    cs.label,
    cs.games_played,
    cs.points_per_game,
    cs.peak_points_per_game,
    cs.computed_at
from cooked_scores cs
join players p on p.player_id = cs.player_id
where cs.status = 'scored';
