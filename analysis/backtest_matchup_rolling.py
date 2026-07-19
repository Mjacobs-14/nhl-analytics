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
    pred_home_goals = ph_xg x FINISH(away goalie)
    (symmetric for away). Independent Poisson on the two expected counts ->
    P(home win), ties split 50/50 (OT/SO). Scored vs the real final result.

FINISH factor -- how well the defending side converts shot-quality into saves:
  * team pool (baselines): defending team's actual GA / xGA.
  * STARTING GOALIE (rolling, the +goalie model): the actual starter's own
    GA/xGA, shots-shrunk (league 1.0 + prior season + season-to-date). Adding
    this lifts rolling accuracy 58.0 -> 58.9% and log-loss 0.673 -> 0.671,
    strongest late season (games 40+: 59 -> 63%). Starter = the goalie who
    faced the most shots in that game (known pre-game in live use).

Tested and REJECTED (see analysis/README.md): opponent / strength-of-schedule
adjustment (wash-to-negative over a full season) and coach-style clash
(~0 residual correlation).

This backtests the model's xG CORE + goalie. The page's EV/PP special-teams
split is a further layer, not yet folded in here.

DATA: fetched live from Postgres via DATABASE_URL (same var the app uses), or
from a --snapshot JSON file. Pass --write-snapshot PATH to cache a fetch.

USAGE:
    python backtest_matchup_rolling.py                    # live DB
    python backtest_matchup_rolling.py --snapshot bt.json # offline
    DATABASE_URL=... python backtest_matchup_rolling.py --write-snapshot bt.json
"""
import os, sys, json, math, argparse, statistics as st

# Per-game, per-team, venue-split shot xG/goals for & against, + the real final
# score carried on every row.
SQL_TEAM = """
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

# Per-game, per-team goalie workload -- used to identify each game's starter and
# roll each goalie's save-vs-expected forward.
SQL_GOALIE = """
select game_id, season, def_team team, goalie_id,
  count(*) shots, sum(is_goal) ga, round(sum(xg),2) xga
from shot_xg_v
where game_type='regular' and goalie_id is not null
group by game_id, season, def_team, goalie_id
order by season, game_id, def_team, count(*) desc
"""

K = 15          # team profile shrinkage (pseudo-games)
KG = 250        # goalie shrinkage toward league 1.0 (pseudo-shots)
PS_CAP = 1200   # cap prior-season goalie shots used as prior weight

# ---------------------------------------------------------------- data loading
def _connect(url):
    try:
        import psycopg; return psycopg.connect(url)
    except Exception:
        try:
            import psycopg2; return psycopg2.connect(url)
        except Exception as e:
            sys.exit("No DATABASE_URL driver (pip install 'psycopg[binary]') "
                     "and no --snapshot given. " + str(e))

def fetch_live():
    url = os.environ.get("DATABASE_URL")
    if not url: return None
    conn = _connect(url); out = {}
    for key, sql in (("team", SQL_TEAM), ("goalie", SQL_GOALIE)):
        cur = conn.cursor(); cur.execute(sql)
        cols = [c[0] for c in cur.description]
        out[key] = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    for r in out["team"]:
        for k in ("xgf", "xga"):
            if r[k] is not None: r[k] = float(r[k])
    for r in out["goalie"]:
        if r["xga"] is not None: r["xga"] = float(r["xga"])
    return out

def get_data(args):
    if args.snapshot and os.path.exists(args.snapshot):
        with open(args.snapshot, encoding="utf-8") as f: return json.load(f)
    data = fetch_live()
    if data is None:
        sys.exit("Set DATABASE_URL for a live fetch, or pass --snapshot PATH.")
    if args.write_snapshot:
        with open(args.write_snapshot, "w", encoding="utf-8") as f: json.dump(data, f)
        print(f"wrote snapshot: {args.write_snapshot}")
    return data

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

def rate(acc, k): return acc[k]/acc["gp"] if acc and acc["gp"] else None
def new_acc(): return dict(gp=0, xgf=0.0, gf=0, xga=0.0, ga=0)
def fold(acc, r):
    acc["gp"]+=1; acc["xgf"]+=r["xgf"] or 0; acc["gf"]+=r["gf"] or 0
    acc["xga"]+=r["xga"] or 0; acc["ga"]+=r["ga"] or 0

def predict(hprof, aprof, lg_road_xga, lg_home_xga, h_fin, a_fin):
    """Expected (home_goals, away_goals). *_fin are defending-side finish factors."""
    ph_xg = rate(hprof,"xgf") * (rate(aprof,"xga")/lg_road_xga)
    pa_xg = rate(aprof,"xgf") * (rate(hprof,"xga")/lg_home_xga)
    return max(ph_xg*a_fin, 0.05), max(pa_xg*h_fin, 0.05)

def metrics(probs, margins):
    N=len(probs)
    acc=sum(1 for p,ov in probs if (p>0.5)==(ov==1))/N
    brier=sum((p-ov)**2 for p,ov in probs)/N
    ll=sum(-(ov*math.log(min(max(p,1e-9),1-1e-9))+(1-ov)*math.log(1-min(max(p,1e-9),1-1e-9))) for p,ov in probs)/N
    hr=sum(ov for _,ov in probs)/N
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
def build(data):
    rows = data["team"]
    games={}
    for r in rows:
        g=games.setdefault(r["game_id"], {"season": r["season"], "hs": r["hs"], "as": r["ascore"]})
        g[r["v"]]=r
    glist=[g for g in games.values() if "home" in g and "road" in g]
    glist.sort(key=lambda g:(g["season"], g["home"]["game_id"]))
    for g in glist:
        g["_hw"]=1 if g["hs"]>g["as"] else 0
        g["_margin"]=g["hs"]-g["as"]
    seasons=sorted({g["season"] for g in glist})
    prev={seasons[i]:seasons[i-1] for i in range(1,len(seasons))}
    final={}; lg={}
    for g in glist:
        for v in ("home","road"):
            r=g[v]; final.setdefault((g["season"],r["team"],v), new_acc())
            fold(final[(g["season"],r["team"],v)], r)
    for (s,t,v),a in final.items():
        L=lg.setdefault((s,v), new_acc())
        for k in L: L[k]+=a[k]
    # goalie structures: per-game rows, each game's starter, prior-season totals
    by_game={}; starter={}; ps_goalie={}
    for r in data.get("goalie", []):
        by_game.setdefault(r["game_id"], []).append(r)
        a=ps_goalie.setdefault((r["season"], r["goalie_id"]), [0,0,0.0])
        a[0]+=r["shots"]; a[1]+=r["ga"]; a[2]+=r["xga"] or 0
    for gid, rs in by_game.items():
        best={}
        for r in rs:
            k=(gid, r["team"])
            if k not in best or r["shots"]>best[k]["shots"]: best[k]=r
        for k,r in best.items(): starter[k]=r["goalie_id"]
    G=dict(by_game=by_game, starter=starter, ps_goalie=ps_goalie)
    return glist, prev, final, lg, G

def lg_denoms(lg, pS):
    return rate(lg.get((pS,"road")),"xga"), rate(lg.get((pS,"home")),"xga")

def team_finish(prof): return (prof["ga"]/prof["xga"]) if prof["xga"] else 1.0

def goalie_finish(G, pS, gid, cacc):
    """Shots-shrunk GA/xGA for a specific goalie (~1.0 = league average)."""
    num=KG*1.0; den=KG*1.0
    ps=G["ps_goalie"].get((pS,gid)) if pS else None
    if ps and ps[2]>0: w=min(ps[0],PS_CAP); num+=w*(ps[1]/ps[2]); den+=w
    if cacc and cacc[2]>0: num+=cacc[0]*(cacc[1]/cacc[2]); den+=cacc[0]
    return num/den

def run_static(glist, prev, final, lg, leaky):
    probs=[]; margins=[]
    for g in glist:
        use = g["season"] if leaky else prev.get(g["season"])
        if use is None: continue
        lr,lh = lg_denoms(lg, use)
        if lr is None or lh is None: continue
        hp=final.get((use,g["home"]["team"],"home")); ap=final.get((use,g["road"]["team"],"road"))
        if not hp or not ap: continue
        lhg,lag=predict(hp,ap,lr,lh, team_finish(hp), team_finish(ap))
        probs.append((p_home_win(lhg,lag), g["_hw"])); margins.append((lhg-lag, g["_margin"]))
    return metrics(probs,margins), probs

def run_rolling(glist, prev, final, lg, G, K, use_goalie):
    cur={}; cgo={}; cseason=None
    probs=[]; margins=[]; buckets={}; records=[]
    for g in glist:
        S=g["season"]
        if S!=cseason: cur={}; cgo={}; cseason=S
        pS=prev.get(S); H=g["home"]; A=g["road"]
        hc=cur.get((H["team"],"home")); ac=cur.get((A["team"],"road"))
        n_h=hc["gp"] if hc else 0; n_a=ac["gp"] if ac else 0
        lr,lh = lg_denoms(lg, pS) if pS else (None,None)
        if pS is not None and lr is not None and lh is not None:
            def blend(team,v,ca):
                b=new_acc(); b["gp"]=1; n=ca["gp"] if ca else 0
                fp=final.get((pS,team,v)); lp=lg.get((pS,v))
                for k in ("xgf","xga","gf","ga"):
                    pv=rate(fp,k) if fp else rate(lp,k)
                    cr=rate(ca,k) if ca else None
                    b[k]= pv if cr is None else (K*pv+n*cr)/(K+n)
                return b
            hp=blend(H["team"],"home",hc); ap=blend(A["team"],"road",ac)
            if use_goalie:
                gh=G["starter"].get((g["home"]["game_id"], A["team"]))  # away starter vs home shots
                ga_=G["starter"].get((g["home"]["game_id"], H["team"])) # home starter vs away shots
                a_fin=goalie_finish(G,pS,gh,cgo.get(gh)) if gh else team_finish(ap)
                h_fin=goalie_finish(G,pS,ga_,cgo.get(ga_)) if ga_ else team_finish(hp)
            else:
                h_fin=team_finish(hp); a_fin=team_finish(ap)
            lhg,lag=predict(hp,ap,lr,lh,h_fin,a_fin)
            P=p_home_win(lhg,lag)
            probs.append((P,g["_hw"])); margins.append((lhg-lag,g["_margin"]))
            m=min(n_h,n_a); b=0 if m<10 else 1 if m<20 else 2 if m<40 else 3
            bk=buckets.setdefault(b,[0,0]); bk[0]+= 1 if (P>0.5)==(g["_hw"]==1) else 0; bk[1]+=1
            records.append((g["home"]["game_id"], S, g["home"]["team"], g["road"]["team"],
                            round(P,4), g["_hw"], m))
        cur.setdefault((H["team"],"home"), new_acc()); fold(cur[(H["team"],"home")], H)
        cur.setdefault((A["team"],"road"), new_acc()); fold(cur[(A["team"],"road")], A)
        for r in G["by_game"].get(g["home"]["game_id"], []):
            a=cgo.setdefault(r["goalie_id"], [0,0,0.0]); a[0]+=r["shots"]; a[1]+=r["ga"]; a[2]+=r["xga"] or 0
    return metrics(probs,margins), probs, buckets, records

BUCKET={0:"each team's games 0-9 (October)",1:"games 10-19",
        2:"games 20-39 (mid-season)",3:"games 40+ (2nd half)"}

def report(m, tag):
    nsl=-(m["hr"]*math.log(m["hr"])+(1-m["hr"])*math.log(1-m["hr"]))
    print(f"{tag:<30} n={m['N']:5d}  acc={m['acc']:.4f}  "
          f"logloss={m['ll']:.4f}  brier={m['brier']:.4f}  margin_corr={m['corr']:.3f}")
    return nsl

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot"); ap.add_argument("--write-snapshot")
    ap.add_argument("--K", type=int, default=None, help="fix shrinkage weight; default sweeps")
    ap.add_argument("--emit-predictions", help="write per-game rolling+goalie predictions to CSV "
                    "(game_id,season,home,away,p_home,home_win,maturity) for score_vs_odds.py")
    args=ap.parse_args()
    data=get_data(args)
    glist, prev, final, lg, G = build(data)
    print(f"games: {len(glist)}   seasons: {sorted({g['season'] for g in glist})}\n")

    print("BASELINES & STATIC MODELS")
    ms,_=run_static(glist,prev,final,lg,leaky=False)
    nsl=report(ms,"prior-season (honest)")
    print(f"{'  no-skill (home-rate)':<30} "
          f"acc={ms['hr']:.4f}  logloss={nsl:.4f}  brier=0.2500  (always-pick-home)")
    ml,_=run_static(glist,prev,final,lg,leaky=True)
    report(ml,"same-season (leaky ceiling)")

    print("\nROLLING AS-OF (shrinkage sweep, xG core, no goalie)")
    Ks=[args.K] if args.K else [10,15,20,25,30,40,60]
    best=None
    for K in Ks:
        mr,_,_,_=run_rolling(glist,prev,final,lg,G,K,use_goalie=False)
        print(f"  K={K:>3}  acc={mr['acc']:.4f}  logloss={mr['ll']:.4f}  brier={mr['brier']:.4f}")
        if best is None or mr["ll"]<best[0]: best=(mr["ll"],K)
    K=best[1]
    mcore,_,_,_=run_rolling(glist,prev,final,lg,G,K,use_goalie=False)
    mg,pr,bk,records=run_rolling(glist,prev,final,lg,G,K,use_goalie=True)
    if args.emit_predictions:
        import csv
        with open(args.emit_predictions,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["game_id","season","home","away","p_home","home_win","maturity"])
            w.writerows(records)
        print(f"\nwrote {len(records)} predictions -> {args.emit_predictions}")
    print(f"\nBEST ROLLING  K={K}")
    report(mcore, "rolling xG core")
    report(mg,    "rolling + starting goalie")
    print("\n  accuracy by season maturity (min games either team has played):")
    for b in sorted(bk):
        c,n=bk[b]; print(f"    {BUCKET[b]:<32} n={n:5d}  acc={c/n:.4f}")
    print("\n  calibration (rolling + goalie)  [P range]   n     mean_pred  actual_home_win")
    for lo,hi,n,mp,acr in calib(pr):
        print(f"    {lo:.1f}-{hi:.1f}   {n:5d}     {mp:.3f}      {acr:.3f}")

if __name__ == "__main__":
    main()
