-- ============================================================
-- Shot locations + game details (officials, attendance).
--
-- shot_events: every unblocked shot attempt (goal / shot-on-goal /
-- missed-shot) with x/y coordinates from the play-by-play feed —
-- populated by etl/pull_play_by_play.py. Blocked shots are excluded
-- on purpose: their coordinates record where the block happened, not
-- where the shot came from, so they poison location analysis.
--
-- games.attendance / referees / linesmen: populated by
-- etl/backfill_game_details.py (attendance comes from the NHL's HTML
-- game reports; officials from the gamecenter right-rail endpoint).
--
-- Idempotent — safe to re-run.
-- ============================================================

alter table games add column if not exists attendance int;
alter table games add column if not exists referees text[];
alter table games add column if not exists linesmen text[];

create table if not exists shot_events (
    game_id        bigint not null references games(game_id),
    event_id       int    not null,
    period         int,
    period_type    text,                -- REG / OT / SO
    time_in_period text,                -- "MM:SS"
    team_id        text,                -- shooting team abbrev
    shooter_id     bigint,
    goalie_id      bigint,
    event_type     text not null,       -- goal | shot-on-goal | missed-shot
    shot_type      text,                -- wrist, snap, slap, ...
    x_coord        smallint,            -- rink coords, +/-100 across the length
    y_coord        smallint,            -- rink coords, +/-42.5 across the width
    zone_code      text,                -- O / N / D from the shooter's perspective
    situation_code text,                -- e.g. 1551 (away goalie/skaters/skaters/home goalie)
    primary key (game_id, event_id)
);

create index if not exists idx_shot_events_shooter on shot_events(shooter_id);
