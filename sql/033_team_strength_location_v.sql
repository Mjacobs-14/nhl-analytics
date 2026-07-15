-- ============================================================
-- Team shot-location profiles split by venue AND strength state —
-- the matchup model's EV + special-teams decomposition. Strength is
-- derived from situation_code (away-goalie, away-skaters, home-skaters,
-- home-goalie): 'pp' = shooter has the skater advantage, 'sh' =
-- shorthanded, 'ev' = equal. Offense rows count a team's own shots;
-- defense rows count shots faced (when the shooter is on the PP, the
-- defender is on the PK — so a team's 'pp' defense rows ARE its
-- penalty kill). Danger bands as in sql/032 (high >= .15 xG / mid / low).
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view team_strength_location_v as
with s as (
  select season, team_id, def_team,
    case when shooter_is_home then 'home' else 'road' end as off_venue,
    case when shooter_is_home then 'road' else 'home' end as def_venue,
    case
      when length(situation_code)=4 and
           (case when shooter_is_home then substr(situation_code,3,1) else substr(situation_code,2,1) end)::int >
           (case when shooter_is_home then substr(situation_code,2,1) else substr(situation_code,3,1) end)::int
        then 'pp'
      when length(situation_code)=4 and
           (case when shooter_is_home then substr(situation_code,3,1) else substr(situation_code,2,1) end)::int <
           (case when shooter_is_home then substr(situation_code,2,1) else substr(situation_code,3,1) end)::int
        then 'sh'
      else 'ev'
    end as strength,
    xg
  from shot_xg_v where game_type='regular' and situation_code is not null
),
o as (
  select season, team_id as team, off_venue as venue, strength,
    count(*) n, count(*) filter (where xg>=0.15) hd, count(*) filter (where xg>=0.05 and xg<0.15) md
  from s group by 1,2,3,4
),
d as (
  select season, def_team as team, def_venue as venue, strength,
    count(*) n, count(*) filter (where xg>=0.15) hd, count(*) filter (where xg>=0.05 and xg<0.15) md
  from s group by 1,2,3,4
)
select coalesce(o.season,d.season) season, coalesce(o.team,d.team) team,
  coalesce(o.venue,d.venue) venue, coalesce(o.strength,d.strength) strength,
  coalesce(o.n,0) sf, round(100.0*o.hd/nullif(o.n,0),1) off_hd, round(100.0*o.md/nullif(o.n,0),1) off_md,
  coalesce(d.n,0) sa, round(100.0*d.hd/nullif(d.n,0),1) def_hd, round(100.0*d.md/nullif(d.n,0),1) def_md
from o full outer join d
  on d.season=o.season and d.team=o.team and d.venue=o.venue and d.strength=o.strength;
