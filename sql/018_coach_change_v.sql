-- ============================================================
-- Coaching-change impact board — the natural experiments. For each
-- mid-season coaching change, the team's before-vs-after deltas: same
-- roster, same season, so this is the closest thing to a causal coach
-- signal (far less roster-confounded than season-long rankings).
--
-- One row per change, pairing the outgoing coach's stint with the
-- incoming coach's. Filter by out_gp / in_gp for sample size — short
-- interim stints are noisy. win_pct is a simple gf>ga share (ignores
-- OT/SO outcome nuance we don't cleanly store), so lean on d_xgf_pct /
-- d_goal_diff as the underlying-performance signals.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view coach_change_v as
with stint as (
  select season, team, coach,
    count(*) as gp,
    min(game_date) as first_game,
    sum((gf > ga)::int) as wins,
    avg(gf) as gf_pg, avg(ga) as ga_pg,
    sum(cf) as cf_sum, sum(ca) as ca_sum,
    sum(xgf) as xgf_sum, sum(xga) as xga_sum
  from coach_game_v
  group by season, team, coach
),
seq as (
  select *,
    row_number() over (partition by season, team order by first_game) as stint_no
  from stint
),
paired as (
  select
    a.season, a.team,
    a.coach as out_coach, b.coach as in_coach,
    a.gp as out_gp, b.gp as in_gp,
    round(100.0*a.wins/a.gp,1) as out_win_pct, round(100.0*b.wins/b.gp,1) as in_win_pct,
    round((a.gf_pg - a.ga_pg)::numeric,2) as out_goal_diff,
    round((b.gf_pg - b.ga_pg)::numeric,2) as in_goal_diff,
    round(100.0*a.cf_sum/(a.cf_sum+a.ca_sum),1) as out_cf_pct,
    round(100.0*b.cf_sum/(b.cf_sum+b.ca_sum),1) as in_cf_pct,
    round(100.0*a.xgf_sum/(a.xgf_sum+a.xga_sum),1) as out_xgf_pct,
    round(100.0*b.xgf_sum/(b.xgf_sum+b.xga_sum),1) as in_xgf_pct
  from seq a
  join seq b on b.season=a.season and b.team=a.team and b.stint_no = a.stint_no + 1
)
select *,
  round(in_win_pct  - out_win_pct, 1)  as d_win_pct,
  round(in_goal_diff - out_goal_diff, 2) as d_goal_diff,
  round(in_cf_pct   - out_cf_pct, 1)   as d_cf_pct,
  round(in_xgf_pct  - out_xgf_pct, 1)  as d_xgf_pct
from paired;
