-- ============================================================
-- NHL Edge Tracking Stats — season-level, per game type
-- Backs etl/pull_edge_data.py
--
-- NOTE: the original 003 was applied to the live database but never
-- committed to git. This file was reconstructed from the live schema
-- (via the PostgREST OpenAPI spec) on 2026-07-07 so a fresh database
-- gets the same table. On the live DB it's a no-op.
-- ============================================================

create table if not exists player_season_edge_stats (
    id                            bigserial primary key,
    player_id                     bigint references players(player_id),
    season                        text not null,   -- e.g. '20232024' (text: the Edge ETL writes strings)
    game_type                     text not null,   -- 'regular' / 'playoff'
    games_played                  int,
    top_skating_speed_mph         numeric,
    bursts_over_20mph             int,
    total_skating_distance_miles  numeric,
    avg_skating_distance_per_game numeric,
    top_shot_speed_mph            numeric,
    offensive_zone_time_pct       numeric,
    neutral_zone_time_pct         numeric,
    defensive_zone_time_pct       numeric,
    shooting_pct                  numeric,
    skating_speed_percentile      numeric,
    shot_speed_percentile         numeric,
    distance_skated_percentile    numeric,
    offensive_zone_percentile     numeric,
    raw_json                      jsonb,
    updated_at                    timestamptz default now(),
    unique (player_id, season, game_type)
);

create index if not exists idx_edge_player on player_season_edge_stats(player_id);
