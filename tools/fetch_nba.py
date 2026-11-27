"""Pull every NBA (and 1947-49 BAA) season's player totals and advanced stats from Basketball-Reference.

Usage: python3 tools/fetch_nba.py [first_year] [last_year]   (years are season end years; default 1947-2027)

Writes data-src/nba/seasons.json:
  {year: {"totals": {"cols": [...], "rows": [[player_id, name, ...cells]]}, "advanced": {...}}}
One request every 3.6 s (Sports Reference allows 20 a minute). A traded player's combined row ("2TM")
comes before his per-team rows, so only the first row per player is kept. Progress is saved after every
season, so re-running resumes where it stopped.
"""
import html, json, os, re, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data-src", "nba", "seasons.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
GAP = 3.6
PAGES = {"totals": "totals_stats", "advanced": "advanced"}


def league(year):
    return "BAA" if year <= 1949 else "NBA"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def text(cell):
    return html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()


def parse(page, table_id):
    page = page.replace("<!--", "").replace("-->", "")  # some tables are hidden in comments
    m = re.search(r'<table[^>]*id="%s"[^>]*>.*?</table>' % re.escape(table_id), page, re.S)
    if not m:
        return None
    t = m.group(0)
    head = re.search(r"<thead>(.*?)</thead>", t, re.S).group(1)
    last = re.findall(r"<tr[^>]*>(.*?)</tr>", head, re.S)[-1]
    cols = re.findall(r'data-stat="([a-z0-9_]+)"', last)
    rows, seen = [], set()
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", t, re.S).group(1), re.S):
        link = re.search(r'href="(/players/[^"]+)"', tr)
        if not link or link.group(1) in seen:
            continue
        seen.add(link.group(1))
        cells = {k: text(v) for k, v in re.findall(r'data-stat="([a-z0-9_]+)"[^>]*>(.*?)</t[dh]>', tr, re.S)}
        name = cells.get("name_display") or cells.get("player") or ""
        rows.append([link.group(1), name.rstrip("*"), *[cells.get(c, "") for c in cols]])
    return {"cols": cols, "rows": rows}


def main():
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 1947
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 2027
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for year in range(last, first - 1, -1):
        if str(year) in data and all(p in data[str(year)] for p in PAGES):
            continue
        season = {}
        for page, table_id in PAGES.items():
            url = f"https://www.basketball-reference.com/leagues/{league(year)}_{year}_{page}.html"
            try:
                t = parse(fetch(url), table_id)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    t = None
                else:
                    print(f"Stopped at {year} {page}: HTTP {e.code}. Re-run later to resume.", flush=True)
                    return
            if t:
                season[page] = t
            print(f"{year} {page}: {len(t['rows']) if t else 'none'} players", flush=True)
            time.sleep(GAP)
        data[str(year)] = season
        json.dump(data, open(OUT, "w"), separators=(",", ":"))
    print(f"Done: {len(data)} seasons in {OUT}", flush=True)


if __name__ == "__main__":
    main()
