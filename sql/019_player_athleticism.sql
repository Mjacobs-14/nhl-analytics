-- ============================================================
-- Player athleticism (NHL Edge tracking) — 2021-26 regular season.
-- Its own surface, deliberately separate from coach_style_v: speed,
-- bursts, and distance are roster athleticism, not coach system, so they
-- don't belong in the coach fingerprint. Zone-time % is the more
-- system-flavored slice but lives here for a complete athletic profile.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view player_athleticism_v as
select
  e.player_id, p.full_name, p.position, e.season, e.games_played,
  e.top_skating_speed_mph,
  e.bursts_over_20mph,
  round(e.bursts_over_20mph::numeric / nullif(e.games_played,0), 2) as bursts_per_game,
  e.total_skating_distance_miles,
  e.avg_skating_distance_per_game,
  e.top_shot_speed_mph,
  e.offensive_zone_time_pct,
  e.neutral_zone_time_pct,
  e.defensive_zone_time_pct,
  e.skating_speed_percentile,
  e.shot_speed_percentile,
  e.distance_skated_percentile
from player_season_edge_stats e
join players p on p.player_id = e.player_id
where e.game_type = 'regular';
