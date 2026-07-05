import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { Filters } from "@/components/Filters";
import { ScoreBar } from "@/components/ScoreBar";
import { getLeaderboard, getTeams, countScored, LeaderboardFilters } from "@/lib/queries";
import { ageInSeason } from "@/lib/cooked/signals";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; team?: string; pos?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const filters: LeaderboardFilters = {
    q: params.q,
    team: params.team,
    pos: params.pos,
    sort: params.sort === "fresh" ? "fresh" : "cooked",
  };
  const [rows, teams, scored] = await Promise.all([
    getLeaderboard(filters),
    getTeams(),
    countScored(),
  ]);

  if (scored === 0) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto mt-10">
        <h2 className="display text-2xl mb-2">Nothing on the board yet</h2>
        <p style={{ color: "var(--muted)" }}>
          Pull the league and score it, then refresh this page:
        </p>
        <p className="stat mt-3 text-sm">npm run setup</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <p className="eyebrow mb-1">2025–26 regular season · {scored} skaters scored</p>
          <h2 className="display text-2xl">The Board</h2>
        </div>
        <Suspense>
          <Filters teams={teams} />
        </Suspense>
      </div>

      <div className="card overflow-x-auto">
        <table className="board">
          <thead>
            <tr>
              <th className="w-10">#</th>
              <th>Player</th>
              <th>Team</th>
              <th>Pos</th>
              <th className="text-right">Age</th>
              <th className="text-right">GP</th>
              <th className="text-right">P/GP</th>
              <th className="text-right">Peak</th>
              <th>Cooked score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ player, cooked }, i) => (
              <tr key={player.id}>
                <td className="stat text-xs" style={{ color: "var(--faint)" }}>{i + 1}</td>
                <td>
                  <Link href={`/player/${player.id}`} className="flex items-center gap-2 font-medium">
                    {player.headshotUrl && (
                      <Image
                        src={player.headshotUrl}
                        alt=""
                        width={32}
                        height={32}
                        className="rounded-full"
                        style={{ background: "var(--chip-bg)" }}
                      />
                    )}
                    {player.firstName} {player.lastName}
                  </Link>
                </td>
                <td className="stat text-sm">{player.teamAbbrev}</td>
                <td className="stat text-sm">{player.position}</td>
                <td className="stat text-sm text-right">
                  {player.birthDate && cooked.season
                    ? Math.floor(ageInSeason(player.birthDate, cooked.season))
                    : "—"}
                </td>
                <td className="stat text-sm text-right">{cooked.gamesPlayed ?? "—"}</td>
                <td className="stat text-sm text-right">{cooked.pointsPerGame?.toFixed(2) ?? "—"}</td>
                <td className="stat text-sm text-right" style={{ color: "var(--muted)" }}>
                  {cooked.peakPointsPerGame?.toFixed(2) ?? "—"}
                </td>
                <td>{cooked.score !== null && <ScoreBar score={cooked.score} label={cooked.label} />}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-8" style={{ color: "var(--muted)" }}>
                  No players match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs mt-3" style={{ color: "var(--faint)" }}>
        Score blends age curve, production vs. personal peak, three-season trend, and ice-time
        changes, minus a rescue for shooting-luck victims. Rookies and short careers read
        &ldquo;Too Fresh to Judge&rdquo; and stay off the board.
      </p>
    </div>
  );
}
