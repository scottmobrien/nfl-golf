"""Generate nba/, mlb/ and nhl/ index.html from nfl/index.html, swapping in each sport's wording,
tees, Red Tees categories and game settings (window.GOLF, read by shared/game.js).

Usage: python3 tools/make_sport_pages.py   (re-run after changing nfl/index.html)
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCH = "2026-11-27"  # The Daily 9 #1 for the new sports

SPORTS = {
    "nba": dict(
        short="NBA", example="career assists", source="Basketball-Reference",
        desc="Name the player closest to a random spot on an all-time NBA leaderboard. Scored like golf, with a Daily 9 for everyone.",
        fams=[("score", "Scoring", True), ("reb", "Rebounding", True), ("play", "Playmaking", True),
              ("def", "Defense", True), ("gen", "Games &amp; Minutes", False), ("adv", "Advanced", False)],
        champ=["score", "reb", "play", "def", "gen"], members=["score", "reb", "play", "def", "gen"],
        tees=["All statistical categories (including advanced stats like Win Shares, PER and VORP), all time. A challenging round for true NBA sickos.",
              "All time periods, all categories except advanced stats. Still very tough, good luck.",
              "All categories except advanced stats, but only since 2000.",
              None],
        seasons_note="Seasons are labeled by the year they end (2024 = the 2023-24 season).",
    ),
    "mlb": dict(
        short="MLB", example="career home runs", source="the Lahman Baseball Database",
        desc="Name the player closest to a random spot on an all-time MLB leaderboard. Scored like golf, with a Daily 9 for everyone.",
        fams=[("bat", "Hitting", True), ("run", "Baserunning", True), ("pitch", "Pitching", True), ("misc", "Odds &amp; Ends", False)],
        champ=["bat", "run", "pitch"], members=["bat", "run", "pitch"],
        tees=["All statistical categories (including odds and ends like sacrifice flies and wild pitches), all time. A challenging round for true MLB sickos.",
              "All time periods, hitting, baserunning and pitching (no odds and ends). Still very tough, good luck.",
              "Hitting, baserunning and pitching, but only since 2000.",
              None],
        seasons_note="",
    ),
    "nhl": dict(
        short="NHL", example="career assists", source="the NHL",
        desc="Name the player closest to a random spot on an all-time NHL leaderboard. Scored like golf, with a Daily 9 for everyone.",
        fams=[("score", "Scoring", True), ("skate", "Skating &amp; Physical", True), ("goal", "Goaltending", False)],
        champ=["score", "skate"], members=["score", "skate", "goal"],
        tees=["All statistical categories (including goaltending), all time. A challenging round for true NHL sickos.",
              "All time periods, all skater categories (no goaltending). Still very tough, good luck.",
              "All categories, but only since 2000.",
              None],
        seasons_note="Seasons are labeled by the year they end (2024 = the 2023-24 season). Hits, blocks, takeaways and giveaways start in 2005-06.",
    ),
}

nfl = open(os.path.join(ROOT, "nfl", "index.html"), encoding="utf-8").read()

for sport, c in SPORTS.items():
    s, short = nfl, c["short"]
    nfl_desc = re.search(r'<meta name="description" content="([^"]*)"', s).group(1)
    s = s.replace(nfl_desc, c["desc"])
    s = s.replace("<title>NFL Golf</title>", f"<title>{short} Golf</title>")
    s = s.replace("NFL Golf — Sports", f"{short} Golf — Sports")
    s = s.replace("https://sportsbutmakeitgolf.com/nfl/", f"https://sportsbutmakeitgolf.com/{sport}/")
    s = s.replace('aria-label="NFL Golf home"><span class="flag">⛳</span> NFL <em>Golf</em>',
                  f'aria-label="{short} Golf home"><span class="flag">⛳</span> {short} <em>Golf</em>')
    s = s.replace("Welcome to NFL Golf", f"Welcome to {short} Golf")
    s = s.replace("is an NFL statistical category (e.g. rushing touchdowns)", f"is an {short} statistical category (e.g. {c['example']})")
    # Tee descriptions, in order: Tips, Championship, Members, Red (None keeps the NFL wording).
    copies = re.findall(r'<span class="tee-copy">(.*?)</span>', s)
    for old, new in zip(copies, c["tees"]):
        if new:
            s = s.replace(f'<span class="tee-copy">{old}</span>', f'<span class="tee-copy">{new}</span>', 1)
    # Red Tees categories.
    fams = re.search(r'<div class="fams">.*?</div>', s, re.S).group(0)
    boxes = "\n".join(f'            <label><input type="checkbox" name="fam" value="{v}"{" checked" if on else ""} /> {label}</label>'
                      for v, label, on in c["fams"])
    s = s.replace(fams, f'<div class="fams">\n{boxes}\n          </div>')
    if c["seasons_note"]:
        s = s.replace('<p id="redNote" class="fine red-note"></p>',
                      f'<p class="fine">{c["seasons_note"]}</p>\n          <p id="redNote" class="fine red-note"></p>')
    # Game settings for shared/game.js.
    golf = {
        "name": f"{short} Golf", "key": f"{sport}golf", "dailySeed": f"{sport}-golf-daily:", "dailyEpoch": LAUNCH,
        "uniformFirstDaily": False, "source": c["source"],
        "leaderboard": True, "lbSport": sport,
        "allFams": [v for v, _, _ in c["fams"]], "tees": {"champ": c["champ"], "members": c["members"]},
        "membersFrom": 2000,
    }
    s = s.replace('  <script src="../shared/leaderboard-config.js',
                  f'  <script>window.GOLF = {json.dumps(golf)};</script>\n  <script src="../shared/leaderboard-config.js', 1)
    assert "NFL" not in s.replace("NFLGOLF", ""), [l for l in s.splitlines() if "NFL" in l]
    os.makedirs(os.path.join(ROOT, sport), exist_ok=True)
    open(os.path.join(ROOT, sport, "index.html"), "w", encoding="utf-8").write(s)
    print(f"{sport}/index.html written")
