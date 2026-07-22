"""
Score the matchup model against historical CLOSING MONEYLINE odds
=================================================================

The definitive edge test. Winning-pick accuracy (58.9%) only says the model has
skill vs a coin flip; this asks the question that matters: does it find value the
MARKET missed? You must beat the closing line (~52.4% break-even at -110), not 50%.

INPUTS
------
1. Model predictions CSV (from the backtest):
      python backtest_matchup_rolling.py --emit-predictions preds.csv
   columns: game_id, season, home, away, p_home, home_win, maturity

2. Odds CSV -- NOT in our DB yet; supply your own. One row per game:
      game_id, home_ml, away_ml       (American odds, e.g. -135 / +115)
   game_id must match the NHL gamePk used throughout (e.g. 2023020001). If your
   source keys by date+teams instead, map it to game_id first. Decimal odds are
   auto-detected (values > 0 and < ~30 with a decimal point) -- or pass --decimal.

   Where to get it (all external; none pulled automatically):
     * sportsbookreviewsonline.com -- free historical NHL odds spreadsheets by
       season (keyed by date/teams -> needs a game_id join).
     * the-odds-api.com / oddsapi.io -- historical endpoints (paid tiers).
     * Kaggle NHL odds datasets (coverage varies by season).

WHAT IT COMPUTES
----------------
Per game: devig the two-sided closing prices to a fair market prob, compare to the
model's p_home, and "bet" the side where model prob - market prob > --edge. Then:
  * record vs market (how often the model's disagreements were right)
  * flat-stake ROI and quarter-Kelly ROI (1u bets), with break-even reference
  * closing-line value (did we beat the number?)
  * breakdown by favorite/underdog and by season maturity (>=20 games = mature)
No bankroll compounding; flat 1u unless --kelly.

USAGE
    python score_vs_odds.py --preds preds.csv --odds odds.csv [--edge 0.03] [--kelly] [--decimal]
    python score_vs_odds.py --self-test          # validate the math on synthetic odds
"""
import csv, argparse, math, sys, random

def american_to_prob(ml):        # implied prob incl. vig
    ml=float(ml)
    return (-ml)/(-ml+100) if ml < 0 else 100/(ml+100)
def american_to_decimal(ml):
    ml=float(ml)
    return 1+(100/-ml) if ml < 0 else 1+(ml/100)
def to_decimal(v, force_decimal):
    v=float(v)
    if force_decimal: return v
    # heuristic: American odds are |v|>=100 integers; decimals are ~1.01..30
    return v if (1.0 < v < 30.0 and abs(v-round(v))>1e-9) else american_to_decimal(v)
def to_prob(v, force_decimal):
    d=to_decimal(v, force_decimal); return 1.0/d

def load_preds(path):
    out={}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out[str(r["game_id"])]=dict(p=float(r["p_home"]), win=int(r["home_win"]),
                                     mat=int(r.get("maturity",0)),
                                     home=r.get("home"), away=r.get("away"),
                                     season=r.get("season"))
    return out

def load_odds(path, force_decimal):
    out={}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        try:
            hp=to_prob(r["home_ml"], force_decimal); ap=to_prob(r["away_ml"], force_decimal)
            hd=to_decimal(r["home_ml"], force_decimal); ad=to_decimal(r["away_ml"], force_decimal)
        except (KeyError, ValueError): continue
        s=hp+ap
        out[str(r["game_id"])]=dict(mkt_home=hp/s, mkt_away=ap/s, dec_home=hd, dec_away=ad, vig=s-1)
    return out

def score(preds, odds, edge, kelly):
    bets=[]
    for gid, p in preds.items():
        o=odds.get(gid)
        if not o: continue
        # two candidate bets; take the side with positive model edge over the devigged line
        cands=[("home", p["p"],       o["mkt_home"], o["dec_home"], p["win"]),
               ("away", 1.0-p["p"],    o["mkt_away"], o["dec_away"], 1-p["win"])]
        for side, mp, mk, dec, won in cands:
            e=mp-mk
            if e<=edge: continue
            stake=1.0
            if kelly:
                b=dec-1.0; k=(mp*b-(1-mp))/b        # full Kelly edge
                stake=max(0.0, min(k*0.25, 1.0))    # quarter-Kelly, capped 1u
            if stake<=0: continue
            profit=stake*(dec-1.0) if won else -stake
            bets.append(dict(gid=gid, side=side, mp=mp, mk=mk, dec=dec, won=won,
                             stake=stake, profit=profit, mat=p["mat"],
                             fav = mk>=0.5))
    return bets

def summarize(bets, label):
    if not bets:
        print(f"  {label}: no qualifying bets"); return
    n=len(bets); staked=sum(b["stake"] for b in bets); pnl=sum(b["profit"] for b in bets)
    wins=sum(b["won"] for b in bets)
    roi=pnl/staked
    clv=sum((b["mp"]-b["mk"]) for b in bets)/n
    print(f"  {label:<22} bets={n:5d}  win%={wins/n:.3f}  ROI={roi:+.3%}  "
          f"units={pnl:+.1f}  avg_edge(CLV)={clv:+.3f}")

def report(bets):
    print(f"\nqualifying bets: {len(bets)}")
    print("(break-even ROI is 0%; a real edge is positive ROI AND positive avg CLV)\n")
    summarize(bets, "ALL")
    summarize([b for b in bets if b["fav"]],      "favorites")
    summarize([b for b in bets if not b["fav"]],  "underdogs")
    summarize([b for b in bets if b["mat"]>=20],  "mature (>=20 gp)")
    summarize([b for b in bets if b["mat"]<20],   "early (<20 gp)")

# ------------------------------------------------------------------ self-test
def self_test():
    """Validate devig + ROI wiring with two known scenarios:
      A. market == true prob (+vig), model == true prob  -> no edge, ROI ~ -vig.
      B. market == true prob + noise (miscalibrated), model == true prob (sharper)
         -> a real edge, ROI clearly positive."""
    random.seed(1); N=40000; vig=0.045
    def build(noisy_market):
        preds={}; odds={}
        for i in range(N):
            gid=str(i); true_p=random.uniform(0.30,0.70)
            won=1 if random.random()<true_p else 0
            mkt=true_p
            if noisy_market: mkt=min(max(true_p+random.gauss(0,0.05),0.02),0.98)
            mh=mkt*(1+vig); ma=(1-mkt)*(1+vig)
            odds[gid]=dict(mkt_home=mkt, mkt_away=1-mkt, dec_home=1/mh, dec_away=1/ma, vig=vig)
            preds[gid]=dict(p=true_p, win=won, mat=25, home="H", away="A", season="x")  # sharp model
        return preds, odds
    pA,oA=build(False); bA=score(pA,oA,edge=-1,kelly=False)   # force all bets
    roiA=sum(x["profit"] for x in bA)/sum(x["stake"] for x in bA)
    pB,oB=build(True);  bB=score(pB,oB,edge=0.03,kelly=False)
    roiB=sum(x["profit"] for x in bB)/sum(x["stake"] for x in bB) if bB else float("nan")
    print(f"self-test (vig={vig:.1%}):")
    print(f"  A market==truth, model==truth        ROI={roiA:+.3%}  (expect ~ -vig = -{vig:.1%})")
    print(f"  B noisy market, sharper model (e>3%) ROI={roiB:+.3%}  bets={len(bB)}  (expect clearly positive)")
    print("mechanics OK" if (roiB>0 and roiA<-0.02) else "CHECK WIRING")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--preds"); ap.add_argument("--odds")
    ap.add_argument("--edge", type=float, default=0.03, help="min model-minus-market edge to bet")
    ap.add_argument("--kelly", action="store_true", help="quarter-Kelly staking (default flat 1u)")
    ap.add_argument("--decimal", action="store_true", help="odds are decimal, not American")
    ap.add_argument("--self-test", action="store_true")
    a=ap.parse_args()
    if a.self_test: return self_test()
    if not (a.preds and a.odds):
        sys.exit("need --preds and --odds (or --self-test). See module docstring for the odds schema.")
    preds=load_preds(a.preds); odds=load_odds(a.odds, a.decimal)
    matched=sum(1 for g in preds if g in odds)
    print(f"predictions {len(preds)}  odds {len(odds)}  matched {matched}  "
          f"edge>={a.edge}  staking={'quarter-Kelly' if a.kelly else 'flat 1u'}")
    if matched==0: sys.exit("no game_id overlap -- map your odds source to NHL gamePk.")
    report(score(preds, odds, a.edge, a.kelly))

if __name__=="__main__":
    main()
