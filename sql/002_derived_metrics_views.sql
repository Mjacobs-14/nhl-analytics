-- ============================================================
-- Derived / Custom Metrics — Views
-- This is your "add a formula without touching the raw data" layer.
-- To add a new stat: write a new view (or add a column to an existing
-- one) here, run it in the SQL Editor, and it's instantly queryable —
-- no changes needed to the ETL pipeline or raw tables.
-- ============================================================

-- Per-player, per-game rate stats -------------------------------------------------------
create or replace view player_game_rates_v as
select
    pgs.*,
    -- points per 60 minutes of ice time
    case when pgs.toi_seconds > 0
         then round((pgs.points::numeric / pgs.toi_seconds) * 3600, 2)
         else null end as points_per_60,

    -- shooting efficiency
    case when pgs.shots > 0
         then round(pgs.goals::numeric / pgs.shots, 3)
         else null end as shooting_pct,

    -- faceoff win pct (only meaningful for centers)
    case when (pgs.faceoff_wins + pgs.faceoff_losses) > 0
         then round(pgs.faceoff_wins::numeric / (pgs.faceoff_wins + pgs.faceoff_losses), 3)
         else null end as faceoff_win_pct
from player_game_stats pgs;

-- Season-level aggregation per player -------------------------------------------------------
create or replace view player_season_totals_v as
select
    p.player_id,
    p.full_name,
    p.position,
    g.season,
    count(distinct pgs.game_id)                as games_played,
    sum(pgs.goals)                              as goals,
    sum(pgs.assists)                            as assists,
    sum(pgs.points)                             as points,
    sum(pgs.shots)                              as shots,
    sum(pgs.toi_seconds)                        as toi_seconds,
    round(sum(pgs.toi_seconds) / nullif(count(distinct pgs.game_id),0) / 60.0, 2) as avg_toi_minutes,
    round(
      case when sum(pgs.toi_seconds) > 0
           then (sum(pgs.points)::numeric / sum(pgs.toi_seconds)) * 3600
           else null end, 2
    ) as points_per_60,
    round(
      case when sum(pgs.shots) > 0
           then sum(pgs.goals)::numeric / sum(pgs.shots)
           else null end, 3
    ) as shooting_pct
from player_game_stats pgs
join players p on p.player_id = pgs.player_id
join games g   on g.game_id = pgs.game_id
group by p.player_id, p.full_name, p.position, g.season;

-- Team season totals + simple possession proxy -------------------------------------------------------
create or replace view team_season_totals_v as
select
    t.team_id,
    t.team_name,
    g.season,
    count(distinct tgs.game_id)          as games_played,
    sum(tgs.goals)                       as goals_for,
    sum(tgs.shots)                       as shots_for,
    sum(tgs.giveaways)                   as giveaways,
    sum(tgs.takeaways)                   as takeaways,
    -- crude puck-possession proxy: takeaways minus giveaways per game
    round(
      (sum(tgs.takeaways) - sum(tgs.giveaways))::numeric
      / nullif(count(distinct tgs.game_id),0), 2
    ) as possession_margin_per_game
from team_game_stats tgs
join teams t on t.team_id = tgs.team_id
join games g on g.game_id = tgs.game_id
group by t.team_id, t.team_name, g.season;

-- Cooked Score leaderboard -------------------------------------------------------
-- Model output (scripts/cook.ts) joined with player bios, ready for
-- dashboards/notebooks. The Next.js app reads the tables directly.
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

-- ============================================================
-- TEMPLATE for adding your own underrepresented metric:
--
-- create or replace view my_new_metric_v as
-- select
--     <keys>,
--     <your formula here> as my_metric_name
-- from <base table(s)>;
--
-- Then query it directly from the dashboard/analysis code —
-- no ETL or schema migration needed.
-- ============================================================
