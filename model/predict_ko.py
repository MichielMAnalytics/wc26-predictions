#!/usr/bin/env python3
"""
Re-predict the knockout phase AFTER the group stage, using:
  - the ACTUAL group results (now in results_raw.csv) to set the real bracket, and
  - the RETRAINED Dixon-Coles model (refit on data incl. the group stage).

Cross-checks the resolved Round-of-32 against ESPN's actual matchups. Predicts every
KO match (EV-optimal scoreline + advancing team by model win prob) through the champion.
Writes data/predictions/knockout.csv and group_standings_actual.csv.
"""
import csv, json, sys
from datetime import date, datetime
from collections import defaultdict
sys.path.insert(0, "model")
import dc as DC, tournament as T
from scorito import optimal_pick

GROUP_START, GROUP_END = date(2026,6,11), date(2026,6,27)
params = json.load(open("data/model/dc_params.json"))
groups, ko = T.parse_structure()

# ---- actual group results from results_raw ----
def pd(s): return datetime.strptime(s,"%Y-%m-%d").date()
actual = {}
for r in csv.DictReader(open("data/results_raw.csv", encoding="utf-8")):
    if r["tournament"] != "FIFA World Cup": continue
    if r["home_score"] in ("","NA"): continue
    d = pd(r["date"])
    if not (GROUP_START <= d <= GROUP_END): continue
    actual[frozenset((r["home_team"], r["away_team"]))] = (r["home_team"], int(r["home_score"]), int(r["away_score"]))

# ---- standings per group (pts, GD, GF tiebreak) ----
pos = {}; third_info = {}; third_group = {}; standings_rows = []
for g, gd in groups.items():
    tab = {t:{"pts":0,"gf":0,"ga":0} for t in gd["teams"]}
    for home, away in gd["matches"]:
        rec = actual.get(frozenset((home, away)))
        if not rec: continue
        hh, hs, as_ = rec
        a, b = (home, away)
        # rec is oriented (home_team, hs, as_); map to a/b
        if hh == a: ga_, gb = hs, as_
        else:       ga_, gb = as_, hs
        tab[a]["gf"]+=ga_; tab[a]["ga"]+=gb; tab[b]["gf"]+=gb; tab[b]["ga"]+=ga_
        if ga_>gb: tab[a]["pts"]+=3
        elif gb>ga_: tab[b]["pts"]+=3
        else: tab[a]["pts"]+=1; tab[b]["pts"]+=1
    rank = sorted(gd["teams"], key=lambda t:(tab[t]["pts"], tab[t]["gf"]-tab[t]["ga"], tab[t]["gf"]), reverse=True)
    for i,t in enumerate(rank,1):
        pos[f"{i}{g}"] = t
        standings_rows.append({"group":g,"position":i,"team":t,"pts":tab[t]["pts"],
                               "gd":tab[t]["gf"]-tab[t]["ga"],"gf":tab[t]["gf"]})
    third_info[rank[2]] = (tab[rank[2]]["pts"], tab[rank[2]]["gf"]-tab[rank[2]]["ga"], tab[rank[2]]["gf"])
    third_group[rank[2]] = g

# ---- ACTUAL R32 matchups from ESPN (ground truth) ----
ALIAS={"BIH":"BOS","CIV":"IVC","COD":"DRC","CUW":"CUR","KSA":"SAU","MAR":"MOR","SUI":"SWI"}
CODES=set(T.CODE2TEAM)
def code(ab): ab=ab.upper(); return ALIAS.get(ab, ab if ab in CODES else None)
espn_pairs=[]
ej=json.load(open("data/results_2026/espn_ko.json"))
for e in ej["events"]:
    if not ("2026-06-28" <= e["date"][:10] <= "2026-07-04"): continue   # R32 spans through Jul 4
    c=e["competitions"][0]; cs=c["competitors"]
    h=code(next(x for x in cs if x["homeAway"]=="home")["team"]["abbreviation"])
    a=code(next(x for x in cs if x["homeAway"]=="away")["team"]["abbreviation"])
    if not h or not a: continue                                          # skip 'RD32 vs RD32' R16 placeholders
    espn_pairs.append((T.CODE2TEAM[h], T.CODE2TEAM[a]))
def find_opp(team):
    for a,b in espn_pairs:
        if a==team: return b
        if b==team: return a
    return None

# Assign each index.html R32 slot its ACTUAL matchup, anchored on the group
# winner/runner-up side (1X/2X positions are reliable; only the 8th-best third differed).
r32_teams={}
for sid,k in ko.items():
    if not sid.startswith("R32-"): continue
    if not k["h"].startswith("3:"):
        home = pos[k["h"]]; away = find_opp(home)
    else:
        away = pos[k["a"]]; home = find_opp(away)
    r32_teams[sid] = (home, away)
resolved_set={frozenset(v) for v in r32_teams.values()}
print(f"R32 vs ESPN actual: {len(resolved_set & {frozenset(p) for p in espn_pairs})}/16 matchups aligned")

# ---- predict knockouts with the retrained model ----
def pick(a,b):
    h,aw,neu=T.neutral_sides(a,b); M=DC.score_matrix(params,h,aw,neu)
    (pi,pj),_=optimal_pick(M,"group"); pH,pD,pA=DC.outcome_probs(M)
    return ((pi,pj),(pH,pD,pA)) if h==a else ((pj,pi),(pA,pD,pH))

ko_rows=[]; winners={}; losers={}
order=[k for k in ko if k.startswith("R32")]+[k for k in ko if k.startswith("R16")]+\
      [k for k in ko if k.startswith("QF")]+[k for k in ko if k.startswith("SF")]+["TP","FINAL"]
RLAB={"r32":"R32","r16":"R16","qf":"QF","sf":"SF","final":"final","tp":"3rd place"}
def resolve(ref):
    if ref.startswith("W:"): return winners.get(ref[2:])
    if ref.startswith("L:"): return losers.get(ref[2:])
    return None
for sid in order:
    if sid not in ko: continue
    k=ko[sid]
    if sid.startswith("R32-"): a,b = r32_teams[sid]            # actual matchup
    else: a=resolve(k["h"]); b=resolve(k["a"])                 # winners propagate via the tree
    if not a or not b: continue
    (sa,sb),(pa,pdr,pb)=pick(a,b)
    adv = a if pa>=pb else b
    winners[sid]=adv; losers[sid]= b if adv==a else a
    ko_rows.append({"match":sid,"round":RLAB[k["round"]],"home":a,"away":b,
                    "pred":f"{sa}-{sb}","advances":adv,
                    "p_home":round(pa,3),"p_draw":round(pdr,3),"p_away":round(pb,3)})

with open("data/predictions/knockout.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(ko_rows[0].keys())); w.writeheader(); w.writerows(ko_rows)
with open("data/predictions/group_standings_actual.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(standings_rows[0].keys())); w.writeheader(); w.writerows(standings_rows)

# persist the actual R32 bracket + champion summary for the sim / report
json.dump({sid:list(v) for sid,v in r32_teams.items()}, open("data/predictions/r32_actual.json","w"))
try:
    summ=json.load(open("data/predictions/_summary.json"))
except Exception:
    summ={}
summ.update({"champion":winners.get("FINAL"), "runner":losers.get("FINAL"), "third":winners.get("TP")})
json.dump(summ, open("data/predictions/_summary.json","w"), ensure_ascii=False)

print(f"\nChampion: {winners.get('FINAL')} | Runner-up: {losers.get('FINAL')} | 3rd: {winners.get('TP')}")
print("R32 picks:")
for r in ko_rows:
    if r["round"]=="R32": print(f"  {r['home']:13s} {r['pred']} {r['away']:13s} -> {r['advances']}")
