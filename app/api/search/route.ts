import { NextResponse, type NextRequest } from "next/server";
import { and, asc, desc, eq, sql } from "drizzle-orm";
import { db, schema } from "@/db";

/** Global player search for the nav box. Ranks players who have a scored
 *  cooked row first (i.e. real, current skaters) so a query for "mcdavid"
 *  surfaces the active star, not a retired namesake. Prefix matches rank
 *  above mid-string ones. */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim().toLowerCase() ?? "";
  if (q.length < 2) return NextResponse.json([]);

  const like = `%${q}%`;
  const prefix = `${q}%`;

  const rows = await db
    .select({
      id: schema.players.id,
      firstName: schema.players.firstName,
      lastName: schema.players.lastName,
      fullName: schema.players.fullName,
      teamAbbrev: schema.players.teamAbbrev,
      position: schema.players.position,
      headshotUrl: schema.players.headshotUrl,
      scored: sql<number>`case when ${schema.cookedScores.status} = 'scored' then 1 else 0 end`,
    })
    .from(schema.players)
    .leftJoin(schema.cookedScores, eq(schema.cookedScores.playerId, schema.players.id))
    .where(and(sql`lower(${schema.players.fullName}) like ${like}`))
    .orderBy(
      desc(sql`case when ${schema.cookedScores.status} = 'scored' then 1 else 0 end`),
      desc(sql`case when lower(${schema.players.fullName}) like ${prefix} then 1 else 0 end`),
      asc(schema.players.fullName)
    )
    .limit(8);

  return NextResponse.json(rows);
}
