import type { MatchupData, StRow, GkRow } from "@/lib/matchup";

/** Pure matchup math, ported verbatim from Matt's viz/matchup_lab.html v3.
 *  No DB, no React — imported by both the client component and the golden test.
 *
 *  Model (per direction, e.g. road team attacking home team):
 *    expected goals = an EV term + a PP term, each of the form
 *      shots  = (attacker shots/gm) × (defender allowed/gm) ÷ league avg
 *      mix    = odds-ratio-ish blend of attacker shot diet × defender concession
 *      xG     = shots × Σ_band mix_band × (1 − goalie band save %)
 *  Goalie bands are the defending team's goalie's CAREER save %; league bands
 *  fill in when a goalie has <1500 career shots. */

export const LSV = { h: 0.804, m: 0.903, l: 0.975 } as const; // league band save %
export const LEAGUE_RUSH = 9.7; // LR — league rush-share reference for the narrative

export interface Prof {
  sf: number;
  sa: number;
  oh: number;
  om: number;
  ol: number;
  dh: number;
  dm: number;
  dl: number;
}
export interface Term {
  shots: number;
  mix: { h: number; m: number; l: number };
  xg: number;
  xgb: { h: number; m: number; l: number };
}
export interface Direction {
  ev: Term;
  pp: Term;
  xg: number;
}

export function seasonsIn(D: MatchupData): string[] {
  return [...new Set(D.st.map((d) => d.s))].sort().reverse();
}
export function teamsIn(D: MatchupData, s: string): string[] {
  return [...new Set(D.st.filter((d) => d.s === s).map((d) => d.t))].sort();
}

export function gpOf(D: MatchupData, s: string, t: string, v: string, venue: boolean): number {
  return venue
    ? D.gp[`${s}|${t}|${v}`] || 41
    : (D.gp[`${s}|${t}|home`] || 0) + (D.gp[`${s}|${t}|road`] || 0);
}

/** Merged shot profile for a team at a venue (or both venues when the split is
 *  off). Offense shares are shots-for-weighted; defense shares shots-against. */
export function prof(
  D: MatchupData,
  s: string,
  t: string,
  v: string,
  k: "ev" | "pp",
  venue: boolean,
): Prof | null {
  const rows = D.st.filter((d) => d.s === s && d.t === t && d.k === k && (venue ? d.v === v : true));
  if (!rows.length) return null;
  const sf = rows.reduce((a, d) => a + d.sf, 0);
  const sa = rows.reduce((a, d) => a + d.sa, 0);
  const wsum = (sel: (d: StRow) => number, w: (d: StRow) => number, tot: number) =>
    tot ? rows.reduce((a, d) => a + (sel(d) || 0) * w(d), 0) / tot : 0;
  const oh = wsum((d) => d.oh, (d) => d.sf, sf);
  const om = wsum((d) => d.om, (d) => d.sf, sf);
  const dh = wsum((d) => d.dh, (d) => d.sa, sa);
  const dm = wsum((d) => d.dm, (d) => d.sa, sa);
  return { sf, sa, oh, om, ol: 100 - oh - om, dh, dm, dl: 100 - dh - dm };
}

/** League baselines for a strength state: shots-against per game (the model's
 *  divisor) and the league concession mix. Not venue-split, matching v3. */
export function leagueK(D: MatchupData, s: string, k: "ev" | "pp") {
  const rs = D.st.filter((d) => d.s === s && d.k === k);
  const sa = rs.reduce((a, d) => a + d.sa, 0);
  const gp = Object.keys(D.gp)
    .filter((key) => key.startsWith(`${s}|`))
    .reduce((a, key) => a + D.gp[key], 0);
  const dh = sa ? rs.reduce((a, d) => a + (d.dh || 0) * d.sa, 0) / sa : 0;
  const dm = sa ? rs.reduce((a, d) => a + (d.dm || 0) * d.sa, 0) / sa : 0;
  return { sapg: gp ? sa / gp : 0, h: dh, m: dm, l: 100 - dh - dm };
}

export function term(
  A: Prof | null,
  B: Prof | null,
  L: ReturnType<typeof leagueK>,
  gk: GkRow | null,
  gpA: number,
  gpB: number,
): Term {
  if (!A || !B || !A.sf || !B.sa)
    return { shots: 0, mix: { h: 0, m: 0, l: 0 }, xg: 0, xgb: { h: 0, m: 0, l: 0 } };
  const shots = (A.sf / gpA) * (B.sa / gpB) / L.sapg;
  let mh = (A.oh * B.dh) / L.h;
  let mm = (A.om * B.dm) / L.m;
  let ml = (A.ol * B.dl) / L.l;
  const tot = mh + mm + ml;
  mh /= tot;
  mm /= tot;
  ml /= tot;
  const sv = {
    h: gk && gk.gh != null ? gk.gh : LSV.h,
    m: gk && gk.gm != null ? gk.gm : LSV.m,
    l: gk && gk.gl != null ? gk.gl : LSV.l,
  };
  return {
    shots,
    mix: { h: mh * 100, m: mm * 100, l: ml * 100 },
    xg: shots * (mh * (1 - sv.h) + mm * (1 - sv.m) + ml * (1 - sv.l)),
    xgb: { h: shots * mh * (1 - sv.h), m: shots * mm * (1 - sv.m), l: shots * ml * (1 - sv.l) },
  };
}

/** One team attacking the other: EV + PP terms and their total. */
export function direction(
  D: MatchupData,
  s: string,
  tA: string,
  vA: "home" | "road",
  tB: string,
  vB: "home" | "road",
  gk: GkRow | null,
  venue: boolean,
): Direction {
  const gpA = gpOf(D, s, tA, vA, venue);
  const gpB = gpOf(D, s, tB, vB, venue);
  const ev = term(prof(D, s, tA, vA, "ev", venue), prof(D, s, tB, vB, "ev", venue), leagueK(D, s, "ev"), gk, gpA, gpB);
  const pp = term(prof(D, s, tA, vA, "pp", venue), prof(D, s, tB, vB, "pp", venue), leagueK(D, s, "pp"), gk, gpA, gpB);
  return { ev, pp, xg: ev.xg + pp.xg };
}

export function gkList(D: MatchupData, s: string, t: string): GkRow[] {
  return D.gk.filter((g) => g.s === s && g.t === t); // already ordered by season shots desc
}
export function pickGk(D: MatchupData, s: string, t: string, override: string | null): GkRow | null {
  const l = gkList(D, s, t);
  if (override) {
    const m = l.find((g) => g.n === override);
    if (m) return m;
  }
  return l[0] || null;
}

/** The "style clash" narrative bits (plain sentences), ported from v3.
 *  `ab` = tA(road) attacking tB(home); `ba` = the reverse. gkB prices ab, gkA prices ba. */
export function styleClash(
  D: MatchupData,
  s: string,
  tA: string,
  tB: string,
  ab: Direction,
  ba: Direction,
  gkA: GkRow | null,
  gkB: GkRow | null,
  venue: boolean,
): string[] {
  const bits: string[] = [];
  const Lev = leagueK(D, s, "ev");
  const Aev = prof(D, s, tA, "road", "ev", venue);
  const Bev = prof(D, s, tB, "home", "ev", venue);
  if (Aev && Bev) {
    if (Aev.oh - Lev.h > 1.5 && Bev.dh - Lev.h < -1.5)
      bits.push(`${tA} hunts the slot at evens (${Aev.oh.toFixed(1)}% HD) but ${tB} concedes only ${Bev.dh.toFixed(1)}% — a genuine style fight.`);
    else if (Aev.oh - Lev.h > 1.5 && Bev.dh - Lev.h > 1.5)
      bits.push(`${tA} hunts the slot AND ${tB} bleeds it (${Bev.dh.toFixed(1)}% HD allowed) — the danger zone lights up.`);
  }

  const ppGap = ab.pp.xg - ba.pp.xg;
  if (Math.abs(ppGap) > 0.12)
    bits.push(`Special-teams edge: ${ppGap > 0 ? tA : tB} by ${Math.abs(ppGap).toFixed(2)} PP xG — ${ppGap > 0 ? `${tA}'s power play vs ${tB}'s kill` : `${tB}'s power play vs ${tA}'s kill`} is the mismatch.`);

  const rA = D.rush[`${s}|${tA}`];
  const rB = D.rush[`${s}|${tB}`];
  const LR = LEAGUE_RUSH;
  if (rA && rB) {
    if (rA[0] > LR + 0.7 && rB[1] > LR + 0.5)
      bits.push(`Transition: ${tA} plays rush hockey (${rA[0].toFixed(1)}% of attempts) and ${tB} gives up rush chances (${rB[1].toFixed(1)}% allowed) — watch odd-man traffic.`);
    else if (rA[0] > LR + 0.7 && rB[1] < LR - 0.4)
      bits.push(`Transition: ${tA} wants to rush (${rA[0].toFixed(1)}%) but ${tB} shuts the door in the neutral zone (${rB[1].toFixed(1)}% allowed).`);
    if (rB[0] > LR + 0.7 && rA[1] > LR + 0.5)
      bits.push(`Other way: ${tB} attacks off the rush (${rB[0].toFixed(1)}%) into ${tA}'s leaky transition D (${rA[1].toFixed(1)}% allowed).`);
  }

  const eB = gkB && gkB.gh != null ? gkB.gh - LSV.h : 0;
  const eA = gkA && gkA.gh != null ? gkA.gh - LSV.h : 0;
  if (Math.abs(eB - eA) > 0.01) {
    const win = eB > eA ? { gk: gkB, t: tB } : { gk: gkA, t: tA };
    if (win.gk)
      bits.push(`Goalie edge on high-danger: ${win.gk.n} (${win.t}) by ${(Math.abs(eB - eA) * 100).toFixed(1)} points of HD save %.`);
  }
  return bits;
}
