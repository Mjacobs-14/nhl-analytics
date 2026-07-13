"use client";

import { useState } from "react";
import type { VegasFluRow } from "@/lib/analytics";

const W = 640;
const ROW_H = 26;
const BAR_H = 14;
const TOP = 30;
const GAP = 30; // between the flu ward and the immune group
const N = 10; // per group

/** Diverging bars around zero: road P/GP in Vegas minus every other road
 *  game. Negative (red) = caught the flu; positive (blue) = thrives at
 *  T-Mobile. Warm/cool poles, values at the tips, full-width hover rows. */
export function VegasFluChart({ rows }: { rows: VegasFluRow[] }) {
  const [hover, setHover] = useState<number | null>(null);

  // rows arrive sorted ascending by fluPpg: worst flu first
  const flu = rows.slice(0, N);
  const immune = rows.slice(-N).reverse(); // best first
  const shown = [...flu, ...immune];

  const maxAbs = Math.max(...shown.map((r) => Math.abs(r.fluPpg)), 0.1);
  const cx = W / 2;
  const span = W / 2 - 150; // room for names and tip values on both sides
  const xv = (v: number) => cx + (v / maxAbs) * span;
  const rowY = (i: number) => TOP + i * ROW_H + (i >= N ? GAP : 0);
  const H = TOP + shown.length * ROW_H + GAP + 8;

  const h = hover !== null ? shown[hover] : null;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Points per game in Vegas minus all other road games, worst and best ten players"
      >
        {/* pole captions */}
        <text x={cx - 12} y={14} textAnchor="end" fontSize="10"
          fill="var(--zone-5)" fontFamily="var(--font-display)" letterSpacing="1.5">
          ← CAUGHT THE FLU
        </text>
        <text x={cx + 12} y={14} fontSize="10"
          fill="var(--rink-blue)" fontFamily="var(--font-display)" letterSpacing="1.5">
          THRIVES IN VEGAS →
        </text>

        {/* zero axis */}
        <line x1={cx} x2={cx} y1={TOP - 8} y2={H - 4} stroke="var(--faint)" strokeWidth="1" />

        {/* group label for the immune half */}
        <text x={cx} y={rowY(N) - 12} textAnchor="middle" fontSize="10"
          fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
          · · ·
        </text>

        {shown.map((r, i) => {
          const neg = r.fluPpg < 0;
          const y = rowY(i);
          const barX = neg ? xv(r.fluPpg) : cx + 1;
          const barW = Math.max(Math.abs(xv(r.fluPpg) - cx) - 1, 2);
          const color = neg ? "var(--zone-5)" : "var(--rink-blue)";
          return (
            <g key={r.playerId}>
              {/* rounded data-end, square at the zero baseline */}
              <path
                d={
                  neg
                    ? `M ${barX + barW} ${y} H ${barX + 4} Q ${barX} ${y} ${barX} ${y + 4} V ${y + BAR_H - 4} Q ${barX} ${y + BAR_H} ${barX + 4} ${y + BAR_H} H ${barX + barW} Z`
                    : `M ${barX} ${y} H ${barX + barW - 4} Q ${barX + barW} ${y} ${barX + barW} ${y + 4} V ${y + BAR_H - 4} Q ${barX + barW} ${y + BAR_H} ${barX + barW - 4} ${y + BAR_H} H ${barX} Z`
                }
                fill={color}
                opacity={hover === null || hover === i ? 1 : 0.45}
              />
              {/* name on the empty side of the axis */}
              <text
                x={neg ? cx + 8 : cx - 8}
                y={y + BAR_H - 3}
                textAnchor={neg ? "start" : "end"}
                fontSize="11"
                fill="var(--ink)"
                fontFamily="var(--font-body)"
              >
                {r.name}
              </text>
              {/* value at the tip */}
              <text
                x={neg ? barX - 5 : barX + barW + 5}
                y={y + BAR_H - 3}
                textAnchor={neg ? "end" : "start"}
                fontSize="10"
                fill="var(--muted)"
                fontFamily="var(--font-mono)"
              >
                {r.fluPpg > 0 ? "+" : ""}
                {r.fluPpg.toFixed(2)}
              </text>
              {/* full-width hit target */}
              <rect
                x={0}
                y={y - (ROW_H - BAR_H) / 2}
                width={W}
                height={ROW_H}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover(null)}
              />
            </g>
          );
        })}
      </svg>

      {h && hover !== null && (
        <div
          className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
          style={{
            left: "50%",
            top: `${(rowY(hover) / H) * 100}%`,
            transform: `translate(${h.fluPpg < 0 ? "12px" : "calc(-100% - 12px)"}, ${hover > shown.length / 2 ? "-100%" : "8px"})`,
          }}
        >
          <div className="font-medium mb-0.5">
            {h.name} <span style={{ color: "var(--muted)" }}>· {h.position}</span>
          </div>
          <div className="stat font-semibold">
            {h.vegasPpg.toFixed(2)} P/GP in Vegas ({h.vegasGp} GP)
          </div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            {h.roadPpg.toFixed(2)} P/GP other roads ({h.roadGp} GP)
          </div>
        </div>
      )}

      <details className="mt-2">
        <summary className="eyebrow cursor-pointer select-none">
          View all {rows.length} qualifying players as table
        </summary>
        <div className="overflow-y-auto mt-2" style={{ maxHeight: 320 }}>
          <table className="board text-sm">
            <thead>
              <tr>
                <th>Player</th>
                <th>Pos</th>
                <th className="text-right">Vegas GP</th>
                <th className="text-right">Vegas P/GP</th>
                <th className="text-right">Road P/GP</th>
                <th className="text-right">Δ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.playerId}>
                  <td>{r.name}</td>
                  <td className="stat">{r.position}</td>
                  <td className="stat text-right">{r.vegasGp}</td>
                  <td className="stat text-right">{r.vegasPpg.toFixed(2)}</td>
                  <td className="stat text-right">{r.roadPpg.toFixed(2)}</td>
                  <td className="stat text-right">
                    {r.fluPpg > 0 ? "+" : ""}
                    {r.fluPpg.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
