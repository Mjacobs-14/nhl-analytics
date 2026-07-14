-- ============================================================
-- Goalie streakiness / consistency — who runs hot, who runs cold,
-- who bounces back. Per-game save % is reconstructed from shot_events
-- (goalie_id sits on every on-net shot; empty-net goals are already
-- excluded since they have no goalie in net). A "start" = >= 15 shots
-- faced, to drop brief relief appearances.
--
-- A "hot" start clears .900 save % (~ the median start over 2018-2026,
-- so it splits ~50/50 — good for run analysis). Runs and start-to-start
-- transitions are computed WITHIN a season (streaks don't cross the
-- offseason), then pooled across the goalie's career (min 100 starts).
--
--   hot_rate            - share of starts that clear .900
--   longest_hot_streak  - gets hot and stays hot
--   longest_cold_streak - stays cold longest
--   avg_hot_run / avg_cold_run - typical run lengths
--   p_hot_after_hot     - stays-hot persistence
--   p_hot_after_cold    - bounce-back rate (hot right after a cold start)
--   streakiness         - p_hot_after_hot - p_hot_after_cold. ~0 = starts are
--                         independent (consistent); high = clustered (streaky).
--                         This DIFFERENCE is base-rate independent, so it's the
--                         clean clustering signal; the raw p_* rates and
--                         longest_hot_streak are partly confounded by how good
--                         the goalie is overall. Descriptive, noisy on small n.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create or replace view goalie_game_v as
select se.goalie_id as player_id, p.full_name, g.season, g.game_date, se.game_id,
  count(*) filter (where se.event_type in ('shot-on-goal','goal')) as shots_faced,
  count(*) filter (where se.event_type='goal') as goals_against,
  round(1.0 - count(*) filter (where se.event_type='goal')::numeric
    / nullif(count(*) filter (where se.event_type in ('shot-on-goal','goal')),0), 4) as sv_pct
from shot_events se
join games g on g.game_id = se.game_id
join players p on p.player_id = se.goalie_id
where se.goalie_id is not null and g.game_type = 'regular'
group by se.goalie_id, p.full_name, g.season, g.game_date, se.game_id
having count(*) filter (where se.event_type in ('shot-on-goal','goal')) >= 15;

create or replace view goalie_streak_v as
with base as (
  select player_id, full_name, season, game_id, game_date, sv_pct, (sv_pct >= 0.9) as hot
  from goalie_game_v
),
lagged as (
  select *, lag(hot) over (partition by player_id, season order by game_date, game_id) as prev_hot
  from base
),
runs as (
  select player_id, hot,
    row_number() over (partition by player_id, season order by game_date, game_id)
    - row_number() over (partition by player_id, season, hot order by game_date, game_id) as grp
  from base
),
run_len as (select player_id, hot, count(*) as len from runs group by player_id, hot, grp),
run_agg as (
  select player_id,
    max(len) filter (where hot)     as longest_hot_streak,
    max(len) filter (where not hot) as longest_cold_streak,
    round(avg(len) filter (where hot),2)     as avg_hot_run,
    round(avg(len) filter (where not hot),2) as avg_cold_run
  from run_len group by player_id
),
trans as (
  select player_id, full_name,
    count(*) as starts,
    round(avg(hot::int),3) as hot_rate,
    round(avg(hot::int) filter (where prev_hot),3)          as p_hot_after_hot,
    round(avg(hot::int) filter (where prev_hot is false),3) as p_hot_after_cold
  from lagged group by player_id, full_name
),
career as (
  select player_id, round(1.0 - sum(goals_against)::numeric / nullif(sum(shots_faced),0), 4) as sv_pct
  from goalie_game_v group by player_id
)
select t.player_id, t.full_name, t.starts, c.sv_pct as career_sv_pct, t.hot_rate,
  ra.longest_hot_streak, ra.longest_cold_streak, ra.avg_hot_run, ra.avg_cold_run,
  t.p_hot_after_hot, t.p_hot_after_cold,
  round(t.p_hot_after_hot - t.p_hot_after_cold, 3) as streakiness
from trans t
join run_agg ra on ra.player_id = t.player_id
join career c on c.player_id = t.player_id
where t.starts >= 100;
