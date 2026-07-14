-- ============================================================
-- Clutch / game-state production — points by score state per
-- player-season (regular season), from player_game_state_events.
-- Who produces when it's close vs. when the game is already decided.
--
--   pts_tied / up1 / up2 / up3p / down1 / down2 / down3p — the 7 states
--   pts_close      — tied or within one goal
--   pts_blowout    — up or down 3+
--   pts_late_close — 3rd period or OT, tied or within one (the classic
--                    clutch situation); goals_late_close = goals only
--   pts_ot         — overtime (period >= 4)
--
-- League baseline (all seasons pooled): ~69% of points come in close
-- situations, ~21% late-and-close — compare a player's shares against
-- these rather than reading raw counts (time spent in each state biases
-- raw counts). Goalies excluded. primary_team = most games that season.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view player_clutch_v as
with ev as (
  select e.player_id, g.season, e.role, e.game_state_before as st, e.period
  from player_game_state_events e
  join games g on g.game_id = e.game_id
  where g.game_type = 'regular'
),
agg as (
  select player_id, season,
    count(*) as pts,
    count(*) filter (where st='tied')         as pts_tied,
    count(*) filter (where st='up_1')         as pts_up1,
    count(*) filter (where st='up_2')         as pts_up2,
    count(*) filter (where st='up_3_plus')    as pts_up3p,
    count(*) filter (where st='down_1')       as pts_down1,
    count(*) filter (where st='down_2')       as pts_down2,
    count(*) filter (where st='down_3_plus')  as pts_down3p,
    count(*) filter (where st in ('tied','up_1','down_1'))            as pts_close,
    count(*) filter (where st in ('up_3_plus','down_3_plus'))         as pts_blowout,
    count(*) filter (where period>=3 and st in ('tied','up_1','down_1')) as pts_late_close,
    count(*) filter (where period>=3 and st in ('tied','up_1','down_1') and role='goal') as goals_late_close,
    count(*) filter (where period>=4) as pts_ot
  from ev group by player_id, season
),
gp as (
  select s.player_id, g.season, count(*) as gp
  from player_game_stats s join games g on g.game_id=s.game_id
  where g.game_type='regular' group by s.player_id, g.season
)
select p.player_id, p.full_name, p.position, a.season,
  coalesce(gp.gp,0) as gp, pt.team as primary_team,
  a.pts, a.pts_tied, a.pts_up1, a.pts_up2, a.pts_up3p,
  a.pts_down1, a.pts_down2, a.pts_down3p,
  a.pts_close, a.pts_blowout, a.pts_late_close, a.goals_late_close, a.pts_ot
from agg a
join players p on p.player_id = a.player_id
left join gp on gp.player_id=a.player_id and gp.season=a.season
left join lateral (
  select s2.team_id as team from player_game_stats s2
  where s2.player_id=a.player_id and s2.season=a.season
  group by s2.team_id order by count(*) desc limit 1
) pt on true
where p.position <> 'G';
