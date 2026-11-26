# NFL Golf

Each hole is an all-time NFL career leaderboard with a random pin (rank). Name the player sitting
closest to that rank. Your score on the hole is how far off you were as a percentage of the list
(out of bounds = 100). Lowest total wins.

Play: open `index.html` through any static web server (it fetches `data.json`).

## Data

Career leaderboards come from [Pro Football Reference](https://www.pro-football-reference.com/leaders/).

To refresh:
1. In a pro-football-reference.com tab, paste `tools/pfr-export-all.js` (and `tools/pfr-qbwins-export.js`) into the DevTools console.
2. Move the downloaded JSON files into `data-src/` (`pfr_all_career_leaders.json`, `pfr_qb_teams_beaten.json`).
3. `python3 tools/build_data.py` to regenerate `data.json`.

`python3 tools/build_artifact.py` bundles a single-page version into `dist/` for publishing as a Claude artifact.
