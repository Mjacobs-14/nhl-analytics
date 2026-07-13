import { client } from "@/db";

/** Queries for the /analytics section. These read Matt's SQL views directly
 *  (they aren't part of the drizzle schema — sql/ is the source of truth for
 *  views), so numerics come back as strings and get coerced here. */

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

export async function getShotVolumeSeasons(): Promise<number[]> {
  const rows = await client`
    select distinct season from player_shot_volume_output_v order by season desc`;
  return rows.map((r) => Number(r.season));
}

export async function getShotVolumeOutput(season: number): Promise<ShotVolumePoint[]> {
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
}

export async function getVegasFlu(): Promise<VegasFluRow[]> {
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
}

export function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
