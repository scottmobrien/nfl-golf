"""Build data.json for NFL Golf.

Usage: python3 tools/build_data.py

Inputs (in data-src/):
  pfr_all_career_leaders.json  — from tools/pfr-export-all.js (every board on PFR's /leaders/ index)
  pfr_qb_teams_beaten.json     — from tools/pfr-qbwins-export.js (/friv/qb-wins.htm)

Each board keeps PFR's own row order (so "lower is better" stats like INT% rank correctly);
tied values share a rank. Boards that are too short or too tie-heavy to play well are skipped.
"""
import collections, json, os, re

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


def board_name(key, title):
    t = re.sub(r"^NFL ", "", title)
    t = re.sub(r" Career Leaders", "", t)
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

for key, b in pfr.items():
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

# Resolve display names: one per player id, unique across the whole game.
names, years = {}, {}
for b in boards:
    for r in b["rows"]:
        names.setdefault(r["id"], r["name"])
        if r["years"]:
            years.setdefault(r["id"], r["years"])
by_name = collections.defaultdict(set)
for pid, n in names.items():
    by_name[n].add(pid)
for n, pids in by_name.items():
    if len(pids) > 1:
        for pid in pids:
            names[pid] = RENAME.get(pid) or f"{n} ({years.get(pid, '?')})"

players = sorted(set(names.values()))
index = {n: i for i, n in enumerate(players)}
cats = []
for b in boards:
    leaders, prev = [], None
    for i, r in enumerate(b["rows"]):
        rank = prev[0] if prev and prev[1] == r["value"] else i + 1
        prev = (rank, r["value"])
        leaders.append([rank, index[names[r["id"]]], r["disp"]])
    cats.append({"id": b["id"], "name": b["name"], "l": leaders})

# data.json: {asOf, players: [names], categories: [{id, name, l: [[rank, player index, display value]]}]}
with open(os.path.join(ROOT, "data.json"), "w") as f:
    json.dump({"asOf": meta["retrieved"][:10], "players": players, "categories": cats},
              f, ensure_ascii=False, separators=(",", ":"))

print(f"{len(cats)} categories, {len(players)} players")
print("Skipped:", *skipped, sep="\n  ")
print("Shared names:", [n for n, p in by_name.items() if len(p) > 1])
