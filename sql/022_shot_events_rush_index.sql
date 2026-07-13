-- ============================================================
-- Partial index supporting the --refresh-shots resume query.
-- get_existing_game_ids(..., not_null='is_rush') runs
-- `select game_id from shot_events where is_rush is not null`; without
-- this index that's a full seq scan of ~1.3M rows (and times out against
-- PostgREST while nothing is classified yet, since it must scan the whole
-- table to find zero matches). The partial index makes it an index-only
-- scan — tiny at the start of the backfill, growing as games are classified.
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

create index if not exists idx_shot_events_rush_done
  on shot_events (game_id) where is_rush is not null;
