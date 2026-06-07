#!/usr/bin/env python3
"""
World-Football-Elo ratings for ALL international teams, from martj42 results_raw.csv.

Processes every full international chronologically from START_ELO to REF_DATE and
updates Elo with: importance-weighted K, margin-of-victory multiplier, and a
home-field adjustment (neutral games get none). This is the strength backbone for
the goals model and the tournament sim.

Output: data/model/ratings.csv  (team, elo, n_matches, last_date)
        data/model/elo_timeline.csv  (optional sanity: elo of WC48 teams over time)
stdlib only.
"""
import csv, os, math
from datetime import date, datetime

REF_DATE  = date(2026, 6, 7)
START_ELO = date(2010, 1, 1)     # 16y burn-in so ratings are well converged by 2026
HOME_ADV  = 100                  # Elo points added to the home side's expectation
INIT      = 1500.0
os.makedirs("data/model", exist_ok=True)

def parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def is_num(s): return s not in ("", "NA", None)

def k_factor(tournament):
    t = tournament.lower()
    if "friendly" in t: return 20
    if "fifa world cup" in t and "qual" not in t: return 60
    if any(k in t for k in ["uefa euro","copa am","african cup of nations","afc asian cup",
                            "gold cup","confederations"]) and "qual" not in t: return 50
    if "nations league" in t: return 40
    if "qualif" in t: return 40           # WC + continental qualifiers
    return 30                              # other competitive

def mov_mult(gd, elo_diff_winner):
    """Margin-of-victory multiplier (World Football Elo)."""
    if gd <= 1: return 1.0
    if gd == 2: return 1.5
    return (11 + gd) / 8.0

WC48 = {r["team"] for r in csv.DictReader(open("data/team_summary.csv", encoding="utf-8"))}

def compute_ratings(ref=REF_DATE, start=START_ELO, path="data/results_raw.csv"):
    """Compute Elo for all teams using matches in [start, ref]. Returns (elo, n, last, timeline)."""
    elo, n, last, timeline = {}, {}, {}, []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = parse_date(r["date"])
            if d < start or d > ref: continue
            if not (is_num(r["home_score"]) and is_num(r["away_score"])): continue
            rows.append(r)
    rows.sort(key=lambda r: r["date"])
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        neutral = r["neutral"] == "TRUE"
        Rh = elo.get(h, INIT); Ra = elo.get(a, INIT)
        dh = Rh + (0 if neutral else HOME_ADV) - Ra
        We_h = 1.0 / (1 + 10 ** (-dh / 400))
        if hs > as_: Wh, wd = 1.0, Rh - Ra
        elif hs < as_: Wh, wd = 0.0, Ra - Rh
        else: Wh, wd = 0.5, 0
        K = k_factor(r["tournament"]) * mov_mult(abs(hs-as_), wd)
        delta = K * (Wh - We_h)
        elo[h] = Rh + delta; elo[a] = Ra - delta
        for t in (h, a):
            n[t] = n.get(t, 0) + 1; last[t] = r["date"]
        if h in WC48: timeline.append({"team": h, "date": r["date"], "elo": round(elo[h], 1)})
        if a in WC48: timeline.append({"team": a, "date": r["date"], "elo": round(elo[a], 1)})
    return elo, n, last, timeline

elo, n, last, timeline = compute_ratings()
out = [{"team": t, "elo": round(elo[t], 1), "n_matches": n[t], "last_date": last[t]}
       for t in elo]
out.sort(key=lambda r: -r["elo"])
with open("data/model/ratings.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["team","elo","n_matches","last_date"]); w.writeheader(); w.writerows(out)
with open("data/model/elo_timeline.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["team","date","elo"]); w.writeheader(); w.writerows(timeline)

print(f"ratings.csv: {len(out)} teams rated")
print("top 15 (all teams):")
for r in out[:15]: print(f"  {r['elo']:7.1f}  {r['team']}")
print("\nWC48 ratings (ranked):")
wc = [r for r in out if r["team"] in WC48]
for i, r in enumerate(wc, 1):
    print(f"  {i:2d}. {r['elo']:7.1f}  {r['team']}  (n={r['n_matches']})")
