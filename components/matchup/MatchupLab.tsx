"use client";

import { useMemo, useState } from "react";
import type { GkRow, MatchupData } from "@/lib/matchup";
import {
  LSV,
  type Direction,
  type Prof,
  direction,
  gkList,
  gpOf,
  pickGk,
  prof,
  seasonsIn,
  styleClash,
  teamsIn,
} from "@/lib/matchup-compute";

// Danger bands map onto the app's rink tokens: high = center-line red,
// medium = the "cooked" amber, low = neutral grey.
const BAND = { h: "var(--rink-red)", m: "var(--zone-4)", l: "var(--zone-3)" };

const fmtSeason = (s: string) => `${s.slice(0, 4)}–${s.slice(6)}`;

function MixBar({ h, m, l }: { h: number; m: number; l: number }) {
  return (
    <div>
      <div style={{ display: "flex", height: 22, borderRadius: 6, overflow: "hidden" }}>
        <div style={{ width: `${h}%`, background: BAND.h }} />
        <div style={{ width: `${m}%`, background: BAND.m }} />
        <div style={{ width: `${l}%`, background: BAND.l }} />
      </div>
      <div
        className="stat"
        style={{ display: "flex", justifyContent: "space-between", color: "var(--faint)", fontSize: 11.5, marginTop: 3 }}
      >
        <span>{h.toFixed(1)}% HD</span>
        <span>{m.toFixed(1)}% MD</span>
        <span>{l.toFixed(1)}% LD</span>
      </div>
    </div>
  );
}

function MixLabel({ left, right }: { left: string; right: string }) {
  return (
    <div
      style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 12, margin: "10px 0 3px", fontWeight: 600 }}
    >
      <span>{left}</span>
      <span>blend</span>
      <span>{right}</span>
    </div>
  );
}

function BandMeter({ label, value, league }: { label: string; value: number | null; league: number }) {
  // Save % scaled onto a 0.75–1.00 track (the meaningful band), with a grey
  // league tick. When the goalie has no career sample, we show the league rate.
  const lo = 0.75;
  const hi = 1.0;
  const val = value ?? league;
  const w = Math.max(0, Math.min(100, ((val - lo) / (hi - lo)) * 100));
  const tk = ((league - lo) / (hi - lo)) * 100;
  const d = value == null ? null : value - league;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "80px 1fr auto", gap: 8, alignItems: "center", fontSize: 12.5, marginTop: 5 }}>
      <div style={{ color: "var(--muted)", fontWeight: 600 }}>{label}</div>
      <div style={{ position: "relative", height: 12, background: "var(--gauge-track)", borderRadius: 3 }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${w}%`, borderRadius: 3, background: "var(--rink-blue)", opacity: 0.8 }} />
        <div style={{ position: "absolute", top: -3, bottom: -3, left: `${tk}%`, width: 2, background: "var(--faint)" }} />
      </div>
      <div className="stat" style={{ fontWeight: 700 }}>
        .{Math.round(val * 1000)}
        {d != null && (
          <span style={{ color: d >= 0 ? "var(--rink-blue)" : "var(--rink-red)" }}>
            {" "}
            ({d >= 0 ? "+" : ""}
            {(d * 100).toFixed(1)})
          </span>
        )}
      </div>
    </div>
  );
}

function GoaliePanel({
  list,
  gk,
  d,
  onSelect,
  teamY,
}: {
  list: GkRow[];
  gk: GkRow | null;
  d: Direction;
  onSelect: (name: string) => void;
  teamY: string;
}) {
  const small = gk != null && gk.gh == null;
  const xgb = {
    h: d.ev.xgb.h + d.pp.xgb.h,
    m: d.ev.xgb.m + d.pp.xgb.m,
    l: d.ev.xgb.l + d.pp.xgb.l,
  };
  return (
    <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
        <span aria-hidden style={{ fontSize: 15 }}>
          🥅
        </span>
        <select
          className="control"
          style={{ padding: "4px 8px", fontSize: 12.5 }}
          aria-label={`Goalie for ${teamY}`}
          value={gk?.n ?? ""}
          onChange={(e) => onSelect(e.target.value)}
        >
          {list.map((g) => (
            <option key={g.n} value={g.n}>
              {g.n} ({g.sh} shots)
            </option>
          ))}
        </select>
        {small && (
          <span style={{ color: "var(--faint)", fontSize: 11.5 }}>&lt;1500 career shots — league-avg rates used</span>
        )}
      </div>
      <BandMeter label="High danger" value={gk?.gh ?? null} league={LSV.h} />
      <BandMeter label="Medium" value={gk?.gm ?? null} league={LSV.m} />
      <BandMeter label="Low danger" value={gk?.gl ?? null} league={LSV.l} />
      <div className="stat" style={{ color: "var(--faint)", fontSize: 11.5, marginTop: 5 }}>
        grey tick = league band save % · total xGA by band: HD {xgb.h.toFixed(2)} · MD {xgb.m.toFixed(2)} · LD {xgb.l.toFixed(2)}
      </div>
    </div>
  );
}

function Panel({
  tX,
  tY,
  vx,
  vy,
  d,
  gk,
  gkListY,
  onSelectGk,
  Aev,
  Bev,
  App,
  Bpp,
  gpX,
  gpY,
}: {
  tX: string;
  tY: string;
  vx: string;
  vy: string;
  d: Direction;
  gk: GkRow | null;
  gkListY: GkRow[];
  onSelectGk: (name: string) => void;
  Aev: Prof | null;
  Bev: Prof | null;
  App: Prof | null;
  Bpp: Prof | null;
  gpX: number;
  gpY: number;
}) {
  return (
    <div className="card p-4">
      <h3 className="display" style={{ fontSize: 15.5 }}>
        {tX} ({vx.toLowerCase()}) attacking {tY} ({vy.toLowerCase()})
      </h3>
      <div style={{ color: "var(--muted)", fontSize: 12.5, marginBottom: 12 }}>
        Even strength: {tX} generates {Aev ? (Aev.sf / gpX).toFixed(1) : "0"} on-net/gm · {tY} allows{" "}
        {Bev ? (Bev.sa / gpY).toFixed(1) : "0"} → blended <b>{d.ev.shots.toFixed(1)}</b> for <b>{d.ev.xg.toFixed(2)} xG</b>
      </div>

      <MixLabel left={`${tX} wants (EV)`} right={`${tY} concedes (EV)`} />
      {Aev && <MixBar h={Aev.oh} m={Aev.om} l={Aev.ol} />}
      <div style={{ height: 7 }} />
      <MixBar h={d.ev.mix.h} m={d.ev.mix.m} l={d.ev.mix.l} />
      <div style={{ color: "var(--faint)", fontSize: 11.5, marginTop: 3 }}>↑ blended EV attack mix</div>
      <div style={{ height: 7 }} />
      {Bev && <MixBar h={Bev.dh} m={Bev.dm} l={Bev.dl} />}

      <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--chip-bg)", borderRadius: 9, fontSize: 12.5, color: "var(--muted)" }}>
        <span style={{ color: "var(--zone-1)", fontWeight: 700 }}>⚡ Special teams:</span> {tX}&rsquo;s PP puts{" "}
        <b>{App && App.sf ? (App.sf / gpX).toFixed(1) : "0"}</b> shots/gm on net ({App ? App.oh.toFixed(0) : 0}% HD) · {tY}&rsquo;s PK
        concedes <b>{Bpp && Bpp.sa ? (Bpp.sa / gpY).toFixed(1) : "0"}</b>/gm ({Bpp ? Bpp.dh.toFixed(0) : 0}% HD) →{" "}
        <b>{d.pp.xg.toFixed(2)} PP xG</b>
      </div>

      <GoaliePanel list={gkListY} gk={gk} d={d} onSelect={onSelectGk} teamY={tY} />
    </div>
  );
}

export function MatchupLab({ data }: { data: MatchupData }) {
  const seasons = useMemo(() => seasonsIn(data), [data]);
  const [season, setSeason] = useState(seasons[0]);
  const teams = useMemo(() => teamsIn(data, season), [data, season]);

  const has = (t: string) => teams.includes(t);
  const [teamA, setTeamA] = useState(has("DAL") ? "DAL" : teams[0]);
  const [teamB, setTeamB] = useState(has("VGK") ? "VGK" : teams.find((t) => t !== (has("DAL") ? "DAL" : teams[0])) ?? teams[1]);
  const [venue, setVenue] = useState(true);
  const [gkAName, setGkAName] = useState<string | null>(null);
  const [gkBName, setGkBName] = useState<string | null>(null);

  function onSeason(newS: string) {
    const ts = teamsIn(data, newS);
    const a = ts.includes(teamA) ? teamA : ts[0];
    const b = ts.includes(teamB) && teamB !== a ? teamB : ts.find((t) => t !== a) ?? ts[1];
    setSeason(newS);
    setTeamA(a);
    setTeamB(b);
    setGkAName(null);
    setGkBName(null);
  }
  function onTeamA(v: string) {
    if (v === teamB) {
      setTeamB(teams.find((t) => t !== v) ?? teamB);
      setGkBName(null);
    }
    setTeamA(v);
    setGkAName(null);
  }
  function onTeamB(v: string) {
    if (v === teamA) {
      setTeamA(teams.find((t) => t !== v) ?? teamA);
      setGkAName(null);
    }
    setTeamB(v);
    setGkBName(null);
  }
  function onSwap() {
    setTeamA(teamB);
    setTeamB(teamA);
    setGkAName(gkBName);
    setGkBName(gkAName);
  }

  const m = useMemo(() => {
    const gkB = pickGk(data, season, teamB, gkBName);
    const gkA = pickGk(data, season, teamA, gkAName);
    const ab = direction(data, season, teamA, "road", teamB, "home", gkB, venue);
    const ba = direction(data, season, teamB, "home", teamA, "road", gkA, venue);
    const vA = venue ? "road" : "all";
    const vB = venue ? "home" : "all";
    const p1 = {
      Aev: prof(data, season, teamA, "road", "ev", venue),
      Bev: prof(data, season, teamB, "home", "ev", venue),
      App: prof(data, season, teamA, "road", "pp", venue),
      Bpp: prof(data, season, teamB, "home", "pp", venue),
      gpX: gpOf(data, season, teamA, "road", venue),
      gpY: gpOf(data, season, teamB, "home", venue),
    };
    const p2 = {
      Aev: prof(data, season, teamB, "home", "ev", venue),
      Bev: prof(data, season, teamA, "road", "ev", venue),
      App: prof(data, season, teamB, "home", "pp", venue),
      Bpp: prof(data, season, teamA, "road", "pp", venue),
      gpX: gpOf(data, season, teamB, "home", venue),
      gpY: gpOf(data, season, teamA, "road", venue),
    };
    const bits = styleClash(data, season, teamA, teamB, ab, ba, gkA, gkB, venue);
    return { gkA, gkB, ab, ba, vA, vB, p1, p2, bits };
  }, [data, season, teamA, teamB, venue, gkAName, gkBName]);

  const same = teamA === teamB;

  return (
    <div>
      {/* controls */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select className="control" aria-label="Season" value={season} onChange={(e) => onSeason(e.target.value)}>
          {seasons.map((s) => (
            <option key={s} value={s}>
              {fmtSeason(s)}
            </option>
          ))}
        </select>
        <select className="control" aria-label="Road team" value={teamA} onChange={(e) => onTeamA(e.target.value)}>
          {teams.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <span style={{ color: "var(--faint)", fontWeight: 600 }}>at</span>
        <select className="control" aria-label="Home team" value={teamB} onChange={(e) => onTeamB(e.target.value)}>
          {teams.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button type="button" className="chip" style={{ cursor: "pointer", border: "1px solid var(--line)" }} onClick={onSwap}>
          ⇄ swap
        </button>
        <button
          type="button"
          className="chip"
          style={{ cursor: "pointer", border: "1px solid var(--line)", color: venue ? "var(--ink)" : "var(--muted)" }}
          aria-pressed={venue}
          onClick={() => setVenue((v) => !v)}
        >
          home/road split: {venue ? "ON" : "OFF"}
        </button>
        <span className="stat" style={{ display: "inline-flex", gap: 14, alignItems: "center", color: "var(--muted)", fontSize: 12 }}>
          <span style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 11, height: 11, borderRadius: 3, background: BAND.h, display: "inline-block" }} /> high danger
          </span>
          <span style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 11, height: 11, borderRadius: 3, background: BAND.m, display: "inline-block" }} /> medium
          </span>
          <span style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 11, height: 11, borderRadius: 3, background: BAND.l, display: "inline-block" }} /> low
          </span>
        </span>
      </div>

      {same ? (
        <div className="card p-6 text-center" style={{ color: "var(--muted)" }}>
          Pick two different teams.
        </div>
      ) : (
        <>
          {/* score */}
          <div
            className="card mb-4"
            style={{ padding: "18px 22px", display: "flex", alignItems: "center", justifyContent: "center", gap: 26, flexWrap: "wrap" }}
          >
            <div className="display" style={{ fontSize: 22, textAlign: "center" }}>
              {teamA}
              <span style={{ display: "block", fontSize: 11, color: "var(--faint)", fontWeight: 600 }}>{m.vA.toUpperCase()}</span>
            </div>
            <div className="stat" style={{ fontSize: 34, fontWeight: 700, textAlign: "center", letterSpacing: "-0.02em" }}>
              {m.ab.xg.toFixed(2)}
              <span style={{ display: "block", fontSize: 11.5, color: "var(--faint)", fontWeight: 600 }}>
                EV {m.ab.ev.xg.toFixed(2)} · PP {m.ab.pp.xg.toFixed(2)}
              </span>
            </div>
            <div style={{ color: "var(--faint)", fontSize: 13, textAlign: "center" }}>
              expected goals
              <br />({fmtSeason(season)} profiles)
            </div>
            <div className="stat" style={{ fontSize: 34, fontWeight: 700, textAlign: "center", letterSpacing: "-0.02em" }}>
              {m.ba.xg.toFixed(2)}
              <span style={{ display: "block", fontSize: 11.5, color: "var(--faint)", fontWeight: 600 }}>
                EV {m.ba.ev.xg.toFixed(2)} · PP {m.ba.pp.xg.toFixed(2)}
              </span>
            </div>
            <div className="display" style={{ fontSize: 22, textAlign: "center" }}>
              {teamB}
              <span style={{ display: "block", fontSize: 11, color: "var(--faint)", fontWeight: 600 }}>{m.vB.toUpperCase()}</span>
            </div>
          </div>

          {/* panels */}
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            <Panel
              tX={teamA}
              tY={teamB}
              vx={m.vA}
              vy={m.vB}
              d={m.ab}
              gk={m.gkB}
              gkListY={gkList(data, season, teamB)}
              onSelectGk={setGkBName}
              {...m.p1}
            />
            <Panel
              tX={teamB}
              tY={teamA}
              vx={m.vB}
              vy={m.vA}
              d={m.ba}
              gk={m.gkA}
              gkListY={gkList(data, season, teamA)}
              onSelectGk={setGkAName}
              {...m.p2}
            />
          </div>

          {/* style clash */}
          <div className="card mt-4" style={{ padding: "14px 18px", color: "var(--muted)", fontSize: 13.5 }}>
            <b style={{ color: "var(--ink)" }}>Style clash:</b>{" "}
            {m.bits.length ? m.bits.join(" ") : "No extreme mismatches — both teams close to league-average profiles."}
          </div>
        </>
      )}

      <p style={{ color: "var(--faint)", fontSize: 12.5, marginTop: 16, maxWidth: "90ch" }}>
        How it works: expected goals = an even-strength term + a power-play term, each: attacker shots/gm × defender allowed/gm ÷
        league average at that strength, with the attack mix from an odds-ratio blend of shot diet × concession profile, priced by
        the selected goalie&rsquo;s career danger-band save % (high ≥ .15 xG / mid / low; league .804/.903/.975).{" "}
        {venue
          ? "Road team uses road profiles, home team home profiles (toggle off for full-season — venue splits halve samples). "
          : "Full-season profiles (venue split off). "}
        PP volume bakes in penalty rates and PP efficiency together. Shorthanded offense (~3% of shots) is ignored. Rush is shown as
        a style clash, not priced — rush shots are already valued through their locations. Goalie bands are career, pooled across
        strengths. <b>A descriptive style-clash preview with predictive-leaning structure, not a betting model</b> — no rest,
        injuries, or current form.
      </p>
    </div>
  );
}
