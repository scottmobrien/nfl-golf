"""Fetch one MLB season from Baseball-Reference, for seasons the Lahman database doesn't have yet.

Usage: python3 tools/fetch_mlb_season.py 2026

Writes data-src/mlb/bref_<year>.json with stats renamed to Lahman's column names, keyed by Baseball-Reference
player id (Lahman's People.csv maps bbrefID -> playerID). Two requests, 3.6 s apart. A traded player gets one
row per team (the combined "2TM" row is skipped), each with its team, for Team Tees. Delete the file once Lahman
adds the season.
"""
import html, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
BAT = {"b_games": "G", "b_ab": "AB", "b_r": "R", "b_h": "H", "b_doubles": "2B", "b_triples": "3B", "b_hr": "HR",
       "b_rbi": "RBI", "b_sb": "SB", "b_cs": "CS", "b_bb": "BB", "b_so": "SO", "b_ibb": "IBB", "b_hbp": "HBP",
       "b_sh": "SH", "b_sf": "SF", "b_gidp": "GIDP"}
PIT = {"p_w": "W", "p_l": "L", "p_g": "G", "p_gs": "GS", "p_cg": "CG", "p_sho": "SHO", "p_sv": "SV", "p_ip": "IP",
       "p_h": "H", "p_er": "ER", "p_hr": "HR", "p_bb": "BB", "p_so": "SO", "p_wp": "WP", "p_hbp": "HBP"}


def num(x):
    m = re.search(r"-?\d+(\.\d+)?", (x or "").replace(",", ""))
    return float(m.group()) if m else 0.0


def table(year, kind, table_id, mapping):
    req = urllib.request.Request(f"https://www.baseball-reference.com/leagues/majors/{year}-standard-{kind}.shtml",
                                 headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace").replace("<!--", "").replace("-->", "")
    t = re.search(r'<table[^>]*id="%s".*?</table>' % table_id, page, re.S).group(0)
    out, seen = [], set()
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", t, re.S).group(1), re.S):
        pid = re.search(r'data-append-csv="([^"]+)"', tr)
        if not pid:
            continue
        cells = {k: html.unescape(re.sub(r"<[^>]+>", "", v)).strip() for k, v in re.findall(r'data-stat="([a-z0-9_]+)"[^>]*>(.*?)</t[dh]>', tr, re.S)}
        team = cells.get("team_name_abbr") or cells.get("team_ID") or ""
        if re.fullmatch(r"\d+TM|TOT", team) or (pid.group(1), team) in seen:
            continue
        seen.add((pid.group(1), team))
        stats = {lah: num(cells.get(br)) for br, lah in mapping.items()}
        if "IP" in stats:  # "180.1" means 180 1/3 innings
            whole, _, thirds = cells.get("p_ip", "0").partition(".")
            stats["IPouts"] = num(whole) * 3 + num(thirds or "0")
            del stats["IP"]
        code = re.split(r"[^0-9A-Z]", (cells.get("pos") or "").lstrip("*/"))[0]
        pos = {"1": "P", "2": "C", "3": "1B", "4": "2B", "5": "3B", "6": "SS", "7": "LF", "8": "CF", "9": "RF",
               "D": "DH"}.get(code[:1], "") if kind == "batting" else "P"
        out.append({"bbref": pid.group(1), "name": cells.get("name_display", "").rstrip("*#+ "), "pos": pos, "team": team, "stats": stats})
    return out


year = sys.argv[1]
bat = table(year, "batting", "players_standard_batting", BAT)
time.sleep(3.6)
pitch = table(year, "pitching", "players_standard_pitching", PIT)
path = os.path.join(ROOT, "data-src", "mlb", f"bref_{year}.json")
json.dump({"year": int(year), "bat": bat, "pitch": pitch}, open(path, "w"), ensure_ascii=False)
print(f"{path}: {len(bat)} batters, {len(pitch)} pitchers")
