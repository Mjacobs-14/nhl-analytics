import { unstable_cache } from "next/cache";
import { client } from "@/db";

/** Queries for the /analytics section. These read Matt's SQL views directly
 *  (they aren't part of the drizzle schema — sql/ is the source of truth for
 *  views), so numerics come back as strings and get coerced here.
 *
 *  Everything is wrapped in unstable_cache: the coach views recompute
 *  per-game xG over the full shot history (~13s cold), and the data only
 *  moves when the daily ETL runs — an hour of staleness costs nothing. */
const cached = <A extends unknown[], R>(fn: (...args: A) => Promise<R>, key: string) =>
  unstable_cache(fn, [key], { revalidate: 3600 });

export interface ShotVolumePoint {
  playerId: number;
  name: string;
  position: string;
  gp: number;
  points: number;
  ppg: number;
  sogPer60: number;
  toiMinPerGame: number;
}

export interface VegasFluRow {
  playerId: number;
  name: string;
  position: string;
  vegasGp: number;
  roadGp: number;
  vegasPpg: number;
  roadPpg: number;
  fluPpg: number;
}

export const getShotVolumeSeasons = cached(async (): Promise<number[]> => {
  const rows = await client`
    select distinct season from player_shot_volume_output_v order by season desc`;
  return rows.map((r) => Number(r.season));
}, "shot-volume-seasons");

export const getShotVolumeOutput = cached(async (season: number): Promise<ShotVolumePoint[]> => {
  const rows = await client`
    select player_id, full_name, position, gp, points, ppg, sog_per_60, toi_min_per_game
    from player_shot_volume_output_v
    where season = ${season}`;
  return rows.map((r) => ({
    playerId: Number(r.player_id),
    name: r.full_name as string,
    position: r.position as string,
    gp: Number(r.gp),
    points: Number(r.points),
    ppg: Number(r.ppg),
    sogPer60: Number(r.sog_per_60),
    toiMinPerGame: Number(r.toi_min_per_game),
  }));
}, "shot-volume-output");

export const getVegasFlu = cached(async (): Promise<VegasFluRow[]> => {
  const rows = await client`
    select player_id, full_name, position, vegas_gp, road_gp,
           vegas_ppg, road_ppg, vegas_flu_ppg
    from player_vegas_flu_v
    order by vegas_flu_ppg asc`;
  return rows.map((r) => ({
    playerId: Number(r.player_id),
    name: r.full_name as string,
    position: r.position as string,
    vegasGp: Number(r.vegas_gp),
    roadGp: Number(r.road_gp),
    vegasPpg: Number(r.vegas_ppg),
    roadPpg: Number(r.road_ppg),
    fluPpg: Number(r.vegas_flu_ppg),
  }));
}, "vegas-flu");

export interface XgCell {
  distBin: number; // 1..18 → 0–90 ft in 5 ft steps
  angleBin: number; // 1..9 → 0–90° in 10° steps
  shots: number;
  goals: number;
  xg: number;
}

export interface CoachStyleRow {
  coach: string;
  team: string;
  gp: number;
  gfPerGame: number;
  gaPerGame: number;
  cfPerGame: number;
  xgfPerGame: number;
  xgaPerGame: number;
  avgShotDistFor: number;
  blockPct: number;
  teamSvPct: number;
  gsax: number;
  pimPerGame: number;
}

export interface CoachChangeRow {
  season: number;
  team: string;
  outCoach: string;
  inCoach: string;
  outGp: number;
  inGp: number;
  outXgfPct: number;
  inXgfPct: number;
  dXgfPct: number;
  dWinPct: number;
  dGoalDiff: number;
}

export interface AthleticismRow {
  playerId: number;
  name: string;
  position: string;
  gp: number;
  topSpeedMph: number;
  burstsPerGame: number;
  milesPerGame: number;
  topShotSpeedMph: number;
  speedPctile: number | null;
  shotPctile: number | null;
  distPctile: number | null;
}

export const getXgGrid = cached(async (): Promise<XgCell[]> => {
  // bins 19/10 are width_bucket overflow (beyond 90 ft / the exact-90° edge)
  const rows = await client`
    select dist_bin, angle_bin, shots, goals, xg
    from xg_grid
    where dist_bin <= 18 and angle_bin <= 9`;
  return rows.map((r) => ({
    distBin: Number(r.dist_bin),
    angleBin: Number(r.angle_bin),
    shots: Number(r.shots),
    goals: Number(r.goals),
    xg: Number(r.xg),
  }));
}, "xg-grid");

export const getCoachStyle = cached(async (season: number): Promise<CoachStyleRow[]> => {
  const rows = await client`
    select coach, team, gp, gf_per_game, ga_per_game, cf_per_game,
           xgf_per_game, xga_per_game, avg_shot_dist_for, block_pct,
           team_sv_pct, gsax, pim_per_game
    from coach_style_v
    where season = ${season}`;
  return rows.map((r) => ({
    coach: r.coach as string,
    team: r.team as string,
    gp: Number(r.gp),
    gfPerGame: Number(r.gf_per_game),
    gaPerGame: Number(r.ga_per_game),
    cfPerGame: Number(r.cf_per_game),
    xgfPerGame: Number(r.xgf_per_game),
    xgaPerGame: Number(r.xga_per_game),
    avgShotDistFor: Number(r.avg_shot_dist_for),
    blockPct: Number(r.block_pct),
    teamSvPct: Number(r.team_sv_pct),
    gsax: Number(r.gsax),
    pimPerGame: Number(r.pim_per_game),
  }));
}, "coach-style");

export const getCoachChanges = cached(async (): Promise<CoachChangeRow[]> => {
  // short interim stints are noise — require a real sample on both sides
  const rows = await client`
    select season, team, out_coach, in_coach, out_gp, in_gp,
           out_xgf_pct, in_xgf_pct, d_xgf_pct, d_win_pct, d_goal_diff
    from coach_change_v
    where out_gp >= 10 and in_gp >= 10
    order by d_xgf_pct desc`;
  return rows.map((r) => ({
    season: Number(r.season),
    team: r.team as string,
    outCoach: r.out_coach as string,
    inCoach: r.in_coach as string,
    outGp: Number(r.out_gp),
    inGp: Number(r.in_gp),
    outXgfPct: Number(r.out_xgf_pct),
    inXgfPct: Number(r.in_xgf_pct),
    dXgfPct: Number(r.d_xgf_pct),
    dWinPct: Number(r.d_win_pct),
    dGoalDiff: Number(r.d_goal_diff),
  }));
}, "coach-changes");

export const getAthleticism = cached(async (season: number): Promise<AthleticismRow[]> => {
  const rows = await client`
    select player_id, full_name, position, games_played,
           top_skating_speed_mph, bursts_per_game, avg_skating_distance_per_game,
           top_shot_speed_mph, skating_speed_percentile, shot_speed_percentile,
           distance_skated_percentile
    from player_athleticism_v
    where season = ${season} and games_played >= 20
      and top_skating_speed_mph is not null and bursts_per_game is not null`;
  return rows.map((r) => ({
    playerId: Number(r.player_id),
    name: r.full_name as string,
    position: r.position as string,
    gp: Number(r.games_played),
    topSpeedMph: Number(r.top_skating_speed_mph),
    burstsPerGame: Number(r.bursts_per_game),
    milesPerGame: Number(r.avg_skating_distance_per_game),
    topShotSpeedMph: Number(r.top_shot_speed_mph),
    speedPctile: r.skating_speed_percentile === null ? null : Number(r.skating_speed_percentile),
    shotPctile: r.shot_speed_percentile === null ? null : Number(r.shot_speed_percentile),
    distPctile: r.distance_skated_percentile === null ? null : Number(r.distance_skated_percentile),
  }));
}, "athleticism");

export function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
