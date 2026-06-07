#!/usr/bin/env python3
"""
Bounded availability/form adjustment layer — folds the Part 2 research (injuries,
momentum) into the goals model as small, transparent nudges to each team's attack
and defence (log-space). This is the edge over pure-results entrants. Magnitudes are
deliberately conservative and capped; it cannot be backtested (Part 2 is a current
snapshot), so it stays a disciplined prior, not a free parameter.

Rules (all capped to +/-0.20 total per team per channel):
  attack:
    - a FW/MF ruled OUT costs attack in proportion to his share of the squad's
      international goals (capped per player), x0.5 if only a 'doubt'
    - an OUT/doubt attacker we can't match to the roster -> small generic penalty
    - momentum rising +0.03, declining -0.03
  defence:
    - a DF/GK ruled OUT with >=30 caps (a regular) costs defence a flat amount,
      x0.5 if a doubt

Output: data/model/adjustments.csv (team, d_atk, d_def, notes). Importable: load_adjustments().
"""
import csv, math
from collections import defaultdict

CAP = 0.20
ATT_OUT_MAX = 0.10     # max attack hit from a single key forward out
DEF_OUT = 0.05         # defence hit for a key defender/GK out
GEN_OUT = 0.03         # generic attack hit for an unmatched out attacker
MOM = {"rising": 0.03, "declining": -0.03, "steady": 0.0}

def _last(name): return name.strip().split()[-1].lower() if name.strip() else ""

def build():
    roster = list(csv.DictReader(open("data/squad_roster.csv", encoding="utf-8")))
    by_team = defaultdict(list)
    for r in roster: by_team[r["team"]].append(r)
    goal_mass = {}
    for t, ps in by_team.items():
        goal_mass[t] = sum(int(p["intl_goals"]) for p in ps
                           if p["position"] in ("FW","MF") and p["intl_goals"].isdigit()) or 1
    state = {r["team"]: r for r in csv.DictReader(open("data/team_state.csv", encoding="utf-8"))}
    inj = list(csv.DictReader(open("data/team_injuries.csv", encoding="utf-8")))

    d_atk = defaultdict(float); d_def = defaultdict(float); notes = defaultdict(list)
    for row in inj:
        t = row["team"]; status = (row["status"] or "").lower()
        if status not in ("out", "doubt", "suspended"): continue
        definite = status in ("out", "suspended")
        w = 1.0 if definite else 0.25          # doubts barely count (minor knocks, often play)
        ln = _last(row["player"])
        match = next((p for p in by_team.get(t, []) if _last(p["player"]) == ln and ln), None)
        if match:
            pos = match["position"]; g = int(match["intl_goals"]) if match["intl_goals"].isdigit() else 0
            caps = int(match["caps"]) if match["caps"].isdigit() else 0
            if pos in ("FW", "MF"):
                hit = min(ATT_OUT_MAX, 0.30 * g / goal_mass[t]) * w
                d_atk[t] -= hit; notes[t].append(f"-atk {row['player']}({pos},{g}g) {hit:.02f}")
            elif definite and caps >= 30:       # only a definite-out regular defender/GK
                d_def[t] -= DEF_OUT; notes[t].append(f"-def {row['player']}({pos}) {DEF_OUT:.02f}")
        elif definite:                          # unmatched & definitely out -> likely a key attacker
            d_atk[t] -= GEN_OUT; notes[t].append(f"-atk {row['player']}(out,unmatched) {GEN_OUT:.02f}")

    rows = []
    for t in sorted(by_team):
        da = d_atk[t] + MOM.get(state.get(t, {}).get("momentum", "steady"), 0.0)
        dd = d_def[t]
        if state.get(t, {}).get("momentum") in MOM and MOM[state[t]["momentum"]]:
            notes[t].append(f"momentum {state[t]['momentum']}")
        da = max(-CAP, min(CAP, da)); dd = max(-CAP, min(CAP, dd))
        rows.append({"team": t, "d_atk": round(da, 3), "d_def": round(dd, 3),
                     "notes": "; ".join(notes[t])})
    with open("data/model/adjustments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team","d_atk","d_def","notes"]); w.writeheader(); w.writerows(rows)
    return rows

def load_adjustments(path="data/model/adjustments.csv"):
    try:
        return {r["team"]: (float(r["d_atk"]), float(r["d_def"]))
                for r in csv.DictReader(open(path, encoding="utf-8"))}
    except FileNotFoundError:
        return {}

if __name__ == "__main__":
    rows = build()
    rows.sort(key=lambda r: r["d_atk"]+r["d_def"])
    print(f"adjustments.csv: {len(rows)} teams")
    print("\nmost-penalised:")
    for r in rows[:10]:
        if r["d_atk"] or r["d_def"]: print(f"  {r['team']:14s} d_atk {r['d_atk']:+.2f} d_def {r['d_def']:+.2f} | {r['notes']}")
    print("\nmost-boosted:")
    for r in rows[-5:]:
        if r["d_atk"] or r["d_def"]: print(f"  {r['team']:14s} d_atk {r['d_atk']:+.2f} d_def {r['d_def']:+.2f} | {r['notes']}")
