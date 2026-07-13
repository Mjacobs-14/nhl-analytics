-- ============================================================
-- Rush-vs-cycle coach identity — how much of a team's offense comes
-- off the rush (quick transition) vs. off the cycle/set play, and how
-- many rush chances it surrenders. Reads shot_events.is_rush
-- (etl/pull_play_by_play.py). Regular season, min 20 GP.
--
-- Only classified games (is_rush not null) contribute, so this view is
-- correct at any stage of the is_rush backfill — gp reflects how many
-- games are classified so far. It becomes meaningful once the
-- `--refresh-shots` backfill has covered a full season.
--
--   rush_for_pct     — share of the team's own shot attempts off the rush
--   rush_against_pct — share of opponents' attempts (vs this team) off the rush
--   rush_differential — for minus against (positive = more rush-driven than
--                       the rush chances it allows)
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view coach_rush_v as
with team_games as (
  select game_id, season, home_team_id as team, away_team_id as opp, home_coach as coach
  from games where home_coach is not null and game_type='regular'
  union all
  select game_id, season, away_team_id, home_team_id, away_coach
  from games where away_coach is not null and game_type='regular'
),
shots as (
  select game_id, team_id,
    count(*) as attempts,
    count(*) filter (where is_rush) as rush
  from shot_events
  where is_rush is not null
  group by game_id, team_id
)
select tg.coach, tg.team, tg.season,
  count(*) as gp,
  round(100.0*sum(sf.rush)/nullif(sum(sf.attempts),0),1) as rush_for_pct,
  round(100.0*sum(sa.rush)/nullif(sum(sa.attempts),0),1) as rush_against_pct,
  round((100.0*sum(sf.rush)/nullif(sum(sf.attempts),0))
      - (100.0*sum(sa.rush)/nullif(sum(sa.attempts),0)),1) as rush_differential
from team_games tg
join shots sf on sf.game_id=tg.game_id and sf.team_id=tg.team
join shots sa on sa.game_id=tg.game_id and sa.team_id=tg.opp
group by tg.coach, tg.team, tg.season
having count(*) >= 20;
