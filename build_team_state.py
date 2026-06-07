#!/usr/bin/env python3
"""
Part 2 — DERIVED team-state layer (reproducible, no fabrication, no external calls).

Computes the hard "how in shape are they" signals straight from team_match_log.csv:
recent form, the run-in (2026 warm-up / friendly results), streaks, rest days, and
qualification-window record. These fill the derivable columns of team_state.csv
(see SCHEMA_PART2.md) before any researched columns (manager/injuries/news) are added.

Output: data/team_state_form.csv  (one row per team, 48 rows)
stdlib only. Run build_dataset.py first.
"""
import csv
from datetime import date, datetime
from collections import defaultdict

REF = date(2026, 6, 7)
log = list(csv.DictReader(open("data/team_match_log.csv", encoding="utf-8")))
by_team = defaultdict(list)
for r in log:
    by_team[r["team"]].append(r)

def d(s): return datetime.strptime(s, "%Y-%m-%d").date()

def form_str(rows):           # most recent first
    return "".join(r["result"] for r in rows)

def pts(rows):  return sum(int(r["points"]) for r in rows)
def gf(rows):   return sum(int(r["gf"]) for r in rows)
def ga(rows):   return sum(int(r["ga"]) for r in rows)

out = []
for team, rows in sorted(by_team.items()):
    rows.sort(key=lambda r: r["date"])                 # ascending
    disp = rows[0]["team_display"]; grp = rows[0]["wc_group"]
    recent = rows[-10:][::-1]                           # last 10, most-recent first
    last5  = recent[:5]
    prev5  = rows[-10:-5][::-1] if len(rows) >= 10 else []
    # 2026 run-in: every match played in 2026 (warm-ups + any late qualifiers)
    runin = [r for r in rows if r["date"] >= "2026-01-01"][::-1]
    warmups = [r for r in runin if r["competition_type"] == "Friendly"]
    last = rows[-1]
    # unbeaten / win streak from most recent backwards
    win_streak = 0
    for r in recent:
        if r["result"] == "W": win_streak += 1
        else: break
    unbeaten = 0
    for r in recent:
        if r["result"] in ("W", "D"): unbeaten += 1
        else: break
    def fmt(r):  # compact match line for the run-in list
        ha = {"home":"vs","away":"@","neutral":"vN"}[r["venue"]]
        return f"{r['date']} {ha} {r['opponent']} {r['gf']}-{r['ga']} {r['result']}"
    p5, pp5 = pts(last5), pts(prev5)
    out.append({
        "team": team, "team_display": disp, "wc_group": grp,
        "matches_in_window": len(rows),
        "last_match_date": last["date"],
        "rest_days_to_ref": (REF - d(last["date"])).days,
        "form_last5": form_str(last5),
        "form_last10": form_str(recent),
        "points_last5": p5, "points_last10": pts(recent),
        "gd_last5": gf(last5) - ga(last5), "gd_last10": gf(recent) - ga(recent),
        "ppg_last5": round(p5 / max(len(last5), 1), 2),
        "form_trend": ("rising" if p5 > pp5 + 2 else "declining" if p5 < pp5 - 2 else "steady") if prev5 else "n/a",
        "win_streak": win_streak, "unbeaten_run": unbeaten,
        "n_2026_matches": len(runin),
        "n_2026_warmups": len(warmups),
        "warmup_results": " | ".join(fmt(r) for r in warmups) or "",
        "runin_2026": " | ".join(fmt(r) for r in runin) or "",
    })

with open("data/team_state_form.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

print(f"team_state_form.csv: {len(out)} teams")
print(f"teams with >=1 match in 2026: {sum(1 for r in out if r['n_2026_matches'])}")
print(f"teams with >=1 warm-up friendly in 2026: {sum(1 for r in out if r['n_2026_warmups'])}")
print("\nsample (most rested vs least):")
for r in sorted(out, key=lambda r: r['rest_days_to_ref'])[:3] + sorted(out, key=lambda r: -r['rest_days_to_ref'])[:3]:
    print(f"  {r['team_display']:14s} last {r['last_match_date']} ({r['rest_days_to_ref']}d ago) form {r['form_last5']} 2026:{r['n_2026_matches']}m")
