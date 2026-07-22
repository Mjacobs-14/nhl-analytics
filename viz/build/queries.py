"""
The SQL behind every viz/ snapshot — the single source of truth for how each
page's numbers are defined.

These were reverse-engineered from the original snapshot dumps and verified
row-for-row against them (see viz/build/README.md for verification status).
If a definition here is ambiguous, THIS file is the answer — that ambiguity is
exactly what caused issue #26 (the RUSH definition drift in the /matchup port).
"""

# ---------------------------------------------------------------- matchup lab
# Four datasets. Verified against the 2026-07-14 snapshot:
#   st 1518 rows, gp 506, rush 253, goalies 790 (145 with NULL bands) — all exact.
MATCHUP = {
    # Team shot-location profiles by venue x strength. The view's columns are
    # already exactly the snapshot's fields.
    "st": "select * from team_strength_location_v",

    # Games played per season/team/venue (denominator for per-game rates).
    "gp": """
        select season, team, venue, count(*) as gp
        from (
          select season, home_team_id as team, 'home' as venue, game_id
            from games where game_type='regular'
          union all
          select season, away_team_id, 'road', game_id
            from games where game_type='regular'
        ) x
        group by season, team, venue
        order by season, team, venue
    """,

    # RUSH — the definition that drifted in #26. It is the is_rush share of ALL
    # shot attempts (all four event_types), REGULAR SEASON ONLY, at season x team.
    # NOT on-net only (that gives DAL 2025-26 = 8.7), NOT including playoffs (9.5).
    # Correct value: DAL 2025-26 = 9.7071 -> 9.7.
    # Do NOT source this from coach_rush_v: that view is coach-scoped and silently
    # drops games when a team changed coach (2025-26 VGK = 74 of 82 games).
    "rush": """
        with se as (
          select g.season, se.team_id, se.is_rush,
                 case when se.team_id = g.home_team_id then g.away_team_id
                      else g.home_team_id end as def_team
          from shot_events se
          join games g on g.game_id = se.game_id
          where g.game_type='regular'
        ),
        f as (select season, team_id as team,
                     round(100.0*count(*) filter (where is_rush)/count(*), 1) as rush_for
              from se group by season, team_id),
        a as (select season, def_team as team,
                     round(100.0*count(*) filter (where is_rush)/count(*), 1) as rush_against
              from se group by season, def_team)
        select f.season, f.team, f.rush_for, a.rush_against
        from f join a on a.season=f.season and a.team=f.team
        order by f.season, f.team
    """,

    # Goalies available per season x team: TOP 4 BY SHOTS FACED for that team.
    # LEFT join to goalie_location_v so sub-1500-shot goalies still appear in the
    # dropdown with NULL bands (145 such rows). gk_name is players.full_name
    # verbatim — the table already stores some names abbreviated ("C. Johnson").
    # Traded goalies intentionally appear once per team (not merged to one team).
    "goalies": """
        with gk as (
          select s.season, s.def_team as team, s.goalie_id, count(*) as shots
          from shot_xg_v s
          where s.game_type='regular' and s.goalie_id is not null
          group by s.season, s.def_team, s.goalie_id
        ),
        ranked as (
          select *, row_number() over (partition by season, team order by shots desc) as rn
          from gk
        )
        select r.season, r.team, p.full_name as gk_name, r.shots,
               gl.sv_hd, gl.sv_md, gl.sv_ld
        from ranked r
        join players p on p.player_id = r.goalie_id
        left join goalie_location_v gl on gl.player_id = r.goalie_id
        where r.rn <= 4
        order by r.season, r.team, r.shots desc
    """,
}

# ------------------------------------------------------------ goalie hot hand
# goalie_streak_v (80 rows, min 100 starts) + a per-season start timeline.
GOALIE = """
    select gs.*,
      (select json_object_agg(season, arr) from (
         select gg.season, json_agg(gg.sv_pct order by gg.game_date) as arr
         from goalie_game_v gg
         where gg.player_id = gs.player_id
         group by gg.season
       ) s) as timeline
    from goalie_streak_v gs
    order by gs.starts desc
"""

# --------------------------------------------------------------- shot quadrants
# Verified: 5563 rows, exact match to snapshot.
QUADRANTS = "select * from player_shot_volume_output_v"

# ------------------------------------------------------------ edge athleticism
# NHL Edge tracking, 2021-22 onward. Rows without tracking data are dropped.
# NOTE: row count drifts from the 2026-07-14 snapshot (3552 then, 4733 now) —
# Edge data has been backfilled since. The definition is unchanged.
EDGE = """
    select * from player_athleticism_v
    where top_skating_speed_mph is not null
"""

# ---------------------------------------------------------- coach fingerprints
# Verified: 282 rows, and the style<->rush join is 1:1 at (coach, team, season).
COACH_STYLE = """
    select cs.*, cr.rush_for_pct, cr.rush_against_pct
    from coach_style_v cs
    join coach_rush_v cr
      on cr.coach = cs.coach and cr.team = cs.team and cr.season = cs.season
    order by cs.season, cs.team
"""

# Mid-season coach-change turnarounds. The original builder read a derived
# coach_changes.json that no longer exists; these are exactly the 13 columns the
# page embeds (verified field-for-field against the committed HTML's CH array —
# e.g. 2025-26 LAK Hiller->Smith matches on all 13).
# The >=10 games guard keeps tiny-sample turnarounds out. NOTE: the original
# snapshot had 30 rows; the view now yields 37 under this filter (coach-change
# data has grown). Descriptive section only — affects no other page's numbers.
COACH_CHANGE = """
    select season, team, out_coach, in_coach, out_gp, in_gp,
           out_xgf_pct, in_xgf_pct, d_xgf_pct,
           out_goal_diff, in_goal_diff, d_goal_diff, d_win_pct
    from coach_change_v
    where out_gp >= 10 and in_gp >= 10
    order by season desc, team
"""

# ------------------------------------------------------------------- clutch
# Points-by-game-state. The pts>=10 floor is what the original snapshot used
# (verified: 6615 rows unfiltered -> 4482 at pts>=10, exactly the committed
# page's record count). It keeps the embedded payload small; the page then
# applies its own stricter pts>=30 filter for the scatter.
CLUTCH = "select * from player_clutch_v where pts >= 10"

ALL = {
    "matchup": MATCHUP, "goalie": GOALIE, "quadrants": QUADRANTS,
    "edge": EDGE, "coach_style": COACH_STYLE, "coach_change": COACH_CHANGE,
    "clutch": CLUTCH,
}
