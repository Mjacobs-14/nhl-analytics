import { unstable_cache } from "next/cache";
import { client } from "@/db";

/** Per-player metric slices that hang off the /player/[id] profile — clutch,
 *  shot volume, and NHL Edge skating. These read the SQL views directly (not the
 *  drizzle schema), so numerics come back as strings and are coerced here. Same
 *  1-hour cache as lib/analytics.ts: the data only moves on the daily ETL. */
const cached = <A extends unknown[], R>(fn: (...args: A) => Promise<R>, key: string) =>
  unstable_cache(fn, [key], { revalidate: 3600 });

const n = (x: unknown): number => Number(x);
const nn = (x: unknown): number | null => (x == null ? null : Number(x));
// player_athleticism_v stores percentiles as 0–1 fractions; the UI wants 0–100.
const pct = (x: unknown): number | null => (x == null ? null : Number(x) * 100);

export interface ShotVolumeSeason {
  season: number;
  gp: number;
  points: number;
  goals: number;
  ppg: number;
  sog: number;
  sogPer60: number;
  toiMinPerGame: number;
}

export interface AthleticismSeason {
  season: number;
  gamesPlayed: number;
  topSkatingSpeedMph: number | null;
  burstsPerGame: number | null;
  avgSkatingDistancePerGame: number | null;
  topShotSpeedMph: number | null;
  offensiveZoneTimePct: number | null;
  skatingSpeedPct: number | null;
  shotSpeedPct: number | null;
  distancePct: number | null;
}

export interface ClutchSeason {
  season: number;
  gp: number;
  team: string;
  pts: number;
  state: {
    tied: number; up1: number; up2: number; up3: number;
    down1: number; down2: number; down3: number;
  };
  ptsClose: number;
  ptsBlowout: number;
  ptsLateClose: number;
  goalsLateClose: number;
  ptsOt: number;
  closeShare: number;        // share of points in close (tied/1-goal) states
  leagueCloseShare: number;  // that season's league-wide close share
  tilt: number;              // (player − league) close share, in percentage points
}

export interface PlayerProfile {
  shotVolume: ShotVolumeSeason[];   // ascending by season
  athleticism: AthleticismSeason[];
  clutch: ClutchSeason[];
}

export const getPlayerProfile = cached(async (playerId: number): Promise<PlayerProfile> => {
  const [sv, ath, clu] = await Promise.all([
    client`
      select season, gp, points, goals, ppg, sog, sog_per_60, toi_min_per_game
      from player_shot_volume_output_v
      where player_id = ${playerId}
      order by season`,
    client`
      select season, games_played, top_skating_speed_mph, bursts_per_game,
             avg_skating_distance_per_game, top_shot_speed_mph, offensive_zone_time_pct,
             skating_speed_percentile, shot_speed_percentile, distance_skated_percentile
      from player_athleticism_v
      where player_id = ${playerId}
      order by season`,
    client`
      with lg as (
        select season, sum(pts_close)::numeric / nullif(sum(pts), 0) as lg_close
        from player_clutch_v group by season
      )
      select c.season, c.gp, c.primary_team, c.pts,
             c.pts_tied, c.pts_up1, c.pts_up2, c.pts_up3p,
             c.pts_down1, c.pts_down2, c.pts_down3p,
             c.pts_close, c.pts_blowout, c.pts_late_close, c.goals_late_close, c.pts_ot,
             lg.lg_close
      from player_clutch_v c
      join lg on lg.season = c.season
      where c.player_id = ${playerId}
      order by c.season`,
  ]);

  return {
    shotVolume: sv.map((r) => ({
      season: n(r.season), gp: n(r.gp), points: n(r.points), goals: n(r.goals),
      ppg: n(r.ppg), sog: n(r.sog), sogPer60: n(r.sog_per_60),
      toiMinPerGame: n(r.toi_min_per_game),
    })),
    athleticism: ath.map((r) => ({
      season: n(r.season), gamesPlayed: n(r.games_played),
      topSkatingSpeedMph: nn(r.top_skating_speed_mph),
      burstsPerGame: nn(r.bursts_per_game),
      avgSkatingDistancePerGame: nn(r.avg_skating_distance_per_game),
      topShotSpeedMph: nn(r.top_shot_speed_mph),
      offensiveZoneTimePct: nn(r.offensive_zone_time_pct),
      skatingSpeedPct: pct(r.skating_speed_percentile),
      shotSpeedPct: pct(r.shot_speed_percentile),
      distancePct: pct(r.distance_skated_percentile),
    })),
    clutch: clu.map((r) => {
      const pts = n(r.pts);
      const close = n(r.pts_close);
      const leagueCloseShare = n(r.lg_close);
      const closeShare = pts > 0 ? close / pts : 0;
      return {
        season: n(r.season), gp: n(r.gp), team: r.primary_team as string, pts,
        state: {
          tied: n(r.pts_tied), up1: n(r.pts_up1), up2: n(r.pts_up2), up3: n(r.pts_up3p),
          down1: n(r.pts_down1), down2: n(r.pts_down2), down3: n(r.pts_down3p),
        },
        ptsClose: close, ptsBlowout: n(r.pts_blowout),
        ptsLateClose: n(r.pts_late_close), goalsLateClose: n(r.goals_late_close),
        ptsOt: n(r.pts_ot),
        closeShare, leagueCloseShare,
        tilt: (closeShare - leagueCloseShare) * 100,
      };
    }),
  };
}, "player-profile");
