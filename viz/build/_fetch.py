"""
Shared data loader for the viz/ page builders.

Fetches from Postgres via DATABASE_URL (the same var the app uses), running the
SQL in queries.py. Results can be cached to a snapshot JSON so a page can be
rebuilt offline / reproducibly:

    python build_matchup.py ../matchup_lab.html --save-snapshot snap/matchup.json
    python build_matchup.py ../matchup_lab.html --snapshot snap/matchup.json

A query entry may be a single SQL string (-> list of rows) or a dict of named
SQL strings (-> dict of lists), which is what the matchup page uses.
"""
import os, sys, json, argparse
import queries as Q


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set — export it, or pass --snapshot PATH to "
                 "build from a cached snapshot.")
    try:
        import psycopg                      # psycopg 3
        return psycopg.connect(url)
    except ImportError:
        try:
            import psycopg2
            return psycopg2.connect(url)
        except ImportError:
            sys.exit("No Postgres driver. pip install 'psycopg[binary]'")


def _run(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    out = []
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        for k, v in d.items():                      # Decimal/date -> JSON-safe
            if hasattr(v, "quantize"):
                d[k] = float(v)
            elif hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


def load(name, argv=None):
    """Return the dataset for `name` (a key in queries.ALL)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="output HTML path")
    ap.add_argument("--snapshot", help="build from this cached JSON instead of the DB")
    ap.add_argument("--save-snapshot", help="write the fetched data here for reuse")
    args, _ = ap.parse_known_args(argv if argv is not None else sys.argv[1:])

    if args.snapshot and os.path.exists(args.snapshot):
        with open(args.snapshot, encoding="utf-8") as f:
            data = json.load(f)
    else:
        spec = Q.ALL[name]
        conn = _connect()
        if isinstance(spec, dict):
            data = {k: _run(conn, sql) for k, sql in spec.items()}
        else:
            data = _run(conn, spec)
        conn.close()
        if args.save_snapshot:
            os.makedirs(os.path.dirname(args.save_snapshot) or ".", exist_ok=True)
            with open(args.save_snapshot, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print(f"saved snapshot -> {args.save_snapshot}")

    n = (sum(len(v) for v in data.values()) if isinstance(data, dict) else len(data))
    print(f"[{name}] loaded {n} rows"
          + (f" across {len(data)} datasets" if isinstance(data, dict) else ""))
    global _ARGS
    _ARGS = args
    return data, args.out


_ARGS = None

# The builders emit a fragment (starting at <meta charset>); the committed pages
# in viz/ wrap it in a minimal HTML document. Keeping the wrapper here means a
# rebuild reproduces the committed file byte-for-byte.
_HEAD = ('<!doctype html>\n<html lang="en">\n'
         '<head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width, initial-scale=1"></head>\n'
         '<body>\n')
_TAIL = '</body>\n</html>\n'


def write_page(out, html):
    with open(out, "w", encoding="utf-8") as f:
        f.write(_HEAD + html + _TAIL)
    print(f"wrote {out}: {os.path.getsize(out)} bytes")


def load_extra(name):
    """Second dataset for a page (e.g. coach changes). When --snapshot was used,
    reads a sibling file named <name>.json in the same directory."""
    if _ARGS is not None and _ARGS.snapshot:
        sib = os.path.join(os.path.dirname(_ARGS.snapshot) or ".", f"{name}.json")
        if os.path.exists(sib):
            with open(sib, encoding="utf-8") as f:
                rows = json.load(f)
            print(f"[{name}] loaded {len(rows)} rows (snapshot)")
            return rows
        sys.exit(f"--snapshot given but sibling {sib} is missing; "
                 f"re-run with --save-snapshot against the DB first.")
    conn = _connect()
    rows = _run(conn, Q.ALL[name])
    conn.close()
    if _ARGS is not None and _ARGS.save_snapshot:
        sib = os.path.join(os.path.dirname(_ARGS.save_snapshot) or ".", f"{name}.json")
        with open(sib, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        print(f"saved snapshot -> {sib}")
    print(f"[{name}] loaded {len(rows)} rows")
    return rows
