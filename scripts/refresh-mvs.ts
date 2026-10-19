// Refreshes the materialized views that nothing else keeps current.
//
//   npm run refresh:mvs
//
// Runs at the end of the daily ETL. It goes over the direct Postgres connection
// (DATABASE_URL) rather than the Supabase API on purpose: team_empty_net_mv
// takes ~16s to rebuild, and the API path enforces an 8s statement_timeout.

import { client } from "../db";

const VIEWS = ["team_empty_net_mv", "pbp_faceoff_mv", "pbp_hit_grid_mv"] as const;

async function main() {
  for (const view of VIEWS) {
    const t0 = Date.now();
    // Identifiers can't be bound as parameters; VIEWS is a fixed allow-list.
    await client.unsafe(`refresh materialized view public.${view}`);
    console.log(`refreshed ${view} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }
  await client.end();
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
