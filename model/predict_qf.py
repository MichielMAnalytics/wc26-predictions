#!/usr/bin/env python3
"""
Predict the quarter-finals from the ACTUAL bracket (ESPN), using the model retrained
through the Round of 16. Also picks the QF-phase top scorers (surviving 8 teams).
Writes data/predictions/qf_predictions.csv, qf_topscorers.csv, _qf_picks.json.
"""
import csv, json, math, sys
from collections import defaultdict
sys.path.insert(0, "model")
import dc as DC, tournament as T
from scorito import optimal_pick

params = json.load(open("data/model/dc_params.json"))
ALIAS={"BIH":"BOS","CIV":"IVC","COD":"DRC","CUW":"CUR","KSA":"SAU","MAR":"MOR","SUI":"SWI"}
CODES=set(T.CODE2TEAM)
def code(ab): ab=ab.upper(); return ALIAS.get(ab, ab if ab in CODES else None)

# actual QF fixtures from ESPN (Jul 9-12, 'pre', real team names)
ej=json.load(open("data/results_2026/espn_ko2.json"))
qf=[]
for e in ej["events"]:
    if not ("2026-07-09" <= e["date"][:10] <= "2026-07-12"): continue
    c=e["competitions"][0]; cs=c["competitors"]
    h=code(next(x for x in cs if x["homeAway"]=="home")["team"]["abbreviation"])
    a=code(next(x for x in cs if x["homeAway"]=="away")["team"]["abbreviation"])
    if not h or not a: continue
    qf.append((T.CODE2TEAM[h], T.CODE2TEAM[a], e["date"][:10]))

def pick(a,b):
    h,aw,neu=T.neutral_sides(a,b); M=DC.score_matrix(params,h,aw,neu)
    (pi,pj),_=optimal_pick(M,"group"); pH,pD,pA=DC.outcome_probs(M)
    return ((pi,pj),(pH,pD,pA)) if h==a else ((pj,pi),(pA,pD,pH))

rows=[]
print("QUARTER-FINALS — predicted scores (model retrained through R16):")
for a,b,dt in qf:
    (sa,sb),(pa,pd,pb)=pick(a,b)
    adv=a if pa>=pb else b
    rows.append({"date":dt,"home":a,"away":b,"pred":f"{sa}-{sb}","advances":adv,
                 "p_home":round(pa,3),"p_draw":round(pd,3),"p_away":round(pb,3)})
    print(f"  {dt}  {a} {sa}-{sb} {b}  -> {adv}  (W/D/L {pa:.0%}/{pd:.0%}/{pb:.0%})")
with open("data/predictions/qf_predictions.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---- QF top scorers: surviving 8 teams, ~1.5 expected QF+ matches per team via win prob ----
surviving=set()
for a,b,_ in qf: surviving.add(a); surviving.add(b)
mean_def=sum(params["def"].values())/len(params["def"])
def tl(t): return math.exp(params["mu"]+params["atk"].get(t,params["atk_other"])-mean_def)
# expected remaining matches ~ 1 (QF) + P(win QF)*... approx by win prob vs field
advp={}
for r in rows:
    advp[r["home"]]=r["p_home"]; advp[r["away"]]=r["p_away"]
def ematch(t): return 1 + 1.6*advp.get(t,0.3)   # QF + partial SF/final

club={}
import os
if os.path.exists("data/club_form_raw.csv"):
    for r in csv.DictReader(open("data/club_form_raw.csv")):
        if str(r["club_goals_2526"]).strip() and str(r["club_apps_2526"]).strip():
            club[r["player"]]=(int(r["club_goals_2526"]),int(r["club_apps_2526"]))
inj={(r["team"],r["player"].split()[-1].lower()):(r["status"] or "").lower() for r in csv.DictReader(open("data/team_injuries.csv"))}
roster=[r for r in csv.DictReader(open("data/squad_roster.csv")) if r["team"] in surviving]
def prop(p):
    caps=int(p["caps"]) if p["caps"].isdigit() else 0; g=int(p["intl_goals"]) if p["intl_goals"].isdigit() else 0
    career=(g+0.6)/(caps+5); cf=club.get(p["player"])
    if cf and cf[1]>=3:
        cg,ca=cf; w=min(0.55,ca/45*0.55); return (1-w)*career+w*min(1.6,cg/ca)
    return career
tw=defaultdict(float); pw={}
for p in roster:
    st=inj.get((p["team"],p["player"].split()[-1].lower()))
    av=0.0 if st in ("out","suspended") else (0.5 if st=="doubt" else 1.0)
    age=int(p["age"]) if p["age"].isdigit() else 27; am=max(0.55,min(1.0,1-0.05*max(0,age-34)))
    w=prop(p)*av*am; pw[id(p)]=w; tw[p["team"]]+=w
ts=[]
for p in roster:
    caps=int(p["caps"]) if p["caps"].isdigit() else 0
    if caps<5 or pw[id(p)]==0 or tw[p["team"]]==0: continue
    eg=(pw[id(p)]/tw[p["team"]])*tl(p["team"])*ematch(p["team"])
    ts.append({"player":p["player"],"team":p["team"],"position":p["position"],"exp_qf_goals":round(eg,2)})
ts.sort(key=lambda r:-r["exp_qf_goals"])
with open("data/predictions/qf_topscorers.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(ts[0].keys())); w.writeheader(); w.writerows(ts)
print("\nQF top scorers (pick 4):")
for i,r in enumerate(ts[:4],1): print(f"  {i}. {r['player']} ({r['team']}, {r['position']}) — {r['exp_qf_goals']}")
print("  next:", ", ".join(f"{r['player']} ({r['team']})" for r in ts[4:8]))

json.dump({"qf":[{"home":r["home"],"away":r["away"],"pred":r["pred"],"advances":r["advances"]} for r in rows],
           "top4":[{"player":r["player"],"team":r["team"],"pos":r["position"]} for r in ts[:4]]},
          open("data/predictions/_qf_picks.json","w"), ensure_ascii=False)
