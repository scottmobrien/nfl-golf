"""Shared builder for the season-based golf games (NBA, MLB, NHL).

A sport adapter gives us, per season year, per stat page, per player id, a dict of numbers, plus each
player's name and position counts. From that we write, into <sport>/:

  data.json     {asOf, firstSeason, lastSeason, players, categories: [{id, name, f, l: [[rank, idx, disp]], n}]}
                — the all-time boards (The Tips / Championship), built from full career totals.
  seasons.json  {years, extraPlayers, boards: [specs], seasons: {year: {page: {c: [stats], r: [[idx, ...]]}}}}
                — what the page sums for any span (Members Tees, Red Tees, the Daily 9).

The all-time boards here use the same rules as the in-browser span boards in shared/game.js (rangeBoard):
rate stats need a minimum volume (qMin per season, x10 seasons), lists stop at rank 250, a giant tie at
the bottom is trimmed, and a board needs 100+ players with no tie over 20% of the list.
"""
import collections, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_RANK, MAX_TIE_SHARE, MIN_ROWS_ALL_TIME = 250, 0.2, 100

# Formulas for boards that aren't a plain ratio (must match FORMULAS in shared/game.js).
FORMULAS = {
    # OBP + SLG. k: h, bb, hbp, sf, ab, tb (att = ab).
    "ops": lambda v: ((v["h"] + v["bb"] + v["hbp"]) / (v["ab"] + v["bb"] + v["hbp"] + v["sf"])
                      if (v["ab"] + v["bb"] + v["hbp"] + v["sf"]) else 0) + v["tb"] / v["att"],
}


def add(o, keys):
    return sum(o.get(k, 0) for k in keys)


def spec_keys(sp):
    ks = []
    for f in ("sum", "num", "den", "q"):
        ks += sp.get(f, [])
    for v in sp.get("k", {}).values():
        ks += v
    return ks


def js_round(v, dec):
    d = 10 ** dec
    return math.floor(v * d + 0.5) / d  # Math.round, not banker's rounding


def fmt(spec, v):
    dec = spec.get("dec", 0)
    s = f"{v:,.{dec}f}"
    if spec.get("nolead"):
        s = s.replace("0.", ".", 1) if s.startswith("0.") else s
    return s + "%" if spec.get("pct") else f"{s} {spec['unit']}"


def board(spec, tot, years, min_rows):
    """Port of rangeBoard() in shared/game.js. tot: {player idx: {"page.stat": total}}."""
    q_min = 1
    if spec.get("q") and not spec.get("qFlat"):
        full = spec["qMin"] * min(years, 10)
        vols = sorted((add(o, spec["q"]) for o in tot.values()), reverse=True)
        q_min = max(1, min(full, max(full / 3, vols[59] if len(vols) > 59 else 0)))
    rows = []
    for pi, o in tot.items():
        if spec.get("qFlat") and add(o, spec["q"]) < spec["qFlat"]:
            continue
        if "sum" in spec:
            v = add(o, spec["sum"])
        else:
            if add(o, spec["q"]) < q_min:
                continue
            if "formula" in spec:
                vals = {n: add(o, ks) for n, ks in spec["k"].items()}
                if not vals.get("att"):
                    continue
                v = FORMULAS[spec["formula"]](vals)
            else:
                den = add(o, spec["den"])
                if not den:
                    continue
                v = add(o, spec["num"]) / den * spec.get("mult", 1)
        v = js_round(v, spec.get("dec", 0))
        if v > 0 or (spec.get("low") and v == 0 and "sum" not in spec):
            rows.append((pi, v))
    rows.sort(key=lambda r: r[1] if spec.get("low") else -r[1])
    ranked = []
    for i, (pi, v) in enumerate(rows):
        rank = ranked[-1][0] if ranked and ranked[-1][2] == v else i + 1
        if rank > MAX_RANK:
            break
        ranked.append((rank, pi, v))
    while ranked:  # trim a giant tie off the bottom
        tail = sum(1 for r in ranked if r[0] == ranked[-1][0])
        if tail <= MAX_TIE_SHARE * len(ranked):
            break
        ranked = ranked[:-tail]
    biggest = max(collections.Counter(r[0] for r in ranked).values(), default=0)
    if len(ranked) < min_rows or biggest > MAX_TIE_SHARE * len(ranked):
        return None, f"{len(ranked)} rows, biggest tie {biggest}"
    mn = spec.get("qFlat") or (math.ceil(q_min) if spec.get("q") else 0)
    note = " · ".join(x for x in [f"Minimum {mn:,} {spec['qLabel']}" if mn > 1 and spec.get("qLabel") else "",
                                  spec.get("note", "")] if x)
    return {"ranked": ranked, "note": note}, None


def build(sport, seasons, people, specs, source_label):
    """seasons: {year: {page: {pid: {stat: number}}}}; people: {pid: {"name", "pos": Counter, "years": set}}."""
    out_dir = os.path.join(ROOT, sport)
    os.makedirs(out_dir, exist_ok=True)
    years = sorted(seasons)
    first, last = years[0], years[-1]

    # Drop boards whose stats the data never has.
    have = collections.defaultdict(set)
    for yr in seasons.values():
        for page, rows in yr.items():
            for st in rows.values():
                have[page].update(st)
    specs = [sp for sp in specs if all(k.split(".")[1] in have[k.split(".")[0]] for k in spec_keys(sp))]
    needed = collections.defaultdict(list)
    for sp in specs:
        for k in spec_keys(sp):
            pg, st = k.split(".")
            if st not in needed[pg]:
                needed[pg].append(st)

    # Career totals by player id.
    career = collections.defaultdict(lambda: collections.defaultdict(float))
    for yr, pages in seasons.items():
        for page, rows in pages.items():
            for pid, st in rows.items():
                for s in needed.get(page, []):
                    if st.get(s):
                        career[pid][f"{page}.{s}"] += st[s]

    # All-time boards on player ids first; display names are resolved after.
    all_time, skipped = [], []
    for sp in specs:
        b, why = board(sp, career, len(years), MIN_ROWS_ALL_TIME)
        if b:
            all_time.append((sp, b))
        else:
            skipped.append(f"{sp['id']} ({why})")

    # Display names: unique across the game. If one namesake is on an all-time board he keeps the plain name;
    # the others get "(years, position)".
    famous = {pid for _, b in all_time for _, pid, _ in b["ranked"]}
    def years_of(pid):
        ys = sorted(people[pid]["years"])
        return f"{ys[0]}-{ys[-1]}" if ys[0] != ys[-1] else str(ys[0])
    def pos_of(pid):
        c = people[pid]["pos"]
        return c.most_common(1)[0][0] if c else ""
    by_name = collections.defaultdict(list)
    for pid, p in people.items():
        by_name[p["name"]].append(pid)
    names = {}
    for n, pids in by_name.items():
        if len(pids) == 1:
            names[pids[0]] = n
            continue
        fam = [p for p in pids if p in famous]
        for pid in pids:
            if len(fam) == 1 and pid == fam[0]:
                names[pid] = n
            else:
                pos = pos_of(pid)
                names[pid] = f"{n} ({years_of(pid)}{', ' + pos if pos else ''})"
    # Still-identical labels (same name, years and position) get a running number.
    seen = collections.Counter(names.values())
    count = collections.Counter()
    for pid in sorted(names):
        if seen[names[pid]] > 1:
            count[names[pid]] += 1
            names[pid] = f"{names[pid]} #{count[names[pid]]}"

    players = sorted({names[p] for p in famous})
    extra = sorted({names[p] for p in people if p not in famous} - set(players))
    index = {n: i for i, n in enumerate(players + extra)}

    cats = []
    for sp, b in all_time:
        name = "Career " + sp["name"]
        if sp.get("since"):  # stat not recorded before then: "X (since 1973-74)", "X (Batting, since 1955)"
            name = name[:-1] + f", since {sp['since']})" if name.endswith(")") else f"{name} (since {sp['since']})"
        cat = {"id": sp["id"], "name": name, "f": sp["f"],
               "l": [[rank, index[names[pid]], fmt(sp, v)] for rank, pid, v in b["ranked"]]}
        if b["note"]:
            cat["n"] = b["note"]
        cats.append(cat)

    # Seasons for spans: only needed stats, only rows with something in them.
    out = {}
    for yr in years:
        pages = {}
        for page, rows in seasons[yr].items():
            if page not in needed:
                continue
            r = []
            for pid, st in rows.items():
                vals = [st.get(s, 0) for s in needed[page]]
                vals = [int(v) if float(v).is_integer() else round(v, 3) for v in vals]
                if any(vals):
                    r.append([index[names[pid]], *vals])
            if r:
                pages[page] = {"c": needed[page], "r": r}
        out[str(yr)] = pages

    as_of = __import__("datetime").date.today().isoformat()
    with open(os.path.join(out_dir, "data.json"), "w") as f:
        json.dump({"asOf": as_of, "firstSeason": first, "lastSeason": last, "players": players,
                   "categories": cats}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "seasons.json"), "w") as f:
        json.dump({"years": [first, last], "extraPlayers": extra, "boards": specs, "seasons": out},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"{sport}: {len(cats)} all-time boards, {len(specs)} span boards, {len(players)} + {len(extra)} players, "
          f"seasons {first}-{last}; source {source_label}")
    if skipped:
        print("  all-time boards skipped:", *skipped, sep="\n    ")
    return {"cats": cats, "names": names, "index": index, "career": career, "players": players + extra}
