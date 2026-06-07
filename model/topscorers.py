#!/usr/bin/env python3
"""
Top-scorer prediction.

Expected tournament goals per player =
    player's share of his team's international goals (lightly shrunk)
  × team's expected goals per match (Dixon-Coles attack, injury+market adjusted)
  × team's expected number of matches (from the Monte-Carlo: deeper runs => more games)

Outputs data/predictions/topscorers.csv with:
  - exp_goals   -> the Golden Boot ranking (who scores most goals)
  - scorito_ev  -> exp_goals × Scorito position weight (FW 8 / MF 16 / DF·GK 32 per goal),
                   i.e. the best picks for Scorito's position-weighted top-scorer game

Injured/withdrawn players are already absent from the announced 26-man squads, so they
can't be picked. Requires the model params, sim probs, adjustments. stdlib + json.
"""
import csv, json, math, os
from collections import defaultdict

POS_W = {"FW": 8, "MF": 16, "DF": 32, "GK": 32}     # Scorito group-stage points per goal

params = json.load(open("data/model/dc_params.json"))
adj = {}
if os.path.exists("data/model/adjustments.csv"):
    adj = {r["team"]: (float(r["d_atk"]), float(r["d_def"]))
           for r in csv.DictReader(open("data/model/adjustments.csv"))}
sim = {r["team"]: r for r in csv.DictReader(open("data/model/sim_team_probs.csv"))}
roster = list(csv.DictReader(open("data/squad_roster.csv")))

# injury status by (team, surname) — downweight doubts, exclude out/suspended
def _last(s): return s.strip().split()[-1].lower() if s.strip() else ""
status = {}
if os.path.exists("data/team_injuries.csv"):
    for r in csv.DictReader(open("data/team_injuries.csv")):
        status[(r["team"], _last(r["player"]))] = (r["status"] or "").lower()
def avail_mult(p):
    st = status.get((p["team"], _last(p["player"])))
    if st in ("out", "suspended"): return 0.0
    if st == "doubt": return 0.5
    return 1.0

mean_def = sum(params["def"].values()) / len(params["def"])

def team_lambda(team):
    a = params["atk"].get(team, params["atk_other"]) + adj.get(team, (0, 0))[0]
    return math.exp(params["mu"] + a - mean_def)        # exp goals/match vs an average side (neutral)

def exp_matches(team):
    r = sim.get(team)
    if not r: return 3.0
    return 3.0 + float(r["p_advance_R32"]) + float(r["p_reach_R16"]) + \
           float(r["p_reach_QF"]) + float(r["p_reach_SF"]) + float(r["p_final"])

# team goal "mass": sum of squad international goals (the denominator for shares)
mass = defaultdict(float)
for p in roster:
    if p["intl_goals"].isdigit(): mass[p["team"]] += int(p["intl_goals"])

rows = []
for p in roster:
    team = p["team"]; pos = p["position"]
    caps = int(p["caps"]) if p["caps"].isdigit() else 0
    g = int(p["intl_goals"]) if p["intl_goals"].isdigit() else 0
    if caps < 5: continue                               # too little signal
    # share of team goals, lightly shrunk toward the squad-average share
    n = sum(1 for q in roster if q["team"] == team)
    share = (g + 0.5) / (mass[team] + 0.5 * n)          # additive-smoothed share
    av = avail_mult(p)
    if av == 0.0: continue                              # ruled out / suspended
    age = int(p["age"]) if p["age"].isdigit() else 27
    age_mult = max(0.4, min(1.0, 1 - 0.06*max(0, age-32)))   # output declines past ~32
    tl, em = team_lambda(team), exp_matches(team)
    team_total = tl * em                                # expected team goals over the tournament
    exp_goals = share * team_total * av * age_mult      # doubts ×0.5, veterans decayed
    rows.append({
        "player": p["player"], "team": team, "position": pos,
        "caps": caps, "intl_goals": g,
        "exp_matches": round(em, 2), "team_xg_per_match": round(tl, 2),
        "exp_goals": round(exp_goals, 2),
        "scorito_ev": round(exp_goals * POS_W.get(pos, 8), 1),
    })

rows.sort(key=lambda r: -r["exp_goals"])
with open("data/predictions/topscorers.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

print(f"topscorers.csv: {len(rows)} players")
print("\n=== GOLDEN BOOT (most goals) ===")
for r in rows[:12]:
    print(f"  {r['exp_goals']:.2f}  {r['player']:22s} {r['team']:13s} {r['position']} ({r['intl_goals']}g/{r['caps']}c)")
print("\n=== SCORITO top-scorer picks (goals × position weight) ===")
for r in sorted(rows, key=lambda r:-r["scorito_ev"])[:12]:
    print(f"  ev {r['scorito_ev']:5.1f}  {r['player']:22s} {r['team']:13s} {r['position']} (exp {r['exp_goals']:.2f}g)")

# summary for the report / page
summ = {
    "golden_boot": [{"player": r["player"], "team": r["team"], "pos": r["position"],
                     "exp_goals": r["exp_goals"]} for r in rows[:10]],
    "scorito": [{"player": r["player"], "team": r["team"], "pos": r["position"],
                 "ev": r["scorito_ev"]} for r in sorted(rows, key=lambda r:-r["scorito_ev"])[:10]],
}
json.dump(summ, open("data/predictions/_topscorers.json", "w"), ensure_ascii=False)
