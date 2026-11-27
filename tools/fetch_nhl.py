"""Pull every NHL regular season's skater and goalie stats from the NHL stats API.

Usage: python3 tools/fetch_nhl.py [first_start_year] [last_start_year]   (default 1917-2026, i.e. 1917-18 to 2026-27)

Writes data-src/nhl/seasons.json:
  {"20232024": {"skaters": [...], "realtime": [...], "goalies": [...]}}
skaters = skater/summary (goals, assists, points, +/-, PIM, PP/SH/GW goals, shots, games),
realtime = skater/realtime (hits, blocked shots; tracked since 2005-06), goalies = goalie/summary.
The API returns 100 rows a request, so each season is paged; one request every 0.5 s. Progress is saved
after every season, so re-running resumes.
"""
import json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data-src", "nhl", "seasons.json")
BASE = "https://api.nhle.com/stats/rest/en"
ENDPOINTS = {"skaters": "skater/summary", "realtime": "skater/realtime", "goalies": "goalie/summary"}
REALTIME_FROM = 2005  # hits and blocks start in 2005-06


def get(path, season, start):
    q = urllib.parse.urlencode({
        "limit": 100, "start": start,
        "sort": json.dumps([{"property": "playerId", "direction": "ASC"}]),
        "cayenneExp": f"seasonId={season} and gameTypeId=2",
    })
    req = urllib.request.Request(f"{BASE}/{path}?{q}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 1917
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for y in range(last, first - 1, -1):
        season = f"{y}{y + 1}"
        if season in data:
            continue
        out = {}
        for key, path in ENDPOINTS.items():
            if key == "realtime" and y < REALTIME_FROM:
                continue
            rows, start = [], 0
            while True:
                page = get(path, season, start)
                rows += page["data"]
                time.sleep(0.5)
                start += 100
                if start >= page["total"] or not page["data"]:
                    break
            out[key] = rows
        if out.get("skaters") or out.get("goalies"):
            data[season] = out
            json.dump(data, open(OUT, "w"), separators=(",", ":"))
        print(f"{season}: " + ", ".join(f"{k} {len(v)}" for k, v in out.items()), flush=True)
    print(f"Done: {len(data)} seasons in {OUT}", flush=True)


if __name__ == "__main__":
    main()
