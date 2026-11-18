# Model validation

Out-of-sample tests of whether our models actually predict NHL games.

Two benchmarks, in increasing difficulty:

1. **Real outcomes** — accuracy, log-loss and calibration against what actually
   happened, compared with naive baselines (always pick the home team).
2. **Sportsbook closing lines** — the market's final odds are the sharpest public
   forecast of a game, so they are the toughest available yardstick. A model that
   comes close to the closing line has learned much of what the best forecasters
   know; where it disagrees with the line, the line is usually right. Odds are used here purely
   as a measuring stick — this is not a betting project.

**Summary:** the matchup model is genuinely predictive (58.9% winner accuracy vs.
53.6% for "always pick home", well calibrated) but **trails the closing line**.
On the same 3,497 games, the closing-line favorite won 60.8% of the time versus
59.2% for the model, and the market's probabilities score better on log-loss
and Brier. The signal the model captures is real, and already priced in. Along the way: what moved the model (starting-goalie identity), four
refinements that didn't, why game totals and player props are dominated by
randomness, and one market inefficiency (tired home teams) that faded over time.

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

In October the model runs on last year's stale prior and performs like it.
**Accuracy stabilizes after about 20 games played per team** (roughly late
November), when current-season data outweighs the prior, at around 60% —
most of the way to the leaky ceiling.

### What this does and doesn't show

58% (59%+ mid-season) is a real, calibrated model — but beating a coin flip or
the home team doesn't show it knows more than the market. The stricter
comparison is the closing line, scored on exactly the same games (next
section): there the market is ahead.

### Totals & team totals — tested, rejected (2026-07)

We re-scored the *same* rolling model against over/unders, since it emits
expected goals directly. **Game totals are a dead end for this model:**
corr(predicted total, actual total) = **0.07**, and over/under 6.5 log-loss
(0.694) is *worse than a coin flip*. The cause is structural — the model
predicts nearly every game at 5.9–6.2 (predicted-total SD 0.52 vs actual 2.30),
because offense/defense strengths cancel in the *sum*. And the ceiling is low
for anyone: actual-total SD (2.30) ≈ pure Poisson noise at 6.2 goals (2.49), so
game totals are mostly irreducible randomness.

Team totals had a faint pulse (corr 0.17, calibrated) but only tie "always predict
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

## Validation against closing lines — RESULT: skilled, but trails the market

`score_vs_odds.py` removes the bookmaker margin ("devigs") from closing
moneylines to get the market's probability for each game, then measures what
happens in the games where the model disagrees with the market by more than
`--edge`. Each disagreement is scored by the return of a hypothetical fixed
stake on the model's side at the closing price — a standard way to weight the
disagreements by how confident the market was: positive means the model was
right more often than the market implied. It reports that return, plus
favorite/underdog and season-maturity breakdowns. `fetch_sbr_odds.py` pulls the closing lines from Sportsbook
Reviews Online (free archive, 2018-19 .. 2022-23) and maps them to gamePk.

```
python fetch_sbr_odds.py --out odds.csv                            # scrape + map odds
python backtest_matchup_rolling.py --emit-predictions preds.csv    # model side
python score_vs_odds.py --preds preds.csv --odds odds.csv          # score it
python score_vs_odds.py --self-test                                # validate the math
```

**Verdict: the model trails the market.** 4 out-of-sample seasons
(2019-20 .. 2022-23), 3,497 games matched to closing lines.

Head to head on the same games (market = the closing line's devigged
probability; a pick is whichever side it favors):

| | Picks winner | Log-loss (lower better) | Brier (lower better) |
|---|---|---|---|
| Always pick home | 53.4% | — | — |
| **Model** | **59.2%** | 0.669 | 0.238 |
| **Closing line** | **60.8%** | **0.659** | **0.233** |

The two agree on 81% of games. In the 635 games where they pick different
winners, the model is right 45.7% of the time. The gap holds in both parts of
the season: 58.5% vs 59.7% before each team's 20th game, 60.4% vs 62.6% after.

Scoring the disagreements against the closing price says the same thing:

| Model–market disagreement | Games | Model right | Return vs. market |
|---|---|---|---|
| model differs by ≥3% | 2,376 | 44.1% | **−2.4%** |
| model differs by ≥5% | 1,662 | 43.1% | **−2.0%** |
| model differs by ≥2% (weighted by size of disagreement) | 2,731 | 44.4% | **−1.7%** |

Every threshold comes out slightly negative — about the size of the bookmaker
margin. The decisive cut is maturity: **the mature-game segment (≥20 gp), where
the model's raw accuracy peaks at 60%, is where it adds the least beyond the
market (−7% return).** Its skill is entirely priced in. Favorites ≈ break-even;
underdogs negative; the only non-negative slice is early-season (<20 gp), which
is noise. The "underdog value" and "mature-game" hypotheses are falsified.

**Bottom line:** a genuinely skilled, well-calibrated winner-picker (58.9%
overall) that **trails the closing line** by about 1.6 points of accuracy.
That's the expected result for a model built only on public shot data — the
market also prices injuries, line changes and confirmed starters — and it
validates that the model measures something real rather than overfitting.

## Rest / back-to-backs / travel — a real market bias that later faded

`fatigue_market_test.py` asks whether the *market* under-prices fatigue (not just
whether it affects games). Unlike the model — which was priced-in everywhere —
fatigue shows the **first genuine crack in market efficiency**:

| Back-to-back situation | n | actual home-win | market-implied | gap |
|---|---|---|---|---|
| neither on b2b | 3,509 | 0.535 | 0.541 | −0.005 (priced) |
| away on b2b only | 710 | 0.583 | 0.564 | +0.019 (small) |
| **home on b2b only** | **227** | **0.419** | **0.500** | **−0.081** |
| both on b2b | 305 | 0.505 | 0.523 | −0.018 |

**The book over-prices tired home teams:** on a back-to-back they win 41.9% but
are lined at 50.0% — the market over-weights home ice and under-adjusts for
fatigue. Siding with the rested team in those games scored **+4.3% vs. the
closing price over 937 games**.

**But it isn't robust:**
- Season-unstable: per-season return was +1.6%, **−4.0%**, +26% (COVID bubble,
  n=66, unrepresentative), +11%, **−8.3%** — 2 of 5 seasons negative, and the
  aggregate leans on the empty-arena COVID season.
- The larger group (tired away team, 710 games) is only +1.9% — inside the
  noise; essentially priced. The real signal is the smaller tired-home-team
  group (227 games, ~1.8σ vs the market).
- Rest-differential, travel distance, and 3-in-4 congestion showed **no**
  mispricing (all priced or noise).

Verdict: a real, directionally-sensible bias worth pursuing — the market
under-prices home-team back-to-back fatigue — but the sample is too thin and
season-to-season too inconsistent to rely on. It points somewhere real.

### The effect is fading (free robustness check, our own data)

Before buying recent odds, we tested whether the *raw* home-b2b effect even
persists — it needs only schedule + outcomes, which we have for all 8 seasons:

| Era | home-b2b games | home win % |
|---|---|---|
| 2018–2023 (where the bias showed) | 283 | **41.3%** |
| 2023–2026 (no free odds archive) | 217 | **48.8%** |

2025-26 (complete) shows **53.9%** — no effect; tired home teams now win at their
normal home rate. The signal behind the +4.3% has decayed toward league
average (likely league-wide load-management + market adjustment). So buying
2023-26 closing odds would most likely just confirm the bias has closed, so
recent odds weren't worth sourcing.

### Odds sources surveyed (for the record)

| Source | Recent seasons | Closing ML? | Cost | Verdict |
|---|---|---|---|---|
| Sportsbook Reviews Online | no (stops 2022-23) | yes | free | already used |
| checkbestodds.com | 2023-26 | **no** (best/3-way) | free | best-available odds, not closing; unfit |
| Scottfree Analytics CSV | unconfirmed | yes | $69 one-time | clean but coverage unconfirmed |
| The Odds API | from late-2020 | snapshot≈close | usage-priced | programmatic; snapshot proxy |

## Player props — fail the gate (structurally)

Player-level stats were the next question: **can we predict a skater's shots
on goal better than the naive trailing average** (roughly how sportsbook player
lines are set)?
Rolling as-of over 128,966 player-games (2023-26), predicting with *expected*
(rolling) TOI — never the actual TOI of the game being predicted.

| model | MAE | log-loss @2.5 |
|---|---|---|
| naive trailing mean (≈ the book's line) | 1.0930 | 0.5067 |
| EWMA (recency-weighted) | 1.1017 | 0.5182 |
| shots/60 × expected TOI | **1.0919** | **0.5059** |

Our usage model beats naive by **0.1%**. Recency-weighting is actively *worse* —
chasing hot shooters is a mistake; the long-run mean wins.

**The decisive diagnostic is the Poisson noise floor** — the MAE a model that
knew each player's *true* rate would still have:

| stat | naive MAE | perfect-model floor | max possible gain |
|---|---|---|---|
| shots on goal | 1.0930 | 1.0388 | **5.1%** |
| blocked shots | 0.7533 | 0.7263 | **3.7%** |

Individual-game props are overwhelmingly **irreducible randomness**. A trailing
average already captures ~98% of the predictable signal, and even a *perfect*
model gains only 3.7–5.1% — less than the margin built into a typical player
line. This
is a structural ceiling, not a modelling failure: you cannot out-model Poisson
noise. Same story as game totals.

Caveat: the opponent-suppression term was effectively untested because
`player_game_stats.opponent_abbrev` is NULL (an ETL gap, flagged separately).
It doesn't change the verdict — a ±3–8% matchup tweak cannot break a ceiling
that sits 5% above naive.

What *does* move single-game player outcomes is same-day information
(tonight's power-play units, line combinations, late scratches) — not more
historical modelling.

### Conclusion

The model is a genuinely skilled, well-calibrated **58.9% winner-picker that
trails the closing line** (59.2% vs 60.8% on the same games): its information
is real and already priced in. The one market inefficiency we found (tired
home teams) was real in 2018-2023 but has **faded** in recent seasons. Net: the
model is a sound tool for previews and for explaining *why* a matchup tilts one
way, and the backtest framework is reusable for testing future features.
