import { unstable_cache } from "next/cache";
import { client } from "@/db";

/** Data layer for the Matchup Lab (/matchup) — a port of Matt's
 *  viz/matchup_lab.html v3 into a live app page. The interactive compute
 *  (blended shot mixes, EV + PP expected goals, goalie band pricing) all runs
 *  client-side in lib/matchup-compute.ts / components/matchup/MatchupLab.tsx,
 *  exactly as the prototype did; this module just reproduces the four data
 *  arrays the prototype embedded as a snapshot, reading Matt's SQL views:
 *
 *    ST   ← team_strength_location_v (sql/033)  venue × strength shot profiles
 *    GK   ← shot_xg_v season workload + goalie_location_v (sql/032) career bands
 *    GP   ← games                                games per season/team/venue
 *    RUSH ← shot_events.is_rush                  team-season rush shares
 *
 *  Views read straight (not via drizzle), so numerics come back as strings and
 *  are coerced here. The public getters are cached: these scan the full shot
 *  history and only move when the daily ETL runs. */
const cached = <A extends unknown[], R>(fn: (...args: A) => Promise<R>, key: string) =>
  unstable_cache(fn, [key], { revalidate: 3600 });

/** One venue×strength row of a team's shot profile. Field names match the
 *  prototype's embedded data so the ported compute needs no renaming. */
export interface StRow {
  s: string; // season, e.g. "20252026"
  t: string; // team abbrev
  v: "home" | "road";
  k: "ev" | "pp"; // strength state (shorthanded rows are dropped — see below)
  sf: number; // shots for (on-net, with a goalie in net)
  oh: number; // offense high-danger share (%)
  om: number; // offense medium share (%)
  sa: number; // shots against
  dh: number; // defense high-danger share allowed (%)
  dm: number; // defense medium share allowed (%)
}

export interface GkRow {
  s: string;
  t: string;
  n: string; // goalie name
  sh: number; // shots faced THAT season for THIS team (ranking + display)
  gh: number | null; // CAREER high-danger save % (null when <1500 career shots)
  gm: number | null;
  gl: number | null;
}

export interface MatchupData {
  st: StRow[];
  gp: Record<string, number>; // key `${s}|${t}|${v}`
  gk: GkRow[];
  rush: Record<string, [number, number]>; // key `${s}|${t}` → [for%, against%]
}

async function stQuery(): Promise<StRow[]> {
  // Only ev/pp feed the model (shorthanded offense ~3% of shots is ignored, as
  // in the prototype), so drop 'sh' rows to shrink the client payload.
  const rows = await client`
    select season, team, venue, strength, sf, off_hd, off_md, sa, def_hd, def_md
    from team_strength_location_v
    where strength in ('ev', 'pp')`;
  return rows.map((r) => ({
    s: String(r.season),
    t: r.team as string,
    v: r.venue as "home" | "road",
    k: r.strength as "ev" | "pp",
    sf: Number(r.sf),
    oh: Number(r.off_hd),
    om: Number(r.off_md),
    sa: Number(r.sa),
    dh: Number(r.def_hd),
    dm: Number(r.def_md),
  }));
}

async function gpQuery(): Promise<Record<string, number>> {
  const rows = await client`
    select season, home_team_id as team, 'home' as venue, count(*)::int n
    from games where game_type = 'regular' group by season, home_team_id
    union all
    select season, away_team_id, 'road', count(*)::int
    from games where game_type = 'regular' group by season, away_team_id`;
  const gp: Record<string, number> = {};
  for (const r of rows) gp[`${r.season}|${r.team}|${r.venue}`] = Number(r.n);
  return gp;
}

async function gkQuery(): Promise<GkRow[]> {
  // Season workload comes from shot_xg_v (goalie_id + def_team = the goalie's
  // own team); career danger-band save % from goalie_location_v (min 1500
  // career shots → a goalie below that isn't in the view, so gh/gm/gl come back
  // null and the UI falls back to league-average rates). Top 4 by season shots
  // per team, matching the prototype's "four most-used goalies that season".
  const rows = await client`
    with ss as (
      select season, def_team as team, goalie_id, count(*)::int sh
      from shot_xg_v
      where game_type = 'regular' and goalie_id is not null
      group by season, def_team, goalie_id
    ),
    ranked as (
      select ss.*, row_number() over (partition by season, team order by sh desc) rn
      from ss
    )
    select r.season, r.team, pl.full_name n, r.sh,
           gl.sv_hd gh, gl.sv_md gm, gl.sv_ld gl_low
    from ranked r
    join players pl on pl.player_id = r.goalie_id
    left join goalie_location_v gl on gl.player_id = r.goalie_id
    where r.rn <= 4
    order by r.season, r.team, r.sh desc`;
  return rows.map((r) => ({
    s: String(r.season),
    t: r.team as string,
    n: r.n as string,
    sh: Number(r.sh),
    gh: r.gh === null ? null : Number(r.gh),
    gm: r.gm === null ? null : Number(r.gm),
    gl: r.gl_low === null ? null : Number(r.gl_low),
  }));
}

async function rushQuery(): Promise<Record<string, [number, number]>> {
  // Rush share of shot attempts (is_rush over all classified attempts, the same
  // definition as coach_rush_v), for and against, per team-season. Feeds only
  // the transition style-clash narrative, not the xG math.
  const rows = await client`
    with se as (
      select se.game_id, se.team_id, g.season, se.is_rush,
             g.home_team_id, g.away_team_id
      from shot_events se
      join games g on g.game_id = se.game_id
      where se.is_rush is not null and g.game_type = 'regular'
    ),
    fa as (
      select season, team_id team, count(*) n, count(*) filter (where is_rush) r
      from se group by season, team_id
    ),
    ag as (
      select season, opp team, count(*) n, count(*) filter (where is_rush) r
      from (
        select season, is_rush,
               case when team_id = home_team_id then away_team_id else home_team_id end opp
        from se
      ) z group by season, opp
    )
    select fa.season, fa.team,
           round(100.0 * fa.r / nullif(fa.n, 0), 1) rf,
           round(100.0 * ag.r / nullif(ag.n, 0), 1) ra
    from fa join ag on ag.season = fa.season and ag.team = fa.team`;
  const rush: Record<string, [number, number]> = {};
  for (const r of rows) rush[`${r.season}|${r.team}`] = [Number(r.rf), Number(r.ra)];
  return rush;
}

const getSt = cached(stQuery, "matchup-st");
const getGp = cached(gpQuery, "matchup-gp");
const getGk = cached(gkQuery, "matchup-gk");
const getRush = cached(rushQuery, "matchup-rush");

/** Cached — for the page (runs inside a Next request). */
export async function getMatchupData(): Promise<MatchupData> {
  const [st, gp, gk, rush] = await Promise.all([getSt(), getGp(), getGk(), getRush()]);
  return { st, gp, gk, rush };
}

/** Uncached — for scripts/tests that run outside a Next request context
 *  (unstable_cache throws there). Same data, no memoization. */
export async function getMatchupDataUncached(): Promise<MatchupData> {
  const [st, gp, gk, rush] = await Promise.all([stQuery(), gpQuery(), gkQuery(), rushQuery()]);
  return { st, gp, gk, rush };
}
