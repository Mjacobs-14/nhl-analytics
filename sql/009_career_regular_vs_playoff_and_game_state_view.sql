-- ============================================================
-- Career regular-vs-playoff table + refresh function, and the
-- per-game-state points view — reconstructed from the live DB.
-- Same category of gap as sql/003 and sql/007: these existed live
-- but were only ever created via the Supabase SQL Editor.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

-- PLAYER CAREER REGULAR VS PLAYOFF STATS ---------------------------
-- A refreshed-on-demand table (not a view) — no trigger keeps it in
-- sync automatically, call refresh_player_career_regular_vs_playoff_stats()
-- after backfills or whenever career totals should reflect new games.
create table if not exists player_career_regular_vs_playoff_stats (
    player_id                  bigint primary key references players(player_id),
    full_name                  text,
    position                   text,
    regular_games_played       int,
    regular_points             int,
    regular_avg_ppg            numeric,
    playoff_games_played       int,
    playoff_points             int,
    playoff_avg_ppg            numeric,
    playoff_vs_regular_ppg_gap numeric,
    refreshed_at               timestamptz default now()
);

create or replace function refresh_player_career_regular_vs_playoff_stats()
returns void
language plpgsql
as $function$
begin
    truncate table player_career_regular_vs_playoff_stats;

    insert into player_career_regular_vs_playoff_stats (
        player_id, full_name, position,
        regular_games_played, regular_points, regular_avg_ppg,
        playoff_games_played, playoff_points, playoff_avg_ppg,
        playoff_vs_regular_ppg_gap
    )
    select
        p.player_id,
        p.full_name,
        p.position,

        sum(pgs.games_played) filter (where pgs.game_type = 'regular'),
        sum(pgs.points)       filter (where pgs.game_type = 'regular'),
        round(
            sum(pgs.points) filter (where pgs.game_type = 'regular')::numeric
            / nullif(sum(pgs.games_played) filter (where pgs.game_type = 'regular'), 0)
        , 2),

        sum(pgs.games_played) filter (where pgs.game_type = 'playoff'),
        sum(pgs.points)       filter (where pgs.game_type = 'playoff'),
        round(
            sum(pgs.points) filter (where pgs.game_type = 'playoff')::numeric
            / nullif(sum(pgs.games_played) filter (where pgs.game_type = 'playoff'), 0)
        , 2),

        round(
            (sum(pgs.points) filter (where pgs.game_type = 'playoff')::numeric
                / nullif(sum(pgs.games_played) filter (where pgs.game_type = 'playoff'), 0))
            -
            (sum(pgs.points) filter (where pgs.game_type = 'regular')::numeric
                / nullif(sum(pgs.games_played) filter (where pgs.game_type = 'regular'), 0))
        , 2)

    from player_season_totals_by_type_v pgs
    join players p on p.player_id = pgs.player_id
    where p.position != 'G'
    group by p.player_id, p.full_name, p.position;
end;
$function$;

-- PLAYER POINTS BY GAME STATE ---------------------------------------
-- Goals/assists/points split by the score situation they happened in
-- (tied, up_1, down_2, etc. — from goal_events / player_game_state_events).
create or replace view player_points_by_game_state_v as
select
    p.player_id,
    p.full_name,
    p.position,
    g.season,
    g.game_type,
    e.game_state_before,
    count(*) filter (where e.role = 'goal')   as goals,
    count(*) filter (where e.role = 'assist') as assists,
    count(*)                                  as points
from player_game_state_events e
join players p on p.player_id = e.player_id
join games   g on g.game_id   = e.game_id
group by p.player_id, p.full_name, p.position, g.season, g.game_type, e.game_state_before;
