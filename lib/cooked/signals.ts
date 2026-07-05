// Each signal maps a slice of a player's history to a 0..1 "cooked-ness".
// Signals return null when there isn't enough data to say anything —
// null signals drop out and remaining weights renormalize.

import { THRESHOLDS } from "./config";

export interface SeasonLine {
  season: number;
  gamesPlayed: number;
  points: number;
  shots: number | null;
  shootingPctg: number | null;
  avgToiSeconds: number | null;
}

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

/** Linear ramp: 0 at `safe`, 1 at `cooked` (works whichever direction). */
function ramp(value: number, safe: number, cooked: number): number {
  return clamp01((value - safe) / (cooked - safe));
}

export function ppg(s: SeasonLine): number {
  return s.gamesPlayed > 0 ? s.points / s.gamesPlayed : 0;
}

/** Mean PPG of the player's best 3 qualifying seasons (excluding `excludeSeason`). */
export function peakBaseline(history: SeasonLine[], excludeSeason: number): number | null {
  const qualifying = history
    .filter((s) => s.season !== excludeSeason && s.gamesPlayed >= THRESHOLDS.minBaselineGp)
    .map(ppg)
    .sort((a, b) => b - a)
    .slice(0, 3);
  if (qualifying.length < 2) return null;
  return qualifying.reduce((a, b) => a + b, 0) / qualifying.length;
}

/** Age at the (approximate) end of a season: Jan 1 of the season's closing year. */
export function ageInSeason(birthDate: string, season: number): number {
  const closingYear = season % 10000; // 20252026 -> 2026
  const birth = new Date(birthDate);
  return closingYear - birth.getFullYear() - (birth.getMonth() >= 6 ? 1 : 0) + 0.5;
}

// ── Signals ─────────────────────────────────────────────────────

export function agePressure(birthDate: string | null, position: string, season: number): number | null {
  if (!birthDate) return null;
  const group = position === "D" ? "D" : position === "G" ? "G" : "F";
  const age = ageInSeason(birthDate, season);
  return ramp(age, THRESHOLDS.ageFloor[group], THRESHOLDS.ageCeiling[group]);
}

export function productionFade(current: SeasonLine, peak: number | null): number | null {
  if (peak === null || peak <= 0) return null;
  const ratio = ppg(current) / peak;
  return ramp(ratio, THRESHOLDS.productionRatio.safe, THRESHOLDS.productionRatio.cooked);
}

/**
 * Least-squares slope of PPG over the last 3 qualifying seasons, normalized by
 * peak PPG. Distinguishes a sustained slide from one bad season.
 */
export function trendSlope(history: SeasonLine[], peak: number | null): number | null {
  if (peak === null || peak <= 0) return null;
  const recent = history
    .filter((s) => s.gamesPlayed >= THRESHOLDS.minSeasonGp)
    .slice(-3);
  if (recent.length < 3) return null;
  const ys = recent.map(ppg);
  const n = ys.length;
  const xMean = (n - 1) / 2;
  const yMean = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0;
  let den = 0;
  ys.forEach((y, x) => {
    num += (x - xMean) * (y - yMean);
    den += (x - xMean) ** 2;
  });
  const slopePerSeason = num / den / peak; // fraction of peak lost per season
  return ramp(slopePerSeason, 0, THRESHOLDS.trendSlopeFloor);
}

export function deploymentDrop(history: SeasonLine[], current: SeasonLine): number | null {
  if (!current.avgToiSeconds) return null;
  const prior = history
    .filter((s) => s.season !== current.season && s.gamesPlayed >= THRESHOLDS.minSeasonGp)
    .slice(-2)
    .map((s) => s.avgToiSeconds)
    .filter((t): t is number => t !== null);
  if (prior.length === 0) return null;
  const ratio = current.avgToiSeconds / Math.max(...prior);
  return ramp(ratio, THRESHOLDS.toiRatio.safe, THRESHOLDS.toiRatio.cooked);
}

/**
 * Subtractive rescue: shooting % collapsed below career norm while shot volume
 * held (≥85% of prior rate) → results look cooked but the process doesn't.
 */
export function luckRescue(
  history: SeasonLine[],
  current: SeasonLine,
  careerShootingPctg: number | null
): number | null {
  if (!careerShootingPctg || careerShootingPctg <= 0) return null;
  if (current.shootingPctg === null || current.shots === null || current.gamesPlayed === 0) return null;
  const priorSeasons = history.filter(
    (s) => s.season !== current.season && s.gamesPlayed >= THRESHOLDS.minSeasonGp && s.shots !== null
  );
  if (priorSeasons.length === 0) return null;
  const priorShotRate =
    priorSeasons.reduce((a, s) => a + (s.shots as number) / s.gamesPlayed, 0) / priorSeasons.length;
  const currentShotRate = current.shots / current.gamesPlayed;
  if (priorShotRate <= 0 || currentShotRate < 0.85 * priorShotRate) return 0;
  const deficit = (careerShootingPctg - current.shootingPctg) / careerShootingPctg;
  return clamp01(deficit / 0.5); // 50% below career sh% = full rescue
}
