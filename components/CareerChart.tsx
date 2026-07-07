"use client";

import { useState } from "react";
import { formatSeason } from "@/lib/zones";

interface SeasonPoint {
  season: number;
  ppg: number;
  gamesPlayed: number;
}

const W = 560;
const H = 200;
const M = { top: 18, right: 20, bottom: 30, left: 40 };

/** Career points-per-game, one line, with the peak baseline the algorithm
 *  compares against. Crosshair + tooltip on hover. */
export function CareerChart({ points, peak }: { points: SeasonPoint[]; peak: number | null }) {
  const [hover, setHover] = useState<number | null>(null);

  if (points.length < 2) {
    return (
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        Not enough NHL seasons to chart yet.
      </p>
    );
  }

  const yMax = Math.max(...points.map((p) => p.ppg), peak ?? 0) * 1.15 || 1;
  const x = (i: number) => M.left + (i / (points.length - 1)) * (W - M.left - M.right);
  const y = (v: number) => H - M.bottom - (v / yMax) * (H - M.top - M.bottom);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.ppg).toFixed(1)}`).join(" ");
  const gridVals = [0.25, 0.5, 0.75].map((f) => yMax * f);
  const h = hover !== null ? points[hover] : null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Points per game by season">
        {gridVals.map((v) => (
          <g key={v}>
            <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
            <text x={M.left - 6} y={y(v) + 3} textAnchor="end" fontSize="10" fill="var(--faint)"
              fontFamily="var(--font-mono)">
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        <line x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} stroke="var(--faint)" strokeWidth="1" />

        {peak !== null && (
          <g>
            <line x1={M.left} x2={W - M.right} y1={y(peak)} y2={y(peak)}
              stroke="var(--zone-4)" strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={M.left + 4} y={y(peak) - 5} textAnchor="start" fontSize="10"
              fill="var(--zone-4)" fontFamily="var(--font-display)" letterSpacing="1">
              PEAK BASELINE {peak.toFixed(2)}
            </text>
          </g>
        )}

        {hover !== null && (
          <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom}
            stroke="var(--faint)" strokeWidth="1" strokeDasharray="3 3" />
        )}

        <path d={line} fill="none" stroke="var(--rink-blue)" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />

        {points.map((p, i) => (
          <g key={p.season}>
            <circle cx={x(i)} cy={y(p.ppg)} r={i === hover ? 5 : 3.5} fill="var(--rink-blue)"
              stroke="var(--card)" strokeWidth="2" />
            {/* oversized hit target */}
            <circle cx={x(i)} cy={y(p.ppg)} r="14" fill="transparent"
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
          </g>
        ))}

        {/* direct label on the last point */}
        <text x={x(points.length - 1)} y={y(points[points.length - 1].ppg) - 10} textAnchor="end"
          fontSize="11" fill="var(--ink)" fontFamily="var(--font-mono)" fontWeight="600">
          {points[points.length - 1].ppg.toFixed(2)}
        </text>

        {points.map((p, i) =>
          points.length <= 12 || i % 2 === 0 || i === points.length - 1 ? (
            <text key={p.season} x={x(i)} y={H - M.bottom + 16} textAnchor="middle" fontSize="9.5"
              fill="var(--muted)" fontFamily="var(--font-mono)">
              {formatSeason(p.season).slice(2)}
            </text>
          ) : null
        )}
      </svg>

      {h && hover !== null && (
        <div
          className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm"
          style={{
            left: `${(x(hover) / W) * 100}%`,
            top: 0,
            transform: `translateX(${hover > points.length / 2 ? "-110%" : "10%"})`,
          }}
        >
          <div className="eyebrow">{formatSeason(h.season)}</div>
          <div className="stat font-semibold">{h.ppg.toFixed(2)} P/GP</div>
          <div className="stat" style={{ color: "var(--muted)" }}>{h.gamesPlayed} GP</div>
        </div>
      )}
    </div>
  );
}
