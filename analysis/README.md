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
| rolling as-of, xG core (K=15) | 58.0% | 0.673 | 0.240 | 0.22 |
| **rolling + starting goalie** | **58.9%** | **0.671** | **0.239** | **0.23** |
| leaky ceiling (xG core) | 61.6% | 0.654 | 0.231 | 0.31 |

Coin-flip log-loss is 0.6931. The rolling model sits where it should — above
the stale prior, climbing toward the leaky ceiling — and is **well calibrated**
(say-55% teams win ~55%). `K` is flat from 10–25, so the result is not a
tuning artifact.

### The maturity curve — the actionable part for 2026-27

Rolling + starting goalie, by how many games each team has played:

| When in the season | n | Accuracy |
|---|---|---|
| each team's first 0–9 games (October) | 2,428 | 57.3% |
| games 10–19 | 2,214 | 58.9% |
| games 20–39 (mid-season) | 3,768 | **60.0%** |
| games 40+ | 100 | 63.0% |

In October the model runs on last year's stale prior and performs like it. By
~US Thanksgiving, once both teams have ~20 games logged, it clears 60% —
most of the way to the ceiling. **Practical rule for 2026-27: treat October as
warm-up; trust the picks from late November on.**

### Honest bottom line

58% (59%+ mid-season) is a real, calibrated model — but **not proof of a
betting edge.** The market already picks winners at ~62–65% because favorites
win often; the bar is beating the *closing line* (52.4% break-even at −110
against the line, not against a coin flip). We've shown skill; we have **not**
shown skill the market hasn't already priced.

### Totals & team totals — tested, rejected (2026-07)

We re-scored the *same* rolling model against over/unders, since it emits
expected goals directly. **Game totals are a dead end for this model:**
corr(predicted total, actual total) = **0.07**, and over/under 6.5 log-loss
(0.694) is *worse than a coin flip*. The cause is structural — the model
predicts nearly every game at 5.9–6.2 (predicted-total SD 0.52 vs actual 2.30),
because offense/defense strengths cancel in the *sum*. And the ceiling is low
for anyone: actual-total SD (2.30) ≈ pure Poisson noise at 6.2 goals (2.49), so
game totals are mostly irreducible randomness.

Team totals had a faint pulse (corr 0.17, calibrated) but only tie "always bet
over" on accuracy. Takeaway: **the model is far better at *differences* (who
wins, margin corr 0.22) than *sums* (how many goals).** Moneyline / margin is
our market. Don't revisit totals without a fundamentally different model.

### Feature experiments (2026-07)

| Feature | Effect on rolling | Verdict |
|---|---|---|
| **Starting-goalie identity** (#4) | acc 58.0→58.9%, log-loss 0.673→0.671, best late-season (59→63%) | **Adopted** |
| Opponent / strength-of-schedule adjustment (#1) | wash-to-negative; even the maturity-gentled version was a tie | Rejected |
| Coach-style **clash** | style-clash interactions correlate ~0.00 with model residuals, even in-sample | Rejected |

- **Starting goalie:** replaces the defending *team*'s pooled finish factor with
  the actual *starter*'s GA/xGA, shots-shrunk (league 1.0 + prior season +
  season-to-date). Starter = the goalie who faced the most shots that game
  (known pre-game in live use). Now the default in `run_rolling`.
- **Opponent adjustment:** over a full 82-game season, schedules balance enough
  that a per-game SOS correction adds nothing the rolling ratings don't already
  hold; early-season it was too noisy and *hurt* October.
- **Coach clash:** a coach's style is already embedded in his team's xG profile,
  so the effect is additive, not interactive — no matchup signal survives. The
  only coach-level stats with residual pulse were plain team/goalie quality
  (goalie `gsax`, defensive shot-volume), already captured or captured by #4.
  Side-note: the defensive shot-volume signal hints a **possession/Corsi term**
  (the model is pure-xG and ignores raw shot volume) could be a small feature.

### Next

1. **Score vs. historical closing odds** — the definitive edge test (needs an
   odds dataset not yet in the DB). Underdog mid-season picks, where calibration
   is strongest, are the place to look.
2. **Fold in the EV/PP special-teams split** and re-run rolling.
3. **Try a possession/Corsi term** (small, from the coach-probe side-finding).
