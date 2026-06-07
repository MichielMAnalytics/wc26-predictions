#!/usr/bin/env python3
"""
Generate a localStorage seed for index.html from the model predictions, and inject it
into index.html so the wall-chart opens pre-filled with the model's picks.

- group scores: EV-optimal scoreline per group match (data/predictions/group_matches.csv)
- knockout: every team slot pinned via koManual (display names), and each koScore made
  DECISIVE in favour of the model's advancing team (the sheet advances by score, so draws
  wouldn't propagate). Champion ends up = model's bracket champion.

Writes data/predictions/sheet_seed.json and patches index.html (embeds MODEL_PREDICTIONS,
auto-fills if the sheet is empty, adds a "Fill with model predictions" button).
"""
import csv, json, re, sys
sys.path.insert(0, "model")
from tournament import CODE2TEAM, parse_structure

TEAM2CODE = {v: k for k, v in CODE2TEAM.items()}
html = open("index.html", encoding="utf-8").read()
# parse T: code -> display name
DISP = {}
for m in re.finditer(r"(\w{3}):\['([^']+)','", html):
    DISP[m.group(1)] = m.group(2)
def disp(team):           # dataset name -> sheet display name
    return DISP.get(TEAM2CODE.get(team, ""), team)

groups, ko = parse_structure()

# ---- group scores: match order within each group == GROUPS[g].m order ----
gm = list(csv.DictReader(open("data/predictions/group_matches.csv")))
# group rows preserve file order, which follows group_matches build order == GROUPS order
idx_in_group = {}
groupScores = {}
for r in gm:
    g = r["group"]; i = idx_in_group.get(g, 0); idx_in_group[g] = i + 1
    x, y = r["pred"].split("-")
    groupScores[f"{g}{i}"] = {"h": x, "a": y}

# ---- knockout: pin teams + decisive scores toward the advancer ----
kos = list(csv.DictReader(open("data/predictions/knockout.csv")))
koScores = {}; koManual = {}
for r in kos:
    mid = r["match"]; home = r["home"]; away = r["away"]; adv = r["advances"]
    koManual[f"{mid}:h"] = disp(home)
    koManual[f"{mid}:a"] = disp(away)
    x, y = map(int, r["pred"].split("-"))
    adv_home = (adv == home)
    if x == y:                                   # draw -> give advancer +1
        if adv_home: x = y + 1
        else: y = x + 1
    elif (x > y) != adv_home:                     # decisive but wrong winner -> orient to advancer
        hi, lo = max(x, y), min(x, y)
        x, y = (hi, lo) if adv_home else (lo, hi)
    koScores[mid] = {"h": str(x), "a": str(y)}

seed = {"groupScores": groupScores, "koScores": koScores, "koManual": koManual,
        "name": "Model (Dixon-Coles + market)"}
json.dump(seed, open("data/predictions/sheet_seed.json", "w"), ensure_ascii=False, indent=0)

# ---- inject into index.html ----
blob = "const MODEL_PREDICTIONS = " + json.dumps(seed, ensure_ascii=False) + ";"
# 1) define MODEL_PREDICTIONS + auto-fill-if-empty, right after the state load line
anchor = "const save = ()=>localStorage.setItem(LS, JSON.stringify(state));"
autofill = (anchor + "\n" + blob +
    "\nif(!Object.keys(state.groupScores||{}).length && !Object.keys(state.koScores||{}).length){"
    "state.groupScores=MODEL_PREDICTIONS.groupScores;state.koScores=MODEL_PREDICTIONS.koScores;"
    "state.koManual=MODEL_PREDICTIONS.koManual;if(!state.name)state.name=MODEL_PREDICTIONS.name;save();}")
if "const MODEL_PREDICTIONS" not in html:
    html = html.replace(anchor, autofill, 1)
# 2) a button that (re)applies the model predictions
if "modelBtn" not in html:
    html = html.replace('<button class="btn cyan" id="printBtn">Print / PDF</button>',
        '<button class="btn" id="modelBtn" style="background:#16a34a;color:#fff" title="Fill the whole sheet with the model predictions">⚡ Fill with model</button>\n      <button class="btn cyan" id="printBtn">Print / PDF</button>', 1)
    handler = ("document.getElementById('modelBtn').addEventListener('click', ()=>{"
        "state.groupScores=JSON.parse(JSON.stringify(MODEL_PREDICTIONS.groupScores));"
        "state.koScores=JSON.parse(JSON.stringify(MODEL_PREDICTIONS.koScores));"
        "state.koManual=JSON.parse(JSON.stringify(MODEL_PREDICTIONS.koManual));"
        "if(!state.name)state.name=MODEL_PREDICTIONS.name;save();location.reload();});")
    html = html.replace("document.getElementById('printBtn')", handler + "\ndocument.getElementById('printBtn')", 1)
open("index.html", "w", encoding="utf-8").write(html)

print(f"seed: {len(groupScores)} group scores, {len(koScores)} KO scores, {len(koManual)} pinned teams")
print(f"champion in sheet = FINAL winner: ", end="")
fx, fy = (koScores['FINAL']['h'], koScores['FINAL']['a'])
fr = [r for r in kos if r['match']=='FINAL'][0]
print(fr['advances'], f"({fr['home']} {fx}-{fy} {fr['away']})")
print("index.html patched (auto-fills if empty; '⚡ Fill with model' button added)")
