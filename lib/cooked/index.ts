import { WEIGHTS, LUCK_RESCUE_WEIGHT, THRESHOLDS, zoneLabel } from "./config";
import {
  SeasonLine,
  agePressure,
  productionFade,
  trendSlope,
  deploymentDrop,
  luckRescue,
  peakBaseline,
  ppg,
} from "./signals";

export interface SignalBreakdown {
  key: keyof typeof WEIGHTS | "luckRescue";
  /** 0..1 cooked-ness (or rescue strength), null = not enough data */
  value: number | null;
  weight: number;
  /** weighted contribution to the final 0..100 score (negative for rescue) */
  contribution: number;
}

export interface CookedResult {
  status: "scored" | "not_enough_data" | "goalie";
  score: number | null;
  label: string;
  smallSample: boolean;
  currentSeason: number | null;
  pointsPerGame: number | null;
  peakPointsPerGame: number | null;
  signals: SignalBreakdown[];
}

export interface PlayerInput {
  position: string;
  birthDate: string | null;
  careerShootingPctg: number | null;
  /** NHL regular-season lines, ascending by season */
  history: SeasonLine[];
}

export function computeCookedScore(player: PlayerInput): CookedResult {
  const empty: CookedResult = {
    status: "not_enough_data",
    score: null,
    label: "Too Fresh to Judge",
    smallSample: false,
    currentSeason: null,
    pointsPerGame: null,
    peakPointsPerGame: null,
    signals: [],
  };

  if (player.position === "G") {
    // Goalies are voodoo. v2 problem.
    return { ...empty, status: "goalie", label: "Goalies Are Voodoo" };
  }

  const history = [...player.history].sort((a, b) => a.season - b.season);
  const qualifying = history.filter((s) => s.gamesPlayed >= THRESHOLDS.minSeasonGp);
  if (qualifying.length < THRESHOLDS.minSeasons) return empty;

  const current = qualifying[qualifying.length - 1];
  const peak = peakBaseline(history, current.season);

  const raw: Array<{ key: SignalBreakdown["key"]; value: number | null; weight: number }> = [
    { key: "agePressure", value: agePressure(player.birthDate, player.position, current.season), weight: WEIGHTS.agePressure },
    { key: "productionFade", value: productionFade(current, peak), weight: WEIGHTS.productionFade },
    { key: "trendSlope", value: trendSlope(qualifying, peak), weight: WEIGHTS.trendSlope },
    { key: "deploymentDrop", value: deploymentDrop(history, current), weight: WEIGHTS.deploymentDrop },
  ];

  const active = raw.filter((s) => s.value !== null);
  if (active.length < 2) return empty; // can't say anything meaningful

  const totalWeight = active.reduce((a, s) => a + s.weight, 0);
  let score01 = active.reduce((a, s) => a + (s.value as number) * (s.weight / totalWeight), 0);

  const rescue = luckRescue(history, current, player.careerShootingPctg);
  if (rescue !== null && rescue > 0) {
    score01 -= rescue * LUCK_RESCUE_WEIGHT;
  }
  score01 = Math.max(0, Math.min(1, score01));
  const score = Math.round(score01 * 1000) / 10;

  const signals: SignalBreakdown[] = raw.map((s) => ({
    key: s.key,
    value: s.value,
    weight: s.weight,
    contribution:
      s.value === null ? 0 : Math.round((s.value * (s.weight / totalWeight)) * 1000) / 10,
  }));
  signals.push({
    key: "luckRescue",
    value: rescue,
    weight: LUCK_RESCUE_WEIGHT,
    contribution: rescue ? -Math.round(rescue * LUCK_RESCUE_WEIGHT * 1000) / 10 : 0,
  });

  return {
    status: "scored",
    score,
    label: zoneLabel(score),
    smallSample: current.gamesPlayed < THRESHOLDS.minCurrentGp,
    currentSeason: current.season,
    pointsPerGame: Math.round(ppg(current) * 100) / 100,
    peakPointsPerGame: peak === null ? null : Math.round(peak * 100) / 100,
    signals,
  };
}
