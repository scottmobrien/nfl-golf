"""Bundle the game into dist/ for publishing as a claude.ai artifact.

Usage: python3 tools/build_artifact.py
Writes dist/index.html (CSS and JS inlined, no <html>/<head>/<body> wrapper — the artifact
host adds that) and copies data.json and seasons.json beside it.
"""
import os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
GAME = os.path.join(ROOT, "nfl")  # the NFL game lives in nfl/
read = lambda name: open(os.path.join(GAME, name), encoding="utf-8").read()

html = read("index.html")
title = re.search(r"<title>.*?</title>", html, re.S).group()
body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = re.sub(r'\s*<script src="app\.js[^"]*"></script>', "", body)

page = "\n".join([
    title,
    '<meta name="claude:viewport-fit-sides" content="cover">',
    "<style>\n" + read("styles.css") + "</style>",
    body.strip(),
    "<script>\n" + read("app.js") + "</script>",
    "",
])
os.makedirs(DIST, exist_ok=True)
open(os.path.join(DIST, "index.html"), "w", encoding="utf-8").write(page)
for name in ("data.json", "seasons.json"):
    if os.path.exists(os.path.join(GAME, name)):
        shutil.copy(os.path.join(GAME, name), os.path.join(DIST, name))
print("dist/index.html", len(page), "bytes; dist/data.json", os.path.getsize(os.path.join(DIST, "data.json")), "bytes")
