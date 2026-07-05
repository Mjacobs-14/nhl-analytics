-- ============================================================
-- NHL Analytics Database — Core Schema (unified)
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- (or `npm run db:apply`, which runs the sql/ files for you)
--
-- Written by two pipelines:
--   etl/pull_nhl_data.py  — daily boxscores (games, team stats, per-game hits/blocks/faceoffs)
--   scripts/ingest.ts     — rosters, bios, career season totals, current-season game logs
-- and read by the Next.js app + the cooked model (scripts/cook.ts).
--
-- db/schema.ts is the typed mirror of this file — keep them in sync.
-- ============================================================

-- TEAMS -------------------------------------------------------
create table if not exists teams (
    team_id      text primary key,       -- e.g. 'BOS', 'TOR' (NHL 3-letter code)
    team_name    text not null,          -- e.g. 'Boston Bruins'
    conference   text,                   -- 'Eastern' / 'Western'
    division     text,                   -- 'Atlantic', 'Metropolitan', etc.
    logo_url     text,
    updated_at   timestamptz default now()
);

-- PLAYERS -------------------------------------------------------
create table if not exists players (
    player_id       bigint primary key,     -- NHL player id
    full_name       text not null,
    first_name      text,                   -- filled by roster ingest
    last_name       text,                   -- filled by roster ingest
    position        text,                   -- 'C','L','R','D','G'
    birth_date      date,
    nationality     text,
    shoots_catches  text,                   -- 'L' / 'R'
    current_team_id text references teams(team_id),
    sweater_number  int,
    headshot_url    text,
    height_cm       numeric,
    weight_kg       numeric,
    updated_at      timestamptz default now()
);

-- GAMES -------------------------------------------------------
create table if not exists games (
    game_id       bigint primary key,   -- NHL game id
    game_date     date not null,
    season        int not null,         -- e.g. 20252026
    game_type     text,                 -- 'regular', 'playoff', 'preseason'
    home_team_id  text references teams(team_id),
    away_team_id  text references teams(team_id),
    home_score    int,
    away_score    int,
    venue         text,
    updated_at    timestamptz default now()
);

-- PLAYER GAME STATS (one row per player per game) --------
-- Union of the boxscore pull (hits, blocks, faceoffs, ...) and the
-- game-log pull (opponent, home/road, shifts, ...). Each writer fills
-- the columns it knows about; the rest stay null.
create table if not exists player_game_stats (
    id               bigserial primary key,
    game_id          bigint not null references games(game_id),
    player_id        bigint not null references players(player_id),
    team_id          text references teams(team_id),
    season           int,
    game_date        date,
    opponent_abbrev  text,
    home_road        text,                -- 'H' / 'R'
    position         text,
    goals            int not null default 0,
    assists          int not null default 0,
    points           int generated always as (goals + assists) stored,
    shots            int,
    hits             int,
    blocked_shots    int,
    penalty_minutes  int,
    plus_minus       int,
    powerplay_goals  int,
    powerplay_points int,
    faceoff_wins     int,
    faceoff_losses   int,
    toi_seconds      int,                 -- time on ice, in seconds
    shifts           int,
    constraint player_game_stats_game_player_uq unique (game_id, player_id)
);

-- TEAM GAME STATS (one row per team per game) --------
create table if not exists team_game_stats (
    id                      bigserial primary key,
    game_id                 bigint not null references games(game_id),
    team_id                 text references teams(team_id),
    goals                   int default 0,
    shots                   int default 0,
    hits                    int default 0,
    penalty_minutes         int default 0,
    powerplay_goals         int default 0,
    powerplay_opportunities int default 0,
    faceoff_win_pct         numeric,
    giveaways               int default 0,
    takeaways               int default 0,
    constraint team_game_stats_game_team_uq unique (game_id, team_id)
);

-- SEASON TOTALS (career history: one row per player per NHL regular season) --------
-- Backfilled from the player landing endpoint by scripts/ingest.ts —
-- this is what the cooked model's baselines and trends are computed from.
create table if not exists season_totals (
    player_id         bigint not null references players(player_id),
    season            int not null,        -- e.g. 20252026
    team_name         text,
    games_played      int not null,
    goals             int not null,
    assists           int not null,
    points            int not null,
    shots             int,
    shooting_pctg     double precision,
    avg_toi_seconds   int,
    plus_minus        int,
    pim               int,
    power_play_points int,
    primary key (player_id, season)
);

-- COOKED SCORES (model output — rebuilt by `npm run cook`) --------
create table if not exists cooked_scores (
    player_id            bigint primary key references players(player_id),
    season               int not null,
    score                double precision,   -- 0..100, null when not enough data
    label                text not null,      -- Fresh ... Cooked / Too Fresh to Judge
    status               text not null,      -- scored | not_enough_data | goalie
    games_played         int,
    points_per_game      double precision,
    peak_points_per_game double precision,
    signals              text,               -- JSON breakdown for the UI
    computed_at          text not null
);

-- Helpful indexes -------------------------------------------------------
create index if not exists idx_pgs_player on player_game_stats(player_id);
create index if not exists idx_pgs_game   on player_game_stats(game_id);
create index if not exists idx_tgs_team   on team_game_stats(team_id);
create index if not exists idx_games_date on games(game_date);
create index if not exists idx_st_season  on season_totals(season);
