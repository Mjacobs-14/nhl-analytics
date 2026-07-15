"""
Backtest the Matchup model against actual NHL game outcomes
===========================================================

Scores the Matchup Lab model's expected-goals predictions against every
regular-season result (2018-2026) to measure real, out-of-sample predictive
skill -- the honest test before any monetization.

Three scorings, same math, differing only in what data the prediction is
allowed to see:

  1. prior-season  -- predict season S using season S-1's final profiles.
                      Honest but stale (roster churn erodes it).
  2. leaky ceiling -- predict season S using season S's profiles, which
                      INCLUDE the game being predicted. Upper bound only.
  3. rolling as-of -- predict each game from last season's profile as a prior,
                      blended toward this-season's games-played-to-date via a
                      shrinkage weight K (pseudo-games). This is how you would
                      actually forecast live (e.g. for 2026-27): the model only
                      ever knows the past. A game never sees itself.

Prediction (home H vs away A), venue-split location xG:
    ph_xg = H_home_xGF/gm x (A_road_xGA/gm / league_road_xGA/gm)
    pred_home_goals = ph_xg x (A_road actualGA / A_road xGA)   # goalie/finish
    (symmetric for away). Independent Poisson on the two expected counts ->
    P(home win), ties split 50/50 (OT/SO). Scored vs the real final result.

This backtests the model's xG CORE (venue-split shot-quality strengths x a
goalie finish factor). The page's EV/PP-split and per-band goalie refinements
are a further layer, not yet folded in here.

DATA: fetched live from Postgres via DATABASE_URL (same var the app uses), or
from a --snapshot JSON file. Pass --write-snapshot PATH to cache a fetch.

USAGE:
    python backtest_matchup_rolling.py                    # live DB
    python backtest_matchup_rolling.py --snapshot bt.json # offline
    DATABASE_URL=... python backtest_matchup_rolling.py --write-snapshot bt.json
"""
import os, sys, json, math, argparse, statistics as st

# One query: per-game, per-team, venue-split shot xG/goals for & against,
# plus the real final score carried on every row.
SQL = """
select g.game_id, g.season,
  case when fo.team = g.home_team_id then 'home' else 'road' end as v,
  fo.team, fo.xgf, fo.gf, de.xga, de.ga,
  g.home_score as hs, g.away_score as ascore
from (
    select game_id, team_id team, round(sum(xg),2) xgf, sum(is_goal) gf
    from shot_xg_v where game_type='regular' group by game_id, team_id
  ) fo
  join (
    select game_id, def_team team, round(sum(xg),2) xga, sum(is_goal) ga
    from shot_xg_v where game_type='regular' group by game_id, def_team
  ) de on de.game_id = fo.game_id and de.team = fo.team
  join games g on g.game_id = fo.game_id
where g.game_type='regular' and g.home_score is not null and g.away_score is not null
order by g.season, g.game_id, v
"""

# ---------------------------------------------------------------- data loading
def fetch_live():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg  # psycopg 3
        conn = psycopg.connect(url)
    except Exception:
        try:
            import psycopg2 as _p2
            conn = _p2.connect(url)
        except Exception as e:
            sys.exit("No DATABASE_URL driver (pip install 'psycopg[binary]') "
                     "and no --snapshot given. " + str(e))
    cur = conn.cursor()
    cur.execute(SQL)
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    # normalise Decimals -> float
    for r in rows:
        for k in ("xgf", "xga"):
            if r[k] is not None: r[k] = float(r[k])
    return rows

def load_snapshot(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_data(args):
    if args.snapshot and os.path.exists(args.snapshot):
        return load_snapshot(args.snapshot)
    rows = fetch_live()
    if rows is None:
        sys.exit("Set DATABASE_URL for a live fetch, or pass --snapshot PATH.")
    if args.write_snapshot:
        with open(args.write_snapshot, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        print(f"wrote snapshot: {args.write_snapshot} ({len(rows)} rows)")
    return rows

# ------------------------------------------------------------------- modelling
def pmf(lam, kmax=16):
    out=[]; p=math.exp(-lam)
    for k in range(kmax+1): out.append(p); p=p*lam/(k+1)
    return out
def p_home_win(lh, la, kmax=16):
    ph=pmf(lh,kmax); pa=pmf(la,kmax); win=tie=0.0
    for h in range(kmax+1):
        for a in range(kmax+1):
            pr=ph[h]*pa[a]
            if h>a: win+=pr
            elif h==a: tie+=pr
    return win+0.5*tie

def rate(acc, k):
    return acc[k]/acc["gp"] if acc and acc["gp"] else None

def new_acc(): return dict(gp=0, xgf=0.0, gf=0, xga=0.0, ga=0)
def fold(acc, r):
    acc["gp"]+=1; acc["xgf"]+=r["xgf"] or 0; acc["gf"]+=r["gf"] or 0
    acc["xga"]+=r["xga"] or 0; acc["ga"]+=r["ga"] or 0

def predict(hprof, aprof, lg_road_xga, lg_home_xga):
    """Expected (home_goals, away_goals) from home & away venue profiles."""
    def pg(p,k): return rate(p,k)
    ph_xg = pg(hprof,"xgf") * (pg(aprof,"xga")/lg_road_xga)
    pa_xg = pg(aprof,"xgf") * (pg(hprof,"xga")/lg_home_xga)
    a_fin = (aprof["ga"]/aprof["xga"]) if aprof["xga"] else 1.0
    h_fin = (hprof["ga"]/hprof["xga"]) if hprof["xga"] else 1.0
    return max(ph_xg*a_fin, 0.05), max(pa_xg*h_fin, 0.05)

def metrics(probs, margins):
    N=len(probs)
    o=[x[1] for x in probs]
    acc=sum(1 for p,ov in probs if (p>0.5)==(ov==1))/N
    brier=sum((p-ov)**2 for p,ov in probs)/N
    ll=sum(-(ov*math.log(min(max(p,1e-9),1-1e-9))+(1-ov)*math.log(1-min(max(p,1e-9),1-1e-9))) for p,ov in probs)/N
    hr=sum(o)/N
    pm=[m[0] for m in margins]; am=[m[1] for m in margins]
    mpm=st.mean(pm); mam=st.mean(am)
    corr=(sum((p-mpm)*(a-mam) for p,a in margins)/N)/(st.pstdev(pm)*st.pstdev(am))
    return dict(N=N, acc=acc, brier=brier, ll=ll, hr=hr, corr=corr)

def calib(probs, bins=10):
    out=[]
    for b in range(bins):
        lo=b/bins; hi=lo+1/bins
        sel=[(p,ov) for p,ov in probs if (lo<=p<hi) or (b==bins-1 and p==1.0)]
        if sel: out.append((lo,hi,len(sel),sum(p for p,_ in sel)/len(sel),
                             sum(ov for _,ov in sel)/len(sel)))
    return out

# ------------------------------------------------------------------- harness
def build(rows):
    games={}
    for r in rows:
        g=games.setdefault(r["game_id"], {"season": r["season"],
                                          "hs": r["hs"], "as": r["ascore"]})
        g[r["v"]]=r
    glist=[g for g in games.values() if "home" in g and "road" in g]
    glist.sort(key=lambda g:(g["season"], g["home"]["game_id"]))
    for g in glist:
        g["_hw"]=1 if g["hs"]>g["as"] else 0
        g["_margin"]=g["hs"]-g["as"]
    seasons=sorted({g["season"] for g in glist})
    prev={seasons[i]:seasons[i-1] for i in range(1,len(seasons))}
    # season-final profiles + league totals
    final={}; lg={}
    for g in glist:
        for v in ("home","road"):
            r=g[v]; final.setdefault((g["season"],r["team"],v), new_acc())
            fold(final[(g["season"],r["team"],v)], r)
    for (s,t,v),a in final.items():
        L=lg.setdefault((s,v), new_acc())
        for k in L: L[k]+=a[k]
    return glist, prev, final, lg

def lg_denoms(lg, pS):
    lr=rate(lg.get((pS,"road")),"xga"); lh=rate(lg.get((pS,"home")),"xga")
    return lr, lh

def run_static(glist, prev, final, lg, leaky):
    probs=[]; margins=[]
    for g in glist:
        S=g["season"]; use = S if leaky else prev.get(S)
        if use is None: continue
        lr,lh = lg_denoms(lg, use)
        if lr is None or lh is None: continue
        hp=final.get((use,g["home"]["team"],"home"))
        ap=final.get((use,g["road"]["team"],"road"))
        if not hp or not ap: continue
        lhg,lag=predict(hp,ap,lr,lh)
        P=p_home_win(lhg,lag)
        probs.append((P,g["_hw"])); margins.append((lhg-lag,g["_margin"]))
    return metrics(probs,margins), probs

def run_rolling(glist, prev, final, lg, K):
    cur={}; cseason=None
    probs=[]; margins=[]; buckets={}
    for g in glist:
        S=g["season"]
        if S!=cseason: cur={}; cseason=S
        pS=prev.get(S)
        H=g["home"]; A=g["road"]
        hc=cur.get((H["team"],"home")); ac=cur.get((A["team"],"road"))
        n_h=hc["gp"] if hc else 0; n_a=ac["gp"] if ac else 0
        lr,lh = lg_denoms(lg, pS) if pS else (None,None)
        scored = pS is not None and lr is not None and lh is not None
        if scored:
            def blend(team,v,ca):
                out=new_acc(); out["gp"]=1  # placeholder; we build rates directly
                pr={k:(rate(final.get((pS,team,v)),k) if final.get((pS,team,v))
                       else rate(lg.get((pS,v)),k)) for k in ("xgf","xga","gf","ga")}
                n=ca["gp"] if ca else 0
                blended=new_acc(); blended["gp"]=1
                for k in ("xgf","xga","gf","ga"):
                    cr=rate(ca,k) if ca else None
                    pv=pr[k] if pr[k] is not None else cr
                    val=pv if cr is None else (K*pv+n*cr)/(K+n)
                    blended[k]=val  # store as per-game rate with gp=1
                return blended
            hp=blend(H["team"],"home",hc); ap=blend(A["team"],"road",ac)
            lhg,lag=predict(hp,ap,lr,lh)
            P=p_home_win(lhg,lag)
            probs.append((P,g["_hw"])); margins.append((lhg-lag,g["_margin"]))
            m=min(n_h,n_a); b=0 if m<10 else 1 if m<20 else 2 if m<40 else 3
            bk=buckets.setdefault(b,[0,0])
            bk[0]+= 1 if (P>0.5)==(g["_hw"]==1) else 0; bk[1]+=1
        cur.setdefault((H["team"],"home"), new_acc()); fold(cur[(H["team"],"home")], H)
        cur.setdefault((A["team"],"road"), new_acc()); fold(cur[(A["team"],"road")], A)
    return metrics(probs,margins), probs, buckets

BUCKET={0:"each team's games 0-9 (October)",1:"games 10-19",
        2:"games 20-39 (mid-season)",3:"games 40+ (2nd half)"}

def report(m, tag):
    nsl=-(m["hr"]*math.log(m["hr"])+(1-m["hr"])*math.log(1-m["hr"]))
    print(f"{tag:<26} n={m['N']:5d}  acc={m['acc']:.4f}  "
          f"logloss={m['ll']:.4f}  brier={m['brier']:.4f}  margin_corr={m['corr']:.3f}")
    return nsl

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot"); ap.add_argument("--write-snapshot")
    ap.add_argument("--K", type=int, default=None, help="fix shrinkage weight; default sweeps")
    args=ap.parse_args()
    rows=get_data(args)
    glist, prev, final, lg = build(rows)
    print(f"games: {len(glist)}   seasons: {sorted({g['season'] for g in glist})}\n")

    print("BASELINES & STATIC MODELS")
    ms,_=run_static(glist,prev,final,lg,leaky=False)
    nsl=report(ms,"prior-season (honest)")
    print(f"{'  no-skill (home-rate)':<26} "
          f"acc={ms['hr']:.4f}  logloss={nsl:.4f}  brier=0.2500  (always-pick-home)")
    ml,_=run_static(glist,prev,final,lg,leaky=True)
    report(ml,"same-season (leaky ceiling)")

    print("\nROLLING AS-OF (shrinkage sweep)")
    Ks=[args.K] if args.K else [10,15,20,25,30,40,60]
    best=None
    for K in Ks:
        mr,pr,bk=run_rolling(glist,prev,final,lg,K)
        print(f"  K={K:>3}  acc={mr['acc']:.4f}  logloss={mr['ll']:.4f}  brier={mr['brier']:.4f}")
        if best is None or mr["ll"]<best[0]: best=(mr["ll"],K,mr,pr,bk)
    _,K,mr,pr,bk=best
    print(f"\nBEST ROLLING  K={K}")
    report(mr, f"rolling as-of (K={K})")
    print("\n  accuracy by season maturity (min games either team has played):")
    for b in sorted(bk):
        c,n=bk[b]; print(f"    {BUCKET[b]:<32} n={n:5d}  acc={c/n:.4f}")
    print("\n  calibration   [P range]   n     mean_pred  actual_home_win")
    for lo,hi,n,mp,acr in calib(pr):
        print(f"    {lo:.1f}-{hi:.1f}   {n:5d}     {mp:.3f}      {acr:.3f}")

if __name__ == "__main__":
    main()
