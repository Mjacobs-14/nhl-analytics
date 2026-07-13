-- Backfill player_game_stats.shots from shot_events.
--
-- The boxscore ETL read the wrong API field ("shots" instead of "sog"),
-- so the column defaulted to 0 for virtually every row. shot_events has
-- full play-by-play coverage of every game in player_game_stats, and for
-- the 113 rows that did have real boxscore values the PBP-derived count
-- matches 113/113 — so this rebuild is exact, no re-ingest needed.
--
-- SOG = shot-on-goal + goal events, excluding shootout attempts (the
-- boxscore stat doesn't count them). Players with no SOG events in a
-- game genuinely had 0 shots, so missing aggregate rows coalesce to 0.

update player_game_stats s
set shots = coalesce(p.sog, 0)
from (
    select game_id,
           shooter_id as player_id,
           count(*) filter (
               where event_type in ('shot-on-goal', 'goal')
                 and coalesce(period_type, 'REG') <> 'SO'
           )::int as sog
    from shot_events
    group by 1, 2
) p
where s.game_id = p.game_id
  and s.player_id = p.player_id
  and s.shots is distinct from coalesce(p.sog, 0);
