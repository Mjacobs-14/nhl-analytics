-- ============================================================
-- 036 — edge_pull_status_v: what etl/pull_edge_data.py needs to fetch
--
-- One row per player who appeared in a game, per season x game type, with
-- games played from the boxscores (actual_gp) next to the games covered by
-- their stored Edge row (edge_gp). The Edge pull fetches only rows where
-- edge_gp is missing or behind actual_gp.
--
-- Replaces the old approach of requesting every player in `players` for both
-- game types (~6,000 calls a day, nearly all 404s, ~2 hours with rate-limit
-- penalties) and skipping anyone already pulled — which froze in-season Edge
-- rows at the first pull (2026-10: 667 of 768 players stuck at 1 game).
--
-- player_game_stats is unique on (game_id, player_id), so count(*) is games
-- played. Only games with ice time count: backup goalies get a boxscore row
-- for games they dress but don't play, which Edge doesn't count. ~13 ms for
-- one season through the API.
--
-- Depends on games.game_type being set. Placeholder game rows (game_type
-- NULL) drop out of every regular-season view; etl/pull_nhl_data.py now
-- refetches those instead of skipping them.
-- ============================================================

create or replace view public.edge_pull_status_v as
with played as (
  select pgs.player_id, g.season::text as season, g.game_type, count(*) as actual_gp
  from player_game_stats pgs
  join games g on g.game_id = pgs.game_id
  where g.game_type in ('regular', 'playoff')
    and coalesce(pgs.toi_seconds, 0) > 0   -- backup goalies dress without playing
  group by pgs.player_id, g.season, g.game_type
)
select pl.player_id, p.position, p.full_name, pl.season, pl.game_type,
       pl.actual_gp, e.games_played as edge_gp, e.updated_at as edge_updated_at
from played pl
join players p on p.player_id = pl.player_id
left join player_season_edge_stats e
  on e.player_id = pl.player_id and e.season = pl.season and e.game_type = pl.game_type;
