import { and, asc, desc, eq, sql } from "drizzle-orm";
import { db, schema } from "@/db";

export interface LeaderboardFilters {
  q?: string;
  team?: string;
  pos?: string; // F | D
  sort?: "cooked" | "fresh";
}

export async function getLeaderboard(filters: LeaderboardFilters) {
  const conds = [eq(schema.cookedScores.status, "scored")];
  if (filters.team) conds.push(eq(schema.players.teamAbbrev, filters.team));
  if (filters.pos === "D") conds.push(eq(schema.players.position, "D"));
  if (filters.pos === "F") conds.push(sql`${schema.players.position} != 'D'`);
  if (filters.q) {
    conds.push(sql`lower(${schema.players.fullName}) like ${"%" + filters.q.toLowerCase() + "%"}`);
  }

  return db
    .select({
      player: schema.players,
      cooked: schema.cookedScores,
    })
    .from(schema.cookedScores)
    .innerJoin(schema.players, eq(schema.players.id, schema.cookedScores.playerId))
    .where(and(...conds))
    .orderBy(
      filters.sort === "fresh"
        ? asc(schema.cookedScores.score)
        : desc(schema.cookedScores.score)
    )
    .limit(200);
}

export async function getTeams() {
  return db.select().from(schema.teams).orderBy(asc(schema.teams.abbrev));
}

export async function getPlayerDetail(id: number) {
  const [player] = await db.select().from(schema.players).where(eq(schema.players.id, id));
  if (!player) return null;
  const [cooked] = await db
    .select()
    .from(schema.cookedScores)
    .where(eq(schema.cookedScores.playerId, id));
  const seasons = await db
    .select()
    .from(schema.seasonTotals)
    .where(eq(schema.seasonTotals.playerId, id))
    .orderBy(asc(schema.seasonTotals.season));
  return { player, cooked: cooked ?? null, seasons };
}

export async function countScored() {
  const [row] = await db
    // count(*) is bigint in Postgres (comes back as a string) — cast it down
    .select({ n: sql<number>`cast(count(*) as int)` })
    .from(schema.cookedScores)
    .where(eq(schema.cookedScores.status, "scored"));
  return row?.n ?? 0;
}
