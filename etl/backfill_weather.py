"""
Game-Day Weather ETL
====================
Stamps daily weather (mean temp, precipitation, snowfall) onto every
game, using the venue's location. Sources, both free and key-less:

  - Coordinates: built-in map of NHL arenas, falling back to the
    Open-Meteo geocoder for neutral-site / international venues.
    Resolved coords are cached in etl/venue_coords.json so reruns
    (and code review) don't re-geocode.
  - Weather: Open-Meteo historical archive, one request per venue
    covering that venue's whole game-date span.

NHL games are indoors — this is attendance/curiosity data, except for
the outdoor games where it's the real thing.

SETUP: run sql/011_game_weather.sql first.

USAGE:
    python backfill_weather.py            # all games missing weather
    python backfill_weather.py --force    # re-stamp everything
"""

import os
import sys
import json
import time
import argparse
from collections import defaultdict
from pathlib import Path

import requests
from supabase import create_client

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
COORDS_CACHE = Path(__file__).with_name("venue_coords.json")

# The 32 current arenas plus common renames; everything else geocodes.
KNOWN_VENUES = {
    "Amerant Bank Arena": (26.1585, -80.3255), "American Airlines Center": (32.7905, -96.8103),
    "Ball Arena": (39.7487, -105.0077), "Bell Centre": (45.4961, -73.5693),
    "Benchmark International Arena": (27.9427, -82.4518), "Bridgestone Arena": (36.1592, -86.7785),
    "Canada Life Centre": (49.8928, -97.1436), "Canadian Tire Centre": (45.2969, -75.9272),
    "Capital One Arena": (38.8981, -77.0209), "Climate Pledge Arena": (47.6221, -122.3540),
    "Crypto.com Arena": (34.0430, -118.2673), "Delta Center": (40.7683, -111.9011),
    "Enterprise Center": (38.6266, -90.2026), "Honda Center": (33.8078, -117.8766),
    "KeyBank Center": (42.8750, -78.8765), "Lenovo Center": (35.8033, -78.7219),
    "Little Caesars Arena": (42.3411, -83.0553), "Madison Square Garden": (40.7505, -73.9934),
    "Nationwide Arena": (39.9694, -83.0061), "PNC Arena": (35.8033, -78.7219),
    "PPG Paints Arena": (40.4395, -79.9892), "Prudential Center": (40.7336, -74.1710),
    "Rogers Arena": (49.2778, -123.1089), "Rogers Place": (53.5469, -113.4979),
    "SAP Center at San Jose": (37.3327, -121.9012), "Scotiabank Arena": (43.6435, -79.3791),
    "Scotiabank Saddledome": (51.0374, -114.0519), "T-Mobile Arena": (36.1029, -115.1784),
    "TD Garden": (42.3662, -71.0621), "UBS Arena": (40.7128, -73.5904),
    "United Center": (41.8807, -87.6742), "Wells Fargo Center": (39.9012, -75.1720),
    "Xcel Energy Center": (44.9447, -93.1013), "Grand Casino Arena": (44.9447, -93.1013),
    "FLA Live Arena": (26.1585, -80.3255), "BB&T Center": (26.1585, -80.3255),
    "Amalie Arena": (27.9427, -82.4518), "Vivint Arena": (40.7683, -111.9011),
    "Staples Center": (34.0430, -118.2673), "Gila River Arena": (33.5319, -112.2611),
    "Mullett Arena": (33.4242, -111.9281), "Bell MTS Place": (49.8928, -97.1436),
    # Name variants the API uses
    "Centre Bell": (45.4961, -73.5693), "STAPLES Center": (34.0430, -118.2673),
    "Pepsi Center": (39.7487, -105.0077), "Xfinity Mobile Arena": (39.9012, -75.1720),
    "Barclays Center": (40.6826, -73.9754), "NYCB Live/Nassau Coliseum": (40.7231, -73.5906),
    "Nassau Veterans Memorial Coliseum": (40.7231, -73.5906), "Nassau Coliseum": (40.7231, -73.5906),
    "SAP Center": (37.3327, -121.9012), "Paycom Center": (35.4634, -97.5151),
    # International & outdoor
    "Milano Santagiulia Ice Hockey Arena": (45.4408, 9.2426), "Fiera Milano Rho": (45.5203, 9.0805),
    "Avicii Arena": (59.2935, 18.0835), "Ericsson Globe": (59.2935, 18.0835),
    "O2 Czech Republic": (50.1046, 14.4939), "O2 Arena": (50.1046, 14.4939),
    "Nokia Arena": (61.4934, 23.7743), "Hartwall Arena": (60.2055, 24.9291),
    "Rod Laver Arena": (-37.8215, 144.9785), "PostFinance Arena": (46.9424, 7.4638),
    "Mercedes-Benz Arena": (52.5065, 13.4436), "Uber Arena": (52.5065, 13.4436),
    "MetLife Stadium": (40.8135, -74.0745), "Edgewood Tahoe Resort": (38.9670, -119.9407),
    "Cotton Bowl": (32.7797, -96.7601), "Wrigley Field": (41.9484, -87.6553),
    "Ohio Stadium": (40.0017, -83.0197), "Commonwealth Stadium": (53.5599, -113.4767),
    "Tim Hortons Field": (43.2521, -79.8300), "Carter-Finley Stadium": (35.8005, -78.7192),
    "Truist Field": (35.2285, -80.8481), "Raymond James Stadium": (27.9759, -82.5033),
}


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL / SUPABASE_KEY environment variables.")
    return create_client(url, key)


def fetch_json(url, params, retries=5):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
        except requests.exceptions.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def resolve_coords(venue, cache):
    # KNOWN_VENUES wins over the cache so newly added aliases aren't
    # shadowed by a cached geocoder miss from an earlier run.
    if venue in KNOWN_VENUES:
        cache[venue] = KNOWN_VENUES[venue]
        return cache[venue]
    if venue in cache:
        return cache[venue]
    data = fetch_json(GEOCODE_URL, {"name": venue, "count": 1})
    results = (data or {}).get("results") or []
    if results:
        cache[venue] = (results[0]["latitude"], results[0]["longitude"])
    else:
        cache[venue] = None  # cache the miss so we don't retry every run
    time.sleep(0.5)
    return cache[venue]


def main():
    parser = argparse.ArgumentParser(description="Backfill game-day weather.")
    parser.add_argument("--force", action="store_true", help="Re-stamp games that already have weather")
    args = parser.parse_args()

    sb = get_supabase_client()

    games = []
    page_size = 1000
    offset = 0
    while True:
        q = sb.table("games").select("game_id, game_date, season, venue, temp_c, humidity_pct")
        q = q.range(offset, offset + page_size - 1)
        rows = q.execute().data
        if not rows:
            break
        games.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    if not args.force:
        games = [g for g in games if g["temp_c"] is None or g["humidity_pct"] is None]
    games = [g for g in games if g.get("venue") and g.get("game_date")]
    print(f"Stamping weather on {len(games)} games.")

    by_venue = defaultdict(list)
    for g in games:
        by_venue[g["venue"]].append(g)

    cache = json.loads(COORDS_CACHE.read_text()) if COORDS_CACHE.exists() else {}
    cache = {k: tuple(v) if v else None for k, v in cache.items()}

    stamped = 0
    skipped_venues = []
    for venue, vgames in sorted(by_venue.items(), key=lambda kv: -len(kv[1])):
        coords = resolve_coords(venue, cache)
        if not coords:
            skipped_venues.append(venue)
            continue

        dates = sorted(g["game_date"] for g in vgames)
        data = fetch_json(ARCHIVE_URL, {
            "latitude": coords[0], "longitude": coords[1],
            "start_date": dates[0], "end_date": dates[-1],
            "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum,relative_humidity_2m_mean",
            "timezone": "auto",
        })
        daily = (data or {}).get("daily") or {}
        by_date = {
            d: (t, p, s, h)
            for d, t, p, s, h in zip(
                daily.get("time", []),
                daily.get("temperature_2m_mean", []),
                daily.get("precipitation_sum", []),
                daily.get("snowfall_sum", []),
                daily.get("relative_humidity_2m_mean", []),
            )
        }
        if not by_date:
            skipped_venues.append(venue)
            continue

        patches = []
        for g in vgames:
            w = by_date.get(g["game_date"])
            if not w or w[0] is None:
                continue
            patches.append({
                "game_id": g["game_id"], "game_date": g["game_date"], "season": g["season"],
                "temp_c": w[0], "precip_mm": w[1], "snowfall_cm": w[2], "humidity_pct": w[3],
            })
        if patches:
            sb.table("games").upsert(patches, on_conflict="game_id").execute()
            stamped += len(patches)
        print(f"  {venue}: {len(patches)}/{len(vgames)} games stamped")
        time.sleep(0.3)

    COORDS_CACHE.write_text(json.dumps({k: list(v) if v else None for k, v in cache.items()}, indent=1))
    if skipped_venues:
        print(f"  ! No coords/weather for {len(skipped_venues)} venue(s): {', '.join(skipped_venues[:8])}...")
    print(f"\nDone. Weather stamped on {stamped} games.")


if __name__ == "__main__":
    main()
