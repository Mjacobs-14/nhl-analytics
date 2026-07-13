-- ============================================================
-- Shot Volume vs. Output — per-player-season SOG/60 and points
-- per game, the two axes of the quadrant chart (who fires away
-- with little to show for it, who converts modest volume, etc.).
--
-- SOG comes from shot_events (shot-on-goal + goal), NOT
-- player_game_stats.shots — that column was never populated by
-- the boxscore ETL (see issue #5). Regular season only, min 20
-- GP, goalies excluded. Quadrant midlines = per-season medians,
-- computed by the consumer.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view player_shot_volume_output_v as
with sog as (
  select se.shooter_id as player_id, g.season, count(*) as sog
  from shot_events se
  join games g on g.game_id = se.game_id
  where se.event_type in ('shot-on-goal', 'goal')
    and g.game_type = 'regular'
  group by se.shooter_id, g.season
),
base as (
  select pgs.player_id, g.season,
         count(*) as gp,
         sum(pgs.points) as points,
         sum(pgs.goals) as goals,
         sum(pgs.toi_seconds) as toi_seconds
  from player_game_stats pgs
  join games g on g.game_id = pgs.game_id
  where g.game_type = 'regular'
  group by pgs.player_id, g.season
)
select
  p.player_id, p.full_name, p.position, b.season,
  b.gp, b.points, b.goals,
  round(b.points::numeric / b.gp, 2) as ppg,
  coalesce(s.sog, 0) as sog,
  round(coalesce(s.sog, 0) * 3600.0 / nullif(b.toi_seconds, 0), 2) as sog_per_60,
  round(b.toi_seconds / b.gp / 60.0, 1) as toi_min_per_game
from base b
join players p on p.player_id = b.player_id
left join sog s on s.player_id = b.player_id and s.season = b.season
where b.gp >= 20            -- meaningful season sample
  and p.position <> 'G'
  and b.toi_seconds > 0;
