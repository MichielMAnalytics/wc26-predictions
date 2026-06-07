#!/usr/bin/env python3
"""
Enrich matches with api-football (API-Sports v3) CONTEXT fields.

Adds what martj42 lacks: competition stage/round + matchday, stadium NAME,
referee, halftime score, extra-time + penalty score breakdown, and final status.

Key gating: api-football FREE plan = 100 requests/day. So we DON'T fetch per-fixture
stats (1850+ calls). Instead one /fixtures?league=&season= call returns a whole
competition's fixtures with all the context above. ~40 calls covers the competitive
comps in the window. Friendlies (global league=10) are too large to pull cheaply and
are left as a documented gap.

Budget-aware + resumable: every response is cached under data/apifootball_raw/ ;
re-runs cost 0 calls. The script checks remaining daily quota and stops with margin,
so it can be finished across days.

Key read from .env (gitignored): APIFOOTBALL_KEY=...
Run build_dataset.py first (needs data/matches.csv to join).
"""
import csv, json, os, time, urllib.request, urllib.error
from datetime import datetime, timedelta

RAW = "data/apifootball_raw"
BASE = "https://v3.football.api-sports.io"
MARGIN = 5          # stop when this many daily calls remain
os.makedirs(RAW, exist_ok=True)

def load_key():
    for line in open(".env"):
        if line.startswith("APIFOOTBALL_KEY="):
            return line.strip().split("=",1)[1]
    raise SystemExit("APIFOOTBALL_KEY not in .env")
KEY = load_key()

def api(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def remaining():
    s = api("status")["response"]["requests"]
    return s["limit_day"] - s["current"]

# (league_id, season, label) — competitive international comps in 2022-06-07..2026-06-07.
# Cups are tagged by edition start year in api-football.
TARGETS = [
    (1,2022,"World Cup 2022"),
    (37,2022,"WC22 Intercontinental Play-offs"),
    (4,2024,"Euro 2024"), (960,2023,"Euro 2024 Qualification"),
    (9,2024,"Copa America 2024"),
    (6,2023,"AFCON 2023"), (6,2025,"AFCON 2025"),
    (36,2022,"AFCON Qual"),(36,2023,"AFCON Qual"),(36,2024,"AFCON Qual"),(36,2025,"AFCON Qual"),
    (7,2023,"Asian Cup 2023"),
    (35,2023,"Asian Cup Qual"),(35,2024,"Asian Cup Qual"),(35,2025,"Asian Cup Qual"),
    (22,2023,"Gold Cup 2023"),(22,2025,"Gold Cup 2025"),
    (5,2022,"UEFA Nations League 22/23"),(5,2024,"UEFA Nations League 24/25"),
    (536,2022,"CONCACAF NL"),(536,2023,"CONCACAF NL"),(536,2024,"CONCACAF NL"),(536,2025,"CONCACAF NL"),
    (29,2023,"WCQ Africa"),(29,2024,"WCQ Africa"),(29,2025,"WCQ Africa"),
    (30,2023,"WCQ Asia"),(30,2024,"WCQ Asia"),(30,2025,"WCQ Asia"),
    (31,2024,"WCQ CONCACAF"),(31,2025,"WCQ CONCACAF"),
    (32,2025,"WCQ Europe"),
    (34,2023,"WCQ South America"),(34,2024,"WCQ South America"),(34,2025,"WCQ South America"),
    (33,2024,"WCQ Oceania"),
    (37,2026,"WC26 Intercontinental Play-offs"),
]

def cache_path(lg,se): return f"{RAW}/fixtures_{lg}_{se}.json"

def fetch_target(lg, se):
    """Fetch a league-season (the fixtures endpoint returns ALL results in one call,
    it rejects a page param), cache the response list. Returns #calls used."""
    p = cache_path(lg,se)
    if os.path.exists(p):
        return 0
    d = api(f"fixtures?league={lg}&season={se}")
    with open(p,"w",encoding="utf-8") as f: json.dump(d["response"],f)
    return 1

if __name__ == "__main__":
    import sys
    if "--build-only" not in sys.argv:
        rem = remaining()
        print(f"daily quota remaining: {rem}")
        for lg, se, label in TARGETS:
            if os.path.exists(cache_path(lg,se)):
                continue
            if rem <= MARGIN:
                print(f"[budget] stopping with {rem} calls left; re-run tomorrow to continue.")
                break
            try:
                used = fetch_target(lg, se)
            except urllib.error.HTTPError as e:
                print(f"  {label} ({lg}/{se}): HTTP {e.code}"); continue
            rem -= used
            n = len(json.load(open(cache_path(lg,se)))) if os.path.exists(cache_path(lg,se)) else 0
            print(f"  {label:32s} lg={lg} se={se}: {n:4d} fixtures  ({used} call(s), {rem} left)")
            time.sleep(7)

    # ---------- build context table from whatever is cached ----------
    NAME = {  # api-football -> martj42 spelling (only differers)
        "Czechia":"Czech Republic","Korea Republic":"South Korea","USA":"United States",
        "IR Iran":"Iran","Côte d'Ivoire":"Ivory Coast","Cape Verde Islands":"Cape Verde",
        "DR Congo":"DR Congo","Turkey":"Turkey","Türkiye":"Turkey","Curacao":"Curaçao",
    }
    def n(x): return NAME.get(x, x)

    mrows = {}
    for r in csv.DictReader(open("data/matches.csv", encoding="utf-8")):
        mrows[(r["date"], frozenset((r["home_team"], r["away_team"])))] = r
    def find(dt, teams):
        d = datetime.strptime(dt, "%Y-%m-%d").date()
        for off in (0,-1,1):
            k=((d+timedelta(days=off)).isoformat(), teams)
            if k in mrows: return mrows[k]
        return None

    out, seen = [], set()
    for fp in sorted(__import__("glob").glob(f"{RAW}/fixtures_*.json")):
        for x in json.load(open(fp, encoding="utf-8")):
            fx, lg, tm, sc = x["fixture"], x["league"], x["teams"], x["score"]
            home, away = n(tm["home"]["name"]), n(tm["away"]["name"])
            dt = fx["date"][:10]
            rec = find(dt, frozenset((home, away)))
            if not rec or rec["match_id"] in seen: continue
            seen.add(rec["match_id"])
            ch, ca = rec["home_team"], rec["away_team"]
            swap = (ch == away and ca == home)   # api home/away vs canonical
            def pick(d, k): return d.get(k)
            ht, et, pen = sc["halftime"], sc["extratime"], sc["penalty"]
            hh,ah = (ht["away"],ht["home"]) if swap else (ht["home"],ht["away"])
            eh,ea = (et["away"],et["home"]) if swap else (et["home"],et["away"])
            ph,pa = (pen["away"],pen["home"]) if swap else (pen["home"],pen["away"])
            out.append({
                "match_id": rec["match_id"], "date": rec["date"],
                "home_team": ch, "away_team": ca,
                "af_competition": lg["name"], "af_round": lg["round"],
                "venue_name": (fx["venue"] or {}).get("name","") or "",
                "venue_city": (fx["venue"] or {}).get("city","") or "",
                "referee": fx["referee"] or "",
                "status": fx["status"]["long"],
                "ht_home": "" if hh is None else hh, "ht_away": "" if ah is None else ah,
                "et_home": "" if eh is None else eh, "et_away": "" if ea is None else ea,
                "pen_home": "" if ph is None else ph, "pen_away": "" if pa is None else pa,
            })
    out.sort(key=lambda r:(r["date"], r["home_team"]))
    if out:
        with open("data/apifootball_context.csv","w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"\napifootball_context.csv: {len(out)} matches joined "
          f"(from {len(__import__('glob').glob(f'{RAW}/fixtures_*.json'))} cached comp-seasons)")
