-- ============================================================
-- Vegas Flu — players whose scoring craters (or spikes) when
-- visiting T-Mobile Arena, vs their performance in every OTHER
-- regular-season road game. Road-vs-road comparison removes the
-- normal home/road split, isolating the Vegas effect.
--
-- Rules: regular season only (no playoffs/preseason), VGK players
-- excluded (home teams can't catch the flu), min 5 Vegas games and
-- 20 other road games. Negative vegas_flu_ppg = caught the flu.
--
-- SOG comes from shot_events, NOT player_game_stats.shots — that
-- column was never populated by the boxscore ETL (255 shots across
-- 452k rows as of 2026-07-12).
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view player_vegas_flu_v as
with sog as (
  select game_id, shooter_id as player_id,
         count(*) as sog
  from shot_events
  where event_type in ('shot-on-goal', 'goal')
  group by game_id, shooter_id
),
rs as (
  select pgs.player_id,
         pgs.points, pgs.goals, coalesce(sog.sog, 0) as sog,
         (g.home_team_id = 'VGK' and pgs.team_id = g.away_team_id) as in_vegas,
         (pgs.team_id = g.away_team_id) as is_road
  from player_game_stats pgs
  join games g on g.game_id = pgs.game_id
  left join sog on sog.game_id = pgs.game_id and sog.player_id = pgs.player_id
  where g.game_type = 'regular'      -- no playoffs, no preseason
    and pgs.team_id <> 'VGK'         -- home teams can't catch the Vegas flu
),
per_player as (
  select player_id,
    count(*) filter (where in_vegas) as vegas_gp,
    avg(points) filter (where in_vegas) as vegas_ppg,
    avg(goals)  filter (where in_vegas) as vegas_gpg,
    avg(sog)    filter (where in_vegas) as vegas_sog_pg,
    count(*) filter (where is_road and not in_vegas) as road_gp,
    avg(points) filter (where is_road and not in_vegas) as road_ppg,
    avg(goals)  filter (where is_road and not in_vegas) as road_gpg,
    avg(sog)    filter (where is_road and not in_vegas) as road_sog_pg
  from rs
  group by player_id
)
select
  p.player_id, p.full_name, p.position,
  pp.vegas_gp, pp.road_gp,
  round(pp.vegas_ppg, 2)  as vegas_ppg,
  round(pp.road_ppg, 2)   as road_ppg,
  round(pp.vegas_ppg - pp.road_ppg, 2) as vegas_flu_ppg,
  round(pp.vegas_gpg - pp.road_gpg, 2) as vegas_flu_goals,
  round(pp.vegas_sog_pg, 2) as vegas_sog_per_game,
  round(pp.road_sog_pg, 2)  as road_sog_per_game,
  round(pp.vegas_sog_pg - pp.road_sog_pg, 2) as vegas_flu_sog
from per_player pp
join players p on p.player_id = pp.player_id
where pp.vegas_gp >= 5          -- minimum sample
  and pp.road_gp >= 20          -- baseline needs a real road sample too
  and p.position <> 'G';
