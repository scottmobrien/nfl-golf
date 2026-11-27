"""Render tools/og/og.html to og.png (1200x630) at the site root, using headless Chrome.

Usage: python3 tools/og/render.py
"""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
out = os.path.join(ROOT, "og.png")
subprocess.run([
    CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
    "--window-size=1200,630", f"--screenshot={out}", "file://" + os.path.join(HERE, "og.html"),
], check=True, capture_output=True)
print(out, os.path.getsize(out), "bytes")
