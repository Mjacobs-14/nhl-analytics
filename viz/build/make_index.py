"""Writes index.html for the published viz site: links to each page plus the
time the data was pulled. Usage: python make_index.py <site dir>"""
import sys, os, html
from datetime import datetime, timezone

PAGES = [
    ("matchup_lab.html", "Matchup Lab", "Two-team style-clash previews"),
    ("shot_quadrants.html", "Shot Quadrants", "Shot volume vs. points per game"),
    ("clutch.html", "Clutch or Cushion?", "Where each player's points come from by game state"),
    ("goalie_hot_hand.html", "The Hot Hand", "Goalie streakiness vs. quality"),
    ("edge_athleticism.html", "Speed & Motor", "NHL Edge skating: top speed, bursts, distance"),
    ("coach_fingerprints.html", "Coach Fingerprints", "How teams play under their coaches"),
]

site = sys.argv[1]
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
items = "\n".join(
    f'<li><a href="{f}">{html.escape(t)}</a><span>{html.escape(d)}</span></li>'
    for f, t, d in PAGES if os.path.exists(os.path.join(site, f))
)
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NHL Deep Stats</title>
<style>
:root{{--bg:#fff;--ink:#16181d;--muted:#5f6670;--line:#e3e5e8;--link:#1f5fbf}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121417;--ink:#e8eaed;--muted:#9aa1ab;--line:#2a2e34;--link:#7fb0ff}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:640px;margin:0 auto;padding:32px 16px}}
h1{{font-size:24px;margin:0 0 4px}} p{{color:var(--muted);margin:0 0 24px}}
ul{{list-style:none;padding:0;margin:0}} li{{padding:12px 0;border-top:1px solid var(--line)}}
a{{color:var(--link);font-weight:600;text-decoration:none}} a:hover{{text-decoration:underline}}
span{{display:block;color:var(--muted);font-size:14px}}
</style></head><body><main>
<h1>NHL Deep Stats</h1>
<p>Rebuilt from the database after each daily data pull. Last built {stamp}.</p>
<ul>
{items}
</ul>
</main></body></html>
"""
with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
    f.write(page)
print(f"wrote index.html ({stamp})")
