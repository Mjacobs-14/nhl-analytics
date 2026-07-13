-- ============================================================
-- Rush flag on shot_events — whether a shot came off the rush
-- (quick transition) vs. off a set play / cycle. Populated by
-- etl/pull_play_by_play.py from the play preceding each shot:
-- prior play in the neutral/defensive zone, within ~5s, and not a
-- whistle/faceoff. A heuristic proxy (no possession tracking), the
-- raw material for rush-vs-cycle coach identity.
--
-- Backfill existing games after applying this:
--   python etl/pull_play_by_play.py --refresh-shots
-- Run this in Supabase: Project > SQL Editor > New Query > paste > Run
-- ============================================================

alter table shot_events add column if not exists is_rush boolean;
