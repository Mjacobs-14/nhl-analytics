"use client";

import { useState } from "react";
import type { CoachChangeRow } from "@/lib/analytics";
import { formatSeason } from "@/lib/zones";

const W = 640;
const ROW_H = 24;
const TOP = 34;
const LABEL_W = 118; // "VGK · 2023–24"
const VALUE_W = 52; // Δ column on the right

/** Dumbbell board: every mid-season coaching change, old coach's xGF%
 *  stint → new coach's, sorted by the swing. One hue, two shades — the
 *  light dot is the fired guy. */
export function CoachChangeChart({ rows }: { rows: CoachChangeRow[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const H = TOP + rows.length * ROW_H + 10;
  const vals = rows.flatMap((r) => [r.outXgfPct, r.inXgfPct]);
  const lo = Math.floor(Math.min(...vals)) - 1;
  const hi = Math.ceil(Math.max(...vals)) + 1;
  const x = (v: number) => LABEL_W + ((v - lo) / (hi - lo)) * (W - LABEL_W - VALUE_W);
  const rowY = (i: number) => TOP + i * ROW_H + ROW_H / 2;

  const outColor = "color-mix(in oklab, var(--rink-blue) 40%, var(--card))";
  const ticks = [];
  for (let v = Math.ceil(lo / 5) * 5; v <= hi; v += 5) ticks.push(v);

  const h = hover !== null ? rows[hover] : null;

  return (
    <div className="relative">
      <div className="flex items-center gap-4 mb-2 text-xs" style={{ color: "var(--muted)" }}>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full border" style={{ background: outColor, borderColor: "var(--line)" }} />
          Old coach
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "var(--rink-blue)" }} />
          New coach
        </span>
        <span>· share of expected goals (xGF%), 50% = break-even</span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Expected-goal share before and after each mid-season coaching change"
        onPointerLeave={() => setHover(null)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={x(v)} x2={x(v)} y1={TOP - 6} y2={H - 8}
              stroke={v === 50 ? "var(--faint)" : "var(--line)"} strokeWidth="1" />
            <text x={x(v)} y={TOP - 12} textAnchor="middle" fontSize="10"
              fill="var(--faint)" fontFamily="var(--font-mono)">
              {v}%
            </text>
          </g>
        ))}

        {rows.map((r, i) => {
          const y = rowY(i);
          const dim = hover !== null && hover !== i;
          return (
            <g key={`${r.team}-${r.season}-${r.inCoach}`} opacity={dim ? 0.4 : 1}>
              <text x={LABEL_W - 10} y={y + 3.5} textAnchor="end" fontSize="10.5"
                fill="var(--muted)" fontFamily="var(--font-mono)">
                {r.team} {formatSeason(r.season).slice(2)}
              </text>
              <line x1={x(r.outXgfPct)} x2={x(r.inXgfPct)} y1={y} y2={y}
                stroke={outColor} strokeWidth="2" />
              <circle cx={x(r.outXgfPct)} cy={y} r="4.5" fill={outColor}
                stroke="var(--card)" strokeWidth="2" />
              <circle cx={x(r.inXgfPct)} cy={y} r="4.5" fill="var(--rink-blue)"
                stroke="var(--card)" strokeWidth="2" />
              <text x={W - VALUE_W + 8} y={y + 3.5} fontSize="10.5"
                fill={r.dXgfPct >= 0 ? "var(--ink)" : "var(--zone-5)"}
                fontFamily="var(--font-mono)" fontWeight="600">
                {r.dXgfPct >= 0 ? "+" : ""}{r.dXgfPct.toFixed(1)}
              </text>
              <rect x={0} y={y - ROW_H / 2} width={W} height={ROW_H} fill="transparent"
                onPointerEnter={() => setHover(i)} />
            </g>
          );
        })}
      </svg>

      {h && hover !== null && (
        <div
          className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
          style={{
            left: `${(x(Math.max(h.outXgfPct, h.inXgfPct)) / W) * 100}%`,
            top: `${(rowY(hover) / (TOP + rows.length * ROW_H + 10)) * 100}%`,
            transform: `translate(12px, ${hover > rows.length / 2 ? "-100%" : "-8px"})`,
          }}
        >
          <div className="font-medium mb-0.5">
            {h.team} {formatSeason(h.season)}
          </div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            {h.outCoach} ({h.outGp} GP, {h.outXgfPct.toFixed(1)}%)
          </div>
          <div className="stat font-semibold">
            → {h.inCoach} ({h.inGp} GP, {h.inXgfPct.toFixed(1)}%)
          </div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            Δ win% {h.dWinPct > 0 ? "+" : ""}{h.dWinPct.toFixed(1)} · Δ goal diff {h.dGoalDiff > 0 ? "+" : ""}{h.dGoalDiff.toFixed(2)}
          </div>
        </div>
      )}

      <details className="mt-2">
        <summary className="eyebrow cursor-pointer select-none">View as table</summary>
        <div className="overflow-y-auto mt-2" style={{ maxHeight: 320 }}>
          <table className="board text-sm">
            <thead>
              <tr>
                <th>Team</th>
                <th>Season</th>
                <th>Out</th>
                <th>In</th>
                <th className="text-right">xGF% out</th>
                <th className="text-right">xGF% in</th>
                <th className="text-right">Δ xGF%</th>
                <th className="text-right">Δ win%</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.team}-${r.season}-${r.inCoach}`}>
                  <td className="stat">{r.team}</td>
                  <td className="stat">{formatSeason(r.season)}</td>
                  <td>{r.outCoach}</td>
                  <td>{r.inCoach}</td>
                  <td className="stat text-right">{r.outXgfPct.toFixed(1)}</td>
                  <td className="stat text-right">{r.inXgfPct.toFixed(1)}</td>
                  <td className="stat text-right">{r.dXgfPct >= 0 ? "+" : ""}{r.dXgfPct.toFixed(1)}</td>
                  <td className="stat text-right">{r.dWinPct >= 0 ? "+" : ""}{r.dWinPct.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
