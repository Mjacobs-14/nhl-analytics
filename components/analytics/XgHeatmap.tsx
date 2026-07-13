"use client";

import { useState } from "react";
import type { XgCell } from "@/lib/analytics";

const W = 640;
const M = { top: 14, right: 18, bottom: 44, left: 64 };
const COLS = 18; // distance: 0–90 ft, 5 ft bins
const ROWS = 9; // angle: 0–90°, 10° bins
const CELL_H = 26;
const H = M.top + ROWS * CELL_H + M.bottom;
const GAP = 2; // surface gap between fills

/** Goal probability by shot location — distance from the net vs. angle off
 *  the center line, one sequential ramp (rink red, more-is-more-dangerous).
 *  color-mix against the card keeps the ramp honest in both themes. */
export function XgHeatmap({ cells }: { cells: XgCell[] }) {
  const [hover, setHover] = useState<XgCell | null>(null);

  const maxXg = Math.max(...cells.map((c) => c.xg));
  const plotW = W - M.left - M.right;
  const cellW = plotW / COLS;
  // angle 0° (head-on) sits on the bottom row, next to the axis
  const cx = (c: XgCell) => M.left + (c.distBin - 1) * cellW;
  const cy = (c: XgCell) => M.top + (ROWS - c.angleBin) * CELL_H;
  const mix = (c: XgCell) => 6 + 94 * (c.xg / maxXg);

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Goal probability by shot distance and angle"
        onPointerLeave={() => setHover(null)}
      >
        {cells.map((c) => {
          const pct = mix(c);
          const showLabel = c.xg >= 0.08;
          const isHover = hover?.distBin === c.distBin && hover?.angleBin === c.angleBin;
          return (
            <g key={`${c.distBin}-${c.angleBin}`}>
              <rect
                x={cx(c)}
                y={cy(c)}
                width={cellW - GAP}
                height={CELL_H - GAP}
                rx="2"
                fill={`color-mix(in oklab, var(--rink-red) ${pct.toFixed(1)}%, var(--card))`}
                stroke={isHover ? "var(--ink)" : "none"}
                strokeWidth="1.5"
                onPointerEnter={() => setHover(c)}
              />
              {showLabel && (
                <text
                  x={cx(c) + (cellW - GAP) / 2}
                  y={cy(c) + CELL_H / 2 + 3}
                  textAnchor="middle"
                  fontSize="9.5"
                  fontFamily="var(--font-mono)"
                  fill={pct > 55 ? "#ffffff" : "var(--ink)"}
                  pointerEvents="none"
                >
                  {Math.round(c.xg * 100)}
                </text>
              )}
            </g>
          );
        })}

        {/* distance ticks every 15 ft */}
        {[0, 15, 30, 45, 60, 75, 90].map((ft) => (
          <text key={ft} x={M.left + (ft / 90) * plotW} y={H - M.bottom + 16}
            textAnchor="middle" fontSize="10" fill="var(--faint)" fontFamily="var(--font-mono)">
            {ft}
          </text>
        ))}
        {/* angle ticks */}
        {[0, 30, 60, 90].map((deg) => (
          <text key={deg} x={M.left - 8} y={M.top + (ROWS - deg / 10) * CELL_H + 3}
            textAnchor="end" fontSize="10" fill="var(--faint)" fontFamily="var(--font-mono)">
            {deg}°
          </text>
        ))}

        <text x={M.left + plotW / 2} y={H - 6} textAnchor="middle" fontSize="10"
          fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5">
          DISTANCE FROM NET (FT)
        </text>
        <text x={14} y={M.top + (ROWS * CELL_H) / 2} textAnchor="middle" fontSize="10"
          fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5"
          transform={`rotate(-90 14 ${M.top + (ROWS * CELL_H) / 2})`}>
          ANGLE OFF CENTER
        </text>
      </svg>

      {hover && (
        <div
          className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
          style={{
            left: `${((cx(hover) + cellW / 2) / W) * 100}%`,
            top: `${(cy(hover) / H) * 100}%`,
            transform: `translate(${cx(hover) > W / 2 ? "calc(-100% - 8px)" : "8px"}, -110%)`,
          }}
        >
          <div className="eyebrow">
            {(hover.distBin - 1) * 5}–{hover.distBin * 5} ft · {(hover.angleBin - 1) * 10}–{hover.angleBin * 10}°
          </div>
          <div className="stat font-semibold">{(hover.xg * 100).toFixed(1)}% goal rate</div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            {hover.goals.toLocaleString()} goals / {hover.shots.toLocaleString()} shots
          </div>
        </div>
      )}

      {/* scale legend */}
      <div className="flex items-center gap-2 mt-1 text-xs" style={{ color: "var(--muted)" }}>
        <span className="stat">0%</span>
        <div
          className="h-2 rounded-full flex-1 max-w-48"
          style={{
            background: `linear-gradient(to right, color-mix(in oklab, var(--rink-red) 6%, var(--card)), var(--rink-red))`,
            border: "1px solid var(--line)",
          }}
        />
        <span className="stat">{Math.round(maxXg * 100)}% of shots become goals</span>
      </div>
    </div>
  );
}
