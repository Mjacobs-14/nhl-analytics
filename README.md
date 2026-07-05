# NHL Analytics

A database + pipeline for digging into underrepresented NHL stats — built on
free/public tools so it's easy to run and easy to collaborate on.

## Stack

* **Database:** [Supabase](https://supabase.com) (hosted Postgres, free tier, browser GUI)
* **Data sources:** NHL public API (`api-web.nhle.com`)
* **ETL:** Python script, scheduled via GitHub Actions (no server needed)
* **Dashboard:** Streamlit (coming next)
* **Collaboration:** GitHub

## Project structure

```
nhl-analytics/
├── sql/
│   ├── 001\_schema.sql                # core tables: teams, players, games, stats
│   └── 002\_derived\_metrics\_views.sql # custom formulas as SQL views
├── etl/
│   ├── pull\_nhl\_data.py              # pulls NHL API data into Supabase
│   └── requirements.txt
├── dashboard/                        # Streamlit app (next step)
└── .github/workflows/etl.yml         # runs the ETL daily, automatically
```

## Setup (one-time)

### 1\. Create your database

1. Go to [supabase.com](https://supabase.com) and create a free account + new project.
2. Once it spins up, go to **SQL Editor** (left sidebar) → **New query**.
3. Paste in the contents of `sql/001\_schema.sql`, click **Run**.
4. New query again → paste `sql/002\_derived\_metrics\_views.sql` → **Run**.
5. You now have tables and derived-stat views. You can browse them anytime
under **Table Editor** — no SQL required to just look at data.

### 2\. Get your API credentials

1. In Supabase: **Project Settings** → **API**.
2. Copy the **Project URL** and the **service\_role** key (not the "anon" one —
the ETL needs write access).

### 3\. Run the ETL locally (test it once before automating)

```bash
cd nhl-analytics/etl
pip install -r requirements.txt

export SUPABASE\_URL="https://xxxx.supabase.co"
export SUPABASE\_KEY="your-service-role-key"

python pull\_nhl\_data.py --date 2026-01-15
```

Check Supabase's Table Editor afterward — you should see rows in `games`,
`players`, and `player\_game\_stats`.

### 4\. Automate it with GitHub Actions

1. Push this repo to GitHub (see below).
2. In your GitHub repo: **Settings** → **Secrets and variables** → **Actions**.
3. Add two repository secrets: `SUPABASE\_URL` and `SUPABASE\_KEY`.
4. That's it — `.github/workflows/etl.yml` runs daily at 9am UTC and pulls
the previous day's games automatically. You can also trigger it manually
from the **Actions** tab.

## Adding your own custom metrics (no ETL changes needed)

The whole point of the views in `002\_derived\_metrics\_views.sql` is that you
can layer new formulas on top of raw data without touching the pipeline:

1. Open Supabase's SQL Editor.
2. Write a new `create or replace view my\_metric\_v as select ... `.
3. Run it. It's now a live, queryable table-like object — pull it into the
dashboard or a notebook immediately.

A template for this is at the bottom of `002\_derived\_metrics\_views.sql`.

## Pushing to GitHub

```bash
cd nhl-analytics
git init
git add .
git commit -m "Initial schema + ETL pipeline"
git branch -M main
git remote add origin https://github.com/<your-username>/nhl-analytics.git
git push -u origin main
```

A couple of notes before you push:

* Never commit your actual Supabase keys — this project reads them from
environment variables / GitHub secrets specifically so they stay out of
the repo.
* Add a `.gitignore` (see below) so you don't accidentally commit local
`.env` files.

## What's next

* \[ ] Add more boxscore fields you care about (e.g. shot attempts, xG from MoneyPuck)
* \[ ] Build out the Streamlit dashboard in `/dashboard`
* \[ ] Pick 2-3 "underrepresented" metrics to feature first (we can brainstorm these)
* \[ ] Backfill historical data for a season or two once the daily pipeline is stable

