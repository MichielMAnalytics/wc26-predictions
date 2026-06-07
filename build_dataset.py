#!/usr/bin/env python3
"""
Build the WC2026 historical-form dataset.

Source: martj42/international_results (results.csv, goalscorers.csv, shootouts.csv)
        https://github.com/martj42/international_results  (open data, attribution kept)

Output (in ./data):
  - matches.csv          one row per match (canonical), richly annotated
  - team_match_log.csv   one row per WC26 team per match (long / model-ready)
  - team_summary.csv     per-team aggregate over the window (quick sanity + features)

Window: REF_DATE - 4 years  ..  REF_DATE   (inclusive), played matches only.
"""
import csv, hashlib, json
from datetime import date, datetime
from collections import defaultdict

REF_DATE = date(2026, 6, 7)          # "today" per the brief (7 June 2026)
START    = date(2022, 6, 7)          # 4 years back
DATA = "data"

# ---- the 48 WC2026 teams, mapped to EXACT dataset spellings (verified) ----
# left = dataset name, right = display name on the wall chart
WC48 = {
    "Mexico":"Mexico", "South Africa":"South Africa", "South Korea":"South Korea",
    "Czech Republic":"Czechia", "Canada":"Canada", "Bosnia and Herzegovina":"Bosnia & Herzegovina",
    "Qatar":"Qatar", "Switzerland":"Switzerland", "Brazil":"Brazil", "Morocco":"Morocco",
    "Haiti":"Haiti", "Scotland":"Scotland", "United States":"USA", "Paraguay":"Paraguay",
    "Australia":"Australia", "Turkey":"Türkiye", "Germany":"Germany", "Curaçao":"Curaçao",
    "Ivory Coast":"Ivory Coast", "Ecuador":"Ecuador", "Netherlands":"Netherlands", "Japan":"Japan",
    "Sweden":"Sweden", "Tunisia":"Tunisia", "Belgium":"Belgium", "Egypt":"Egypt", "Iran":"Iran",
    "New Zealand":"New Zealand", "Spain":"Spain", "Cape Verde":"Cape Verde", "Saudi Arabia":"Saudi Arabia",
    "Uruguay":"Uruguay", "France":"France", "Senegal":"Senegal", "Iraq":"Iraq", "Norway":"Norway",
    "Argentina":"Argentina", "Algeria":"Algeria", "Austria":"Austria", "Jordan":"Jordan",
    "Portugal":"Portugal", "DR Congo":"DR Congo", "Uzbekistan":"Uzbekistan", "Colombia":"Colombia",
    "England":"England", "Croatia":"Croatia", "Ghana":"Ghana", "Panama":"Panama",
}
WC_GROUP = {  # which 2026 group each team is in (handy feature)
 "Mexico":"A","South Africa":"A","South Korea":"A","Czech Republic":"A",
 "Canada":"B","Bosnia and Herzegovina":"B","Qatar":"B","Switzerland":"B",
 "Brazil":"C","Morocco":"C","Haiti":"C","Scotland":"C",
 "United States":"D","Paraguay":"D","Australia":"D","Turkey":"D",
 "Germany":"E","Curaçao":"E","Ivory Coast":"E","Ecuador":"E",
 "Netherlands":"F","Japan":"F","Sweden":"F","Tunisia":"F",
 "Belgium":"G","Egypt":"G","Iran":"G","New Zealand":"G",
 "Spain":"H","Cape Verde":"H","Saudi Arabia":"H","Uruguay":"H",
 "France":"I","Senegal":"I","Iraq":"I","Norway":"I",
 "Argentina":"J","Algeria":"J","Austria":"J","Jordan":"J",
 "Portugal":"K","DR Congo":"K","Uzbekistan":"K","Colombia":"K",
 "England":"L","Croatia":"L","Ghana":"L","Panama":"L",
}

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def is_num(s):
    return s not in ("", "NA", None)

def comp_type(t):
    """Bucket the tournament string into a coarse competition type."""
    tl = t.lower()
    q = "qualification" in tl or "qualifier" in tl
    if "friendly" in tl: return "Friendly"
    if "fifa world cup" in tl:
        return "WC Qualifier" if q else "World Cup"
    if "nations league" in tl: return "Nations League"
    if any(k in tl for k in ["uefa euro","copa américa","copa america","african cup of nations",
                             "afc asian cup","gold cup","oceania nations cup","confederations"]):
        return "Continental Qualifier" if q else "Continental Cup"
    return "Other"

# ---------- load companion tables ----------
def key(d,h,a): return f"{d}|{h}|{a}"

shootouts = {}
with open(f"{DATA}/shootouts_raw.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        shootouts[key(r["date"],r["home_team"],r["away_team"])] = r["winner"]

scorers = defaultdict(lambda: defaultdict(list))  # key -> team -> ["Name 23' (pen)"]
with open(f"{DATA}/goalscorers_raw.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        k = key(r["date"],r["home_team"],r["away_team"])
        tag = r["scorer"] or "?"
        mn  = r["minute"]
        suffix = ""
        if r["penalty"]=="TRUE": suffix+=" (pen)"
        if r["own_goal"]=="TRUE": suffix+=" (og)"
        label = f"{tag} {mn}'{suffix}".strip() if is_num(mn) else f"{tag}{suffix}".strip()
        scorers[k][r["team"]].append(label)

# ---------- main filter + build matches.csv ----------
matches = []
with open(f"{DATA}/results_raw.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        d = parse_date(r["date"])
        if d < START or d > REF_DATE: continue
        if not (is_num(r["home_score"]) and is_num(r["away_score"])): continue   # played only
        h, a = r["home_team"], r["away_team"]
        h_wc, a_wc = h in WC48, a in WC48
        if not (h_wc or a_wc): continue
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        k = key(r["date"], h, a)
        so_win = shootouts.get(k, "")
        if hs>as_: res, winner, loser = "H", h, a
        elif hs<as_: res, winner, loser = "A", a, h
        else: res, winner, loser = "D", (so_win or "Draw"), ""
        neutral = r["neutral"]=="TRUE"
        mid = hashlib.md5(k.encode()).hexdigest()[:10]
        matches.append({
            "match_id": mid,
            "date": r["date"],
            "days_ago": (REF_DATE-d).days,
            "home_team": h, "away_team": a,
            "home_score": hs, "away_score": as_,
            "total_goals": hs+as_, "goal_difference": hs-as_,
            "result": res, "winner": winner, "loser": loser,
            "went_to_shootout": "TRUE" if so_win else "FALSE",
            "shootout_winner": so_win,
            "tournament": r["tournament"],
            "competition_type": comp_type(r["tournament"]),
            "is_competitive": "FALSE" if comp_type(r["tournament"])=="Friendly" else "TRUE",
            "city": r["city"], "country": r["country"],
            "neutral": "TRUE" if neutral else "FALSE",
            "home_is_host": "TRUE" if (not neutral and r["country"] and h==r["country"]) else ("TRUE" if r["country"]==h else "FALSE"),
            "wc26_home": "TRUE" if h_wc else "FALSE",
            "wc26_away": "TRUE" if a_wc else "FALSE",
            "both_wc26": "TRUE" if (h_wc and a_wc) else "FALSE",
            "home_scorers": "; ".join(scorers[k].get(h, [])),
            "away_scorers": "; ".join(scorers[k].get(a, [])),
            "notes": "",   # reserved for enrichment (injuries, etc.) — see README
        })

matches.sort(key=lambda m:(m["date"], m["home_team"]))
mcols = list(matches[0].keys())
with open(f"{DATA}/matches.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=mcols); w.writeheader(); w.writerows(matches)

# ---------- team_match_log.csv (one row per WC team per match) ----------
log=[]
for m in matches:
    for side in ("home","away"):
        team = m["home_team"] if side=="home" else m["away_team"]
        if team not in WC48: continue
        opp  = m["away_team"] if side=="home" else m["home_team"]
        gf   = m["home_score"] if side=="home" else m["away_score"]
        ga   = m["away_score"] if side=="home" else m["home_score"]
        neutral = m["neutral"]=="TRUE"
        venue = "neutral" if neutral else ("home" if side=="home" else "away")
        if gf>ga: result,pts="W",3
        elif gf<ga: result,pts="L",0
        else: result,pts="D",1
        so = m["shootout_winner"]
        log.append({
            "team": team, "team_display": WC48[team], "wc_group": WC_GROUP[team],
            "date": m["date"], "days_ago": m["days_ago"],
            "opponent": opp, "opponent_is_wc26": "TRUE" if opp in WC48 else "FALSE",
            "venue": venue, "is_home_record": "TRUE" if side=="home" else "FALSE",
            "gf": gf, "ga": ga, "goal_diff": gf-ga,
            "result": result, "points": pts,
            "went_to_shootout": m["went_to_shootout"],
            "shootout_won": "TRUE" if (so and so==team) else ("FALSE" if so else ""),
            "tournament": m["tournament"], "competition_type": m["competition_type"],
            "is_competitive": m["is_competitive"],
            "city": m["city"], "country": m["country"], "neutral": m["neutral"],
            "scorers": m["home_scorers"] if side=="home" else m["away_scorers"],
            "match_id": m["match_id"], "notes": "",
        })
log.sort(key=lambda r:(r["team"], r["date"]))
lcols=list(log[0].keys())
with open(f"{DATA}/team_match_log.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=lcols); w.writeheader(); w.writerows(log)

# ---------- team_summary.csv ----------
agg=defaultdict(lambda:{"P":0,"W":0,"D":0,"L":0,"GF":0,"GA":0,"first":"9999","last":"0000"})
for r in log:
    a=agg[r["team"]]
    a["P"]+=1; a["GF"]+=r["gf"]; a["GA"]+=r["ga"]; a[r["result"]]+=1
    a["first"]=min(a["first"],r["date"]); a["last"]=max(a["last"],r["date"])
srows=[]
for team,a in sorted(agg.items()):
    srows.append({
        "team":team,"display":WC48[team],"group":WC_GROUP[team],
        "matches":a["P"],"wins":a["W"],"draws":a["D"],"losses":a["L"],
        "win_pct":round(100*a["W"]/a["P"],1),
        "gf":a["GF"],"ga":a["GA"],"gd":a["GF"]-a["GA"],
        "ppg":round((3*a["W"]+a["D"])/a["P"],2),
        "first_match":a["first"],"last_match":a["last"],
    })
with open(f"{DATA}/team_summary.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(srows[0].keys())); w.writeheader(); w.writerows(srows)

# ---------- manifest ----------
manifest={
 "source":"martj42/international_results (GitHub, master)",
 "built_window":{"start":str(START),"end":str(REF_DATE)},
 "counts":{"matches":len(matches),"team_match_rows":len(log),"teams":len(agg)},
}
with open(f"{DATA}/MANIFEST.json","w") as f: json.dump(manifest,f,indent=2)

print(f"matches.csv:        {len(matches)} rows")
print(f"team_match_log.csv: {len(log)} rows")
print(f"team_summary.csv:   {len(srows)} teams")
print(f"window: {START} .. {REF_DATE}")
