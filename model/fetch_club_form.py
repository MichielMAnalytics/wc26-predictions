#!/usr/bin/env python3
"""
Pull 2025-26 CLUB-season goals/apps for the realistic top-scorer candidates from
Wikipedia (player career-stats tables), to sharpen the top-scorer model with current
form. Keyless (UA required). Caches data/club_form_raw.csv (resumable: re-runs skip
players already cached). Requires pandas.

Candidates = top N players from data/predictions/topscorers.csv by exp_goals (covers
every team's main attackers). Player names == Wikipedia article titles (they came from
the Wikipedia squad templates), so match rate is high; misses are left blank (honest).
"""
import urllib.request, urllib.parse, json, io, re, time, csv, os
import pandas as pd

UA = {"User-Agent": "wc26-predictions/1.0 (research; michiel@melchioranalytics.com)"}
CACHE = "data/club_form_raw.csv"
N = 350

def fetch_html(title, tries=3):
    u = (f"https://en.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(title)}"
         "&prop=text&format=json&formatversion=2&redirects=1")
    for k in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
            d = json.load(r)
            if "parse" not in d: return None
            return d["parse"]["text"]
        except Exception:
            if k == tries-1: return None
            time.sleep(1.0)
    return None

def num(x):
    m = re.match(r"\s*(\d+)", str(x)); return int(m.group(1)) if m else 0

def club_form(title):
    html = fetch_html(title)
    if not html: return None
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception:
        return None
    for t in tables:
        if not isinstance(t.columns, pd.MultiIndex): continue
        if ("Total", "Goals") not in list(t.columns): continue
        scol = [c for c in t.columns if str(c[0]).startswith("Season") or "Season" in str(c[1])]
        if not scol: continue
        sc = scol[0]; g = a = 0; found = False
        for _, row in t.iterrows():
            if re.search(r"2025[–-]26", str(row[sc])):
                g += num(row[("Total","Goals")]); a += num(row[("Total","Apps")]); found = True
        if found: return (g, a)
    return None

# candidate list
cand = list(csv.DictReader(open("data/predictions/topscorers.csv", encoding="utf-8")))
cand = sorted(cand, key=lambda r: -float(r["exp_goals"]))[:N]

done = {}
if os.path.exists(CACHE):
    done = {r["player"]: r for r in csv.DictReader(open(CACHE, encoding="utf-8"))}

rows = list(done.values())
todo = [c for c in cand if c["player"] not in done]
print(f"candidates {len(cand)}, cached {len(done)}, fetching {len(todo)}")
hit = 0
for i, c in enumerate(todo, 1):
    cf = club_form(c["player"])
    g, a = (cf if cf else ("", ""))
    if cf: hit += 1
    rows.append({"player": c["player"], "team": c["team"], "position": c["position"],
                 "club_goals_2526": g, "club_apps_2526": a})
    if i % 50 == 0: print(f"  {i}/{len(todo)} (hits {hit})")
    time.sleep(0.15)

with open(CACHE, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["player","team","position","club_goals_2526","club_apps_2526"])
    w.writeheader(); w.writerows(rows)
got = sum(1 for r in rows if str(r["club_goals_2526"]) != "")
print(f"club_form_raw.csv: {len(rows)} players, {got} with 2025-26 club data")
print("top current scorers:")
for r in sorted([r for r in rows if str(r['club_goals_2526'])!=''], key=lambda r:-int(r['club_goals_2526']))[:10]:
    print(f"  {r['player']:22s} {r['team']:12s} {r['club_goals_2526']}g/{r['club_apps_2526']}a")
