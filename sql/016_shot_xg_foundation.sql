-- ============================================================
-- Shot xG foundation — an empirical location-based expected-goals
-- model, the shared dependency for coach style/impact metrics and
-- the standalone xG/location work.
--
-- xg_grid: goal probability by (distance bin x angle bin), trained on
-- goalie-present unblocked shots. goalie_id IS NULL is a clean empty-net
-- proxy (3880 of 3884 such shots are empty-net goals), so excluding it
-- removes empty-net distortion and makes GSAx meaningful. Bins are pooled
-- across all seasons for stability. In-sample by construction, so
-- leaguewide sum(xg) = sum(goals) exactly (verified gap: 0.2 of 65,822):
-- this is a descriptive shot-quality model, not a trained/validated
-- predictor (no shot type, rebound, or rush context — those are later).
--
-- Refresh the grid after big backfills with:  select refresh_xg_grid();
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create table if not exists xg_grid (
  dist_bin  int not null,
  angle_bin int not null,
  shots     int not null,
  goals     int not null,
  xg        numeric not null,
  primary key (dist_bin, angle_bin)
);

create or replace function refresh_xg_grid() returns void
language plpgsql
set search_path = public
as $$
begin
  truncate xg_grid;
  insert into xg_grid (dist_bin, angle_bin, shots, goals, xg)
  select
    width_bucket(sqrt(power(89-abs(x_coord),2)+power(y_coord,2)), 0, 90, 18) as dist_bin,
    width_bucket(coalesce(degrees(atan2(abs(y_coord), nullif(89-abs(x_coord),0))), 90), 0, 90, 9) as angle_bin,
    count(*),
    sum((event_type='goal')::int),
    round(avg((event_type='goal')::int), 5)
  from shot_events
  where event_type in ('shot-on-goal','goal')
    and goalie_id is not null
    and x_coord is not null and y_coord is not null
  group by 1, 2;
end;
$$;

select refresh_xg_grid();

-- One row per goalie-present unblocked shot, tagged with its xG plus the
-- game/team context every coach metric needs (shooting team, defending
-- team, home flag, strength state, shot type, distance).
create or replace view shot_xg_v as
with base as (
  select
    se.game_id, se.event_id, se.team_id, se.shooter_id, se.goalie_id,
    se.event_type, se.shot_type, se.situation_code,
    g.season, g.game_type, g.game_date, g.home_team_id, g.away_team_id,
    case when se.team_id = g.home_team_id then g.away_team_id else g.home_team_id end as def_team,
    (se.team_id = g.home_team_id) as shooter_is_home,
    (se.event_type = 'goal')::int as is_goal,
    round(sqrt(power(89-abs(se.x_coord),2) + power(se.y_coord,2))::numeric, 1) as shot_distance,
    width_bucket(sqrt(power(89-abs(se.x_coord),2)+power(se.y_coord,2)), 0, 90, 18) as dist_bin,
    width_bucket(coalesce(degrees(atan2(abs(se.y_coord), nullif(89-abs(se.x_coord),0))), 90), 0, 90, 9) as angle_bin
  from shot_events se
  join games g on g.game_id = se.game_id
  where se.event_type in ('shot-on-goal','goal')
    and se.goalie_id is not null
    and se.x_coord is not null and se.y_coord is not null
)
select b.*, coalesce(gr.xg, 0) as xg
from base b
left join xg_grid gr using (dist_bin, angle_bin);
