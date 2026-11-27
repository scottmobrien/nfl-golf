"""Build nba/data.json and nba/seasons.json for NBA Golf.

Input: data-src/nba/seasons.json from tools/fetch_nba.py (Basketball-Reference season totals + advanced,
NBA and its 1946-49 BAA predecessor only; no ABA). Seasons are keyed by the year they end (2023-24 -> 2024).

Usage: python3 tools/build_nba.py
"""
import collections, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golf_build import ROOT, build

raw = json.load(open(os.path.join(ROOT, "data-src", "nba", "seasons.json")))
FIELDS = {
    "totals": ["games", "games_started", "mp", "fg", "fga", "fg3", "fg3a", "ft", "fta", "orb", "drb", "trb",
               "ast", "stl", "blk", "tov", "pf", "pts", "tpl_dbl"],
    "advanced": ["mp", "per", "ows", "dws", "ws", "bpm", "vorp"],
}


def num(x):
    m = re.search(r"-?\d+(\.\d+)?", (x or "").replace(",", ""))
    return float(m.group()) if m else 0.0


seasons, people = {}, {}
for y, pages in raw.items():
    yr = int(y)
    seasons[yr] = {}
    for page, t in pages.items():
        idx = {c: i for i, c in enumerate(t["cols"])}
        out = {}
        for r in t["rows"]:
            pid, name, cells = r[0], r[1], r[2:]
            p = people.setdefault(pid, {"name": name, "pos": collections.Counter(), "years": set()})
            p["years"].add(yr)
            if page == "totals" and "pos" in idx and cells[idx["pos"]]:
                p["pos"][cells[idx["pos"]].split("-")[0]] += 1
            st = {f: num(cells[idx[f]]) for f in FIELDS[page] if f in idx}
            if page == "totals":
                # Per-game averages only count games from seasons that tracked the stat (rebounds from 1950-51,
                # minutes 1951-52, steals and blocks 1973-74), so straddling careers aren't diluted.
                for stat in ("trb", "mp", "stl", "blk"):
                    st[f"games_{stat}"] = st.get("games", 0) if stat in idx else 0
            if page == "advanced":  # minute-weighted, so career PER/BPM = sum(stat x minutes) / sum(minutes)
                st["per_x_mp"] = st.get("per", 0) * st.get("mp", 0)
                st["bpm_x_mp"] = st.get("bpm", 0) * st.get("mp", 0)
            out[pid] = st
        seasons[yr][page] = out

T = lambda f: f"totals.{f}"
A = lambda f: f"advanced.{f}"
GP_Q = dict(q=[T("games")], qMin=40, qLabel="games")                    # x10 = 400 games (Basketball-Reference)
MIN_Q = dict(q=[A("mp")], qMin=1000, qLabel="minutes")                   # x10 = 10,000 minutes
SPECS = [
    dict(id="pts", name="Points", f="score", unit="Pts", sum=[T("pts")]),
    dict(id="fg", name="Field Goals Made", f="score", unit="FG", sum=[T("fg")]),
    dict(id="fga", name="Field Goal Attempts", f="score", unit="FGA", sum=[T("fga")]),
    dict(id="fg3", name="3-Pointers Made", f="score", unit="3P", sum=[T("fg3")]),
    dict(id="fg3a", name="3-Point Attempts", f="score", unit="3PA", sum=[T("fg3a")]),
    dict(id="ft", name="Free Throws Made", f="score", unit="FT", sum=[T("ft")]),
    dict(id="fta", name="Free Throw Attempts", f="score", unit="FTA", sum=[T("fta")]),
    dict(id="ppg", name="Points per Game", f="score", unit="PPG", dec=1, num=[T("pts")], den=[T("games")], **GP_Q),
    dict(id="fg_pct", name="Field Goal %", f="score", pct=True, dec=1, mult=100, num=[T("fg")], den=[T("fga")],
         q=[T("fg")], qMin=200, qLabel="field goals made"),
    dict(id="fg3_pct", name="3-Point %", f="score", pct=True, dec=1, mult=100, num=[T("fg3")], den=[T("fg3a")],
         q=[T("fg3")], qMin=25, qLabel="3-pointers made"),
    dict(id="ft_pct", name="Free Throw %", f="score", pct=True, dec=1, mult=100, num=[T("ft")], den=[T("fta")],
         q=[T("ft")], qMin=120, qLabel="free throws made"),
    dict(id="trb", name="Total Rebounds", f="reb", unit="Reb", sum=[T("trb")]),
    dict(id="orb", name="Offensive Rebounds", f="reb", unit="ORB", sum=[T("orb")]),
    dict(id="drb", name="Defensive Rebounds", f="reb", unit="DRB", sum=[T("drb")]),
    dict(id="rpg", name="Rebounds per Game", f="reb", unit="RPG", dec=1, num=[T("trb")], den=[T("games_trb")], **GP_Q),
    dict(id="ast", name="Assists", f="play", unit="Ast", sum=[T("ast")]),
    dict(id="apg", name="Assists per Game", f="play", unit="APG", dec=1, num=[T("ast")], den=[T("games")], **GP_Q),
    dict(id="tov", name="Turnovers", f="play", unit="TOV", sum=[T("tov")]),
    dict(id="tpl_dbl", name="Triple-Doubles", f="play", unit="TD3", sum=[T("tpl_dbl")]),
    dict(id="stl", name="Steals", f="def", unit="Stl", sum=[T("stl")]),
    dict(id="blk", name="Blocks", f="def", unit="Blk", sum=[T("blk")]),
    dict(id="spg", name="Steals per Game", f="def", unit="SPG", dec=2, num=[T("stl")], den=[T("games_stl")], **GP_Q),
    dict(id="bpg", name="Blocks per Game", f="def", unit="BPG", dec=2, num=[T("blk")], den=[T("games_blk")], **GP_Q),
    dict(id="games", name="Games Played", f="gen", unit="G", sum=[T("games")]),
    dict(id="gs", name="Games Started", f="gen", unit="GS", sum=[T("games_started")]),
    dict(id="mp", name="Minutes Played", f="gen", unit="Min", sum=[T("mp")]),
    dict(id="mpg", name="Minutes per Game", f="gen", unit="MPG", dec=1, num=[T("mp")], den=[T("games_mp")], **GP_Q),
    dict(id="pf", name="Personal Fouls", f="gen", unit="PF", sum=[T("pf")]),
    dict(id="ws", name="Win Shares", f="adv", unit="WS", dec=1, sum=[A("ws")]),
    dict(id="ows", name="Offensive Win Shares", f="adv", unit="OWS", dec=1, sum=[A("ows")]),
    dict(id="dws", name="Defensive Win Shares", f="adv", unit="DWS", dec=1, sum=[A("dws")]),
    dict(id="vorp", name="Value Over Replacement (VORP)", f="adv", unit="VORP", dec=1, sum=[A("vorp")]),
    dict(id="per", name="Player Efficiency Rating (PER)", f="adv", unit="PER", dec=1, num=[A("per_x_mp")], den=[A("mp")], **MIN_Q),
    dict(id="bpm", name="Box Plus/Minus (BPM)", f="adv", unit="BPM", dec=1, num=[A("bpm_x_mp")], den=[A("mp")], **MIN_Q),
]

res = build("nba", seasons, people, SPECS, "Basketball-Reference")
career = res["career"]
for who, pid, key, want in [("Kareem Abdul-Jabbar", "/players/a/abdulka01.html", "totals.pts", 38387),
                            ("Wilt Chamberlain", "/players/c/chambwi01.html", "totals.trb", 23924),
                            ("John Stockton", "/players/s/stockjo01.html", "totals.ast", 15806),
                            ("Hakeem Olajuwon", "/players/o/olajuha01.html", "totals.blk", 3830),
                            ("LeBron James", "/players/j/jamesle01.html", "totals.pts", None)]:
    got = career[pid][key]
    print(f"  check {who} {key}: {got:,.0f}" + (f" (expect {want:,}) {'OK' if round(got) == want else 'MISMATCH'}" if want else " (still active)"))
