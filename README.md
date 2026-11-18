# NHL Analytics — Is He Cooked? 🥅🔥

Group project: a shared NHL database + automated pipeline (Matt) merged with the
"Is He Cooked?" player-decline model and dashboard (Ruston). It started as one
model — every skater gets a **Cooked Score** (0–100) on a fresh-to-cooked gauge —
and grew into a full analytics stack on public NHL data: shot-level
play-by-play since 2018-19, an expected-goals model, a team matchup model,
interactive visualizations, and out-of-sample backtests.

This is an analytics project, not a betting tool. Sportsbook closing lines appear
in the backtests only as a benchmark: they are the sharpest public forecast of
game outcomes, so they're the strictest test of whether a model knows anything.

## What's in here

| Area | What it is | Where |
|---|---|---|
| **Model validation** — start here | Out-of-sample backtest of the matchup model across 9,781 games, scored against real outcomes and against market closing lines | [`analysis/README.md`](analysis/README.md) |
| Matchup model | Team-vs-team expected goals from venue-split shot-location profiles, special teams, and the starting goalie | [`viz/matchup_lab.html`](viz/matchup_lab.html), `sql/032`–`033` |
| Expected goals + shot data | ~1.3M shot attempts with coordinates, game state and rush flags; a location-based xG model built on them | `etl/pull_play_by_play.py`, `sql/016`–`022` |
| Derived metrics | SQL views: shot volume vs. finishing, clutch scoring by game state, goalie streakiness, coach style fingerprints, NHL Edge skating | `sql/` |
| Visualizations | Six self-contained interactive pages | [`viz/`](viz/README.md) |
| Dashboard | Next.js app: the Cooked Score board, player pages, and an analytics page | `app/`, `npm run dev` |
| Cooked Score | The original player-decline model | [below](#the-model-v1), `lib/cooked/` |

**Headline result:** the matchup model picks winners at **58.9%** out of sample
(home team wins 53.6%), and its probabilities are well calibrated — when it says
60%, teams win about 60%. It still trails the betting market: on the same 3,497
games, closing-line favorites won 60.8% to the model's 59.2%, and the market's
probabilities score better. Skilled and well calibrated, but behind the closing
line — the information it captures is already priced in. The write-up
covers how leakage was ruled out, what improved the model (the starting goalie),
the four refinements that didn't, and why player props and game totals are
dominated by randomness.

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
  003–036                        Edge, play-by-play, xG, clutch, goalie, coach and matchup views
etl/pull_nhl_data.py             daily boxscore pull (GitHub Actions, 9:00 UTC)
.github/workflows/etl.yml        the schedule
scripts/
  apply-sql.ts                   applies sql/ files to DATABASE_URL (npm run db:apply)
  ingest.ts                      rosters + career season totals + game logs (npm run ingest)
  cook.ts                        scores everyone (npm run cook)
lib/cooked/                      the model — config.ts (knobs), signals.ts (math), index.ts (blend)
etl/                             Python pullers: boxscores, play-by-play/shots, NHL Edge, game details
analysis/                        backtests + model validation (see analysis/README.md)
viz/                             self-contained interactive visualizations
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
- Cooked Score backtest: probability the score rises next season, tested against history
- Deploy the app (Vercel) so the board lives at a URL
- Pick 2–3 more "underrepresented" metrics to feature as views
