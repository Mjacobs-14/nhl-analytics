// Pulls teams, rosters, career season totals, and current-season game logs
// from the public NHL API into the shared Postgres database.
//
//   npm run ingest                 # full league (~700 players, a few minutes)
//   npm run ingest -- --teams=EDM,TOR,COL
//
// This is the career-backfill side of the house; etl/pull_nhl_data.py is the
// daily boxscore side. Both write the same tables and can run in any order.

import { sql } from "drizzle-orm";
import { db, client, schema } from "../db";
import {
  CURRENT_SEASON,
  REGULAR_SEASON,
  getStandings,
  getRoster,
  getPlayerLanding,
  getGameLog,
  toiToSeconds,
  mapWithConcurrency,
  RosterPlayer,
} from "../lib/nhl";

const teamFilter = process.argv
  .find((a) => a.startsWith("--teams="))
  ?.split("=")[1]
  ?.split(",")
  .map((t) => t.trim().toUpperCase());

async function main() {
  console.log(`Ingesting season ${CURRENT_SEASON}${teamFilter ? ` for ${teamFilter.join(", ")}` : " (full league)"}`);

  // 1. Teams from standings
  const { standings } = await getStandings();
  for (const t of standings) {
    await db
      .insert(schema.teams)
      .values({
        abbrev: t.teamAbbrev.default,
        name: t.teamName.default,
        conference: t.conferenceName,
        division: t.divisionName,
        logoUrl: t.teamLogo,
      })
      .onConflictDoUpdate({
        target: schema.teams.abbrev,
        set: { name: t.teamName.default, conference: t.conferenceName, division: t.divisionName, logoUrl: t.teamLogo },
      });
  }
  const teamAbbrevs = standings
    .map((t) => t.teamAbbrev.default)
    .filter((a) => !teamFilter || teamFilter.includes(a));
  console.log(`Teams: ${standings.length} upserted, ingesting rosters for ${teamAbbrevs.length}`);

  // 2. Rosters
  const rosterEntries: Array<{ player: RosterPlayer; position: string; team: string }> = [];
  for (const abbrev of teamAbbrevs) {
    try {
      const roster = await getRoster(abbrev);
      for (const p of roster.forwards) rosterEntries.push({ player: p, position: p.positionCode, team: abbrev });
      for (const p of roster.defensemen) rosterEntries.push({ player: p, position: "D", team: abbrev });
      for (const p of roster.goalies) rosterEntries.push({ player: p, position: "G", team: abbrev });
      console.log(`  ${abbrev}: ${roster.forwards.length + roster.defensemen.length + roster.goalies.length} players`);
    } catch (err) {
      console.warn(`  ${abbrev}: roster fetch failed (${err}) — skipping`);
    }
  }

  // 3. Per-player: bio + career season totals + current-season game log
  let done = 0;
  await mapWithConcurrency(rosterEntries, 3, async ({ player, position, team }) => {
    try {
      const landing = await getPlayerLanding(player.id);
      const firstName = player.firstName.default;
      const lastName = player.lastName.default;

      await db
        .insert(schema.players)
        .values({
          id: player.id,
          fullName: `${firstName} ${lastName}`,
          firstName,
          lastName,
          position,
          teamAbbrev: team,
          birthDate: player.birthDate ?? landing.birthDate ?? null,
          headshotUrl: player.headshot ?? landing.headshot ?? null,
          sweaterNumber: player.sweaterNumber ?? null,
          shootsCatches: player.shootsCatches ?? null,
        })
        .onConflictDoUpdate({
          target: schema.players.id,
          set: {
            fullName: `${firstName} ${lastName}`,
            firstName,
            lastName,
            teamAbbrev: team,
            position,
            headshotUrl: player.headshot ?? null,
          },
        });

      // Goalies keep their bio row but skip skater stat lines (not scored in v1)
      const nhlSeasons =
        position === "G"
          ? []
          : landing.seasonTotals.filter(
              (s) => s.leagueAbbrev === "NHL" && s.gameTypeId === REGULAR_SEASON
            );
      // Traded players get one row per team per season — combine them into a
      // single season line (sums; TOI weighted by GP; shooting % recomputed).
      const bySeason = new Map<number, typeof nhlSeasons>();
      for (const s of nhlSeasons) {
        bySeason.set(s.season, [...(bySeason.get(s.season) ?? []), s]);
      }
      const seasonRows = [...bySeason.entries()].map(([season, stints]) => {
        const sum = (f: (s: (typeof stints)[number]) => number | undefined) =>
          stints.some((s) => f(s) != null) ? stints.reduce((a, s) => a + (f(s) ?? 0), 0) : null;
        const gamesPlayed = stints.reduce((a, s) => a + s.gamesPlayed, 0);
        const shots = sum((s) => s.shots);
        const goals = stints.reduce((a, s) => a + s.goals, 0);
        const toiStints = stints.filter((s) => toiToSeconds(s.avgToi) !== null && s.gamesPlayed > 0);
        const toiGp = toiStints.reduce((a, s) => a + s.gamesPlayed, 0);
        return {
          playerId: player.id,
          season,
          teamName: stints[stints.length - 1].teamName?.default ?? null,
          gamesPlayed,
          goals,
          assists: stints.reduce((a, s) => a + s.assists, 0),
          points: stints.reduce((a, s) => a + s.points, 0),
          shots,
          shootingPctg: shots ? goals / shots : null,
          avgToiSeconds:
            toiGp > 0
              ? Math.round(
                  toiStints.reduce((a, s) => a + (toiToSeconds(s.avgToi) as number) * s.gamesPlayed, 0) / toiGp
                )
              : null,
          plusMinus: sum((s) => s.plusMinus),
          pim: sum((s) => s.pim),
          powerPlayPoints: sum((s) => s.powerPlayPoints),
        };
      });

      if (seasonRows.length > 0) {
        await db
          .insert(schema.seasonTotals)
          .values(seasonRows)
          .onConflictDoUpdate({
            target: [schema.seasonTotals.playerId, schema.seasonTotals.season],
            set: {
              gamesPlayed: sql`excluded.games_played`,
              goals: sql`excluded.goals`,
              assists: sql`excluded.assists`,
              points: sql`excluded.points`,
              shots: sql`excluded.shots`,
              shootingPctg: sql`excluded.shooting_pctg`,
              avgToiSeconds: sql`excluded.avg_toi_seconds`,
            },
          });
      }

      const { gameLog } = position === "G" ? { gameLog: [] } : await getGameLog(player.id);
      if (gameLog.length > 0) {
        // player_game_stats rows reference games, so make sure a (minimal) game
        // row exists — the daily ETL fills in scores/venue for games it sees.
        await db
          .insert(schema.games)
          .values(
            gameLog.map((g) => ({
              gameId: g.gameId,
              gameDate: g.gameDate,
              season: CURRENT_SEASON,
            }))
          )
          .onConflictDoNothing();

        await db
          .insert(schema.playerGameStats)
          .values(
            gameLog.map((g) => ({
              playerId: player.id,
              gameId: g.gameId,
              teamId: team,
              season: CURRENT_SEASON,
              gameDate: g.gameDate,
              opponentAbbrev: g.opponentAbbrev,
              homeRoad: g.homeRoadFlag,
              position,
              goals: g.goals,
              assists: g.assists,
              // points is a generated column (goals + assists) — not written
              shots: g.shots ?? null,
              plusMinus: g.plusMinus ?? null,
              penaltyMinutes: g.pim ?? null,
              toiSeconds: toiToSeconds(g.toi),
              shifts: g.shifts ?? null,
              powerplayPoints: g.powerPlayPoints ?? null,
            }))
          )
          .onConflictDoNothing({
            target: [schema.playerGameStats.gameId, schema.playerGameStats.playerId],
          });
      }

      done++;
      if (done % 25 === 0) console.log(`  players: ${done}/${rosterEntries.length}`);
    } catch (err) {
      console.warn(`  player ${player.id} (${player.lastName.default}) failed: ${err}`);
    }
  });

  console.log(`Done. ${done}/${rosterEntries.length} players ingested. Now run: npm run cook`);
}

main()
  .then(() => client.end())
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
