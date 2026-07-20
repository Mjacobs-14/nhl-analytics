"""
Does the market UNDER-price fatigue (rest / back-to-backs / travel)?
====================================================================

Fatigue affects outcomes, but books shade lines for it -- so the only question
that matters for betting is whether any fatigue dimension is UNDER-priced.
This tests that directly against closing lines, three ways:

  1. "Is it priced?"  -- for each back-to-back situation, actual home-win rate
     vs the market's devigged implied rate. A non-zero gap = a market bias.
  2. correlation of fatigue features with the MARKET residual (outcome - mkt).
  3. betting sims vs the closing line (fade the tired team; back the rested).

Also reports the correlation with the MODEL residual (would fatigue help the
model at all -- separate from whether it beats the market).

FINDING (2018-2023, see analysis/README.md): the market over-prices tired HOME
teams (on a back-to-back they win 41.9% but are priced at 50.0%). Fading tired
teams returned +4.3% ROI overall -- BUT it is season-unstable (2 of 5 seasons
negative) and leans on the unrepresentative COVID bubble. A real directional
bias, not yet a bankable edge. Needs more seasons of odds to confirm.

INPUTS
  --games  JSON rows {game_id,d,h,a,venue,hs,as} (or pulled live via DATABASE_URL)
  --odds   CSV from fetch_sbr_odds.py (game_id,home_ml,away_ml)
  --preds  CSV from backtest --emit-predictions (optional; for model-residual col)
  --coords venue->[lat,lon] JSON (default etl/venue_coords.json)
"""
import json, os, csv, math, argparse, statistics as st
from datetime import date

HERE=os.path.dirname(os.path.abspath(__file__))

def am_prob(ml): return (-ml)/(-ml+100) if ml<0 else 100/(ml+100)
def am_dec(ml):  return 1+100/(-ml) if ml<0 else 1+ml/100
def haversine(a,b):
    la1,lo1=a; la2,lo2=b; R=6371.0
    p1,p2=math.radians(la1),math.radians(la2); dp=math.radians(la2-la1); dl=math.radians(lo2-lo1)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))
def pdate(s): y,m,d=s.split("-"); return date(int(y),int(m),int(d))

def get_games(args):
    if args.games and os.path.exists(args.games):
        return json.load(open(args.games, encoding="utf-8"))
    url=os.environ.get("DATABASE_URL")
    if not url: raise SystemExit("need --games JSON or DATABASE_URL")
    try: import psycopg; conn=psycopg.connect(url)
    except Exception: import psycopg2; conn=psycopg2.connect(url)
    cur=conn.cursor()
    cur.execute("select game_id, to_char(game_date,'YYYY-MM-DD'), home_team_id, away_team_id, "
                "venue, home_score, away_score from games "
                "where game_type='regular' and home_score is not null")
    rows=[dict(game_id=r[0],d=r[1],h=r[2],a=r[3],venue=r[4],hs=r[5],**{"as":r[6]}) for r in cur.fetchall()]
    conn.close(); return rows

def pearson(xs,ys):
    if not xs: return 0.0
    mx=st.mean(xs);my=st.mean(ys);sx=st.pstdev(xs);sy=st.pstdev(ys)
    return (sum((x-mx)*(y-my) for x,y in zip(xs,ys))/len(xs))/(sx*sy) if sx and sy else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--games"); ap.add_argument("--odds", required=True)
    ap.add_argument("--preds"); ap.add_argument("--coords", default=os.path.join(HERE,"..","etl","venue_coords.json"))
    a=ap.parse_args()
    coords=json.load(open(a.coords, encoding="utf-8"))
    grows=get_games(a)
    odds={}
    for r in csv.DictReader(open(a.odds, encoding="utf-8")):
        odds[int(r["game_id"])]=(int(r["home_ml"]), int(r["away_ml"]))
    preds={}
    if a.preds and os.path.exists(a.preds):
        preds={int(r["game_id"]):float(r["p_home"]) for r in csv.DictReader(open(a.preds, encoding="utf-8"))}

    games=[dict(gid=int(r["game_id"]), d=pdate(r["d"]), h=r["h"], a=r["a"], venue=r["venue"],
                hw=1 if r["hs"]>r["as"] else 0) for r in grows]
    games.sort(key=lambda g:(g["d"], g["gid"]))
    last={}; recent={}; feat={}
    for g in games:
        vc=coords.get(g["venue"]); row={}
        for side,team in (("home",g["h"]),("away",g["a"])):
            pd,pv=last.get(team,(None,None))
            off=(g["d"]-pd).days-1 if pd else None
            trav=haversine(pv,vc) if (pv and vc) else None
            g4=sum(1 for x in recent.get(team,[]) if 0<=(g["d"]-x).days<=3)
            row[side]=dict(off=off, b2b=1 if off==0 else 0, trav=trav, g4=g4)
        feat[g["gid"]]=row
        for team in (g["h"],g["a"]): last[team]=(g["d"],vc); recent.setdefault(team,[]).append(g["d"])

    recs=[]
    for g in games:
        f=feat[g["gid"]]; ho,ao=f["home"],f["away"]
        if ho["off"] is None or ao["off"] is None: continue
        r=dict(gid=g["gid"], hw=g["hw"], rest_diff=ho["off"]-ao["off"],
                home_b2b=ho["b2b"], away_b2b=ao["b2b"],
                trav_diff=(ao["trav"] or 0)-(ho["trav"] or 0), g4_diff=ho["g4"]-ao["g4"])
        if g["gid"] in odds:
            hml,aml=odds[g["gid"]]; hp,ap=am_prob(hml),am_prob(aml); s=hp+ap
            r.update(mkt=hp/s, hml=hml, aml=aml)
        if g["gid"] in preds: r["pmodel"]=preds[g["gid"]]
        recs.append(r)
    mk=[r for r in recs if "mkt" in r]
    print(f"games with fatigue features: {len(recs)}   with odds: {len(mk)}\n")

    def bucket(r):
        if r["home_b2b"] and not r["away_b2b"]: return "home b2b only"
        if r["away_b2b"] and not r["home_b2b"]: return "away b2b only"
        if r["home_b2b"] and r["away_b2b"]:     return "both b2b"
        return "neither b2b"
    print("IS FATIGUE PRICED?  home-win actual vs market-implied")
    print(f"  {'situation':<16}{'n':>6}{'actual':>9}{'mkt':>9}{'gap':>8}")
    for b in ["neither b2b","away b2b only","home b2b only","both b2b"]:
        sub=[r for r in mk if bucket(r)==b]
        if sub:
            act=st.mean(r["hw"] for r in sub); imp=st.mean(r["mkt"] for r in sub)
            print(f"  {b:<16}{len(sub):>6}{act:>9.3f}{imp:>9.3f}{act-imp:>+8.3f}")

    print("\nCORRELATION with residuals")
    print(f"  {'feature':<11}{'vs MARKET':>12}{'vs MODEL':>11}")
    mres=[r["hw"]-r["mkt"] for r in mk]
    pmr=[r for r in recs if "pmodel" in r]; pres=[r["hw"]-r["pmodel"] for r in pmr]
    for fn in ["rest_diff","g4_diff","trav_diff","home_b2b","away_b2b"]:
        print(f"  {fn:<11}{pearson([r[fn] for r in mk],mres):>12.3f}{pearson([r[fn] for r in pmr],pres):>11.3f}")

    print("\nB2B FADE vs closing line (bet the rested side; break-even 0%)")
    hf=[]; af=[]
    for r in mk:
        seas=int(str(r["gid"])[:4])
        if r["away_b2b"] and not r["home_b2b"]:
            w=r["hw"]; af.append((w,(am_dec(r["hml"])-1) if w else -1,seas))
        elif r["home_b2b"] and not r["away_b2b"]:
            w=1-r["hw"]; hf.append((w,(am_dec(r["aml"])-1) if w else -1,seas))
    def rep(bets,label):
        n=len(bets); w=sum(b[0] for b in bets); pnl=sum(b[1] for b in bets)
        z=(w/n-0.5)/(0.5/n**0.5)
        print(f"  {label:<26} n={n:5d}  win%={w/n:.3f}  ROI={pnl/n:+.2%}  (~{z:.1f}sigma vs coinflip)")
    rep(af,"away tired -> bet home"); rep(hf,"home tired -> bet away"); rep(af+hf,"combined fade-tired")
    print("  combined fade-tired per season:")
    allf=af+hf
    for s in sorted({b[2] for b in allf}):
        sub=[b for b in allf if b[2]==s]; n=len(sub); w=sum(b[0] for b in sub); pnl=sum(b[1] for b in sub)
        print(f"    {s}-{s+1}  n={n:4d}  win%={w/n:.3f}  ROI={pnl/n:+.2%}")

if __name__=="__main__":
    main()
