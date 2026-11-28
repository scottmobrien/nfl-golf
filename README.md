# NFL Golf

Each hole is an NFL stat leaderboard with a random pin (rank). Name the player sitting
closest to that rank. Your score on the hole is how far off you were as a percentage of the list
(out of bounds = 100). Lowest total wins.

Live at https://sportsbutmakeitgolf.com. The root `index.html` is the "Sports.......But Make it Golf"
landing page; the NFL game lives in `nfl/` (it fetches `nfl/data.json`, and `nfl/seasons.json` for the
span modes). Serve the repo root with any static web server to play locally.

## Tees (game modes)

| Tee | Boards | Years |
| --- | --- | --- |
| The Tips (Sicko Mode) | every family | all time (PFR career boards) |
| Championship | offense, defense, games/starts/AV/awards (no kicking, punting, returns) | all time |
| Members Tees | everything except punting | 2000–present, rebuilt from season stats |
| Red Tees | player picks families: Offensive, Defensive, Placekicking, Punting/Returning, Games & Starts | player picks From / To |

Board families are set in `family()` in `tools/build_data.py`; points scored counts as placekicking.
Span boards are rebuilt in the browser from season totals. Rate stats (Y/A, completion %, FG %…)
require a minimum volume that scales with the span (10+ seasons = PFR's career minimums). A span
board needs at least 50 players and no single tie covering more than 20% of the list.
Career-only boards (AV, award shares, pick sixes, teams beaten, fumbles) appear only in the all-time tees.

## NBA, MLB and NHL Golf

All four games share `shared/game.js` and `shared/game.css`; each sport's `index.html` sets `window.GOLF`
(name, storage key, Daily 9 seed, tees). The NBA/MLB/NHL pages are generated from `nfl/index.html` by
`tools/make_sport_pages.py`, so re-run it after changing the NFL page.

Their boards are all built from season-by-season stats by `tools/golf_build.py` (all-time boards in
`data.json`, span data in `seasons.json`):

| Sport | Pull | Build | Source |
|---|---|---|---|
| NBA | `python3 tools/fetch_nba.py --teams` (~5 min; one row per player per team, which the build prefers) | `python3 tools/build_nba.py` | Basketball-Reference (NBA + BAA, no ABA) |
| MLB | download the Lahman CSV zip into `data-src/mlb/lahman/`; `python3 tools/fetch_mlb_season.py 2026` for seasons Lahman lacks | `python3 tools/build_mlb.py` | Lahman (CC BY-SA 3.0) + Baseball-Reference |
| NHL | `python3 tools/fetch_nhl.py` (~40 min) | `python3 tools/build_nhl.py` | NHL stats API (NHL only, no WHA) |

**Team Tees.** Each build tags every season row with today's franchise (relocations folded in: Sonics to
Thunder, Nordiques to Avalanche, Cardinals to Arizona). MLB (Lahman stints) and NBA (`--teams` fetch) split a
traded player's season by team. NFL and NHL sources only have a traded season combined, so that season counts
for neither team.

The pullers resume where they stopped. Raw pulls in `data-src/nba|mlb|nhl/` are kept out of git.

## Data

From [Pro Football Reference](https://www.pro-football-reference.com/leaders/).

To refresh:
1. In a pro-football-reference.com tab, paste each script into the DevTools console:
   `tools/pfr-export-all.js` (career boards), `tools/pfr-qbwins-export.js` (teams beaten),
   `tools/pfr-export-seasons.js` (every season's stat pages; about 50 minutes, saves a file per 10 seasons).
2. Move the downloads into `data-src/`: `pfr_all_career_leaders.json`, `pfr_qb_teams_beaten.json`, `pfr_seasons_*.json`.
3. `python3 tools/build_data.py` to regenerate `nfl/data.json` and `nfl/seasons.json`.

`python3 tools/build_artifact.py` bundles a single-page version into `dist/` for publishing as a Claude artifact.
