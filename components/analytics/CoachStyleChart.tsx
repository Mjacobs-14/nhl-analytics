"use client";

import { useMemo, useRef, useState } from "react";
import type { CoachStyleRow } from "@/lib/analytics";

const W = 640;
const H = 420;
const M = { top: 30, right: 26, bottom: 44, left: 52 };

function domainTicks(min: number, max: number): number[] {
  const lo = Math.floor(min * 4) / 4;
  const hi = Math.ceil(max * 4) / 4;
  const out: number[] = [];
  for (let v = lo; v <= hi + 1e-9; v += 0.25) out.push(Number(v.toFixed(2)));
  return out;
}

/** Coach fingerprints: expected goals created vs. conceded per game, one
 *  dot per bench (coach × team, min 20 GP). Single hue — the coaches are
 *  the identity, carried by hover + labels on the extremes. */
export function CoachStyleChart({ rows }: { rows: CoachStyleRow[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const ticksX = domainTicks(
    Math.min(...rows.map((r) => r.xgfPerGame)),
    Math.max(...rows.map((r) => r.xgfPerGame))
  );
  const ticksY = domainTicks(
    Math.min(...rows.map((r) => r.xgaPerGame)),
    Math.max(...rows.map((r) => r.xgaPerGame))
  );
  const x0 = ticksX[0];
  const x1 = ticksX[ticksX.length - 1];
  const y0 = ticksY[0];
  const y1 = ticksY[ticksY.length - 1];
  const x = (v: number) => M.left + ((v - x0) / (x1 - x0)) * (W - M.left - M.right);
  const y = (v: number) => H - M.bottom - ((v - y0) / (y1 - y0)) * (H - M.top - M.bottom);

  // label the best and worst xG differential — the two benches worth naming
  const labeled = useMemo(() => {
    if (rows.length === 0) return new Set<number>();
    let best = 0;
    let worst = 0;
    rows.forEach((r, i) => {
      const d = r.xgfPerGame - r.xgaPerGame;
      if (d > rows[best].xgfPerGame - rows[best].xgaPerGame) best = i;
      if (d < rows[worst].xgfPerGame - rows[worst].xgaPerGame) worst = i;
    });
    return new Set([best, worst]);
  }, [rows]);

  function onMove(e: React.PointerEvent) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    let best = -1;
    let bestD = 24 * (W / rect.width);
    rows.forEach((r, i) => {
      const d = Math.hypot(x(r.xgfPerGame) - px, y(r.xgaPerGame) - py);
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
        No coach data for this season yet.
      </p>
    );
  }

  const h = hover !== null ? rows[hover] : null;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Expected goals for versus against per game, one dot per coach"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {ticksY.map((v) => (
          <g key={`y${v}`}>
            <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" />
            <text x={M.left - 6} y={y(v) + 3} textAnchor="end" fontSize="10"
              fill="var(--faint)" fontFamily="var(--font-mono)">
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        {ticksX.map((v) => (
          <g key={`x${v}`}>
            <line x1={x(v)} x2={x(v)} y1={M.top} y2={H - M.bottom} stroke="var(--line)" strokeWidth="1" />
            <text x={x(v)} y={H - M.bottom + 16} textAnchor="middle" fontSize="10"
              fill="var(--faint)" fontFamily="var(--font-mono)">
              {v.toFixed(2)}
            </text>
          </g>
        ))}

        {/* quadrant captions — remember: LOW xGA (bottom) is the good half */}
        <text x={W - M.right - 4} y={M.top + 12} textAnchor="end" fontSize="10"
          fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
          RUN &amp; GUN
        </text>
        <text x={M.left + 6} y={M.top + 12} fontSize="10"
          fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
          GETTING CAVED IN
        </text>
        <text x={W - M.right - 4} y={H - M.bottom - 8} textAnchor="end" fontSize="10"
          fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
          HAVE IT ALL
        </text>
        <text x={M.left + 6} y={H - M.bottom - 8} fontSize="10"
          fill="var(--faint)" fontFamily="var(--font-display)" letterSpacing="1.5">
          ROCK FIGHT
        </text>

        {rows.map((r, i) => (
          <circle
            key={`${r.coach}-${r.team}`}
            cx={x(r.xgfPerGame)}
            cy={y(r.xgaPerGame)}
            r={i === hover ? 7 : 5}
            fill="var(--rink-blue)"
            stroke="var(--card)"
            strokeWidth="2"
          />
        ))}

        {rows.map((r, i) =>
          labeled.has(i) && i !== hover ? (
            <text
              key={`l${r.coach}-${r.team}`}
              x={x(r.xgfPerGame) + (x(r.xgfPerGame) > W / 2 ? -10 : 10)}
              y={y(r.xgaPerGame) + 4}
              textAnchor={x(r.xgfPerGame) > W / 2 ? "end" : "start"}
              fontSize="10.5"
              fill="var(--ink)"
              fontFamily="var(--font-mono)"
              fontWeight="600"
            >
              {r.coach} ({r.team})
            </text>
          ) : null
        )}

        <text x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle" fontSize="10"
          fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5">
          EXPECTED GOALS FOR / GAME
        </text>
        <text x={12} y={(M.top + H - M.bottom) / 2} textAnchor="middle" fontSize="10"
          fill="var(--muted)" fontFamily="var(--font-display)" letterSpacing="1.5"
          transform={`rotate(-90 12 ${(M.top + H - M.bottom) / 2})`}>
          EXPECTED GOALS AGAINST / GAME
        </text>
      </svg>

      {h && hover !== null && (
        <div
          className="card absolute px-3 py-2 text-xs pointer-events-none shadow-sm z-10"
          style={{
            left: `${(x(h.xgfPerGame) / W) * 100}%`,
            top: `${(y(h.xgaPerGame) / H) * 100}%`,
            transform: `translate(${x(h.xgfPerGame) > W / 2 ? "calc(-100% - 10px)" : "10px"}, -50%)`,
          }}
        >
          <div className="font-medium mb-0.5">
            {h.coach} <span style={{ color: "var(--muted)" }}>· {h.team} · {h.gp} GP</span>
          </div>
          <div className="stat font-semibold">
            {h.xgfPerGame.toFixed(2)} xGF · {h.xgaPerGame.toFixed(2)} xGA
          </div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            {h.gfPerGame.toFixed(2)} GF · {h.gaPerGame.toFixed(2)} GA · {h.blockPct.toFixed(1)}% blocks
          </div>
          <div className="stat" style={{ color: "var(--muted)" }}>
            SV {h.teamSvPct.toFixed(1)}% · GSAx {h.gsax > 0 ? "+" : ""}{h.gsax.toFixed(1)}
          </div>
        </div>
      )}

      <details className="mt-2">
        <summary className="eyebrow cursor-pointer select-none">View as table</summary>
        <div className="overflow-y-auto mt-2" style={{ maxHeight: 320 }}>
          <table className="board text-sm">
            <thead>
              <tr>
                <th>Coach</th>
                <th>Team</th>
                <th className="text-right">GP</th>
                <th className="text-right">xGF/g</th>
                <th className="text-right">xGA/g</th>
                <th className="text-right">CF/g</th>
                <th className="text-right">Block%</th>
                <th className="text-right">GSAx</th>
              </tr>
            </thead>
            <tbody>
              {[...rows]
                .sort((a, b) => (b.xgfPerGame - b.xgaPerGame) - (a.xgfPerGame - a.xgaPerGame))
                .map((r) => (
                  <tr key={`${r.coach}-${r.team}`}>
                    <td>{r.coach}</td>
                    <td className="stat">{r.team}</td>
                    <td className="stat text-right">{r.gp}</td>
                    <td className="stat text-right">{r.xgfPerGame.toFixed(2)}</td>
                    <td className="stat text-right">{r.xgaPerGame.toFixed(2)}</td>
                    <td className="stat text-right">{r.cfPerGame.toFixed(1)}</td>
                    <td className="stat text-right">{r.blockPct.toFixed(1)}</td>
                    <td className="stat text-right">{r.gsax > 0 ? "+" : ""}{r.gsax.toFixed(1)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
