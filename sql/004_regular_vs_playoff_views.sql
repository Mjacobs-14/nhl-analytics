-- ============================================================
-- Regular Season vs. Playoffs — split views
-- The original player_season_totals_v (in 002) combined all
-- game_types together. These versions split them apart, which is
-- what you want when comparing regular season vs. postseason play.
-- ============================================================

-- Season totals, split by game_type -------------------------------------------------------
create or replace view player_season_totals_by_type_v as
select
    p.player_id,
    p.full_name,
    p.position,
    g.season,
    g.game_type,
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
group by p.player_id, p.full_name, p.position, g.season, g.game_type;

-- Side-by-side regular season vs. playoff comparison, per player/season -------------------------------------------------------
create or replace view player_regular_vs_playoff_v as
select
    reg.player_id,
    reg.full_name,
    reg.position,
    reg.season,
    reg.games_played        as regular_games_played,
    reg.points              as regular_points,
    reg.points_per_60        as regular_points_per_60,
    po.games_played          as playoff_games_played,
    po.points                as playoff_points,
    po.points_per_60          as playoff_points_per_60,
    round(po.points_per_60 - reg.points_per_60, 2) as playoff_vs_regular_p60_diff
from player_season_totals_by_type_v reg
left join player_season_totals_by_type_v po
    on po.player_id = reg.player_id
    and po.season = reg.season
    and po.game_type = 'playoff'
where reg.game_type = 'regular';

-- Same split for team totals -------------------------------------------------------
create or replace view team_season_totals_by_type_v as
select
    t.team_id,
    t.team_name,
    g.season,
    g.game_type,
    count(distinct tgs.game_id)          as games_played,
    sum(tgs.goals)                       as goals_for,
    sum(tgs.shots)                       as shots_for,
    sum(tgs.giveaways)                   as giveaways,
    sum(tgs.takeaways)                   as takeaways
from team_game_stats tgs
join teams t on t.team_id = tgs.team_id
join games g on g.game_id = tgs.game_id
group by t.team_id, t.team_name, g.season, g.game_type;
