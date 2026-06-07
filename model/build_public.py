#!/usr/bin/env python3
"""
Build the PUBLIC copy of the wall chart served at wc26-predictions.boxd.sh:
the repo index.html with the Reset + Fill-with-model controls removed (so viewers
of the shared link can't wipe/refill the chart). The repo index.html keeps both
buttons for local editing.

Removes: the #modelBtn and #resetBtn <button> elements and their two JS click
handlers. Keeps MODEL_PREDICTIONS + the auto-fill-if-empty (so fresh visitors still
see the model's predictions). Writes /home/boxd/site/index.html (the webroot).

Run after model/fill_sheet.py whenever predictions change.
"""
import re, os

WEBROOT = "/home/boxd/site/index.html"
lines = open("index.html", encoding="utf-8").read().split("\n")

out, i = [], 0
while i < len(lines):
    ln = lines[i]
    # drop the two button elements
    if 'id="modelBtn"' in ln or 'id="resetBtn">Reset' in ln:
        i += 1; continue
    # drop the single-line modelBtn handler
    if "getElementById('modelBtn').addEventListener" in ln:
        i += 1; continue
    # drop the multi-line resetBtn handler block, up to its closing "});"
    if "getElementById('resetBtn').addEventListener" in ln:
        i += 1
        while i < len(lines) and lines[i].strip() != "});":
            i += 1
        i += 1                       # skip the "});" too
        continue
    out.append(ln); i += 1

html = "\n".join(out)
assert "modelBtn" not in html and "resetBtn" not in html, "button removal failed"
assert "MODEL_PREDICTIONS" in html, "lost the predictions"

# webroot is a clean dir with only index.html (don't expose the repo / .env)
if os.path.islink(WEBROOT) or os.path.exists(WEBROOT):
    os.remove(WEBROOT)
open(WEBROOT, "w", encoding="utf-8").write(html)
print(f"wrote {WEBROOT}: buttons removed, predictions kept ({len(html)} bytes)")
