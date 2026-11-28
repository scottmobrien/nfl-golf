"""Build mlb/data.json and mlb/seasons.json for MLB Golf.

Inputs:
  data-src/mlb/lahman/lahman_1871-2025_csv/  (Lahman Baseball Database, SABR, CC BY-SA 3.0)
  data-src/mlb/bref_2026.json                 (optional: tools/fetch_mlb_season.py, seasons Lahman hasn't added yet)

Usage: python3 tools/build_mlb.py
"""
import collections, csv, glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golf_build import ROOT, build

LAHMAN = glob.glob(os.path.join(ROOT, "data-src", "mlb", "lahman", "*", "Batting.csv"))[0].rsplit("/", 1)[0]
EXTRA = sorted(glob.glob(os.path.join(ROOT, "data-src", "mlb", "bref_*.json")))
BAT = ["G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "CS", "BB", "SO", "IBB", "HBP", "SH", "SF", "GIDP"]
PIT = ["W", "L", "G", "GS", "CG", "SHO", "SV", "IPouts", "H", "ER", "HR", "BB", "SO", "WP", "HBP"]
POS = {"G_p": "P", "G_c": "C", "G_1b": "1B", "G_2b": "2B", "G_3b": "3B", "G_ss": "SS", "G_lf": "LF",
       "G_cf": "CF", "G_rf": "RF", "G_dh": "DH"}


def n(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def rows(name):
    with open(os.path.join(LAHMAN, name + ".csv"), encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


# Traditional major leagues only; the Negro Leagues (NNL, NAL, NN2, ECL...) that Lahman added are left out.
MLB_LEAGUES = {"NL", "AL", "AA", "NA", "UA", "PL", "FL"}

# Team Tees: today's 30 franchises (Lahman franchID), with each season's team mapped through Teams.csv, so the
# Braves include Boston and Milwaukee and the Twins include the Washington Senators.
TEAM_NAMES = {
    "ANA": "Los Angeles Angels", "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves", "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox", "CHC": "Chicago Cubs", "CHW": "Chicago White Sox", "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians", "COL": "Colorado Rockies", "DET": "Detroit Tigers", "FLA": "Miami Marlins",
    "HOU": "Houston Astros", "KCR": "Kansas City Royals", "LAD": "Los Angeles Dodgers", "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins", "NYM": "New York Mets", "NYY": "New York Yankees", "OAK": "Athletics",
    "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates", "SDP": "San Diego Padres", "SEA": "Seattle Mariners",
    "SFG": "San Francisco Giants", "STL": "St. Louis Cardinals", "TBD": "Tampa Bay Rays", "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays", "WSN": "Washington Nationals",
}
BREF_FRANCH = {"ATH": "OAK", "OAK": "OAK", "LAA": "ANA", "MIA": "FLA", "TBR": "TBD"}  # Baseball-Reference -> franchID
FRANCH = {}  # (year, teamID) -> franchID
people = {}
bbref = {}
for r in rows("Teams"):
    FRANCH[(int(r["yearID"]), r["teamID"])] = r["franchID"]


def key_for(pid, franch):
    """One row per player per franchise: 'pid|FR' with _pid/_t, so Team Tees can keep a single franchise."""
    return f"{pid}|{franch}" if franch in TEAM_NAMES else f"{pid}|-"
for r in rows("People"):
    name = f"{r['nameFirst']} {r['nameLast']}".strip()
    people[r["playerID"]] = {"name": name, "pos": collections.Counter(), "years": set()}
    if r["bbrefID"]:
        bbref[r["bbrefID"]] = r["playerID"]

seasons = collections.defaultdict(lambda: {"bat": collections.defaultdict(lambda: collections.defaultdict(float)),
                                           "pitch": collections.defaultdict(lambda: collections.defaultdict(float))})
for r in rows("Batting"):  # one row per team stint; sum them
    if r["lgID"] not in MLB_LEAGUES:
        continue
    yr, pid = int(r["yearID"]), r["playerID"]
    fr = FRANCH.get((yr, r["teamID"]))
    st = seasons[yr]["bat"][key_for(pid, fr)]
    st["_pid"], st["_t"] = pid, fr if fr in TEAM_NAMES else None
    for c in BAT:
        st[c] += n(r[c])
    people[pid]["years"].add(yr)
for r in rows("Pitching"):
    if r["lgID"] not in MLB_LEAGUES:
        continue
    yr, pid = int(r["yearID"]), r["playerID"]
    fr = FRANCH.get((yr, r["teamID"]))
    st = seasons[yr]["pitch"][key_for(pid, fr)]
    st["_pid"], st["_t"] = pid, fr if fr in TEAM_NAMES else None
    for c in PIT:
        st[c] += n(r[c])
    people[pid]["years"].add(yr)
for r in rows("Appearances"):
    if r["lgID"] not in MLB_LEAGUES:
        continue
    games = {POS[c]: n(r[c]) for c in POS}
    best = max(games, key=games.get)
    if games[best]:
        people[r["playerID"]]["pos"][best] += games[best]

# Seasons Lahman hasn't added yet (Baseball-Reference season pages, already in Lahman column names).
for fn in EXTRA:
    ext = json.load(open(fn))
    yr = int(ext["year"])
    for page in ("bat", "pitch"):
        for r in ext[page]:
            pid = bbref.get(r["bbref"]) or "br:" + r["bbref"]
            if pid not in people:
                people[pid] = {"name": r["name"], "pos": collections.Counter(), "years": set()}
            people[pid]["years"].add(yr)
            if r.get("pos"):
                people[pid]["pos"][r["pos"]] += 1
            fr = BREF_FRANCH.get(r.get("team", ""), r.get("team", ""))
            st = seasons[yr][page][key_for(pid, fr)]
            st["_pid"], st["_t"] = pid, fr if fr in TEAM_NAMES else None
            for c, v in r["stats"].items():
                st[c] += v

# Derived stats.
for yr, pages in seasons.items():
    for st in pages["bat"].values():
        st["PA"] = st["AB"] + st["BB"] + st["HBP"] + st["SH"] + st["SF"]
        st["TB"] = st["H"] + st["2B"] + 2 * st["3B"] + 3 * st["HR"]
    for st in pages["pitch"].values():
        st["IP"] = st["IPouts"] / 3
        st["GR"] = st["G"] - st["GS"]  # relief appearances

B = lambda c: f"bat.{c}"
P = lambda c: f"pitch.{c}"
PA_Q = dict(q=[B("PA")], qMin=300, qLabel="plate appearances")      # x10 = 3,000 PA (Baseball-Reference)
IP_Q = dict(q=[P("IP")], qMin=100, qLabel="innings pitched")         # x10 = 1,000 IP
RP_Q = dict(q=[P("IP")], qMin=50, qLabel="innings pitched")          # x10 = 500 IP (relievers pitch far less)
# Roles over the span: a starter made half or more of his appearances as starts, a reliever 20% or fewer.
SP = dict(role=dict(num=[P("GS")], den=[P("G")], min=0.5))
RP = dict(role=dict(num=[P("GS")], den=[P("G")], max=0.2))
# The mixed-role boards these replace stay (retired) so Daily 9s up to Nov 28 replay the same course.
OLD = dict(retired=True, dailyUntil="2026-11-28")
NEW = dict(dailyFrom="2026-11-29")
SPECS = [
    dict(id="h", name="Hits", f="bat", unit="H", sum=[B("H")]),
    dict(id="hr", name="Home Runs", f="bat", unit="HR", sum=[B("HR")]),
    dict(id="rbi", name="Runs Batted In", f="bat", unit="RBI", sum=[B("RBI")]),
    dict(id="r", name="Runs Scored", f="bat", unit="R", sum=[B("R")]),
    dict(id="2b", name="Doubles", f="bat", unit="2B", sum=[B("2B")]),
    dict(id="3b", name="Triples", f="bat", unit="3B", sum=[B("3B")]),
    dict(id="tb", name="Total Bases", f="bat", unit="TB", sum=[B("TB")]),
    dict(id="bb_b", name="Walks (Batting)", f="bat", unit="BB", sum=[B("BB")]),
    dict(id="so_b", name="Strikeouts (Batting)", f="bat", unit="SO", sum=[B("SO")], note="Records incomplete before 1913", noteBefore=1913),
    dict(id="ab", name="At-Bats", f="bat", unit="AB", sum=[B("AB")]),
    dict(id="pa", name="Plate Appearances", f="bat", unit="PA", sum=[B("PA")]),
    dict(id="g_b", name="Games Played", f="bat", unit="G", sum=[B("G")]),
    dict(id="avg", name="Batting Average", f="bat", unit="AVG", dec=3, nolead=True, num=[B("H")], den=[B("AB")], **PA_Q),
    dict(id="obp", name="On-Base Percentage", f="bat", unit="OBP", dec=3, nolead=True,
         num=[B("H"), B("BB"), B("HBP")], den=[B("AB"), B("BB"), B("HBP"), B("SF")], **PA_Q),
    dict(id="slg", name="Slugging Percentage", f="bat", unit="SLG", dec=3, nolead=True, num=[B("TB")], den=[B("AB")], **PA_Q),
    dict(id="ops", name="On-Base Plus Slugging (OPS)", f="bat", unit="OPS", dec=3, nolead=True, formula="ops",
         k=dict(h=[B("H")], bb=[B("BB")], hbp=[B("HBP")], sf=[B("SF")], ab=[B("AB")], tb=[B("TB")], att=[B("AB")]), **PA_Q),
    dict(id="sb", name="Stolen Bases", f="run", unit="SB", sum=[B("SB")]),
    dict(id="w", name="Wins (Pitcher)", f="pitch", unit="W", sum=[P("W")]),
    dict(id="so_p", name="Strikeouts (Pitching)", f="pitch", unit="K", sum=[P("SO")]),
    dict(id="sv", name="Saves", f="pitch", unit="SV", sum=[P("SV")]),
    dict(id="ip", name="Innings Pitched", f="pitch", unit="IP", sum=[P("IP")]),
    dict(id="g_p", name="Games Pitched", f="pitch", unit="G", sum=[P("G")], **OLD),
    dict(id="gs_p", name="Games Started (Pitcher)", f="pitch", unit="GS", sum=[P("GS")]),
    dict(id="cg", name="Complete Games", f="pitch", unit="CG", sum=[P("CG")]),
    dict(id="sho", name="Shutouts", f="pitch", unit="SHO", sum=[P("SHO")]),
    dict(id="era", name="Earned Run Average", f="pitch", unit="ERA", dec=2, low=True, mult=9, num=[P("ER")], den=[P("IP")], **IP_Q, **OLD),
    dict(id="whip", name="WHIP (Walks + Hits per Inning)", f="pitch", unit="WHIP", dec=2, low=True,
         num=[P("H"), P("BB")], den=[P("IP")], **IP_Q, **OLD),
    dict(id="k9", name="Strikeouts per 9 Innings", f="pitch", unit="K/9", dec=1, mult=9, num=[P("SO")], den=[P("IP")], **IP_Q, **OLD),
    dict(id="l", name="Losses (Pitcher)", f="misc", unit="L", sum=[P("L")]),
    dict(id="hr_p", name="Home Runs Allowed", f="misc", unit="HR", sum=[P("HR")]),
    dict(id="bb_p", name="Walks Allowed", f="misc", unit="BB", sum=[P("BB")]),
    dict(id="wp", name="Wild Pitches", f="misc", unit="WP", sum=[P("WP")]),
    dict(id="hbp", name="Times Hit by Pitch", f="misc", unit="HBP", sum=[B("HBP")]),
    dict(id="sh", name="Sacrifice Bunts", f="misc", unit="SH", sum=[B("SH")]),
    dict(id="sf", since="1954", name="Sacrifice Flies", f="misc", unit="SF", sum=[B("SF")]),
    dict(id="ibb", since="1955", name="Intentional Walks (Batting)", f="misc", unit="IBB", sum=[B("IBB")]),
    dict(id="gidp", since="1939", name="Grounded Into Double Plays", f="misc", unit="GIDP", sum=[B("GIDP")]),
    dict(id="cs", name="Caught Stealing", f="misc", unit="CS", sum=[B("CS")], note="Records incomplete before 1951", noteBefore=1951),
    # Starters and relievers apart (added at the end so older Daily 9s keep their board order).
    dict(id="era_sp", name="Earned Run Average (Starters)", f="pitch", unit="ERA", dec=2, low=True, mult=9,
         num=[P("ER")], den=[P("IP")], **IP_Q, **SP, **NEW),
    dict(id="whip_sp", name="WHIP (Starters)", f="pitch", unit="WHIP", dec=2, low=True,
         num=[P("H"), P("BB")], den=[P("IP")], **IP_Q, **SP, **NEW),
    dict(id="k9_sp", name="Strikeouts per 9 Innings (Starters)", f="pitch", unit="K/9", dec=1, mult=9,
         num=[P("SO")], den=[P("IP")], **IP_Q, **SP, **NEW),
    dict(id="era_rp", name="Earned Run Average (Relievers)", f="pitch", unit="ERA", dec=2, low=True, mult=9,
         num=[P("ER")], den=[P("IP")], **RP_Q, **RP, **NEW),
    dict(id="whip_rp", name="WHIP (Relievers)", f="pitch", unit="WHIP", dec=2, low=True,
         num=[P("H"), P("BB")], den=[P("IP")], **RP_Q, **RP, **NEW),
    dict(id="k9_rp", name="Strikeouts per 9 Innings (Relievers)", f="pitch", unit="K/9", dec=1, mult=9,
         num=[P("SO")], den=[P("IP")], **RP_Q, **RP, **NEW),
    dict(id="gr", name="Relief Appearances", f="pitch", unit="G", sum=[P("GR")], **NEW),
]

seasons = {yr: {pg: {pid: dict(st) for pid, st in rows_.items()} for pg, rows_ in pages.items()} for yr, pages in seasons.items()}
people = {pid: p for pid, p in people.items() if p["years"]}
res = build("mlb", seasons, people, SPECS, "Lahman" + (" + Baseball-Reference" if EXTRA else ""),
            teams=sorted(TEAM_NAMES.items(), key=lambda kv: kv[1]))

# Spot checks against well-known career totals.
idx, career = res["index"], res["career"]
for who, pid, key, want in [("Barry Bonds", "bondsba01", "bat.HR", 762), ("Nolan Ryan", "ryanno01", "pitch.SO", 5714),
                            ("Pete Rose", "rosepe01", "bat.H", 4256), ("Rickey Henderson", "henderi01", "bat.SB", 1406),
                            ("Cy Young", "youngcy01", "pitch.W", 511)]:
    got = career[pid][key]
    print(f"  check {who}: {got:,.0f} (expect {want:,}) {'OK' if round(got) == want else 'MISMATCH'}")
