#!/usr/bin/env python3
"""
Generate the Scorito WK 2026 submission: EV-optimal predicted scoreline for every
match (group + knockouts), predicted group standings, a filled bracket through to the
champion, and topscorer suggestions.

EV-optimal pick maximises 30*P(outcome)+15*P(exact) (group); since Scorito's exact:toto
ratio is 1.5 in every round, the optimal scoreline is round-invariant.

Outputs: data/predictions/{group_matches,group_standings,knockout}.csv and
SCORITO_PREDICTIONS.md. Requires numpy.
"""
import sys, csv, os
import numpy as np
sys.path.insert(0, "model")
import dc as DC, tournament as T
from scorito import optimal_pick, outcome
from adjust import load_adjustments

os.makedirs("data/predictions", exist_ok=True)
params = T.load_params()
groups, ko = T.parse_structure()
elo = {r["team"]: float(r["elo"]) for r in csv.DictReader(open("data/model/ratings.csv"))}
ADJ = load_adjustments()
T.ADJ = ADJ
print(f"availability/form adjustments: {'ON' if ADJ else 'OFF'}")

def pick(a, b):
    """EV-optimal scoreline + probs for a (home) vs b, applying host advantage."""
    h, aw, neu = T.neutral_sides(a, b)
    M = DC.score_matrix(params, h, aw, neu, adj=ADJ)
    (pi, pj), ev = optimal_pick(M, "group")
    pH, pD, pA = DC.outcome_probs(M)
    if h == a:  # M is in (h=a) orientation
        return (pi, pj), (pH, pD, pA), ev
    else:       # flip to (a,b) orientation
        return (pj, pi), (pA, pD, pH), ev

# ---------- group matches ----------
gm_rows = []
for g, gd in groups.items():
    for a, b in gd["matches"]:
        (sa, sb), (pa, pd, pb), ev = pick(a, b)
        gm_rows.append({"group":g,"home":a,"away":b,"pred":f"{sa}-{sb}",
                        "p_home":round(pa,3),"p_draw":round(pd,3),"p_away":round(pb,3),
                        "exp_points":round(ev,2)})
with open("data/predictions/group_matches.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(gm_rows[0].keys())); w.writeheader(); w.writerows(gm_rows)

# ---------- predicted standings from predicted scores ----------
def predicted_table(g):
    gd = groups[g]; teams = gd["teams"]
    pts={t:0 for t in teams}; gf={t:0 for t in teams}; ga={t:0 for t in teams}
    for a,b in gd["matches"]:
        (sa,sb),_,_ = pick(a,b)
        gf[a]+=sa; ga[a]+=sb; gf[b]+=sb; ga[b]+=sa
        if sa>sb: pts[a]+=3
        elif sb>sa: pts[b]+=3
        else: pts[a]+=1; pts[b]+=1
    rank=sorted(teams,key=lambda t:(pts[t],gf[t]-ga[t],gf[t],elo.get(t,1500)),reverse=True)
    return rank,{t:(pts[t],gf[t]-ga[t],gf[t]) for t in teams}

pos={}; third_info={}; third_group={}; st_rows=[]
for g in groups:
    rank,info=predicted_table(g)
    for i,t in enumerate(rank,1):
        pos[f"{i}{g}"]=t
        st_rows.append({"group":g,"position":i,"team":t,"pts":info[t][0],"gd":info[t][1],"gf":info[t][2]})
    third_info[rank[2]]=info[rank[2]]; third_group[rank[2]]=g
with open("data/predictions/group_standings.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(st_rows[0].keys())); w.writeheader(); w.writerows(st_rows)

# best 8 thirds (deterministic: by pts, gd, gf, elo)
thirds=sorted(third_info,key=lambda t:(third_info[t][0],third_info[t][1],third_info[t][2],elo.get(t,1500)),reverse=True)
qual_thirds=thirds[:8]
third_slots=[(sid,k["a"][2:]) for sid,k in ko.items() if k["a"].startswith("3:")]
# deterministic assignment via backtracking (reuse sim's matcher with a dummy rng)
class _R:                       # deterministic tiebreak shim
    def random(self): return 0.0
third_assign=T.assign_thirds(third_slots,qual_thirds,third_group,_R())

# ---------- knockouts: fill bracket, predict score + advancing team ----------
ko_rows=[]; winners={}; losers={}
order=[k for k in ko if k.startswith("R32")]+[k for k in ko if k.startswith("R16")]+\
      [k for k in ko if k.startswith("QF")]+[k for k in ko if k.startswith("SF")]+["TP","FINAL"]
def resolve(ref, sid):
    if ref.startswith("3:"): return third_assign.get(sid)
    if ref.startswith("W:"): return winners.get(ref[2:])
    if ref.startswith("L:"): return losers.get(ref[2:])
    return pos.get(ref)
RLAB={"r32":"R32","r16":"R16","qf":"QF","sf":"SF","final":"final","tp":"3rd place"}
for sid in order:
    if sid not in ko: continue
    k=ko[sid]; a=resolve(k["h"],sid); b=resolve(k["a"],sid)
    if not a or not b: continue
    (sa,sb),(pa,pd,pb),ev=pick(a,b)
    # advancing team = higher regulation win prob (pens don't count for score)
    adv = a if pa>=pb else b
    winners[sid]=adv; losers[sid]= b if adv==a else a
    ko_rows.append({"match":sid,"round":RLAB[k["round"]],"home":a,"away":b,
                    "pred":f"{sa}-{sb}","advances":adv,
                    "p_home":round(pa,3),"p_draw":round(pd,3),"p_away":round(pb,3)})
with open("data/predictions/knockout.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(ko_rows[0].keys())); w.writeheader(); w.writerows(ko_rows)

champion=winners.get("FINAL"); runner=losers.get("FINAL")
third=winners.get("TP")

# ---------- topscorer suggestions (heuristic) ----------
sim={r["team"]:float(r["p_reach_SF"]) for r in csv.DictReader(open("data/model/sim_team_probs.csv"))} \
    if os.path.exists("data/model/sim_team_probs.csv") else {}
roster=list(csv.DictReader(open("data/squad_roster.csv")))
ts=[]
for r in roster:
    try: caps=int(r["caps"]); g=int(r["intl_goals"])
    except: continue
    if caps<10 or r["position"] not in ("FW","MF"): continue
    rate=g/caps
    deep=sim.get(r["team"],0.1)+0.05
    ts.append((rate*deep, r["player"], r["team"], r["position"], g, caps))
ts.sort(reverse=True)

print(f"Champion pick: {champion}  | Runner-up: {runner}  | 3rd: {third}")
print(f"group_matches.csv ({len(gm_rows)}), group_standings.csv ({len(st_rows)}), knockout.csv ({len(ko_rows)})")
print("top topscorer suggestions:")
for s in ts[:8]: print(f"  {s[1]} ({s[2]}, {s[3]}) {s[4]}g/{s[5]}c")

# expose for the markdown writer
import json
json.dump({"champion":champion,"runner":runner,"third":third,
           "topscorers":[{"player":s[1],"team":s[2],"pos":s[3]} for s in ts[:12]]},
          open("data/predictions/_summary.json","w"))
