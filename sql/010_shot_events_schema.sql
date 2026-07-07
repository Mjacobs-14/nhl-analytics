-- ============================================================
-- Shot Events Schema — location + strength-state data for every
-- shot attempt (on goal, missed, blocked, and goals themselves),
-- not just the goals that pull_play_by_play.py already tracked.
-- Backs the shot-location half of etl/pull_play_by_play.py.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create table if not exists shot_events (
    id                 bigserial primary key,
    game_id            bigint references games(game_id),
    event_id           int not null,
    event_type         text not null,      -- 'shot-on-goal' | 'missed-shot' | 'blocked-shot' | 'goal'
    period             int,
    period_type        text,               -- 'REG', 'OT', 'SO'
    time_in_period     text,               -- e.g. '14:32'
    team_id            text references teams(team_id),   -- shooting team
    shooting_player_id bigint references players(player_id),
    goalie_player_id   bigint references players(player_id),
    blocking_player_id bigint references players(player_id),  -- only set on blocked-shot
    x_coord            numeric,            -- rink coordinates, NHL's system
    y_coord            numeric,
    zone_code          text,               -- 'O' / 'D' / 'N'
    shot_type          text,               -- 'wrist', 'slap', 'snap', etc.
    situation_code     text,               -- raw NHL strength code, e.g. '1551' (5v5)
    unique (game_id, event_id)
);

create index if not exists idx_shot_events_shooter on shot_events(shooting_player_id);
create index if not exists idx_shot_events_team    on shot_events(team_id);
create index if not exists idx_shot_events_type    on shot_events(event_type);
