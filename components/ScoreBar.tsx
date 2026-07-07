import { zoneVar } from "@/lib/zones";

/** Compact fresh→cooked meter for table rows. Number + label carry the value;
 *  the bar is reinforcement, never the only encoding. */
export function ScoreBar({ score, label }: { score: number; label: string }) {
  return (
    <div className="flex items-center gap-3 min-w-[180px]">
      <span className="stat text-sm font-semibold w-11 text-right">{score.toFixed(1)}</span>
      <div
        className="h-2 flex-1 rounded-full overflow-hidden"
        style={{ background: "var(--gauge-track)" }}
        role="img"
        aria-label={`Cooked score ${score.toFixed(1)} out of 100 — ${label}`}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${score}%`, background: zoneVar(score) }}
        />
      </div>
      <span className="chip" style={{ color: zoneVar(score) }}>
        {label}
      </span>
    </div>
  );
}
