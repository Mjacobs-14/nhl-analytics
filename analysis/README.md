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
| **Starting-goalie identity** | acc 58.0→58.9%, log-loss 0.673→0.671, best late-season (59→63%) | **Adopted** |
| Opponent / strength-of-schedule adjustment | wash-to-negative; even the maturity-gentled version was a tie | Rejected |
| Coach-style **clash** | style-clash interactions correlate ~0.00 with model residuals, even in-sample | Rejected |
| EV/PP special-teams split | acc/log-loss unchanged to 4 dp — special teams already sit in the total-xG rate | Rejected |
| Corsi / possession blend | +0.1pt acc, log-loss flat — inside the noise (xG already dominates Corsi) | Rejected |

**The model has plateaued at ~58.9% out-of-sample.** Starting goalie was the
only feature that moved it; four sensible refinements since have all come back
null. More gain likely needs *different information*, not more processing of the
same shot data. Best untested idea: **rest / back-to-backs / travel** — proven
market signal, and we already have game dates + `etl/venue_coords.json`.

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

## The edge test vs. closing odds — RESULT (2026-07): no edge

`score_vs_odds.py` devigs closing moneylines, bets where model prob − market
prob > `--edge`, and reports ROI, closing-line value, and favorite/underdog/
maturity breakdowns. `fetch_sbr_odds.py` pulls the closing lines from Sportsbook
Reviews Online (free archive, 2018-19 .. 2022-23) and maps them to gamePk.

```
python fetch_sbr_odds.py --out odds.csv                            # scrape + map odds
python backtest_matchup_rolling.py --emit-predictions preds.csv    # model side
python score_vs_odds.py --preds preds.csv --odds odds.csv          # score it
python score_vs_odds.py --self-test                                # validate the math
```

**Verdict: the model does NOT beat the market.** 4 out-of-sample seasons
(2019-20 .. 2022-23), 3,497 games matched to closing lines:

| Bet filter | Bets | Win % | ROI |
|---|---|---|---|
| model edge ≥3% (flat) | 2,376 | 44.1% | **−2.4%** |
| model edge ≥5% (flat) | 1,662 | 43.1% | **−2.0%** |
| model edge ≥2% (¼-Kelly) | 2,731 | 44.4% | **−1.7%** |

Every configuration loses ~the vig. The model's apparent CLV (+0.077) is an
illusion — when it disagrees with the close, the close is usually right. The
decisive cut is maturity: **the mature-game segment (≥20 gp), where the model's
winner-pick skill peaks at 60%, is the WORST betting segment (−7% ROI).** Its
skill is entirely priced in. Favorites ≈ breakeven; underdogs negative; the only
non-negative slice is early-season (<20 gp), but that's noise and the model is
weakest there. The "underdog value" and "mature-game" hypotheses are falsified.

**Bottom line for monetization:** 58.9% is a genuinely skilled, well-calibrated
winner-picker — and it has **no exploitable straight-moneyline edge** in
2019-2023. Not bettable as-is.

### Next

Straight pre-game moneyline is efficient; beating it needs information the market
prices slowly or not at all. Candidates, roughly in order:

1. **Rest / back-to-backs / travel** — proven soft spot, data already in hand
   (game dates + `etl/venue_coords.json`). Test whether the *market* under-prices
   fatigue, not just whether the model predicts it.
2. **Live / in-game** models (different market, less efficient) — a bigger build.
3. **Extend odds coverage** to 2023-26 (SBR stops at 2022-23) to confirm the
   verdict holds on recent seasons before abandoning moneyline entirely.
