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

## Data

From [Pro Football Reference](https://www.pro-football-reference.com/leaders/).

To refresh:
1. In a pro-football-reference.com tab, paste each script into the DevTools console:
   `tools/pfr-export-all.js` (career boards), `tools/pfr-qbwins-export.js` (teams beaten),
   `tools/pfr-export-seasons.js` (every season's stat pages; about 50 minutes, saves a file per 10 seasons).
2. Move the downloads into `data-src/`: `pfr_all_career_leaders.json`, `pfr_qb_teams_beaten.json`, `pfr_seasons_*.json`.
3. `python3 tools/build_data.py` to regenerate `nfl/data.json` and `nfl/seasons.json`.

`python3 tools/build_artifact.py` bundles a single-page version into `dist/` for publishing as a Claude artifact.
