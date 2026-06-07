#!/usr/bin/env python3
"""
Build DERIVED extra tables for the WC2026 dataset, from the same martj42 spine
as build_dataset.py. Additive only: does not touch the canonical 4-year tables.

Outputs (in ./data):
  - deep_history.csv   one row per match, 8-year window (2018-06-07..2026-06-07),
                       same WC48-involved filter. For rating stability / Elo seeding.
  - h2h.csv            head-to-head record for every pair of WC48 teams that met
                       inside the canonical 4-year window.

Run build_dataset.py first (this reuses the raw pulls it relies on). Stdlib only.
"""
import csv, hashlib
from datetime import date, datetime
from collections import defaultdict

REF_DATE  = date(2026, 6, 7)
START_4Y  = date(2022, 6, 7)   # canonical window (matches build_dataset.py)
START_8Y  = date(2018, 6, 7)   # deep-history window
DATA = "data"

# the 48 WC2026 teams (dataset spellings) — kept in sync with build_dataset.py
WC48 = {
    "Mexico","South Africa","South Korea","Czech Republic","Canada",
    "Bosnia and Herzegovina","Qatar","Switzerland","Brazil","Morocco","Haiti",
    "Scotland","United States","Paraguay","Australia","Turkey","Germany","Curaçao",
    "Ivory Coast","Ecuador","Netherlands","Japan","Sweden","Tunisia","Belgium",
    "Egypt","Iran","New Zealand","Spain","Cape Verde","Saudi Arabia","Uruguay",
    "France","Senegal","Iraq","Norway","Argentina","Algeria","Austria","Jordan",
    "Portugal","DR Congo","Uzbekistan","Colombia","England","Croatia","Ghana","Panama",
}

def parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def is_num(s):     return s not in ("", "NA", None)
def key(d,h,a):    return f"{d}|{h}|{a}"

def comp_type(t):
    tl = t.lower()
    q = "qualification" in tl or "qualifier" in tl
    if "friendly" in tl: return "Friendly"
    if "fifa world cup" in tl: return "WC Qualifier" if q else "World Cup"
    if "nations league" in tl: return "Nations League"
    if any(k in tl for k in ["uefa euro","copa américa","copa america",
                             "african cup of nations","afc asian cup","gold cup",
                             "oceania nations cup","confederations"]):
        return "Continental Qualifier" if q else "Continental Cup"
    return "Other"

# ---------- companion: shootouts ----------
shootouts = {}
with open(f"{DATA}/shootouts_raw.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        shootouts[key(r["date"],r["home_team"],r["away_team"])] = r["winner"]

# ---------- read raw once, build the 8-year deep table ----------
deep = []
with open(f"{DATA}/results_raw.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        d = parse_date(r["date"])
        if d < START_8Y or d > REF_DATE: continue
        if not (is_num(r["home_score"]) and is_num(r["away_score"])): continue
        h, a = r["home_team"], r["away_team"]
        h_wc, a_wc = h in WC48, a in WC48
        if not (h_wc or a_wc): continue
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        k = key(r["date"], h, a)
        so_win = shootouts.get(k, "")
        res = "H" if hs>as_ else ("A" if hs<as_ else "D")
        deep.append({
            "match_id": hashlib.md5(k.encode()).hexdigest()[:10],
            "date": r["date"],
            "days_ago": (REF_DATE-d).days,
            "in_4y_window": "TRUE" if d >= START_4Y else "FALSE",
            "home_team": h, "away_team": a,
            "home_score": hs, "away_score": as_,
            "total_goals": hs+as_, "goal_difference": hs-as_,
            "result": res,
            "went_to_shootout": "TRUE" if so_win else "FALSE",
            "shootout_winner": so_win,
            "tournament": r["tournament"],
            "competition_type": comp_type(r["tournament"]),
            "is_competitive": "FALSE" if comp_type(r["tournament"])=="Friendly" else "TRUE",
            "neutral": "TRUE" if r["neutral"]=="TRUE" else "FALSE",
            "city": r["city"], "country": r["country"],
            "wc26_home": "TRUE" if h_wc else "FALSE",
            "wc26_away": "TRUE" if a_wc else "FALSE",
            "both_wc26": "TRUE" if (h_wc and a_wc) else "FALSE",
        })

deep.sort(key=lambda m:(m["date"], m["home_team"]))
with open(f"{DATA}/deep_history.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(deep[0].keys())); w.writeheader(); w.writerows(deep)

# ---------- head-to-head among WC48 teams, over the canonical 4-year window ----------
# unordered pair key; record from team_a's perspective (team_a < team_b alphabetically)
H = defaultdict(lambda:{"played":0,"a_wins":0,"b_wins":0,"draws":0,
                        "a_gf":0,"a_ga":0,"last_date":"","last_score":"","last_tour":""})
for m in deep:
    if m["in_4y_window"]!="TRUE": continue
    if m["both_wc26"]!="TRUE": continue
    h, a = m["home_team"], m["away_team"]
    ta, tb = sorted([h, a])                  # canonical pair order
    rec = H[(ta, tb)]
    # goals from team_a's perspective
    if h == ta: a_gf, a_ga = m["home_score"], m["away_score"]
    else:       a_gf, a_ga = m["away_score"], m["home_score"]
    rec["played"]+=1; rec["a_gf"]+=a_gf; rec["a_ga"]+=a_ga
    if a_gf>a_ga: rec["a_wins"]+=1
    elif a_gf<a_ga: rec["b_wins"]+=1
    else: rec["draws"]+=1
    # last meeting (deep is date-sorted ascending, so last write wins)
    rec["last_date"]=m["date"]
    rec["last_score"]=f"{h} {m['home_score']}-{m['away_score']} {a}"
    rec["last_tour"]=m["tournament"]

h2h=[]
for (ta,tb),r in sorted(H.items()):
    h2h.append({
        "team_a":ta,"team_b":tb,"played":r["played"],
        "a_wins":r["a_wins"],"draws":r["draws"],"b_wins":r["b_wins"],
        "a_goals":r["a_gf"],"b_goals":r["a_ga"],
        "last_meeting":r["last_date"],"last_score":r["last_score"],
        "last_tournament":r["last_tour"],
    })
with open(f"{DATA}/h2h.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(h2h[0].keys())); w.writeheader(); w.writerows(h2h)

print(f"deep_history.csv: {len(deep)} rows  ({START_8Y}..{REF_DATE})")
print(f"h2h.csv:          {len(h2h)} WC48 pairs that met in {START_4Y}..{REF_DATE}")
