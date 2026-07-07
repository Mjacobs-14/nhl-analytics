// Applies the sql/ files (schema + views) to DATABASE_URL, in filename order.
// Everything in sql/ is idempotent (create if not exists / create or replace),
// so this is safe to re-run.
//
//   npm run db:apply
//
// Equivalent to pasting the files into Supabase's SQL Editor — use whichever
// you prefer.

import "dotenv/config";
import fs from "node:fs";
import path from "node:path";
import postgres from "postgres";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("DATABASE_URL is not set. Copy .env.example to .env first.");
  process.exit(1);
}

const sql = postgres(url, { prepare: false, max: 1 });

async function main() {
  const dir = path.join(process.cwd(), "sql");
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".sql"))
    .sort();
  for (const f of files) {
    console.log(`Applying sql/${f} ...`);
    await sql.unsafe(fs.readFileSync(path.join(dir, f), "utf8"));
  }
  console.log("Schema is up to date.");
}

main()
  .then(() => sql.end())
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
