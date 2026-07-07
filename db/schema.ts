// Typed mirror of sql/001_schema.sql — the SQL files are the source of truth
// (they're what gets run in Supabase's SQL Editor). If you change one, change
// the other to match.
//
// TS property names are kept app-friendly (players.id, teams.abbrev) while the
// column names match the SQL schema (player_id, team_id).

import { sql } from "drizzle-orm";
import {
  pgTable,
  text,
  integer,
  bigint,
  bigserial,
  doublePrecision,
  numeric,
  date,
  primaryKey,
  unique,
} from "drizzle-orm/pg-core";

export const teams = pgTable("teams", {
  abbrev: text("team_id").primaryKey(), // NHL 3-letter code, e.g. 'BOS'
  name: text("team_name").notNull(),
  conference: text("conference"),
  division: text("division"),
  logoUrl: text("logo_url"),
});

export const players = pgTable("players", {
  id: bigint("player_id", { mode: "number" }).primaryKey(), // NHL player id
  fullName: text("full_name").notNull(),
  // first/last are filled by the roster ingest; rows created by the daily ETL
  // (players seen in a boxscore but not on a current roster) only have full_name
  firstName: text("first_name"),
  lastName: text("last_name"),
  position: text("position"), // C, L, R, D, G
  teamAbbrev: text("current_team_id").references(() => teams.abbrev),
  birthDate: date("birth_date", { mode: "string" }),
  nationality: text("nationality"),
  shootsCatches: text("shoots_catches"),
  sweaterNumber: integer("sweater_number"),
  headshotUrl: text("headshot_url"),
  heightCm: numeric("height_cm"),
  weightKg: numeric("weight_kg"),
});

export const games = pgTable("games", {
  gameId: bigint("game_id", { mode: "number" }).primaryKey(),
  gameDate: date("game_date", { mode: "string" }).notNull(),
  season: integer("season").notNull(), // e.g. 20252026
  gameType: text("game_type"), // 'regular', 'playoff', 'preseason'
  homeTeamId: text("home_team_id").references(() => teams.abbrev),
  awayTeamId: text("away_team_id").references(() => teams.abbrev),
  homeScore: integer("home_score"),
  awayScore: integer("away_score"),
  venue: text("venue"),
});

// One row per player per game. Written by both pipelines:
//  - etl/pull_nhl_data.py (daily boxscores: hits, blocks, faceoffs, ...)
//  - scripts/ingest.ts (current-season game logs: opponent, shifts, ...)
// Columns the other writer doesn't know about stay null.
export const playerGameStats = pgTable(
  "player_game_stats",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    gameId: bigint("game_id", { mode: "number" })
      .notNull()
      .references(() => games.gameId),
    playerId: bigint("player_id", { mode: "number" })
      .notNull()
      .references(() => players.id),
    teamId: text("team_id").references(() => teams.abbrev),
    season: integer("season"),
    gameDate: date("game_date", { mode: "string" }),
    opponentAbbrev: text("opponent_abbrev"),
    homeRoad: text("home_road"),
    position: text("position"),
    goals: integer("goals").notNull().default(0),
    assists: integer("assists").notNull().default(0),
    points: integer("points").generatedAlwaysAs(sql`goals + assists`),
    shots: integer("shots"),
    hits: integer("hits"),
    blockedShots: integer("blocked_shots"),
    penaltyMinutes: integer("penalty_minutes"),
    plusMinus: integer("plus_minus"),
    powerplayGoals: integer("powerplay_goals"),
    powerplayPoints: integer("powerplay_points"),
    faceoffWins: integer("faceoff_wins"),
    faceoffLosses: integer("faceoff_losses"),
    toiSeconds: integer("toi_seconds"),
    shifts: integer("shifts"),
  },
  (t) => [unique("player_game_stats_game_player_uq").on(t.gameId, t.playerId)]
);

// One row per team per game — written by the daily ETL only.
export const teamGameStats = pgTable(
  "team_game_stats",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    gameId: bigint("game_id", { mode: "number" })
      .notNull()
      .references(() => games.gameId),
    teamId: text("team_id").references(() => teams.abbrev),
    goals: integer("goals"),
    shots: integer("shots"),
    hits: integer("hits"),
    penaltyMinutes: integer("penalty_minutes"),
    powerplayGoals: integer("powerplay_goals"),
    powerplayOpportunities: integer("powerplay_opportunities"),
    faceoffWinPct: numeric("faceoff_win_pct"),
    giveaways: integer("giveaways"),
    takeaways: integer("takeaways"),
  },
  (t) => [unique("team_game_stats_game_team_uq").on(t.gameId, t.teamId)]
);

// NHL regular-season totals, one row per player-season (gameTypeId 2 only).
// Career history for the cooked model — written by scripts/ingest.ts.
export const seasonTotals = pgTable(
  "season_totals",
  {
    playerId: bigint("player_id", { mode: "number" })
      .notNull()
      .references(() => players.id),
    season: integer("season").notNull(), // e.g. 20252026
    teamName: text("team_name"),
    gamesPlayed: integer("games_played").notNull(),
    goals: integer("goals").notNull(),
    assists: integer("assists").notNull(),
    points: integer("points").notNull(),
    shots: integer("shots"),
    shootingPctg: doublePrecision("shooting_pctg"),
    avgToiSeconds: integer("avg_toi_seconds"),
    plusMinus: integer("plus_minus"),
    pim: integer("pim"),
    powerPlayPoints: integer("power_play_points"),
  },
  (t) => [primaryKey({ columns: [t.playerId, t.season] })]
);

// Output of the cooked algorithm — rebuilt by `npm run cook`
export const cookedScores = pgTable("cooked_scores", {
  playerId: bigint("player_id", { mode: "number" })
    .primaryKey()
    .references(() => players.id),
  season: integer("season").notNull(),
  score: doublePrecision("score"), // 0..100, null when not enough data
  label: text("label").notNull(),
  status: text("status").notNull(), // scored | not_enough_data | goalie
  gamesPlayed: integer("games_played"),
  pointsPerGame: doublePrecision("points_per_game"),
  peakPointsPerGame: doublePrecision("peak_points_per_game"),
  signals: text("signals"), // JSON breakdown for the UI
  computedAt: text("computed_at").notNull(),
});
