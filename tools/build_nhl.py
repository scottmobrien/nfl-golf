"""Build nhl/data.json and nhl/seasons.json for NHL Golf.

Input: data-src/nhl/seasons.json from tools/fetch_nhl.py (NHL stats API: skaters, realtime, goalies).
Seasons are keyed by the year they end (2023-24 -> 2024), so "since 2000" starts with 1999-00.

Usage: python3 tools/build_nhl.py
"""
import collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golf_build import ROOT, build

raw = json.load(open(os.path.join(ROOT, "data-src", "nhl", "seasons.json")))
FIELDS = {
    "skaters": ["gamesPlayed", "goals", "assists", "points", "plusMinus", "penaltyMinutes", "ppGoals", "ppPoints",
                "shGoals", "shPoints", "gameWinningGoals", "otGoals", "shots"],
    "realtime": ["hits", "blockedShots", "takeaways", "giveaways"],
    "goalies": ["gamesPlayed", "gamesStarted", "wins", "losses", "ties", "otLosses", "shutouts", "saves",
                "shotsAgainst", "goalsAgainst", "timeOnIce"],
}
# Team Tees: today's franchises, with old codes folded in (Nordiques -> Avalanche, Whalers -> Hurricanes, North
# Stars -> Stars, Thrashers -> Jets). A season split between teams comes combined ("CHI,EDM"), so it counts for
# neither team. Utah is its own franchise (the Coyotes' history stays with the inactive Coyotes).
TEAM_NAMES = {
    "ANA": "Anaheim Ducks", "BOS": "Boston Bruins", "BUF": "Buffalo Sabres", "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes", "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars", "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers", "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild", "MTL": "Montreal Canadiens", "NSH": "Nashville Predators",
    "NJD": "New Jersey Devils", "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins", "SJS": "San Jose Sharks", "SEA": "Seattle Kraken",
    "STL": "St. Louis Blues", "TBL": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs", "UTA": "Utah Mammoth",
    "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights", "WSH": "Washington Capitals", "WPG": "Winnipeg Jets",
}
OLD_CODES = {"AFM": "CGY", "HFD": "CAR", "QUE": "COL", "MNS": "DAL", "DCG": "DET", "DFL": "DET", "KCS": "NJD",
             "CLR": "NJD", "TSP": "TOR", "TAN": "TOR", "ATL": "WPG"}


def franchise(codes):
    if not codes or "," in codes:
        return None
    c = OLD_CODES.get(codes, codes)
    return c if c in TEAM_NAMES else None


seasons, people = {}, {}
for sid, pages in raw.items():
    yr = int(sid[4:])
    seasons[yr] = {}
    for page, rows in pages.items():
        out = {}
        for r in rows:
            pid = str(r["playerId"])
            name = r.get("skaterFullName") or r.get("goalieFullName") or ""
            p = people.setdefault(pid, {"name": name, "pos": collections.Counter(), "years": set()})
            p["years"].add(yr)
            if page != "realtime":
                p["pos"]["G" if page == "goalies" else (r.get("positionCode") or "")] += 1
            st = {f: float(r.get(f) or 0) for f in FIELDS[page]}
            st["_t"] = franchise(r.get("teamAbbrevs"))
            if page == "skaters":  # shots were only tracked from 1959-60: shooting % counts goals from those seasons
                st["goalsWithShots"] = st["goals"] if st["shots"] else 0.0
            out[pid] = st
        seasons[yr][page] = out
for p in people.values():
    p["pos"].pop("", None)

S = lambda f: f"skaters.{f}"
R = lambda f: f"realtime.{f}"
G = lambda f: f"goalies.{f}"
GP_Q = dict(q=[S("gamesPlayed")], qMin=40, qLabel="games")        # x10 = 400 games
SHOT_Q = dict(q=[S("shots")], qMin=100, qLabel="shots")           # x10 = 1,000 shots
GOALIE_Q = dict(q=[G("gamesPlayed")], qMin=25, qLabel="games in goal")  # x10 = 250 games
SPECS = [
    dict(id="goals", name="Goals", f="score", unit="G", sum=[S("goals")]),
    dict(id="assists", name="Assists", f="score", unit="A", sum=[S("assists")]),
    dict(id="points", name="Points", f="score", unit="Pts", sum=[S("points")]),
    dict(id="pp_goals", name="Power-Play Goals", f="score", unit="PPG", sum=[S("ppGoals")]),
    dict(id="pp_points", name="Power-Play Points", f="score", unit="PPP", sum=[S("ppPoints")]),
    dict(id="sh_goals", name="Shorthanded Goals", f="score", unit="SHG", sum=[S("shGoals")]),
    dict(id="gwg", name="Game-Winning Goals", f="score", unit="GWG", sum=[S("gameWinningGoals")]),
    dict(id="ppg", name="Points per Game", f="score", unit="P/GP", dec=2, num=[S("points")], den=[S("gamesPlayed")], **GP_Q),
    dict(id="gpg", name="Goals per Game", f="score", unit="G/GP", dec=2, num=[S("goals")], den=[S("gamesPlayed")], **GP_Q),
    dict(id="shooting_pct", name="Shooting Percentage", f="score", pct=True, dec=1, mult=100,
         num=[S("goalsWithShots")], den=[S("shots")], **SHOT_Q, note="Shots counted since 1959-60", noteBefore=1960),
    dict(id="games", name="Games Played (Skater)", f="skate", unit="GP", sum=[S("gamesPlayed")]),
    dict(id="plus_minus", since="1959-60", name="Plus/Minus", f="skate", unit="+/-", sum=[S("plusMinus")],
         note="Only players with a positive career total are ranked"),
    dict(id="pim", name="Penalty Minutes", f="skate", unit="PIM", sum=[S("penaltyMinutes")]),
    dict(id="shots", since="1959-60", name="Shots on Goal", f="skate", unit="S", sum=[S("shots")]),
    # Skater defensive boards (blocked shots, takeaways) and giveaways left out by choice; goaltending stays.
    dict(id="hits", since="2005-06", name="Hits", f="skate", unit="Hits", sum=[R("hits")]),
    dict(id="g_wins", name="Wins (Goalie)", f="goal", unit="W", sum=[G("wins")]),
    dict(id="g_losses", name="Losses (Goalie)", f="goal", unit="L", sum=[G("losses")]),
    dict(id="shutouts", name="Shutouts", f="goal", unit="SO", sum=[G("shutouts")]),
    dict(id="saves", name="Saves", f="goal", unit="SV", sum=[G("saves")]),
    dict(id="g_games", name="Games Played (Goalie)", f="goal", unit="GP", sum=[G("gamesPlayed")]),
    dict(id="gaa", name="Goals-Against Average", f="goal", unit="GAA", dec=2, low=True, mult=3600,
         num=[G("goalsAgainst")], den=[G("timeOnIce")], **GOALIE_Q),
    dict(id="save_pct", name="Save Percentage", f="goal", unit="SV%", dec=3, nolead=True,
         num=[G("saves")], den=[G("shotsAgainst")], **GOALIE_Q),
]

res = build("nhl", seasons, people, SPECS, "NHL stats API", teams=sorted(TEAM_NAMES.items(), key=lambda kv: kv[1]))
career = res["career"]
for who, pid, key, want in [("Wayne Gretzky", "8447400", "skaters.points", 2857), ("Gordie Howe", "8448000", "skaters.goals", 801),
                            ("Martin Brodeur", "8455710", "goalies.wins", 691), ("Martin Brodeur", "8455710", "goalies.shutouts", 125)]:
    got = career[pid][key]
    print(f"  check {who} {key}: {got:,.0f} (expect {want:,}) {'OK' if round(got) == want else 'MISMATCH'}")
