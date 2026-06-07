#!/usr/bin/env python3
"""
Enrich WC2026 matches with StatsBomb open-data event stats (xG, shots, etc.).

Source: statsbomb/open-data (GitHub) — free, no API key. CC BY-NC-SA 4.0,
attribution kept in SOURCES.md. https://github.com/statsbomb/open-data

In-window tournaments covered (every match involves real shot-level data):
  FIFA World Cup 2022 (43/106), AFCON 2023 (1267/107),
  Copa America 2024 (223/282), UEFA Euro 2024 (55/282)

Caches raw under data/statsbomb_raw/ (matches index committed; bulky per-match
events gitignored but re-downloadable by re-running this script -> reproducible).
Output: data/statsbomb_match_stats.csv (one row per match, both sides' stats),
joined to matches.csv match_id on date + teams.

Honesty: true possession% is NOT in open data; we record pass counts instead and
leave possession blank. Fields with no data are left blank, never fabricated.

stdlib only. Run build_dataset.py first (needs data/matches.csv to join).
"""
import csv, json, os, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

RAW = "data/statsbomb_raw"
EVDIR = f"{RAW}/events"
MDIR  = f"{RAW}/matches"
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
COMPS = {  # (competition_id, season_id): label
    (43,106):"FIFA World Cup 2022", (1267,107):"AFCON 2023",
    (223,282):"Copa America 2024", (55,282):"UEFA Euro 2024",
}
# StatsBomb -> martj42 spelling (only the ones that differ)
NAME_MAP = {
    "Cape Verde Islands":"Cape Verde", "Congo DR":"DR Congo",
    "Côte d'Ivoire":"Ivory Coast",
}
def mj(name): return NAME_MAP.get(name, name)

os.makedirs(EVDIR, exist_ok=True); os.makedirs(MDIR, exist_ok=True)

def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    tmp = path + ".tmp"
    with open(tmp, "wb") as f: f.write(data)
    os.replace(tmp, path)

# ---- 1. ensure match indexes are cached, collect match list ----
match_index = []  # (match_id, meta dict)
for (cid, sid), label in COMPS.items():
    mpath = f"{MDIR}/{cid}_{sid}.json"
    fetch(f"{BASE}/matches/{cid}/{sid}.json", mpath)
    for m in json.load(open(mpath, encoding="utf-8")):
        match_index.append((m["match_id"], label, m))
print(f"matches to process: {len(match_index)}")

# ---- 2. download events (cached, parallel) ----
def get_events(mid):
    p = f"{EVDIR}/{mid}.json"
    try:
        fetch(f"{BASE}/events/{mid}.json", p)
        return mid, True
    except Exception as e:
        return mid, f"ERR {e}"
todo = [mid for mid,_,_ in match_index if not os.path.exists(f"{EVDIR}/{mid}.json")]
print(f"events to download: {len(todo)} (already cached: {len(match_index)-len(todo)})")
errs = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for mid, ok in ex.map(get_events, todo):
        if ok is not True: errs.append((mid, ok))
if errs: print("download errors:", errs[:5], "...total", len(errs))

# ---- 3. derive per-side stats from events ----
ON_TARGET = {"Goal","Saved","Saved to Post"}
def derive(mid):
    ev = json.load(open(f"{EVDIR}/{mid}.json", encoding="utf-8"))
    s = defaultdict(lambda: {"xg":0.0,"shots":0,"sot":0,"goals":0,"fouls":0,
                             "yellow":0,"red":0,"corners":0,"passes":0})
    for e in ev:
        t = mj(e.get("team",{}).get("name"))   # canonical (martj42) spelling for joining
        if not t: continue
        if e.get("period") == 5:        # period 5 = penalty shootout — not in-match play
            continue                    # excluded from xG/shots/goals so stats reflect 0-120'
        typ = e["type"]["name"]
        d = s[t]
        if typ == "Own Goal For":       # credited to the benefiting team -> reconciles scoreline
            d["goals"]+=1
        elif typ == "Shot":
            sh = e["shot"]; d["shots"]+=1; d["xg"]+=float(sh.get("statsbomb_xg",0) or 0)
            oc = sh.get("outcome",{}).get("name","")
            if oc in ON_TARGET: d["sot"]+=1
            if oc == "Goal": d["goals"]+=1
        elif typ == "Pass":
            d["passes"]+=1
            if e.get("pass",{}).get("type",{}).get("name")=="Corner": d["corners"]+=1
        elif typ == "Foul Committed":
            d["fouls"]+=1
            card = e.get("foul_committed",{}).get("card",{}).get("name","")
            if card in ("Yellow Card","Second Yellow"): d["yellow"]+=1
            if card in ("Red Card","Second Yellow"): d["red"]+=1
        elif typ == "Bad Behaviour":
            card = e.get("bad_behaviour",{}).get("card",{}).get("name","")
            if card in ("Yellow Card","Second Yellow"): d["yellow"]+=1
            if card in ("Red Card","Second Yellow"): d["red"]+=1
    return s

# ---- 4. join to matches.csv on unordered teams + date (±1 day) ----
# Copa America 2024 etc. have late US kickoffs that cross UTC midnight, so the
# StatsBomb match_date can be 1 day off martj42's. Tolerate ±1 day, teams must match.
from datetime import datetime, timedelta
mrows = {}  # (date, frozenset{home,away}) -> match row
for r in csv.DictReader(open("data/matches.csv", encoding="utf-8")):
    mrows[(r["date"], frozenset((r["home_team"], r["away_team"])))] = r

def find_match(dt, teams):
    d = datetime.strptime(dt, "%Y-%m-%d").date()
    for off in (0, -1, 1):
        k = ((d + timedelta(days=off)).isoformat(), teams)
        if k in mrows: return mrows[k]
    return None

out = []; unmatched = []
for mid, label, meta in match_index:
    home = mj(meta["home_team"]["home_team_name"])
    away = mj(meta["away_team"]["away_team_name"])
    dt   = meta["match_date"]
    rec  = find_match(dt, frozenset((home, away)))
    if not rec:
        unmatched.append((dt, home, away, label)); continue
    st = derive(mid)
    # align stats to the canonical home/away in matches.csv. SB dict is keyed by
    # SB names (home/away after mj()); canonical sides ch/ca use martj42 names.
    ch, ca = rec["home_team"], rec["away_team"]
    hkey = ch if ch in st else (home if ch in (home, away) else None)
    akey = ca if ca in st else (away if ca in (home, away) else None)
    hs = st.get(hkey, {}); as_ = st.get(akey, {})
    out.append({
        "match_id": rec["match_id"], "date": rec["date"],
        "home_team": ch, "away_team": ca, "competition": label,
        "sb_stage": meta.get("competition_stage",{}).get("name",""),
        "sb_match_week": meta.get("match_week",""),
        "stadium": (meta.get("stadium") or {}).get("name",""),
        "referee": (meta.get("referee") or {}).get("name",""),
        "home_xg": round(hs.get("xg",0),3), "away_xg": round(as_.get("xg",0),3),
        "home_shots": hs.get("shots",""), "away_shots": as_.get("shots",""),
        "home_sot": hs.get("sot",""), "away_sot": as_.get("sot",""),
        "home_corners": hs.get("corners",""), "away_corners": as_.get("corners",""),
        "home_fouls": hs.get("fouls",""), "away_fouls": as_.get("fouls",""),
        "home_yellow": hs.get("yellow",""), "away_yellow": as_.get("yellow",""),
        "home_red": hs.get("red",""), "away_red": as_.get("red",""),
        "home_passes": hs.get("passes",""), "away_passes": as_.get("passes",""),
        "home_goals_sb": hs.get("goals",""), "away_goals_sb": as_.get("goals",""),
        "possession_note": "not in open data; use pass share as proxy",
    })

out.sort(key=lambda r:(r["date"], r["home_team"]))
with open("data/statsbomb_match_stats.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

print(f"\nstatsbomb_match_stats.csv: {len(out)} matches joined")
print(f"unmatched (in SB, not in matches.csv): {len(unmatched)}")
for u in unmatched[:10]: print("   ", u)
