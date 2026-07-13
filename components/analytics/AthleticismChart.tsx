"use client";

import { useMemo, useRef, useState } from "react";
import type { AthleticismRow } from "@/lib/analytics";

const W = 640;
const H = 420;
const M = { top: 26, right: 26, bottom: 44, left: 52 };

/** NHL Edge tracking: burst rate (20+ mph sprints per game) vs. top
 *  recorded speed. Same F/D palette as the shot-volume chart. */
export function AthleticismChart({ rows }: { rows: AthleticismRow[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const xMax = Math.max(...rows.map((r) => r.burstsPerGame)) * 1.06;
  const yLo = Math.floor(Math.min(...rows.map((r) => r.topSpeedMph)) - 0.4);
  const yHi = Math.ceil(Math.max(...rows.map((r) => r.topSpeedMph)) + 0.4);
  const x = (v: number) => M.left + (v / xMax) * (W - M.left - M.right);
  const y = (v: number) => H - M.bottom - ((v - yLo) / (yHi - yLo)) * (H - M.top - M.bottom);

  const xTicks: number[] = [];
  for (let v = 0; v <= xMax; v += 1) xTicks.push(v);
  const yTicks: number[] = [];
  for (let v = yLo; v <= yHi; v += 1) yTicks.push(v);

  const labeled = useMemo(() => {
    if (rows.length === 0) return new Set<number>();
    let fastest = 0;
    let mostBursts = 0;
    rows.forEach((r, i) => {
      if (r.topSpeedMph > rows[fastest].topSpeedMph) fastest = i;
      if (r.burstsPerGame > rows[mostBursts].burstsPerGame) mostBursts = i;
    });
    return new Set([fastest, mostBursts]);
  }, [rows]);

  function onMove(e: React.PointerEvent) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    let best = -1;
    let bestD = 24 * (W / rect.width);
    rows.forEach((r, i) => {
      const d = Math.hypot(x(r.burstsPerGame) - px, y(r.topSpeedMph) - py);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setHover(best === -1 ? null : best);
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        NHL Edge tracking begins in 2021–22 — pick a newer season for this one.
      </p>
    );
  }

  const h = hover !== null ? rows[hover] : null;
  const colorFor = (pos: string) =>
    pos === "D" ? "var(--zone-4)" : "var(--rink-blue)";

  return (
    <div>
      <div className="flex items-center gap-4 mb-2 text-xs" style={{ color: "var(--muted)" }}>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "var(--rink-blue)" }} />
          Forwards ({rows.filter((r) => r.position !== "D").length})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "var(--zone-4)" }} />
          Defensemen ({rows.filter((r) => r.position === "D").length})
        </span>
      </div>

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Twenty-plus mph bursts per game versus top skating speed, one dot per skater"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        >
          {yTicks.map((v) => (
            <g key={`y${v}`}>
              <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
              <text x={M.left - 6} y={y(v) + 3} textAnchor="end" fontSize="10"
                fill="var(--faint)" fontFamily="var(--font-mono)">
                {v}
              </text>
            </g>
          ))}
          {xTicks.map((v) => (
            <g key={`x${v}`}>
              <line x1={x(v)} x2={x(v)} y1={M.top} y2={H - M.bottom} stroke="var(--line)" strokeWidth="1" />
              <text x={x(v)} y={H - M.bottom + 16} textAnchor="middle" fontSize="10"
                fill="var(--faint)" fontFamily="var(--font-mono)">
                {v}
              </text>
            </g>
          ))}

          {rows.map((r, i) => (
            <circle
              key={r.playerId}
              cx={x(r.burstsPerGame)}
              cy={y(r.topSpeedMph)}
              r={i === hover ? 6 : 4}
              fill={colorFor(r.position)}
              stroke="var(--card)"
              strokeWidth="2"
            />
          ))}

          {rows.map((r, i) =>
            labeled.has(i) && i !== hover ? (
              <text
                key={`l${r.playerId}`}
                x={x(r.burstsPerGame) + (x(r.burstsPerGame) > W / 2 ? -9 : 9)}
                y={y(r.topSpeedMph) + 4}
                textAnchor={x(r.burstsPerGame) > W / 2 ? "end" : "start"}
                fontSize="10.5"
                fill="var(--ink)"
                fontFamily="var(--font-mono)"
                fontWeight="600"
              >
                {r.name}
              </text>
            ) : null
          )}

          <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" fontSize="10"
            fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5">
            20+ MPH BURSTS PER GAME
          </text>
          <text x={12} y={(M.top + H - M.bottom) / 2} textAnchor="middle" fontSize="10"
            fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5"
            transform={`rotate(-90 12 ${(M.top + H - M.bottom) / 2})`}>
            TOP SPEED (MPH)
          </text>
        </svg>

        {h && hover !== null && (
          <div
            className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
            style={{
              left: `${(x(h.burstsPerGame) / W) * 100}%`,
              top: `${(y(h.topSpeedMph) / H) * 100}%`,
              transform: `translate(${x(h.burstsPerGame) > W / 2 ? "calc(-100% - 10px)" : "10px"}, -50%)`,
            }}
          >
            <div className="font-medium mb-0.5">
              {h.name} <span style={{ color: "var(--muted)" }}>· {h.position}</span>
            </div>
            <div className="stat font-semibold">
              {h.topSpeedMph.toFixed(1)} mph top · {h.burstsPerGame.toFixed(1)} bursts/gm
            </div>
            <div className="stat" style={{ color: "var(--muted)" }}>
              {h.milesPerGame.toFixed(1)} mi/gm · shot {h.topShotSpeedMph.toFixed(0)} mph · {h.gp} GP
            </div>
            {h.speedPctile !== null && (
              <div className="stat" style={{ color: "var(--muted)" }}>
                speed p{Math.round(h.speedPctile)} · shot p{h.shotPctile !== null ? Math.round(h.shotPctile) : "—"} · dist p{h.distPctile !== null ? Math.round(h.distPctile) : "—"}
              </div>
            )}
          </div>
        )}
      </div>

      <details className="mt-2">
        <summary className="eyebrow cursor-pointer select-none">View as table</summary>
        <div className="overflow-y-auto mt-2" style={{ maxHeight: 320 }}>
          <table className="board text-sm">
            <thead>
              <tr>
                <th>Player</th>
                <th>Pos</th>
                <th className="text-right">GP</th>
                <th className="text-right">Top mph</th>
                <th className="text-right">Bursts/gm</th>
                <th className="text-right">Mi/gm</th>
                <th className="text-right">Shot mph</th>
              </tr>
            </thead>
            <tbody>
              {[...rows]
                .sort((a, b) => b.topSpeedMph - a.topSpeedMph)
                .map((r) => (
                  <tr key={r.playerId}>
                    <td>{r.name}</td>
                    <td className="stat">{r.position}</td>
                    <td className="stat text-right">{r.gp}</td>
                    <td className="stat text-right">{r.topSpeedMph.toFixed(1)}</td>
                    <td className="stat text-right">{r.burstsPerGame.toFixed(1)}</td>
                    <td className="stat text-right">{r.milesPerGame.toFixed(1)}</td>
                    <td className="stat text-right">{r.topShotSpeedMph.toFixed(0)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
