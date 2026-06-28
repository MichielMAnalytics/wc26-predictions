#!/usr/bin/env python3
"""
Pick the top scorers for the KNOCKOUT phase (Scorito asks for 4).

Expected knockout goals per player = scoring propensity (intl rate blended with 2025-26
club form) x team's expected knockout goals/match (retrained Dixon-Coles) x expected
number of knockout matches (from the post-group knockout Monte-Carlo). Only players on
the 32 surviving teams. Writes data/predictions/topscorers_ko.csv + _ko_picks.json.
"""
import csv, json, math
from collections import defaultdict

params = json.load(open("data/model/dc_params.json"))
mean_def = sum(params["def"].values()) / len(params["def"])
def team_lambda(t):
    return math.exp(params["mu"] + params["atk"].get(t, params["atk_other"]) - mean_def)

# surviving teams + expected knockout matches (1 for R32, plus deeper-round reach probs)
kp = {r["team"]: r for r in csv.DictReader(open("data/model/sim_ko_probs.csv"))}
def e_matches(t):
    r = kp.get(t)
    if not r: return 1.0
    return 1.0 + float(r["p_reach_R16"]) + float(r["p_reach_QF"]) + float(r["p_reach_SF"]) + float(r["p_final"])
surviving = set(kp)

# current club form + roster (same blend as the pre-tournament top-scorer model)
club = {}
import os
if os.path.exists("data/club_form_raw.csv"):
    for r in csv.DictReader(open("data/club_form_raw.csv")):
        if str(r["club_goals_2526"]).strip() and str(r["club_apps_2526"]).strip():
            club[r["player"]] = (int(r["club_goals_2526"]), int(r["club_apps_2526"]))
inj = {}
for r in csv.DictReader(open("data/team_injuries.csv")):
    inj[(r["team"], r["player"].split()[-1].lower())] = (r["status"] or "").lower()

roster = [r for r in csv.DictReader(open("data/squad_roster.csv")) if r["team"] in surviving]

def prop(p):
    caps = int(p["caps"]) if p["caps"].isdigit() else 0
    g = int(p["intl_goals"]) if p["intl_goals"].isdigit() else 0
    career = (g + 0.6) / (caps + 5)
    cf = club.get(p["player"])
    if cf and cf[1] >= 3:
        cg, ca = cf; w = min(0.55, ca/45*0.55)
        return (1-w)*career + w*min(1.6, cg/ca)
    return career

# distribute each team's expected knockout goals by player propensity
tw = defaultdict(float); pw = {}
for p in roster:
    st = inj.get((p["team"], p["player"].split()[-1].lower()))
    av = 0.0 if st in ("out","suspended") else (0.5 if st=="doubt" else 1.0)
    age = int(p["age"]) if p["age"].isdigit() else 27
    am = max(0.55, min(1.0, 1-0.05*max(0,age-34)))
    w = prop(p)*av*am; pw[id(p)] = w; tw[p["team"]] += w

rows = []
for p in roster:
    caps = int(p["caps"]) if p["caps"].isdigit() else 0
    if caps < 5 or pw[id(p)] == 0 or tw[p["team"]] == 0: continue
    eg = (pw[id(p)]/tw[p["team"]]) * team_lambda(p["team"]) * e_matches(p["team"])
    rows.append({"player":p["player"],"team":p["team"],"position":p["position"],
                 "exp_ko_goals":round(eg,2)})
rows.sort(key=lambda r:-r["exp_ko_goals"])
with open("data/predictions/topscorers_ko.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

top4 = rows[:4]
print("Top scorers — KNOCKOUT phase (Scorito: pick 4):")
for i,r in enumerate(top4,1): print(f"  {i}. {r['player']} ({r['team']}, {r['position']}) — {r['exp_ko_goals']} xG")
print("\nnext few:")
for r in rows[4:9]: print(f"   {r['player']} ({r['team']}) {r['exp_ko_goals']}")

# bundle R32 game predictions + the 4 picks for the page/report
r32 = [{"home":r["home"],"away":r["away"],"pred":r["pred"]} for r in csv.DictReader(open("data/predictions/r32_predictions.csv"))]
json.dump({"r32":r32, "top4":[{"player":r["player"],"team":r["team"],"pos":r["position"]} for r in top4]},
          open("data/predictions/_ko_picks.json","w"), ensure_ascii=False)
