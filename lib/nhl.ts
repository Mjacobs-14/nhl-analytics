// Thin client for the public NHL API (no key required).
// Docs are community-maintained: https://github.com/Zmalski/NHL-API-Reference

const BASE = "https://api-web.nhle.com/v1";

// Seasons roll over in August: July 2026 is still 20252026, October is 20262027.
// Computed so nobody has to remember to bump it every fall.
function currentSeason(): number {
  const now = new Date();
  const startYear = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;
  return startYear * 10000 + (startYear + 1);
}
export const CURRENT_SEASON = currentSeason();
export const REGULAR_SEASON = 2; // gameTypeId

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Global spacing between requests — the API 429s aggressive parallel pulls.
const MIN_GAP_MS = 150;
let queue: Promise<unknown> = Promise.resolve();
function throttled<T>(fn: () => Promise<T>): Promise<T> {
  const run = queue.then(async () => {
    await sleep(MIN_GAP_MS);
    return fn();
  });
  queue = run.catch(() => {});
  return run as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    const res = await throttled(() => fetch(`${BASE}${path}`));
    if (res.ok) return res.json() as Promise<T>;
    const retryable = res.status === 429 || res.status >= 500;
    if (!retryable || attempt >= 5) throw new Error(`NHL API ${res.status} for ${path}`);
    const retryAfter = Number(res.headers.get("retry-after"));
    const waitMs = retryAfter > 0 ? retryAfter * 1000 : Math.min(60_000, 2000 * 2 ** attempt);
    await sleep(waitMs);
  }
}

type LocalizedString = { default: string };

export interface StandingsTeam {
  teamAbbrev: LocalizedString;
  teamName: LocalizedString;
  conferenceName: string;
  divisionName: string;
  teamLogo: string;
}

export interface RosterPlayer {
  id: number;
  firstName: LocalizedString;
  lastName: LocalizedString;
  positionCode: string;
  sweaterNumber?: number;
  shootsCatches?: string;
  birthDate?: string;
  headshot?: string;
}

export interface SeasonTotalRaw {
  season: number;
  gameTypeId: number;
  leagueAbbrev: string;
  gamesPlayed: number;
  goals: number;
  assists: number;
  points: number;
  shots?: number;
  shootingPctg?: number;
  avgToi?: string; // "22:59"
  plusMinus?: number;
  pim?: number;
  powerPlayPoints?: number;
  teamName?: LocalizedString;
}

export interface PlayerLanding {
  playerId: number;
  position: string;
  birthDate?: string;
  headshot?: string;
  currentTeamAbbrev?: string;
  seasonTotals: SeasonTotalRaw[];
  careerTotals?: {
    regularSeason?: { shootingPctg?: number; shots?: number; gamesPlayed?: number };
  };
}

export interface GameLogEntry {
  gameId: number;
  gameDate: string;
  opponentAbbrev: string;
  homeRoadFlag: string;
  goals: number;
  assists: number;
  points: number;
  shots?: number;
  plusMinus?: number;
  pim?: number;
  toi?: string; // "18:16"
  shifts?: number;
  powerPlayPoints?: number;
}

export function getStandings() {
  return get<{ standings: StandingsTeam[] }>("/standings/now");
}

export function getRoster(teamAbbrev: string, season: number = CURRENT_SEASON) {
  return get<{ forwards: RosterPlayer[]; defensemen: RosterPlayer[]; goalies: RosterPlayer[] }>(
    `/roster/${teamAbbrev}/${season}`
  );
}

export function getPlayerLanding(playerId: number) {
  return get<PlayerLanding>(`/player/${playerId}/landing`);
}

export function getGameLog(playerId: number, season: number = CURRENT_SEASON) {
  return get<{ gameLog: GameLogEntry[] }>(`/player/${playerId}/game-log/${season}/${REGULAR_SEASON}`);
}

/** "18:16" or "22:59" -> seconds. Returns null for missing/malformed values. */
export function toiToSeconds(toi: string | undefined): number | null {
  if (!toi) return null;
  const m = toi.match(/^(\d+):(\d{2})$/);
  if (!m) return null;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

/** Run `fn` over `items` with bounded concurrency (be polite to the free API). */
export async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
