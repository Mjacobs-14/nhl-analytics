-- ============================================================
-- Game-day weather at the venue — populated by etl/backfill_weather.py
-- from the Open-Meteo historical archive (free, no key).
--
-- NHL games are indoors, so this is attendance/curiosity data, not
-- gameplay data — except the outdoor games (Winter Classic, Stadium
-- Series), where it's both. Daily values for the venue's location.
--
-- Idempotent — safe to re-run.
-- ============================================================

alter table games add column if not exists temp_c        real;  -- daily mean, Celsius
alter table games add column if not exists precip_mm     real;  -- daily total precipitation
alter table games add column if not exists snowfall_cm   real;  -- daily total snowfall
alter table games add column if not exists humidity_pct  real;  -- daily mean relative humidity
