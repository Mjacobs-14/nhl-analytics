// Runs the Cooked Score algorithm over every ingested player and stores
// the results. Cheap to re-run — tweak lib/cooked/config.ts and go again.
//
//   npm run cook

import { sql } from "drizzle-orm";
import { db, client, schema } from "../db";
import { computeCookedScore } from "../lib/cooked";
import { SeasonLine } from "../lib/cooked/signals";

async function main() {
  const players = await db.select().from(schema.players);
  const totals = await db.select().from(schema.seasonTotals);

  const bySeason = new Map<number, SeasonLine[]>();
  const careerSh = new Map<number, number | null>();
  for (const t of totals) {
    const list = bySeason.get(t.playerId) ?? [];
    list.push({
      season: t.season,
      gamesPlayed: t.gamesPlayed,
      points: t.points,
      shots: t.shots,
      shootingPctg: t.shootingPctg,
      avgToiSeconds: t.avgToiSeconds,
    });
    bySeason.set(t.playerId, list);
  }
  // Career shooting % = shot-weighted across all seasons with data
  for (const [playerId, lines] of bySeason) {
    const withShots = totals.filter(
      (t) => t.playerId === playerId && t.shots && t.shootingPctg !== null
    );
    const shots = withShots.reduce((a, t) => a + (t.shots as number), 0);
    const goals = withShots.reduce((a, t) => a + (t.shots as number) * (t.shootingPctg as number), 0);
    careerSh.set(playerId, shots > 0 ? goals / shots : null);
    void lines;
  }

  const computedAt = new Date().toISOString();
  let scored = 0;

  const rows = players.map((p) => {
    const result = computeCookedScore({
      // players created by the daily ETL may lack a position; treat as skater
      position: p.position ?? "",
      birthDate: p.birthDate,
      careerShootingPctg: careerSh.get(p.id) ?? null,
      history: bySeason.get(p.id) ?? [],
    });
    if (result.status === "scored") scored++;
    return {
      playerId: p.id,
      season: result.currentSeason ?? 0,
      score: result.score,
      label: result.label,
      status: result.status,
      gamesPlayed: bySeason.get(p.id)?.find((s) => s.season === result.currentSeason)?.gamesPlayed ?? null,
      pointsPerGame: result.pointsPerGame,
      peakPointsPerGame: result.peakPointsPerGame,
      signals: JSON.stringify(result.signals),
      computedAt,
    };
  });

  const CHUNK = 200;
  for (let i = 0; i < rows.length; i += CHUNK) {
    await db
      .insert(schema.cookedScores)
      .values(rows.slice(i, i + CHUNK))
      .onConflictDoUpdate({
        target: schema.cookedScores.playerId,
        set: {
          season: sql`excluded.season`,
          score: sql`excluded.score`,
          label: sql`excluded.label`,
          status: sql`excluded.status`,
          gamesPlayed: sql`excluded.games_played`,
          pointsPerGame: sql`excluded.points_per_game`,
          peakPointsPerGame: sql`excluded.peak_points_per_game`,
          signals: sql`excluded.signals`,
          computedAt: sql`excluded.computed_at`,
        },
      });
  }

  console.log(`Cooked ${scored} of ${players.length} players (rest lack data or are goalies).`);

  const leaders = rows
    .filter((s) => s.score !== null)
    .sort((a, b) => (b.score as number) - (a.score as number))
    .slice(0, 10);
  console.log("\nMost cooked:");
  for (const l of leaders) {
    const p = players.find((x) => x.id === l.playerId);
    console.log(`  ${(l.score as number).toFixed(1).padStart(5)}  ${l.label.padEnd(12)}  ${p?.fullName} (${p?.teamAbbrev})`);
  }
}

main()
  .then(() => client.end())
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
