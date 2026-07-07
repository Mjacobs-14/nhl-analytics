# NHL Analytics — Is He Cooked? 🥅🔥

Group project: a shared NHL database + automated pipeline (Matt) merged with the
"Is He Cooked?" player-decline model and dashboard (Ruston). Every skater in the
league gets a **Cooked Score** (0–100) on a fresh-to-cooked gauge, computed from
public NHL data, on top of a shared Postgres database that grows on its own.
For arguments in the group chat, not for wagering.

## Stack

* **Database:** [Supabase](https://supabase.com) (hosted Postgres, free tier, browser GUI) — one shared source of truth
* **Data source:** NHL public API (`api-web.nhle.com`), no key required
* **Daily ETL:** Python script scheduled via GitHub Actions — boxscores land every morning, no server needed
* **Career backfill + model:** TypeScript scripts (`npm run ingest` / `npm run cook`)
* **Dashboard:** Next.js app (`npm run dev`) — leaderboard + player pages with the gauge
* **Custom metrics:** SQL views in Supabase — add a formula without touching any pipeline

## Project structure

```
sql/
  001_schema.sql                 core tables (source of truth — db/schema.ts mirrors it)
  002_derived_metrics_views.sql  custom formulas as SQL views
etl/pull_nhl_data.py             daily boxscore pull (GitHub Actions, 9:00 UTC)
.github/workflows/etl.yml        the schedule
scripts/
  apply-sql.ts                   applies sql/ files to DATABASE_URL (npm run db:apply)
  ingest.ts                      rosters + career season totals + game logs (npm run ingest)
  cook.ts                        scores everyone (npm run cook)
lib/cooked/                      the model — config.ts (knobs), signals.ts (math), index.ts (blend)
lib/nhl.ts                       NHL API client (throttled + retrying; the API 429s greedy pulls)
db/                              drizzle schema + Postgres client
app/, components/                Next.js UI
```

## Setup

### 1. Database access

One person creates the free Supabase project (already done — ask in the group
chat for credentials); everyone else just needs the connection string.

```bash
cp .env.example .env    # then paste in DATABASE_URL (+ SUPABASE_URL/KEY for the ETL)
```

### 2. Schema + data + scores

```bash
npm install
npm run setup     # applies sql/ files, pulls the league from the NHL API, scores everyone
npm run dev       # http://localhost:3000
```

`setup` = `db:apply` + `ingest` + `cook`. The sql files are idempotent, so
re-running is always safe. You can also paste the sql/ files into Supabase's
SQL Editor by hand — same thing.

### 3. Automation (already configured)

`.github/workflows/etl.yml` runs the Python ETL daily at 9:00 UTC and pulls the
previous day's boxscores into the shared database — player and team game stats
accumulate with zero effort. It needs `SUPABASE_URL` and `SUPABASE_KEY` set as
repo secrets (Settings → Secrets and variables → Actions). Trigger it manually
anytime from the Actions tab, or backfill a stretch locally:

```bash
cd etl && pip install -r requirements.txt
python pull_nhl_data.py --start-date 2026-01-01 --end-date 2026-01-31
```

## The model (v1)

A weighted blend of four signals, each 0–1, defined in `lib/cooked/signals.ts`:

| Signal | Weight | What it measures |
|---|---|---|
| Age curve | 0.22 | Position-specific aging pressure (F/D/G peak and cliff differ) |
| Production vs. peak | 0.30 | This season's P/GP against the player's own best-3-seasons baseline |
| Three-season trend | 0.23 | Least-squares slope of P/GP — a sustained slide, not one bad year |
| Ice time | 0.25 | Minutes vs. prior two seasons — the coach's revealed opinion |

Plus a **luck rescue** (−0.15 max): if shooting % cratered below career norms while shot
volume held, the process looks intact and the score gets walked back.

Zones: `0–20 Fresh · 20–40 Warming Up · 40–60 Simmering · 60–80 Well Done · 80–100 Cooked`

Players with fewer than three NHL seasons are "Too Fresh to Judge." Goalies are voodoo
and unscored (v2).

**Disagree with the model? Good — that's the project.** Weights and thresholds live in
`lib/cooked/config.ts`. Change them, `npm run cook`, refresh the page.

## Adding your own custom metrics (no pipeline changes needed)

The views in `sql/002_derived_metrics_views.sql` are the "add a formula without
touching the raw data" layer:

1. Open Supabase's SQL Editor (or add it to the file and `npm run db:apply`).
2. Write a new `create or replace view my_metric_v as select ...`.
3. Run it — it's instantly queryable from a dashboard or notebook.

There's a template at the bottom of the file, and `cooked_leaderboard_v` exposes
the model output the same way.

## Commands

| Command | What it does |
|---|---|
| `npm run setup` | schema + full ingest + score (first run) |
| `npm run db:apply` | (re)apply `sql/` files — safe to re-run |
| `npm run ingest` | re-pull rosters/careers from the NHL API (`-- --teams=EDM,TOR` to limit) |
| `npm run cook` | re-score everyone from the database (fast — run after tuning) |
| `npm run dev` | dev server |

## Ideas / roadmap

- Goalie model (save % vs. expected, workload decline)
- In-season rolling windows from `player_game_stats` (the daily ETL keeps it growing)
- Use the ETL's hits/blocks/faceoffs for defensive-value signals
- Coach/system fit: does a player look cooked or just miscast in a new system?
- "Cooked odds": probability the score rises next season (backtest against history)
- Deploy the app (Vercel) so the board lives at a URL
- Pick 2–3 more "underrepresented" metrics to feature as views
