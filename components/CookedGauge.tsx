import { ZONES } from "@/lib/cooked/config";
import { zoneVar, ZONE_VARS } from "@/lib/zones";

const CX = 130;
const CY = 132;
const R = 100;

function polar(angleDeg: number, r: number): [number, number] {
  const a = (angleDeg * Math.PI) / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

function arcPath(startDeg: number, endDeg: number, r: number): string {
  const [sx, sy] = polar(startDeg, r);
  const [ex, ey] = polar(endDeg, r);
  return `M ${sx.toFixed(2)} ${sy.toFixed(2)} A ${r} ${r} 0 0 1 ${ex.toFixed(2)} ${ey.toFixed(2)}`;
}

/**
 * The cooked gauge: half a face-off circle. Five zone arcs (fresh → cooked)
 * with surface gaps, boundary ticks, a needle, and the score dead center.
 */
export function CookedGauge({ score, label }: { score: number; label: string }) {
  const needleAngle = (score / 100) * 180; // 0 = fresh (left), 180 = cooked (right)
  const zoneSweep = 180 / ZONES.length;

  return (
    <figure className="flex flex-col items-center m-0">
      <svg viewBox="0 0 260 168" className="w-full max-w-sm" role="img"
        aria-label={`Cooked gauge: ${score.toFixed(1)} out of 100, ${label}`}>
        {/* face-off circle framing */}
        <path d={arcPath(184, 356, R + 14)} fill="none" stroke="var(--line)" strokeWidth="1.5" />
        {[225, 270, 315].map((a) => {
          const [x1, y1] = polar(a, R + 10);
          const [x2, y2] = polar(a, R + 18);
          return <line key={a} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line)" strokeWidth="1.5" />;
        })}

        {/* zone arcs with 2-unit surface gaps */}
        {ZONE_VARS.map((color, i) => (
          <path
            key={i}
            d={arcPath(180 + i * zoneSweep + 1.6, 180 + (i + 1) * zoneSweep - 1.6, R)}
            fill="none"
            stroke={color}
            strokeWidth="15"
            strokeLinecap="butt"
          />
        ))}

        {/* boundary ticks + end labels */}
        {[0, 20, 40, 60, 80, 100].map((v) => {
          const [x1, y1] = polar(180 + (v / 100) * 180, R - 12);
          const [x2, y2] = polar(180 + (v / 100) * 180, R - 18);
          return <line key={v} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--faint)" strokeWidth="1.5" />;
        })}
        <text x={CX - R} y={CY + 22} textAnchor="middle" fontSize="11"
          fill="var(--zone-1)" fontFamily="var(--font-display)" fontWeight="600" letterSpacing="1">
          FRESH
        </text>
        <text x={CX + R} y={CY + 22} textAnchor="middle" fontSize="11"
          fill="var(--zone-5)" fontFamily="var(--font-display)" fontWeight="600" letterSpacing="1">
          COOKED
        </text>

        {/* needle */}
        <g style={{ transform: `rotate(${needleAngle}deg)`, transformOrigin: `${CX}px ${CY}px` }}>
          <line x1={CX} y1={CY} x2={CX - R + 26} y2={CY} stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
        </g>
        <circle cx={CX} cy={CY} r="6" fill="var(--ink)" />

        {/* score */}
        <text x={CX} y={CY - 26} textAnchor="middle" fontSize="40" fill="var(--ink)"
          fontFamily="var(--font-mono)" fontWeight="600">
          {score.toFixed(1)}
        </text>
      </svg>
      <figcaption className="mt-1">
        <span className="chip" style={{ color: zoneVar(score), fontSize: "0.85rem" }}>
          {label}
        </span>
      </figcaption>
    </figure>
  );
}
