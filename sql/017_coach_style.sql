-- ============================================================
-- Coach style/tendency fingerprint — how a team plays under a coach,
-- built on shot_xg_v (sql/016). These are STYLE metrics (shot selection,
-- chance quality, blocking, tempo), which are more coach-attributable
-- than win/loss impact — a team's shooting/defensive identity is a
-- systemic choice, less roster-driven than results.
--
-- Regular season only. Two caveats baked into how you read the output:
--   * avg_shift_sec is the noisiest field — shift counts are ~85%
--     populated, so games missing shift data bias it high. Weakest metric.
--   * gsax uses the season-pooled xg_grid, so its ABSOLUTE value carries a
--     season-level calibration offset (a season that finishes above the
--     8-yr mean skews the whole league negative). Read it within-season /
--     rank-relative, not across seasons.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

-- Foundation: one row per (game, team/coach) — two per game — with the raw
-- for/against inputs. coach_style_v / coach_homeroad_v aggregate from here.
create or replace view coach_game_v as
with team_games as (
  select game_id, season, game_type, game_date,
         home_team_id as team, away_team_id as opp, home_coach as coach,
         true as is_home, home_score as gf, away_score as ga
  from games where home_coach is not null and game_type = 'regular'
  union all
  select game_id, season, game_type, game_date,
         away_team_id, home_team_id, away_coach,
         false, away_score, home_score
  from games where away_coach is not null and game_type = 'regular'
),
se_agg as (
  select game_id, team_id,
    count(*) as cf,
    count(*) filter (where event_type <> 'blocked-shot') as ff,
    count(*) filter (where event_type = 'blocked-shot') as blocked_att,
    count(*) filter (where event_type <> 'blocked-shot' and shot_type in ('tip-in','deflected')) as tips,
    count(*) filter (where event_type <> 'blocked-shot' and shot_type = 'slap') as slaps
  from shot_events
  group by game_id, team_id
),
xg_agg as (
  select game_id, team_id,
    sum(xg) as xg,
    count(*) as shots_onnet,
    sum(is_goal) as goals_onnet,
    sum(shot_distance) as dist_sum
  from shot_xg_v
  group by game_id, team_id
),
box as (
  select game_id, team_id,
    sum(penalty_minutes) as pim,
    sum(toi_seconds) as toi,
    sum(shifts) as shifts
  from player_game_stats
  group by game_id, team_id
)
select
  tg.game_id, tg.season, tg.game_type, tg.game_date,
  tg.coach, tg.team, tg.opp, tg.is_home, tg.gf, tg.ga,
  sef.cf, sef.ff, xf.xg as xgf, xf.shots_onnet as shots_for, xf.dist_sum as dist_for_sum,
  sef.tips as tips_for, sef.slaps as slaps_for,
  sea.cf as ca, sea.ff as fa, xa.xg as xga, xa.shots_onnet as shots_against,
  xa.dist_sum as dist_against_sum,
  sea.blocked_att as blocks_by_team,
  xa.goals_onnet as ga_onnet,
  bx.pim, bx.toi, bx.shifts
from team_games tg
left join se_agg sef on sef.game_id = tg.game_id and sef.team_id = tg.team
left join se_agg sea on sea.game_id = tg.game_id and sea.team_id = tg.opp
left join xg_agg xf  on xf.game_id  = tg.game_id and xf.team_id  = tg.team
left join xg_agg xa  on xa.game_id  = tg.game_id and xa.team_id  = tg.opp
left join box bx     on bx.game_id  = tg.game_id and bx.team_id  = tg.team;

-- The fingerprint, per (coach, team, season), min 20 GP.
create or replace view coach_style_v as
select
  coach, team, season,
  count(*) as gp,
  round(avg(gf),2) as gf_per_game,
  round(avg(ga),2) as ga_per_game,
  -- shooting identity
  round(avg(cf),1) as cf_per_game,
  round(avg(xgf),2) as xgf_per_game,
  round(sum(xgf)/nullif(sum(shots_for),0),4) as xg_per_shot_for,
  round(sum(dist_for_sum)/nullif(sum(shots_for),0),1) as avg_shot_dist_for,
  round(100.0*sum(tips_for)/nullif(sum(ff),0),1) as tip_pct_for,
  round(100.0*sum(slaps_for)/nullif(sum(ff),0),1) as slap_pct_for,
  -- defensive identity
  round(avg(ca),1) as ca_per_game,
  round(avg(xga),2) as xga_per_game,
  round(sum(xga)/nullif(sum(shots_against),0),4) as xga_per_shot,
  round(100.0*sum(blocks_by_team)/nullif(sum(ca),0),1) as block_pct,
  -- goaltending decomposition
  round(100.0*(1 - sum(ga_onnet)::numeric/nullif(sum(shots_against),0)),2) as team_sv_pct,
  round(sum(xga)-sum(ga_onnet),1) as gsax,
  -- tempo / discipline
  round(sum(toi)/nullif(sum(shifts),0),1) as avg_shift_sec,
  round(avg(pim),1) as pim_per_game
from coach_game_v
group by coach, team, season
having count(*) >= 20;

-- Same core metrics split home vs road (last-change / home-system effects).
create or replace view coach_homeroad_v as
select
  coach, team, season,
  case when is_home then 'home' else 'road' end as venue,
  count(*) as gp,
  round(avg(cf),1) as cf_per_game,
  round(avg(xgf),2) as xgf_per_game,
  round(avg(xga),2) as xga_per_game,
  round(sum(xgf)/nullif(sum(shots_for),0),4) as xg_per_shot_for,
  round(sum(xga)/nullif(sum(shots_against),0),4) as xga_per_shot,
  round(100.0*sum(blocks_by_team)/nullif(sum(ca),0),1) as block_pct,
  round(avg(gf),2) as gf_per_game,
  round(avg(ga),2) as ga_per_game
from coach_game_v
group by coach, team, season, is_home
having count(*) >= 10;
