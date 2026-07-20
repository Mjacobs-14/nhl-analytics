"""
Fetch historical NHL closing moneylines from Sportsbook Reviews Online and map
them onto our NHL gamePk, producing an odds CSV for score_vs_odds.py.

Source: sportsbookreviewsonline.com free archives. Coverage 2018-19 .. 2022-23
(the archive stops there and won't be updated). Two rows per game (visitor then
home); we take each side's closing moneyline ("Close" column). Playoff rows are
kept in the source but simply won't match a regular-season gamePk, so they drop.

Join: (game_date, home_abbr, away_abbr) -> game_id. The date/team map comes from
our DB (DATABASE_URL) or an offline --game-map JSON (rows of {game_id,d,h,a}).

USAGE
    python fetch_sbr_odds.py --out odds.csv                    # live DB for the map
    python fetch_sbr_odds.py --out odds.csv --game-map map.json
    python fetch_sbr_odds.py --out odds.csv --seasons 2018-19,2019-20
"""
import re, os, sys, csv, json, argparse, urllib.request

# SBR page slug -> our season code and its calendar start year.
SEASONS = {
    "2018-19": (20182019, 2018),
    "2019-20": (20192020, 2019),
    "2021":    (20202021, 2020),   # COVID season, played Jan-May 2021
    "2021-22": (20212022, 2021),
    "2022-23": (20222023, 2022),
}
BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-"

TEAM = {  # SBR name (spaces stripped) -> our abbreviation
    "Anaheim":"ANA","Arizona":"ARI","Boston":"BOS","Buffalo":"BUF","Carolina":"CAR",
    "Columbus":"CBJ","Calgary":"CGY","Chicago":"CHI","Colorado":"COL","Dallas":"DAL",
    "Detroit":"DET","Edmonton":"EDM","Florida":"FLA","LosAngeles":"LAK","Minnesota":"MIN",
    "Montreal":"MTL","NewJersey":"NJD","Nashville":"NSH","NYIslanders":"NYI","NYRangers":"NYR",
    "Ottawa":"OTT","Philadelphia":"PHI","Pittsburgh":"PIT","Seattle":"SEA","SanJose":"SJS",
    "St.Louis":"STL","TampaBay":"TBL","Toronto":"TOR","Vancouver":"VAN","Vegas":"VGK",
    "Winnipeg":"WPG","Washington":"WSH",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def fetch(slug):
    req = urllib.request.Request(BASE+slug, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

def parse_rows(html):
    """Data rows only: >=10 <td> cells with the V/H flag in column 2."""
    out=[]
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S|re.I):
        cells=[re.sub(r"<[^>]+>","",c).replace("&nbsp;"," ").strip()
               for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S|re.I)]
        if len(cells)>=10 and cells[2] in ("V","H"):
            out.append(cells)
    return out

def to_date(mmdd, start_year):
    mmdd=mmdd.strip()
    if not mmdd.isdigit(): return None
    v=int(mmdd); mm=v//100; dd=v%100
    if not (1<=mm<=12 and 1<=dd<=31): return None
    yr = start_year if mm>=10 else start_year+1   # Oct-Dec = start year; Jan-Jun = next
    return f"{yr:04d}-{mm:02d}-{dd:02d}"

def ml(x):
    x=x.strip().replace("+","")
    try: return int(x)
    except ValueError: return None

def games_from(rows, start_year):
    """Pair consecutive V,H rows -> (date, away_abbr, home_abbr, away_ml, home_ml)."""
    out=[]; i=0
    while i+1 < len(rows):
        v,h=rows[i],rows[i+1]
        if v[2]!="V" or h[2]!="H": i+=1; continue
        d=to_date(v[0], start_year)
        av=TEAM.get(v[3].replace(" ","")); hm=TEAM.get(h[3].replace(" ",""))
        aml=ml(v[9]); hml=ml(h[9])
        if d and av and hm and aml is not None and hml is not None:
            out.append((d, av, hm, aml, hml))
        i+=2
    return out

def load_game_map(args):
    """(date, home_abbr, away_abbr) -> game_id."""
    rows=None
    if args.game_map and os.path.exists(args.game_map):
        rows=json.load(open(args.game_map, encoding="utf-8"))
    elif os.environ.get("DATABASE_URL"):
        url=os.environ["DATABASE_URL"]
        try: import psycopg; conn=psycopg.connect(url)
        except Exception:
            import psycopg2; conn=psycopg2.connect(url)
        cur=conn.cursor()
        cur.execute("select game_id, to_char(game_date,'YYYY-MM-DD'), home_team_id, away_team_id "
                    "from games where game_type='regular' and home_score is not null")
        rows=[dict(game_id=r[0], d=r[1], h=r[2], a=r[3]) for r in cur.fetchall()]
        conn.close()
    else:
        sys.exit("Need DATABASE_URL or --game-map for the date/team -> game_id join.")
    return {(r["d"], r["h"], r["a"]): r["game_id"] for r in rows}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--game-map", help="offline JSON: rows of {game_id,d,h,a}")
    ap.add_argument("--seasons", help="comma list of SBR slugs (default all)")
    a=ap.parse_args()
    gmap=load_game_map(a)
    want=a.seasons.split(",") if a.seasons else list(SEASONS)
    matched=[]; total=0; unmatched=0
    for slug in want:
        if slug not in SEASONS: sys.exit(f"unknown season {slug}; known: {list(SEASONS)}")
        _, start_year = SEASONS[slug]
        gs=games_from(parse_rows(fetch(slug)), start_year)
        m=0
        for d,av,hm,aml,hml in gs:
            gid=gmap.get((d,hm,av))
            if gid is None: unmatched+=1; continue
            matched.append((gid, hml, aml)); m+=1
        total+=len(gs)
        print(f"  {slug:<8} parsed {len(gs):4d} games, matched {m:4d} to gamePk")
    with open(a.out,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["game_id","home_ml","away_ml"]); w.writerows(matched)
    print(f"\nwrote {len(matched)} games -> {a.out}  "
          f"(of {total} parsed; {unmatched} unmatched = playoffs / date-team misses)")

if __name__=="__main__":
    main()
