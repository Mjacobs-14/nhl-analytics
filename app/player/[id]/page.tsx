import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CookedGauge } from "@/components/CookedGauge";
import { CareerChart } from "@/components/CareerChart";
import { getPlayerDetail } from "@/lib/queries";
import { ageInSeason } from "@/lib/cooked/signals";
import { formatSeason, zoneVar } from "@/lib/zones";
import type { SignalBreakdown } from "@/lib/cooked";

export const dynamic = "force-dynamic";

const SIGNAL_COPY: Record<string, { name: string; explain: string }> = {
  agePressure: {
    name: "Age curve",
    explain: "Where they sit on the typical NHL aging curve for their position.",
  },
  productionFade: {
    name: "Production vs. peak",
    explain: "This season's points per game against their own best-3-seasons baseline.",
  },
  trendSlope: {
    name: "Three-season trend",
    explain: "Sustained slide across the last three seasons, not just one bad year.",
  },
  deploymentDrop: {
    name: "Ice time",
    explain: "Minutes vs. the last two seasons — the coach's revealed opinion.",
  },
  luckRescue: {
    name: "Luck rescue",
    explain: "Shooting % cratered while shot volume held: probably unlucky, score walked back.",
  },
};

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await getPlayerDetail(Number(id));
  if (!detail) notFound();
  const { player, cooked, seasons } = detail;

  const chartPoints = seasons
    .filter((s) => s.gamesPlayed > 0)
    .map((s) => ({ season: s.season, ppg: s.points / s.gamesPlayed, gamesPlayed: s.gamesPlayed }));
  const signals: SignalBreakdown[] = cooked?.signals ? JSON.parse(cooked.signals) : [];
  const age =
    player.birthDate && cooked?.season
      ? Math.floor(ageInSeason(player.birthDate, cooked.season))
      : null;

  return (
    <div>
      <Link href="/" className="eyebrow no-underline">← Back to the board</Link>

      <div className="flex items-center gap-4 mt-4 mb-6">
        {player.headshotUrl && (
          <Image
            src={player.headshotUrl}
            alt={`${player.firstName} ${player.lastName}`}
            width={84}
            height={84}
            className="rounded-full border-2"
            style={{ borderColor: "var(--rink-blue)", background: "var(--chip-bg)" }}
          />
        )}
        <div>
          <h2 className="display text-4xl">
            {player.firstName} {player.lastName}
          </h2>
          <p className="stat text-sm mt-1" style={{ color: "var(--muted)" }}>
            {player.teamAbbrev} · {player.position}
            {player.sweaterNumber ? ` · #${player.sweaterNumber}` : ""}
            {age !== null ? ` · ${age} yrs` : ""}
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4 items-start">
        <section className="card p-6">
          {cooked?.status === "scored" && cooked.score !== null ? (
            <>
              <p className="eyebrow text-center mb-2">The verdict</p>
              <CookedGauge score={cooked.score} label={cooked.label} />
              <div className="mt-5 space-y-3">
                {signals.map((s) => {
                  const copy = SIGNAL_COPY[s.key] ?? { name: s.key, explain: "" };
                  const isRescue = s.key === "luckRescue";
                  const width = Math.min(100, Math.abs(s.contribution) * 2.5);
                  return (
                    <div key={s.key}>
                      <div className="flex justify-between text-sm">
                        <span className="font-medium">{copy.name}</span>
                        <span className="stat" style={{ color: "var(--muted)" }}>
                          {s.value === null
                            ? "no data"
                            : `${s.contribution > 0 ? "+" : ""}${s.contribution.toFixed(1)}`}
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full mt-1" style={{ background: "var(--gauge-track)" }}>
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${s.value === null ? 0 : width}%`,
                            background: isRescue ? "var(--zone-1)" : "var(--zone-4)",
                          }}
                        />
                      </div>
                      <p className="text-xs mt-0.5" style={{ color: "var(--faint)" }}>{copy.explain}</p>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="text-center py-10">
              <p className="display text-2xl mb-2">{cooked?.label ?? "Not scored yet"}</p>
              <p className="text-sm" style={{ color: "var(--muted)" }}>
                {cooked?.status === "goalie"
                  ? "Goalie aging is its own dark art — on the roadmap for v2."
                  : "Needs at least three NHL seasons of 10+ games before the gauge means anything."}
              </p>
            </div>
          )}
        </section>

        <section className="card p-6">
          <p className="eyebrow mb-3">Career production</p>
          <CareerChart
            points={chartPoints}
            peak={cooked?.peakPointsPerGame ?? null}
          />

          <div className="overflow-x-auto mt-5">
            <table className="board">
              <thead>
                <tr>
                  <th>Season</th>
                  <th className="text-right">GP</th>
                  <th className="text-right">G</th>
                  <th className="text-right">A</th>
                  <th className="text-right">P</th>
                  <th className="text-right">P/GP</th>
                  <th className="text-right">TOI</th>
                </tr>
              </thead>
              <tbody>
                {[...seasons].reverse().map((s) => (
                  <tr key={s.season}>
                    <td className="stat text-sm">{formatSeason(s.season)}</td>
                    <td className="stat text-sm text-right">{s.gamesPlayed}</td>
                    <td className="stat text-sm text-right">{s.goals}</td>
                    <td className="stat text-sm text-right">{s.assists}</td>
                    <td className="stat text-sm text-right font-semibold">{s.points}</td>
                    <td className="stat text-sm text-right">
                      {s.gamesPlayed > 0 ? (s.points / s.gamesPlayed).toFixed(2) : "—"}
                    </td>
                    <td className="stat text-sm text-right">
                      {s.avgToiSeconds
                        ? `${Math.floor(s.avgToiSeconds / 60)}:${String(s.avgToiSeconds % 60).padStart(2, "0")}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {cooked?.status === "scored" && (
        <p className="text-xs mt-4" style={{ color: "var(--faint)" }}>
          Signal contributions sum (rescue subtracts) to the score
          {cooked.score !== null && (
            <span className="stat" style={{ color: zoneVar(cooked.score) }}>
              {" "}{cooked.score.toFixed(1)}
            </span>
          )}
          . Weights live in <span className="stat">lib/cooked/config.ts</span> — disagree? Change them.
        </p>
      )}
    </div>
  );
}
