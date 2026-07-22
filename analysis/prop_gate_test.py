"""
PROP GATE v2 — fixes the opponent factor, adds the Poisson NOISE FLOOR, and
tests blocked shots as well as shots on goal.

The noise floor is the decisive diagnostic: for a model that knows the TRUE rate
lambda, expected MAE is still E|X-lambda| for X~Poisson(lambda). If our MAE is
already at that floor, the remaining error is irreducible randomness and NO
model can do better -- meaning there is no prop edge to find.
"""
import json, os, math, statistics as st

TR=r"C:\Users\mattj\.claude\projects\C--Users-mattj-OneDrive-Desktop-NHL-Analytics\67b36769-7f32-4de0-bffd-0a3dc90c2e5a\tool-results"
rowsf=os.path.join(TR,"mcp-7830df02-086b-4a57-80cf-9fc3745390ee-execute_sql-1784684321967.txt")
saf  =os.path.join(TR,"mcp-7830df02-086b-4a57-80cf-9fc3745390ee-execute_sql-1784684335474.txt")
def load(p):
    o=json.load(open(p,encoding="utf-8"))["result"]; i=o[o.index("["):o.rindex("]")+1]
    x=json.loads(i); return x[0]["data"] if x and isinstance(x[0],dict) and "data" in x[0] else x
rows=load(rowsf); sa=load(saf)
rows.sort(key=lambda r:(r["g"], r["p"]))
sa_map={}
for r in sa: sa_map.setdefault(r["g"],{})[r["d"]]=r["sa"]
lg_sa=st.mean(r["sa"] for r in sa)

def pmf(lam,kmax=14):
    o=[];p=math.exp(-lam)
    for k in range(kmax+1): o.append(p); p=p*lam/(k+1)
    return o
def p_over(lam,line):
    m=pmf(lam); return 1.0-sum(m[:int(math.floor(line))+1])
def pois_mae(lam):           # E|X - lam| for X ~ Poisson(lam)
    return sum(pk*abs(k-lam) for k,pk in enumerate(pmf(lam)))

def run(stat, lines, label):
    tot=sum(r[stat] or 0 for r in rows); tot_t=sum(r["toi"] or 0 for r in rows)
    LG60=tot/(tot_t/3600.0); lg_toi=st.mean(r["toi"] for r in rows)
    pl={}; opp={}
    P={m:[] for m in ["naive","rate","rate+opp"]}
    fvals=[]
    K_P=6.0; MIN=10
    for r in rows:
        p,g,o,v,toi=r["p"],r["g"],r["o"],r[stat] or 0,r["toi"] or 0
        a=pl.get(p); oa=opp.get(o)
        if a and a["n"]>=MIN and toi>0:
            naive=a["v"]/a["n"]
            r60=(a["v"]+K_P*LG60*(lg_toi/3600.0))/((a["toi"]+K_P*lg_toi)/3600.0)
            rate=r60*((a["toi"]/a["n"])/3600.0)
            f=1.0
            if oa and oa[0]>=5:
                f=(oa[1]/oa[0])/lg_sa; f=max(0.85,min(1.15,f)); fvals.append(f)
            P["naive"].append((max(naive,0.05),v))
            P["rate"].append((max(rate,0.05),v))
            P["rate+opp"].append((max(rate*f,0.05),v))
        if a is None: a=dict(n=0,v=0,toi=0); pl[p]=a
        a["n"]+=1; a["v"]+=v; a["toi"]+=toi
        for d,x in sa_map.get(g,{}).items():
            e=opp.get(d)
            if e is None: opp[d]=[1,x]
            else: e[0]+=1; e[1]+=x
    n=len(P["naive"])
    print(f"\n=== {label} ===  scored {n} player-games   league {stat}/60={LG60:.2f}")
    if fvals:
        print(f"  opponent factor: n={len(fvals)}  mean={st.mean(fvals):.4f}  "
              f"min={min(fvals):.3f} max={max(fvals):.3f}  (1.0 = no adjustment)")
    else:
        print("  opponent factor NEVER APPLIED (bug)")
    hdr=f"  {'model':<10}{'MAE':>8}{'RMSE':>8}"+"".join(f"{('LL@'+str(L)):>9}" for L in lines)
    print(hdr)
    for m in ["naive","rate","rate+opp"]:
        d=P[m]
        mae=sum(abs(x-y) for x,y in d)/len(d)
        rmse=(sum((x-y)**2 for x,y in d)/len(d))**0.5
        line=f"  {m:<10}{mae:>8.4f}{rmse:>8.4f}"
        for L in lines:
            ll=0.0
            for lam,act in d:
                q=min(max(p_over(lam,L),1e-9),1-1e-9); o=1 if act>L else 0
                ll+=-(o*math.log(q)+(1-o)*math.log(1-q))
            line+=f"{ll/len(d):>9.4f}"
        print(line)
    # noise floor using the best model's lambdas
    floor=sum(pois_mae(lam) for lam,_ in P["rate"])/n
    best=min(sum(abs(x-y) for x,y in P[m])/n for m in P)
    print(f"  Poisson NOISE FLOOR (MAE a perfect model still has): {floor:.4f}")
    print(f"  best model MAE {best:.4f}  ->  headroom above floor: {best-floor:+.4f} "
          f"({100*(best-floor)/floor:+.1f}%)")
    for L in lines:
        base=sum(1 for _,a in P["naive"] if a>L)/n
        print(f"    base over-rate @ {L}: {base:.3f}")

run("sh",[1.5,2.5,3.5],"SHOTS ON GOAL")
run("bl",[0.5,1.5,2.5],"BLOCKED SHOTS")
