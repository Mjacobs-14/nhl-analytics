// ── Cooked Score v1 — tuning knobs ──────────────────────────────
// This is the file to argue about. Change a weight, run `npm run cook`,
// refresh the page. Weights don't need to sum to 1; they're normalized.

export const WEIGHTS = {
  /** Age vs. the typical NHL decline curve. */
  agePressure: 0.22,
  /** Current production vs. the player's own peak (best-3-seasons baseline). */
  productionFade: 0.3,
  /** Multi-season trajectory — sustained slide vs. one bad year. */
  trendSlope: 0.23,
  /** Ice-time drop — the coach's revealed opinion. */
  deploymentDrop: 0.25,
};

/**
 * Luck rescue is SUBTRACTIVE: if a player's shooting % cratered below career
 * norms while their shot volume held up, the process is intact and the results
 * are probably bad luck — we walk the score back.
 */
export const LUCK_RESCUE_WEIGHT = 0.15;

export const THRESHOLDS = {
  /** Age where cooked-risk starts accruing, and where it maxes out. */
  ageFloor: { F: 27, D: 27, G: 29 },
  ageCeiling: { F: 37, D: 38, G: 40 },
  /** PPG ratio vs. peak: at/above `safe` contributes 0, at/below `cooked` contributes 1. */
  productionRatio: { safe: 0.9, cooked: 0.45 },
  /** Per-season PPG slope (as a fraction of peak PPG) that maxes the trend signal. */
  trendSlopeFloor: -0.25,
  /** TOI ratio vs. best of prior 2 seasons: at/above `safe` → 0, at/below `cooked` → 1. */
  toiRatio: { safe: 0.97, cooked: 0.7 },
  /** Eligibility. */
  minSeasons: 3, // NHL seasons with ≥ minSeasonGp games
  minSeasonGp: 10,
  minCurrentGp: 15, // below this the score gets a small-sample caveat
  /** A season must have this many GP to count toward the peak baseline. */
  minBaselineGp: 20,
};

export const ZONES = [
  { max: 20, label: "Fresh" },
  { max: 40, label: "Warming Up" },
  { max: 60, label: "Simmering" },
  { max: 80, label: "Well Done" },
  { max: 100, label: "Cooked" },
] as const;

export function zoneLabel(score: number): string {
  return ZONES.find((z) => score <= z.max)?.label ?? "Cooked";
}
