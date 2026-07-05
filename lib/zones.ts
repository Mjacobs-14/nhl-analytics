import { ZONES } from "./cooked/config";

/** CSS variable for the gauge zone a score falls in. */
export function zoneVar(score: number): string {
  const idx = ZONES.findIndex((z) => score <= z.max);
  return `var(--zone-${(idx === -1 ? ZONES.length : idx + 1)})`;
}

export const ZONE_VARS = ZONES.map((_, i) => `var(--zone-${i + 1})`);

export function formatSeason(season: number): string {
  const start = Math.floor(season / 10000);
  return `${start}–${String(season % 100).padStart(2, "0")}`;
}
