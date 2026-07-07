-- ============================================================
-- Game State Schema — goal-differential context for every goal
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- Backs etl/pull_play_by_play.py
-- ============================================================

-- GOAL EVENTS (one row per goal, across all games) --------
create table if not exists goal_events (
    id                       bigserial primary key,
    game_id                  bigint references games(game_id),
    event_id                 int not null,
    period                   int,
    period_type              text,          -- 'REG', 'OT', 'SO'
    time_in_period           text,          -- e.g. '14:32'
    scoring_team_id          text references teams(team_id),
    home_score_after         int,
    away_score_after         int,
    scoring_team_diff_before int,           -- scoring team's goal diff right before this goal
    game_state_before        text,          -- 'tied', 'up_1', 'down_2', 'up_3_plus', etc.
    raw_details              jsonb,
    unique (game_id, event_id)
);

-- PLAYER GAME STATE EVENTS (goal + assist attribution, tagged with game state) --------
create table if not exists player_game_state_events (
    id                 bigserial primary key,
    game_id            bigint references games(game_id),
    event_id           int not null,
    player_id          bigint references players(player_id),
    role               text not null,      -- 'goal' / 'assist'
    team_id            text references teams(team_id),
    game_state_before  text not null,
    period             int,
    unique (game_id, event_id, player_id)
);

-- Helpful indexes -------------------------------------------------------
create index if not exists idx_pgse_player on player_game_state_events(player_id);
create index if not exists idx_pgse_state  on player_game_state_events(game_state_before);
