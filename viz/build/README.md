# viz/ page builders

The scripts that generate the self-contained pages in `viz/`. Previously these
lived only on one laptop and read hardcoded query dumps, so the snapshots
couldn't be regenerated and the **definitions behind the numbers were
undocumented** — which is exactly what caused the `RUSH` drift in the `/matchup`
port (issue #26). `queries.py` is now the single source of truth for every
definition.

## Regenerating a page

```bash
export DATABASE_URL=postgresql://...        # same var the app uses
cd viz/build
python build_matchup.py   ../matchup_lab.html
python build_goalie.py    ../goalie_hot_hand.html
python build_quadrants.py ../shot_quadrants.html
python build_edge.py      ../edge_athleticism.html
python build_coach.py     ../coach_fingerprints.html
```

Needs `psycopg` (`pip install 'psycopg[binary]'`). To work offline or pin a
snapshot for reproducibility:

```bash
python build_matchup.py ../matchup_lab.html --save-snapshot snap/matchup.json
python build_matchup.py ../matchup_lab.html --snapshot      snap/matchup.json
```

`snap/` is gitignored — snapshots are data, not source.

## Verification

Every builder was checked by rebuilding from the original 2026-07-14 query dumps
and diffing against the committed page:

| page | builder | rebuild vs committed |
|---|---|---|
| `matchup_lab.html` | `build_matchup.py` | **byte-identical** |
| `goalie_hot_hand.html` | `build_goalie.py` | **byte-identical** |
| `shot_quadrants.html` | `build_quadrants.py` | **byte-identical** |
| `edge_athleticism.html` | `build_edge.py` | **byte-identical** |
| `coach_fingerprints.html` | `build_coach.py` | **byte-identical** |

The SQL in `queries.py` was likewise verified row-for-row against those dumps
(matchup: st 1518 / gp 506 / rush 253 / goalies 790 incl. 145 NULL-band rows;
quadrants 5563; goalie_streak 80; coach style⋈rush 282).

## The `RUSH` gotcha (issue #26)

`RUSH` is the `is_rush` share of **all shot attempts** (all four `event_type`s),
**regular season only**, at `season × team`. DAL 2025-26 = 9.7071 → **9.7**.

- on-net shots only → 8.7 ✗
- including playoffs → 9.5 ✗
- **do not source it from `coach_rush_v`** — that view is coach-scoped and
  silently drops games when a team changed coach mid-season (2025-26 VGK covers
  74 of 82 games → 9.9/11.3 instead of 10.0/11.0). It is correct for per-coach
  fingerprints, wrong for team-season totals.

Also note `LR = 9.7` in the matchup page is a **hardcoded league baseline**, not
computed at runtime, and the narrative thresholds are tuned against it.

## Known gaps

- **`clutch.html` has no builder.** `build_clutch.py` was lost. The page was
  built from `player_clutch_v` (6615 rows; `queries.CLUTCH`), but the builder
  itself still needs rewriting — until then that page can't be regenerated.
- **Row-count drift vs the July snapshot** (definitions unchanged, data grew):
  `player_athleticism_v` 3552 → 4733 (Edge backfill), `coach_change_v` 30 → 37.
  Both are display-only and affect no other page's numbers.
