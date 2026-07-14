-- ============================================================
-- Shot-location profiles: goalie save % by danger band, and team
-- shoot-from / allow-from mixes. Built on shot_xg_v; "location" is
-- collapsed to xG danger bands (what location actually implies):
--   high >= .15 xG | mid .05-.15 | low < .05
-- League goal rates ~19.6 / 9.7 / 2.5% — an 8x gap between bands.
--
-- goalie_location_v (career, min 1500 shots faced):
--   sv_hd/md/ld           - save % by band
--   sv_*_above_exp        - band save % minus the league's band save %.
--     sv_hd_above_exp is the "slot robbery" skill, separated from
--     padding numbers on perimeter shots. Caveat: survivorship — goalies
--     bad in the slot rarely reach 1500 shots, so the filtered pool
--     skews at-or-above league.
--
-- team_shot_location_v (per season):
--   off_*_share - where the team's own on-net shots come from
--   def_*_share - where opponents' shots against them come from
--
-- Matchup-preview building block: expected goals for team A vs team B ~
-- blend(A's off mix, B's def mix) x B's shots-against volume, priced by
-- B's goalie band save %. All three factors live in these two views.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view goalie_location_v as
with s as (
  select goalie_id, is_goal,
    case when xg >= 0.15 then 'hd' when xg >= 0.05 then 'md' else 'ld' end as band
  from shot_xg_v where game_type = 'regular'
),
lg as (
  select band, avg(is_goal::numeric) as gr from s group by band
),
g as (
  select goalie_id, band, count(*) n, sum(is_goal) ga from s group by goalie_id, band
),
piv as (
  select goalie_id,
    sum(n) as shots_faced, sum(ga) as goals_against,
    sum(n)  filter (where band='hd') as hd_shots,
    sum(ga) filter (where band='hd') as hd_ga,
    sum(n)  filter (where band='md') as md_shots,
    sum(ga) filter (where band='md') as md_ga,
    sum(n)  filter (where band='ld') as ld_shots,
    sum(ga) filter (where band='ld') as ld_ga
  from g group by goalie_id
)
select p.goalie_id as player_id, pl.full_name,
  p.shots_faced,
  round(1.0 - p.goals_against::numeric/p.shots_faced, 4) as sv_pct,
  round(1.0 - p.hd_ga::numeric/nullif(p.hd_shots,0), 4) as sv_hd,
  round(1.0 - p.md_ga::numeric/nullif(p.md_shots,0), 4) as sv_md,
  round(1.0 - p.ld_ga::numeric/nullif(p.ld_shots,0), 4) as sv_ld,
  p.hd_shots, p.md_shots, p.ld_shots,
  round((1.0 - p.hd_ga::numeric/nullif(p.hd_shots,0)) - (1.0 - (select gr from lg where band='hd')), 4) as sv_hd_above_exp,
  round((1.0 - p.md_ga::numeric/nullif(p.md_shots,0)) - (1.0 - (select gr from lg where band='md')), 4) as sv_md_above_exp,
  round((1.0 - p.ld_ga::numeric/nullif(p.ld_shots,0)) - (1.0 - (select gr from lg where band='ld')), 4) as sv_ld_above_exp
from piv p join players pl on pl.player_id = p.goalie_id
where p.shots_faced >= 1500;

create or replace view team_shot_location_v as
with s as (
  select season, team_id, def_team, is_goal,
    case when xg >= 0.15 then 'hd' when xg >= 0.05 then 'md' else 'ld' end as band
  from shot_xg_v where game_type = 'regular'
),
o as (
  select season, team_id as team, count(*) n,
    count(*) filter (where band='hd') hd, count(*) filter (where band='md') md,
    count(*) filter (where band='ld') ld
  from s group by season, team_id
),
d as (
  select season, def_team as team, count(*) n,
    count(*) filter (where band='hd') hd, count(*) filter (where band='md') md,
    count(*) filter (where band='ld') ld
  from s group by season, def_team
)
select o.season, o.team,
  o.n as shots_for,
  round(100.0*o.hd/o.n, 1) as off_hd_share,
  round(100.0*o.md/o.n, 1) as off_md_share,
  round(100.0*o.ld/o.n, 1) as off_ld_share,
  d.n as shots_against,
  round(100.0*d.hd/d.n, 1) as def_hd_share,
  round(100.0*d.md/d.n, 1) as def_md_share,
  round(100.0*d.ld/d.n, 1) as def_ld_share
from o join d on d.season = o.season and d.team = o.team;
