"""Build data.json for NFL Golf.

Usage: python3 tools/build_data.py

Inputs (in data-src/):
  pfr_all_career_leaders.json  — from tools/pfr-export-all.js (every board on PFR's /leaders/ index)
  pfr_qb_teams_beaten.json     — from tools/pfr-qbwins-export.js (/friv/qb-wins.htm)

Each board keeps PFR's own row order (so "lower is better" stats like INT% rank correctly);
tied values share a rank. Boards that are too short or too tie-heavy to play well are skipped.
"""
import collections, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data-src")

MIN_ROWS = 100        # skip boards shorter than this
MAX_TIE_SHARE = 0.20  # skip boards where one tied value covers more than this share of rows
NON_STAT = {"rank", "player", "years", "team", "link"}

# Different players who share a name -> nicer distinct display names (others get "(years)").
RENAME = {
    "/players/m/mattcl00.htm": "Clay Matthews Jr.",
    "/players/m/mattcl99.htm": "Clay Matthews III",
    "/players/w/winske00.htm": "Kellen Winslow Sr.",
    "/players/w/winske01.htm": "Kellen Winslow Jr.",
}


def num(s):
    m = re.search(r"-?\d+(\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


# Boards where only quarterbacks appear, so a hole like "Passes Intercepted" can't be
# mistaken for defensive interceptions.
QB_ONLY = {"pick_six", "gwd", "comebacks"}
NOT_QB = {"pass_defended"}  # a defensive stat despite the pass_ prefix


# Each board belongs to one family; game modes and Red Tees checkboxes choose families.
#   off = offense, def = defense, kick = placekicking (incl. points scored, which kickers own),
#   punt = punting, ret = kick/punt returns, gen = games, starts, AV and award shares.
DEF = {"def_int", "def_int_yds", "tackles_solo", "tackles_combined", "tackles_loss", "fumbles_forced",
       "fumbles_rec", "fumbles_rec_yds", "pass_defended", "sacks"}
KICK = {"xpm", "xpa", "xp_perc", "fgm", "fga", "fg_perc", "scoring"}
PUNT = {"punt", "punt_yds", "punt_yds_per_punt"}
GEN = {"g", "gs", "av", "career_av", "apmvp_share", "apopoy_share", "apdpoy_share"}


def family(key):
    if key in DEF: return "def"
    if key in KICK: return "kick"
    if key in PUNT: return "punt"
    if key in GEN: return "gen"
    if key.startswith(("kick_ret", "punt_ret")) or key in {"ret", "ret_yds"}: return "ret"
    return "off"


# Fumbles Recovered counts every player, and QBs recovering their own fumbles fill the top of it. A
# defenders-only board fails the tie rule (all-time: 105 deep, 24% tied at 17; since 2000: 90 tied at 7,
# 125 at 6), so it stays all-players with this note on the hole.
FR_NOTE = "Includes offensive players (QBs often recover their own fumbles)"


def norm_pos(text):
    pos = re.split(r"[^A-Za-z]", text or "")[0].upper()
    return re.sub(r"^[LR](DE|DT|CB|OLB|ILB|MLB|LB|G|T|DH)$", r"\1", pos)


# PFR's qualifying minimums for career rate boards (checked against the listed players' career totals).
CAREER_NOTES = {
    **{k: "Minimum 1,500 pass attempts" for k in (
        "pass_rating", "pass_yds_per_att", "pass_yds_per_cmp", "pass_adj_yds_per_att", "pass_net_yds_per_att",
        "pass_adj_net_yds_per_att", "pass_cmp_perc", "pass_int_perc", "pass_td_perc", "pass_sacked_perc",
        "pass_yds_per_g", "pass_att_per_g", "pass_cmp_per_g")},
    "rush_yds_per_att": "Minimum 750 rushing attempts",
    "rush_yds_per_g": "Minimum 32 games",
    "rec_yds_per_g": "Minimum 32 games",
    "rec_yds_per_rec": "Minimum 200 receptions",
    "rec_yds_per_tgt": "Minimum 200 receptions",
    "yds_per_touch": "Minimum 750 touches",
    "fg_perc": "Minimum 100 field goal attempts",
    "xp_perc": "Minimum 100 extra point attempts",
    "punt_yds_per_punt": "Minimum 250 punts",
    "kick_ret_yds_per_ret": "Minimum 75 kick returns",
    "punt_ret_yds_per_ret": "Minimum 75 punt returns",
    "fumbles_rec": FR_NOTE,
}


def board_name(key, title):
    t = re.sub(r"^NFL ", "", title)
    t = re.sub(r" Career Leaders", "", t)
    t = re.sub(r"^Games\b(?! Started)", "Games Played", t)  # plain "Games" read as unclear
    t = t if t.startswith("Most ") else "Career " + t
    is_qb = (key.startswith("pass_") and key not in NOT_QB) or key in QB_ONLY
    if is_qb and "QB" not in t:
        m = re.match(r"(.*) \((.*)\)$", t)  # "X (since 1960)" -> "X (QB, since 1960)"
        t = f"{m.group(1)} (QB, {m.group(2)})" if m else f"{t} (QB)"
    return t


def display(text, unit):
    return text if text.endswith("%") else f"{text} {unit}"


pfr = json.load(open(os.path.join(SRC, "pfr_all_career_leaders.json")))
meta = pfr.pop("_meta")
boards, skipped = [], []
# Boards left out by choice: Approximate Value (an opaque PFR metric) and Games Played (every position,
# so it's mostly kickers and punters), Games Started (every position).
CUT = {"av", "career_av", "g", "gs"}

for key, b in pfr.items():
    if key in CUT:
        continue
    stat = next(h for h in b["headers"] if h["stat"] not in NON_STAT)
    rows, seen = [], set()
    for r in b["rows"]:
        pid = r["id"].lower()
        text = r["cells"].get(stat["stat"], "")
        if pid in seen or num(text) is None:
            continue
        seen.add(pid)
        rows.append({"id": pid, "name": r["name"], "years": r["cells"].get("years", ""),
                     "value": num(text), "disp": display(text, stat["text"])})
    biggest_tie = max(collections.Counter(r["value"] for r in rows).values()) if rows else 0
    if len(rows) < MIN_ROWS or biggest_tie > MAX_TIE_SHARE * len(rows):
        skipped.append(f"{key} ({len(rows)} rows, biggest tie {biggest_tie})")
        continue
    boards.append({"id": key, "name": board_name(key, b["title"]), "rows": rows})

qb = json.load(open(os.path.join(SRC, "pfr_qb_teams_beaten.json")))
boards.append({"id": "teams_beaten", "name": "Most Different Teams Beaten (QB)", "rows": [
    {"id": r["_playerId"].lower(), "name": r["player"], "years": "", "value": float(r["teams_beat"]),
     "disp": f"{r['teams_beat']} teams"}
    for r in qb["tables"][0]["rows"] if r.get("teams_beat")
]})

# ---------- season-by-season stats (for Members Tees / Red Tees spans) ----------
# data-src/pfr_seasons_*.json from tools/pfr-export-seasons.js: {year: {page: {cols, rows: [[id, name, ...cells]]}}}
seasons_raw = {}
for fn in sorted(glob.glob(os.path.join(SRC, "pfr_seasons_[0-9]*-[0-9]*.json"))):  # NFL chunks, e.g. 2026-2017
    seasons_raw.update({int(y): v for y, v in json.load(open(fn)).items()})
# AFL (1960-69) and AAFC (1946-49) seasons from tools/pfr-export-afl-aafc.js, keyed "1965_AFL": fold each
# into its year so spans count every major-league season, as PFR's career totals do.
other = os.path.join(SRC, "pfr_seasons_afl_aafc.json")
if os.path.exists(other):
    for key, pages in json.load(open(other)).items():
        yr = int(key.split("_")[0])
        for page, t in pages.items():
            base = seasons_raw.setdefault(yr, {}).setdefault(page, {"cols": t["cols"], "rows": []})
            at = {c: i for i, c in enumerate(t["cols"])}
            # Re-order this league's cells into the NFL table's column order (blank where a stat is missing).
            base["rows"] += [r[:2] + [r[2 + at[c]] if c in at else "" for c in base["cols"]] for r in t["rows"]]
season_cols = collections.defaultdict(set)  # page -> data-stat names seen
for yr in seasons_raw.values():
    for page, t in yr.items():
        season_cols[page].update(t["cols"])


def col(page, *alts):
    """'page.stat' for the first of alts that the export actually has, else None."""
    return next((f"{page}.{a}" for a in alts if a in season_cols[page]), None)


G = ("g", "games")
GS = ("gs", "games_started")
P = {k: col("passing", *a) for k, a in dict(
    cmp=("pass_cmp",), att=("pass_att",), yds=("pass_yds",), td=("pass_td",), int=("pass_int",),
    sk=("pass_sacked",), sky=("pass_sacked_yds",), gwd=("gwd",), qc=("comebacks",), g=G).items()}
RU = {k: col("rushing", *a) for k, a in dict(att=("rush_att",), yds=("rush_yds",), td=("rush_td",), g=G).items()}
RE = {k: col("receiving", *a) for k, a in dict(
    rec=("rec",), yds=("rec_yds",), td=("rec_td",), tgt=("targets",), g=G).items()}
D = {k: col("defense", k) for k in ("def_int", "def_int_yds", "pass_defended", "fumbles_forced", "fumbles_rec",
                                    "fumbles_rec_yds", "sacks", "tackles_combined", "tackles_solo", "tackles_loss")}
K = {k: col("kicking", *a) for k, a in dict(xpm=("xpm",), xpa=("xpa",), fgm=("fgm",), fga=("fga",)).items()}
PU = {k: col("punting", *a) for k, a in dict(punt=("punt",), yds=("punt_yds",)).items()}
RT = {k: col("returns", *a) for k, a in dict(
    kr=("kick_ret",), kry=("kick_ret_yds",), pr=("punt_ret",), pry=("punt_ret_yds",)).items()}
SC = {k: col("scoring", *a) for k, a in dict(td=("all_td", "total_td"), pts=("scoring", "points")).items()}
GP = {"g": "player.g", "gs": "player.gs"}  # built below: a player's games/starts that season, from any table

QBk = dict(cmp=[P["cmp"]], att=[P["att"]], yds=[P["yds"]], td=[P["td"]], int=[P["int"]], sk=[P["sk"]], sky=[P["sky"]])
QB_Q = dict(q=[P["att"]], qMin=150, qLabel="pass attempts")
XQ = dict(q=[K["xpa"]], qFlat=5, qLabel="extra point attempts")
FQ = dict(q=[K["fga"]], qFlat=5, qLabel="field goal attempts")  # x10 seasons = PFR's 1,500-attempt career minimum

# id, name, family, unit, and one of: sum | num/den (+mult, q/qMin, low, pct) | formula/k
SPECS = [
    dict(id="pass_yds", name="Passing Yards (QB)", f="off", unit="Yds", sum=[P["yds"]]),
    dict(id="pass_cmp", name="Passes Completed (QB)", f="off", unit="Cmp", sum=[P["cmp"]]),
    dict(id="pass_att", name="Pass Attempts (QB)", f="off", unit="Att", sum=[P["att"]]),
    dict(id="pass_td", name="Passing Touchdowns (QB)", f="off", unit="TD", sum=[P["td"]]),
    dict(id="pass_int", name="Passes Intercepted (QB)", f="off", unit="Int", sum=[P["int"]]),
    dict(id="pass_sacked", name="Times Sacked (QB)", f="off", unit="Sk", sum=[P["sk"]]),
    dict(id="pass_sacked_yds", name="Sack Yards Lost (QB)", f="off", unit="Yds", sum=[P["sky"]]),
    dict(id="gwd", name="Game-Winning Drives (QB)", f="off", unit="GWD", sum=[P["gwd"]]),
    dict(id="comebacks", name="Fourth Quarter Comebacks (QB)", f="off", unit="4QC", sum=[P["qc"]]),
    dict(id="pass_rating", name="Passer Rating (QB)", f="off", unit="Rate", dec=1, formula="rating", k=QBk, **QB_Q),
    dict(id="pass_adj_yds_per_att", name="Adjusted Yards per Pass Attempt (QB)", f="off", unit="AY/A", dec=2, formula="aya", k=QBk, **QB_Q),
    dict(id="pass_net_yds_per_att", name="Net Yards per Pass Attempt (QB)", f="off", unit="NY/A", dec=2, formula="nya", k=QBk, **QB_Q),
    dict(id="pass_adj_net_yds_per_att", name="Adjusted Net Yards per Pass Attempt (QB)", f="off", unit="ANY/A", dec=2, formula="anya", k=QBk, **QB_Q),
    dict(id="pass_yds_per_att", name="Yards per Pass Attempt (QB)", f="off", unit="Y/A", dec=1, num=[P["yds"]], den=[P["att"]], **QB_Q),
    dict(id="pass_yds_per_cmp", name="Yards per Pass Completion (QB)", f="off", unit="Y/C", dec=1, num=[P["yds"]], den=[P["cmp"]], **QB_Q),
    dict(id="pass_cmp_perc", name="Pass Completion % (QB)", f="off", pct=True, dec=1, mult=100, num=[P["cmp"]], den=[P["att"]], **QB_Q),
    dict(id="pass_td_perc", name="Passing Touchdown % (QB)", f="off", pct=True, dec=1, mult=100, num=[P["td"]], den=[P["att"]], **QB_Q),
    dict(id="pass_int_perc", name="Pass Interception % (QB)", f="off", pct=True, dec=1, mult=100, low=True, num=[P["int"]], den=[P["att"]], **QB_Q),
    dict(id="pass_sacked_perc", name="Sacked % (QB)", f="off", pct=True, dec=2, mult=100, low=True, num=[P["sk"]], den=[P["att"], P["sk"]], **QB_Q),
    dict(id="pass_yds_per_g", name="Passing Yards per Game (QB)", f="off", unit="Y/G", dec=1, num=[P["yds"]], den=[P["g"]], **QB_Q),
    dict(id="pass_att_per_g", name="Pass Attempts per Game (QB)", f="off", unit="A/G", dec=1, num=[P["att"]], den=[P["g"]], **QB_Q),
    dict(id="pass_cmp_per_g", name="Passes Completed per Game (QB)", f="off", unit="C/G", dec=1, num=[P["cmp"]], den=[P["g"]], **QB_Q),
    dict(id="rush_att", name="Rushing Attempts", f="off", unit="Att", sum=[RU["att"]]),
    dict(id="rush_yds", name="Rushing Yards", f="off", unit="Yds", sum=[RU["yds"]]),
    dict(id="rush_td", name="Rushing Touchdowns", f="off", unit="TD", sum=[RU["td"]]),
    dict(id="rush_yds_per_att", name="Yards per Rushing Attempt", f="off", unit="Y/A", dec=1, num=[RU["yds"]], den=[RU["att"]], q=[RU["att"]], qMin=75, qLabel="rushing attempts"),
    dict(id="rush_yds_per_g", name="Rushing Yards per Game", f="off", unit="Y/G", dec=1, num=[RU["yds"]], den=[RU["g"]], q=[RU["att"]], qMin=75, qLabel="rushing attempts"),
    dict(id="rec", name="Receptions", f="off", unit="Rec", sum=[RE["rec"]]),
    dict(id="rec_yds", name="Receiving Yards", f="off", unit="Yds", sum=[RE["yds"]]),
    dict(id="rec_td", name="Receiving Touchdowns", f="off", unit="TD", sum=[RE["td"]]),
    dict(id="targets", name="Pass Targets", f="off", unit="Tgt", sum=[RE["tgt"]]),
    dict(id="rec_yds_per_rec", name="Yards per Reception", f="off", unit="Y/R", dec=1, num=[RE["yds"]], den=[RE["rec"]], q=[RE["rec"]], qMin=20, qLabel="receptions"),
    dict(id="rec_yds_per_tgt", name="Yards per Target", f="off", unit="Y/Tgt", dec=1, num=[RE["yds"]], den=[RE["tgt"]], q=[RE["tgt"]], qMin=30, qLabel="targets"),
    dict(id="rec_yds_per_g", name="Receiving Yards per Game", f="off", unit="Y/G", dec=1, num=[RE["yds"]], den=[RE["g"]], q=[RE["rec"]], qMin=20, qLabel="receptions"),
    dict(id="yds_from_scrimmage", name="Yards From Scrimmage", f="off", unit="YScm", sum=[RU["yds"], RE["yds"]]),
    dict(id="rush_receive_td", name="Rushing & Receiving Touchdowns", f="off", unit="RRTD", sum=[RU["td"], RE["td"]]),
    dict(id="touches", name="Touches", f="off", unit="Touch", sum=[RU["att"], RE["rec"]]),
    dict(id="yds_per_touch", name="Yards per Touch", f="off", unit="Y/Tch", dec=1, num=[RU["yds"], RE["yds"]], den=[RU["att"], RE["rec"]], q=[RU["att"], RE["rec"]], qMin=50, qLabel="touches"),
    dict(id="all_purpose_yds", name="All-Purpose Yards", f="off", unit="APYd", sum=[RU["yds"], RE["yds"], RT["kry"], RT["pry"]]),
    dict(id="all_td", name="Touchdowns", f="off", unit="TD", sum=[SC["td"]]),
    dict(id="def_int", name="Interceptions", f="def", unit="Int", sum=[D["def_int"]]),
    dict(id="def_int_yds", name="Interception Return Yards", f="def", unit="Yds", sum=[D["def_int_yds"]]),
    dict(id="pass_defended", name="Passes Defended", f="def", unit="PD", sum=[D["pass_defended"]]),
    dict(id="fumbles_forced", name="Fumbles Forced", f="def", unit="FF", sum=[D["fumbles_forced"]]),
    dict(id="fumbles_rec", name="Fumbles Recovered", f="def", unit="FR", sum=[D["fumbles_rec"]], note=FR_NOTE),
    dict(id="fumbles_rec_yds", name="Fumble Return Yards", f="def", unit="Yds", sum=[D["fumbles_rec_yds"]]),
    dict(id="sacks", name="Sacks", f="def", unit="Sk", dec=1, sum=[D["sacks"]]),
    dict(id="tackles_combined", name="Tackles Combined", f="def", unit="Comb", sum=[D["tackles_combined"]]),
    dict(id="tackles_solo", name="Solo Tackles", f="def", unit="Solo", sum=[D["tackles_solo"]]),
    dict(id="tackles_loss", name="Tackles For Loss", f="def", unit="TFL", sum=[D["tackles_loss"]]),
    # Kicking count boards skip one-off kickers (punters, position players): 5+ attempts of that kick in the span.
    dict(id="xpm", name="Extra Points Made", f="kick", unit="XPM", sum=[K["xpm"]], **XQ),
    dict(id="xpa", name="Extra Point Attempts", f="kick", unit="XPA", sum=[K["xpa"]], **XQ),
    dict(id="fgm", name="Field Goals Made", f="kick", unit="FGM", sum=[K["fgm"]], **FQ),
    dict(id="fga", name="Field Goal Attempts", f="kick", unit="FGA", sum=[K["fga"]], **FQ),
    dict(id="xp_perc", name="Extra Point %", f="kick", pct=True, dec=1, mult=100, num=[K["xpm"]], den=[K["xpa"]], q=[K["xpa"]], qMin=10, qLabel="extra point attempts"),
    dict(id="fg_perc", name="Field Goal %", f="kick", pct=True, dec=1, mult=100, num=[K["fgm"]], den=[K["fga"]], q=[K["fga"]], qMin=10, qLabel="field goal attempts"),
    dict(id="scoring", name="Points Scored", f="kick", unit="Pts", sum=[SC["pts"]]),
    dict(id="punt", name="Punts", f="punt", unit="Pnt", sum=[PU["punt"]]),
    dict(id="punt_yds", name="Punting Yards", f="punt", unit="Yds", sum=[PU["yds"]]),
    dict(id="punt_yds_per_punt", name="Yards per Punt", f="punt", unit="Y/P", dec=1, num=[PU["yds"]], den=[PU["punt"]], q=[PU["punt"]], qMin=25, qLabel="punts"),
    dict(id="kick_ret", name="Kick Returns", f="ret", unit="Rt", sum=[RT["kr"]]),
    dict(id="kick_ret_yds", name="Kick Return Yards", f="ret", unit="Yds", sum=[RT["kry"]]),
    dict(id="kick_ret_yds_per_ret", name="Yards per Kick Return", f="ret", unit="Y/Rt", dec=1, num=[RT["kry"]], den=[RT["kr"]], q=[RT["kr"]], qMin=7.5, qLabel="kick returns"),
    dict(id="punt_ret", name="Punt Returns", f="ret", unit="Ret", sum=[RT["pr"]]),
    dict(id="punt_ret_yds", name="Punt Return Yards", f="ret", unit="Yds", sum=[RT["pry"]]),
    dict(id="punt_ret_yds_per_ret", name="Yards per Punt Return", f="ret", unit="Y/R", dec=1, num=[RT["pry"]], den=[RT["pr"]], q=[RT["pr"]], qMin=7.5, qLabel="punt returns"),
    dict(id="ret", name="Kick & Punt Returns", f="ret", unit="Rt", sum=[RT["kr"], RT["pr"]]),
    dict(id="ret_yds", name="Kick & Punt Return Yards", f="ret", unit="RtY", sum=[RT["kry"], RT["pry"]]),
    dict(id="g", name="Games Played", f="gen", unit="G", sum=[GP["g"]]),
    dict(id="gs", name="Games Started", f="gen", unit="GS", sum=[GP["gs"]]),
]


def spec_keys(sp):
    ks = []
    for f in ("sum", "num", "den", "q"):
        ks += sp.get(f, [])
    for v in sp.get("k", {}).values():
        ks += v
    return ks


specs = [sp for sp in SPECS if seasons_raw and all(spec_keys(sp)) and sp["id"] not in CUT]
dropped = [sp["id"] for sp in SPECS if sp not in specs and sp["id"] not in CUT]
needed = collections.defaultdict(list)  # page -> stats used by some board
for sp in specs:
    for k in spec_keys(sp):
        pg, st = k.split(".")
        if st not in needed[pg]:
            needed[pg].append(st)


def cell(x):
    v = num(x) if x else None
    return 0 if v is None else (int(v) if v == int(v) else v)


# Team Tees: today's 32 franchises. PFR codes repeat across eras ("STL" = Cardinals 1960-87, Rams 1995-2015;
# "BAL" = Colts to 1983, Ravens from 1996; "HOU" = Oilers to 1996, Texans from 2002), so the year decides.
# A season split between teams only exists combined ("2TM"), so it counts for neither team.
TEAM_NAMES = {
    "crd": "Arizona Cardinals", "atl": "Atlanta Falcons", "rav": "Baltimore Ravens", "buf": "Buffalo Bills",
    "car": "Carolina Panthers", "chi": "Chicago Bears", "cin": "Cincinnati Bengals", "cle": "Cleveland Browns",
    "dal": "Dallas Cowboys", "den": "Denver Broncos", "det": "Detroit Lions", "gnb": "Green Bay Packers",
    "htx": "Houston Texans", "clt": "Indianapolis Colts", "jax": "Jacksonville Jaguars", "kan": "Kansas City Chiefs",
    "rai": "Las Vegas Raiders", "sdg": "Los Angeles Chargers", "ram": "Los Angeles Rams", "mia": "Miami Dolphins",
    "min": "Minnesota Vikings", "nwe": "New England Patriots", "nor": "New Orleans Saints", "nyg": "New York Giants",
    "nyj": "New York Jets", "phi": "Philadelphia Eagles", "pit": "Pittsburgh Steelers", "sfo": "San Francisco 49ers",
    "sea": "Seattle Seahawks", "tam": "Tampa Bay Buccaneers", "oti": "Tennessee Titans", "was": "Washington Commanders",
}


def franchise(code, y):
    simple = {"ARI": "crd", "PHO": "crd", "CRD": "crd", "ATL": "atl", "CAR": "car", "CHI": "chi", "DEN": "den",
              "GNB": "gnb", "TEN": "oti", "IND": "clt", "JAX": "jax", "LVR": "rai", "OAK": "rai", "RAI": "rai",
              "LAC": "sdg", "SDG": "sdg", "LAR": "ram", "RAM": "ram", "NWE": "nwe", "NOR": "nor", "NYG": "nyg",
              "NYJ": "nyj", "NYT": "nyj", "SFO": "sfo", "SEA": "sea", "TAM": "tam", "WAS": "was", "PRT": "det"}
    if code in simple:
        return simple[code]
    rules = {
        "BUF": "buf" if y >= 1960 else None, "CIN": "cin" if y >= 1968 else None, "CLE": "cle" if y >= 1946 else None,
        "DAL": "dal" if y >= 1960 else None, "DET": "det" if y >= 1934 else None, "MIA": "mia" if y >= 1966 else None,
        "MIN": "min" if y >= 1961 else None, "PHI": "phi" if y >= 1933 else None, "PIT": "pit" if y >= 1933 else None,
        "KAN": "kan" if y >= 1963 else None, "DTX": "kan" if 1960 <= y <= 1962 else None,
        "HOU": "htx" if y >= 2002 else "oti" if y >= 1960 else None,
        "BAL": "clt" if 1953 <= y <= 1983 else "rav" if y >= 1996 else None,
        "STL": "crd" if 1960 <= y <= 1987 else "ram" if 1995 <= y <= 2015 else None,
        "BOS": "was" if 1932 <= y <= 1936 else "nwe" if 1960 <= y <= 1970 else None,
    }
    return rules.get(code)


season_team = {}  # (year, pid) -> franchise
season_rows = {}  # year -> page -> {pid: [values]}
season_names, season_years = {}, {}
season_pos = collections.defaultdict(collections.Counter)  # pid -> position counts
for yr, pages in seasons_raw.items():
    out, gp = {}, {}
    for page, t in pages.items():
        idx = {c: i for i, c in enumerate(t["cols"])}
        gi = next((idx[c] for c in G if c in idx), None)
        gsi = next((idx[c] for c in GS if c in idx), None)
        pi = idx.get("pos")
        tmi = idx.get("team_name_abbr")
        rows = {}
        for r in t["rows"]:
            pid, cells = r[0].lower(), r[2:]
            if tmi is not None and cells[tmi]:
                season_team.setdefault((yr, pid), franchise(cells[tmi], yr))
            season_names.setdefault(pid, r[1])
            if pi is not None and cells[pi]:
                season_pos[pid][norm_pos(cells[pi])] += 1
            season_years[pid] = (min(yr, season_years.get(pid, (yr, yr))[0]), max(yr, season_years.get(pid, (yr, yr))[1]))
            g = gp.setdefault(pid, [0, 0])
            if gi is not None: g[0] = max(g[0], cell(cells[gi]))
            if gsi is not None: g[1] = max(g[1], cell(cells[gsi]))
            if page in needed:
                vals = [cell(cells[idx[st]]) if st in idx else 0 for st in needed[page]]  # older seasons lack some stats
                if any(vals):
                    rows[pid] = vals
        out[page] = rows
    out["player"] = {pid: v for pid, v in gp.items() if any(v)}
    season_rows[yr] = out
if seasons_raw:
    needed["player"] = ["g", "gs"]
FIRST_SEASON = min(seasons_raw, default=2000)
LAST_SEASON = max(seasons_raw, default=int(meta["retrieved"][:4]))

# Resolve display names: one per player id, unique across the whole game (career boards + seasons).
names, years = {}, {}
for b in boards:
    for r in b["rows"]:
        names.setdefault(r["id"], r["name"])
        if r["years"]:
            years.setdefault(r["id"], r["years"])
career_ids = set(names)
for pid, n in season_names.items():
    names.setdefault(pid, n)
    if pid not in years:
        a, z = season_years[pid]
        years[pid] = f"{a}-{z}" if a != z else str(a)
by_name = collections.defaultdict(set)
for pid, n in names.items():
    by_name[n].add(pid)
for n, pids in by_name.items():
    if len(pids) > 1:
        # If exactly one namesake is on a career board, he keeps the plain name (Lamar Jackson the QB);
        # everyone else gets "(years, position)".
        famous = [p for p in pids if p in career_ids]
        for pid in pids:
            if len(famous) == 1 and pid == famous[0]:
                continue
            pos = season_pos[pid].most_common(1)[0][0] if season_pos[pid] else ""
            names[pid] = RENAME.get(pid) or f"{n} ({years.get(pid, '?')}{', ' + pos if pos else ''})"

# Career-board players first (data.json); season-only players after them (seasons.json).
players = sorted({names[p] for p in career_ids})
extra = sorted({names[p] for p in names if p not in career_ids} - set(players))
index = {n: i for i, n in enumerate(players + extra)}
cats = []
for b in boards:
    rows = b["rows"]
    leaders, prev = [], None
    for i, r in enumerate(rows):
        rank = prev[0] if prev and prev[1] == r["value"] else i + 1
        prev = (rank, r["value"])
        leaders.append([rank, index[names[r["id"]]], r["disp"]])
    cats.append({"id": b["id"], "name": b["name"], "f": family(b["id"]), "l": leaders,
                 **({"n": CAREER_NOTES[b["id"]]} if b["id"] in CAREER_NOTES else {})})

# data.json: {asOf, players: [names], categories: [{id, name, f: family, l: [[rank, player index, display value]]}]}
with open(os.path.join(ROOT, "nfl", "data.json"), "w") as f:
    json.dump({"asOf": meta["retrieved"][:10], "firstSeason": FIRST_SEASON, "lastSeason": LAST_SEASON,
               "players": players, "categories": cats},
              f, ensure_ascii=False, separators=(",", ":"))

if seasons_raw:
    # seasons.json: {years: [first, last], extraPlayers, boards: [specs], seasons: {year: {page: {c: [stats], r: [[player index, ...values]]}}}}
    out = {}
    for yr, pages in season_rows.items():
        team_ix = {tid: i for i, tid in enumerate(TEAM_NAMES)}
        out[yr] = {pg: {"c": needed[pg], "r": [[index[names[pid]], *v] for pid, v in rows.items()],
                        "t": [team_ix.get(season_team.get((yr, pid)), -1) for pid in rows]}
                   for pg, rows in pages.items() if pg in needed and rows}
    with open(os.path.join(ROOT, "nfl", "seasons.json"), "w") as f:
        json.dump({"years": [FIRST_SEASON, LAST_SEASON], "extraPlayers": extra, "boards": specs, "seasons": out,
                   "teams": [{"id": tid, "name": n} for tid, n in TEAM_NAMES.items()]},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"seasons.json: {len(out)} seasons, {len(specs)} span boards, {len(extra)} season-only players")
    print("Span boards missing columns:", dropped)
print(f"{len(cats)} categories, {len(players)} players")
print("Skipped:", *skipped, sep="\n  ")
print("Shared names:", [n for n, p in by_name.items() if len(p) > 1])
