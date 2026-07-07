import "dotenv/config";
import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import * as schema from "./schema";

const url = process.env.DATABASE_URL;
if (!url) {
  throw new Error(
    "DATABASE_URL is not set. Copy .env.example to .env and paste the Postgres " +
      "connection string from Supabase (Project Settings > Database)."
  );
}

// prepare:false keeps this compatible with Supabase's transaction-mode pooler
// (port 6543), which doesn't support prepared statements.
export const client = postgres(url, { prepare: false });
export const db = drizzle(client, { schema });
export { schema };
