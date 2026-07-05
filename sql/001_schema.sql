-- ============================================================
-- NHL Analytics Database — Core Schema
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

-- TEAMS -------------------------------------------------------
create table if not exists teams (
    team_id      text primary key,       -- e.g. 'BOS', 'TOR' (NHL 3-letter code)
    team_name    text not null,          -- e.g. 'Boston Bruins'
    conference   text,                   -- 'Eastern' / 'Western'
    division     text,                   -- 'Atlantic', 'Metropolitan', etc.
    updated_at   timestamptz default now()
);

-- PLAYERS -------------------------------------------------------
create table if not exists players (
    player_id       bigint primary key,     -- NHL player id
    full_name       text not null,
    position        text,                   -- 'C','L','R','D','G'
    birth_date      date,
    nationality     text,
    shoots_catches  text,                   -- 'L' / 'R'
    current_team_id text references teams(team_id),
    height_cm       numeric,
    weight_kg       numeric,
    updated_at      timestamptz default now()
);

-- GAMES -------------------------------------------------------
create table if not exists games (
    game_id       bigint primary key,   -- NHL game id
    game_date     date not null,
    season        text not null,        -- e.g. '20252026'
    game_type     text,                 -- 'regular', 'playoff', 'preseason'
    home_team_id  text references teams(team_id),
    away_team_id  text references teams(team_id),
    home_score    int,
    away_score    int,
    venue         text,
    updated_at    timestamptz default now()
);

-- PLAYER GAME STATS (raw pull from API, one row per player per game) --------
create table if not exists player_game_stats (
    id               bigserial primary key,
    game_id          bigint references games(game_id),
    player_id        bigint references players(player_id),
    team_id          text references teams(team_id),
    position         text,
    goals            int default 0,
    assists          int default 0,
    points           int generated always as (goals + assists) stored,
    shots            int default 0,
    hits             int default 0,
    blocked_shots    int default 0,
    penalty_minutes  int default 0,
    plus_minus       int default 0,
    powerplay_goals  int default 0,
    powerplay_points int default 0,
    faceoff_wins     int default 0,
    faceoff_losses   int default 0,
    toi_seconds      int default 0,       -- time on ice, in seconds
    unique (game_id, player_id)
);

-- TEAM GAME STATS (one row per team per game) --------
create table if not exists team_game_stats (
    id                    bigserial primary key,
    game_id               bigint references games(game_id),
    team_id               text references teams(team_id),
    goals                 int default 0,
    shots                 int default 0,
    hits                  int default 0,
    penalty_minutes       int default 0,
    powerplay_goals       int default 0,
    powerplay_opportunities int default 0,
    faceoff_win_pct       numeric,
    giveaways             int default 0,
    takeaways             int default 0,
    unique (game_id, team_id)
);

-- Helpful indexes -------------------------------------------------------
create index if not exists idx_pgs_player on player_game_stats(player_id);
create index if not exists idx_pgs_game   on player_game_stats(game_id);
create index if not exists idx_tgs_team   on team_game_stats(team_id);
create index if not exists idx_games_date on games(game_date);
