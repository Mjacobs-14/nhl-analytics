# Model backtests

Honest, out-of-sample tests of whether our models actually predict games —
run **before** treating any of them as a betting edge.

## `backtest_matchup_rolling.py` — Matchup model

Scores the Matchup Lab model's expected-goals predictions against every
regular-season result, 2018–2026 (9,781 games). Self-contained: fetches its
own data from Postgres via `DATABASE_URL` (embedded SQL), or reads a
`--snapshot` JSON for offline runs.

```
python analysis/backtest_matchup_rolling.py                     # live DB
python analysis/backtest_matchup_rolling.py --snapshot bt.json  # offline
DATABASE_URL=... python analysis/backtest_matchup_rolling.py --write-snapshot bt.json
```

### The model under test

Predicts each side's goals from **venue-split location-xG profiles**:

```
ph_xg           = H_home_xGF/gm  ×  (A_road_xGA/gm  ÷  league_road_xGA/gm)
pred_home_goals = ph_xg          ×  (A_road actualGA ÷ A_road xGA)   # goalie/finish factor
```

(symmetric for the away side). Independent Poisson on the two expected counts
→ P(home win), ties split 50/50 for OT/SO. This is the model's **xG core** —
the EV/PP-split and per-band goalie refinements on the page are a further layer
not yet folded in.

### Three scorings — the design that keeps it honest

| Scoring | What it may see | Purpose |
|---|---|---|
| **prior-season** | last season's final profiles | honest but stale |
| **leaky ceiling** | this season's profiles (incl. the game itself) | upper bound only |
| **rolling as-of** | last season as a prior, blended toward this-season games-to-date | how you'd forecast live |

Rolling blends the two by a shrinkage weight `K` (pseudo-games):
`rate = (K·prior_pg + n·current_pg) / (K + n)`. Season start ≈ prior season;
by mid-season ≈ current form. **A game is predicted before it is folded into
the accumulators — nothing ever sees itself.**

### Results (as of 2026-07 snapshot)

| Model | Accuracy | Log-loss | Brier | Margin corr |
|---|---|---|---|---|
| Always pick home | 53.6% | 0.690 | 0.250 | — |
| prior-season (stale) | 56.8% | 0.684 | 0.245 | 0.18 |
| **rolling as-of (K=15)** | **58.0%** | **0.673** | **0.240** | **0.22** |
| leaky ceiling | 61.6% | 0.654 | 0.231 | 0.31 |

Coin-flip log-loss is 0.6931. The rolling model sits where it should — above
the stale prior, climbing toward the leaky ceiling — and is **well calibrated**
(say-55% teams win ~55%). `K` is flat from 10–25, so the result is not a
tuning artifact.

### The maturity curve — the actionable part for 2026-27

| When in the season | n | Accuracy |
|---|---|---|
| each team's first 0–9 games (October) | 2,428 | 56.7% |
| games 10–19 | 2,214 | 57.2% |
| games 20–39 (mid-season) | 3,768 | **59.3%** |
| games 40+ | 100 | 59.0% |

In October the model runs on last year's stale prior and performs like it. By
~US Thanksgiving, once both teams have ~20 games logged, it reaches ~59% —
most of the way to the ceiling. **Practical rule for 2026-27: treat October as
warm-up; trust the picks from late November on.**

### Honest bottom line

58% (59%+ mid-season) is a real, calibrated model — but **not proof of a
betting edge.** The market already picks winners at ~62–65% because favorites
win often; the bar is beating the *closing line* (52.4% break-even at −110
against the line, not against a coin flip). We've shown skill; we have **not**
shown skill the market hasn't already priced.

### Next

1. **Score vs. historical closing odds** — the definitive edge test (needs an
   odds dataset not yet in the DB). Underdog mid-season picks, where calibration
   is strongest, are the place to look.
2. **Fold in the EV/PP-split + per-band goalie layer** and re-run rolling.
