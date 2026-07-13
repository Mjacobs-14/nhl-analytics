"use client";

import { useMemo, useRef, useState } from "react";
import type { ShotVolumePoint } from "@/lib/analytics";

const W = 640;
const H = 440;
const M = { top: 30, right: 26, bottom: 44, left: 48 };

/** Ticks at a clean step so the axis lands on round numbers. */
function ticks(max: number): number[] {
  const step = [0.25, 0.5, 1, 2, 5].find((s) => max / s <= 7) ?? 5;
  const out: number[] = [];
  for (let v = 0; v <= max; v += step) out.push(Number(v.toFixed(2)));
  return out;
}

/** Shot volume (SOG/60) vs output (P/GP) scatter with median midlines —
 *  quadrants separate the trigger-happy from the efficient. Forwards and
 *  defensemen carry distinct hues (validated palette); nearest-point hover
 *  so nobody has to land a pointer on a 4px dot. */
export function QuadrantChart({
  points,
  medianX,
  medianY,
}: {
  points: ShotVolumePoint[];
  medianX: number;
  medianY: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const xMax = Math.max(...points.map((p) => p.sogPer60)) * 1.06;
  const yMax = Math.max(...points.map((p) => p.ppg)) * 1.08;
  const x = (v: number) => M.left + (v / xMax) * (W - M.left - M.right);
  const y = (v: number) => H - M.bottom - (v / yMax) * (H - M.top - M.bottom);

  // Selective direct labels: the season's extremes, not every dot.
  const labeled = useMemo(() => {
    if (points.length === 0) return new Set<number>();
    let topPpg = 0;
    let topSog = 0;
    points.forEach((p, i) => {
      if (p.ppg > points[topPpg].ppg) topPpg = i;
      if (p.sogPer60 > points[topSog].sogPer60) topSog = i;
    });
    return new Set([topPpg, topSog]);
  }, [points]);

  function onMove(e: React.PointerEvent) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    // nearest point within ~24 screen px — a reachable target, not a pinpoint
    let best = -1;
    let bestD = 24 * (W / rect.width);
    points.forEach((p, i) => {
      const d = Math.hypot(x(p.sogPer60) - px, y(p.ppg) - py);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setHover(best === -1 ? null : best);
  }

  if (points.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        No qualifying skaters for this slice.
      </p>
    );
  }

  const h = hover !== null ? points[hover] : null;
  const colorFor = (pos: string) =>
    pos === "D" ? "var(--zone-4)" : "var(--rink-blue)";

  return (
    <div>
      <div className="flex items-center gap-4 mb-2 text-xs" style={{ color: "var(--muted)" }}>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "var(--rink-blue)" }} />
          Forwards ({points.filter((p) => p.position !== "D").length})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "var(--zone-4)" }} />
          Defensemen ({points.filter((p) => p.position === "D").length})
        </span>
      </div>

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Shots on goal per 60 minutes versus points per game, one dot per skater"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        >
          {ticks(yMax).map((v) => (
            <g key={`y${v}`}>
              <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
              <text x={M.left - 6} y={y(v) + 3} textAnchor="end" fontSize="10"
                fill="var(--faint)" fontFamily="var(--font-mono)">
                {v.toFixed(2)}
              </text>
            </g>
          ))}
          {ticks(xMax).map((v) => (
            <g key={`x${v}`}>
              <line x1={x(v)} x2={x(v)} y1={M.top} y2={H - M.bottom} stroke="var(--line)" strokeWidth="1" />
              <text x={x(v)} y={H - M.bottom + 16} textAnchor="middle" fontSize="10"
                fill="var(--faint)" fontFamily="var(--font-mono)">
                {v}
              </text>
            </g>
          ))}

          {/* median midlines — thresholds, so dashed like the peak baseline */}
          <line x1={x(medianX)} x2={x(medianX)} y1={M.top} y2={H - M.bottom}
            stroke="var(--faint)" strokeWidth="1.5" strokeDasharray="5 4" />
          <line x1={M.left} x2={W - M.right} y1={y(medianY)} y2={y(medianY)}
            stroke="var(--faint)" strokeWidth="1.5" strokeDasharray="5 4" />

          {/* quadrant captions */}
          <text x={W - M.right - 4} y={M.top + 12} textAnchor="end" fontSize="10"
            fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
            SHOOTS &amp; CONVERTS
          </text>
          <text x={M.left + 6} y={M.top + 12} fontSize="10"
            fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
            PICKS HIS SPOTS
          </text>
          <text x={W - M.right - 4} y={H - M.bottom - 8} textAnchor="end" fontSize="10"
            fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
            VOLUME, NO PAYOFF
          </text>
          <text x={M.left + 6} y={H - M.bottom - 8} fontSize="10"
            fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
            QUIET NIGHTS
          </text>

          {points.map((p, i) => (
            <circle
              key={p.playerId}
              cx={x(p.sogPer60)}
              cy={y(p.ppg)}
              r={i === hover ? 6 : 4}
              fill={colorFor(p.position)}
              stroke="var(--card)"
              strokeWidth="2"
            />
          ))}

          {points.map((p, i) =>
            labeled.has(i) && i !== hover ? (
              <text
                key={`l${p.playerId}`}
                x={x(p.sogPer60) + (x(p.sogPer60) > W / 2 ? -9 : 9)}
                y={y(p.ppg) + 4}
                textAnchor={x(p.sogPer60) > W / 2 ? "end" : "start"}
                fontSize="10.5"
                fill="var(--ink)"
                fontFamily="var(--font-mono)"
                fontWeight="600"
              >
                {p.name}
              </text>
            ) : null
          )}

          {/* axis titles */}
          <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" fontSize="10"
            fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5">
            SHOTS ON GOAL PER 60
          </text>
          <text x={12} y={(M.top + H - M.bottom) / 2} textAnchor="middle" fontSize="10"
            fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5"
            transform={`rotate(-90 12 ${(M.top + H - M.bottom) / 2})`}>
            POINTS PER GAME
          </text>
        </svg>

        {h && hover !== null && (
          <div
            className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
            style={{
              left: `${(x(h.sogPer60) / W) * 100}%`,
              top: `${(y(h.ppg) / H) * 100}%`,
              transform: `translate(${x(h.sogPer60) > W / 2 ? "calc(-100% - 10px)" : "10px"}, -50%)`,
            }}
          >
            <div className="font-medium mb-0.5" style={{ fontFamily: "var(--font-body)" }}>
              {h.name} <span style={{ color: "var(--muted)" }}>· {h.position}</span>
            </div>
            <div className="stat font-semibold">{h.ppg.toFixed(2)} P/GP</div>
            <div className="stat" style={{ color: "var(--muted)" }}>
              {h.sogPer60.toFixed(2)} SOG/60 · {h.gp} GP · {h.toiMinPerGame.toFixed(1)} min/gm
            </div>
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
                <th className="text-right">P/GP</th>
                <th className="text-right">SOG/60</th>
                <th className="text-right">TOI/GP</th>
              </tr>
            </thead>
            <tbody>
              {[...points]
                .sort((a, b) => b.ppg - a.ppg)
                .map((p) => (
                  <tr key={p.playerId}>
                    <td>{p.name}</td>
                    <td className="stat">{p.position}</td>
                    <td className="stat text-right">{p.gp}</td>
                    <td className="stat text-right">{p.ppg.toFixed(2)}</td>
                    <td className="stat text-right">{p.sogPer60.toFixed(2)}</td>
                    <td className="stat text-right">{p.toiMinPerGame.toFixed(1)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
