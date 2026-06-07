#!/usr/bin/env python3
"""
Assemble the Part 2 (recent team developments) tables from:
  - data/team_state_form.csv      derived form/warm-up signals (build_team_state.py)
  - data/part2_raw/<team>.json    cited research per team (one file per team)

Outputs (see SCHEMA_PART2.md):
  data/team_state.csv        one row per team: derived form + researched coach/qual/
                             momentum/shape verdict + injury & news counts
  data/team_injuries.csv     one row per injury/doubt/suspension (cited)
  data/team_news.csv         one row per dated news item (cited)
  data/team_key_players.csv  one row per key player note

Honesty: blanks are preserved as blanks; nothing is invented here. Every injury and
news row carries the source_url captured during research.
stdlib only.
"""
import csv, json, glob, os

form = {r["team"]: r for r in csv.DictReader(open("data/team_state_form.csv", encoding="utf-8"))}
raw = {}
for fp in glob.glob("data/part2_raw/*.json"):
    d = json.load(open(fp, encoding="utf-8"))
    raw[d["team"]] = d

assert set(raw) == set(form), f"team mismatch: {set(form)^set(raw)}"

state, injuries, news, keyplayers = [], [], [], []
for team in sorted(form):
    f = form[team]; d = raw[team]
    inj = d.get("injuries_doubts") or []
    inj = [x for x in inj if x.get("player")]            # drop empty template rows
    nws = [x for x in (d.get("news") or []) if x.get("headline")]
    kps = [x for x in (d.get("key_players") or []) if x]
    key_inj = "; ".join(f"{x['player']} ({x.get('status','')})" for x in inj) if inj else ""
    state.append({
        "team": team, "team_display": f["team_display"], "wc_group": f["wc_group"],
        "snapshot_date": d.get("snapshot_date","2026-06-07"),
        # --- researched ---
        "head_coach": d.get("head_coach",""),
        "coach_nationality": d.get("coach_nationality",""),
        "coach_appointed": d.get("coach_appointed",""),
        "recent_coach_change": d.get("recent_coach_change",""),
        "base_formation": d.get("base_formation",""),
        "qualification_path": d.get("qualification_path",""),
        "qualification_convincingness": d.get("qualification_convincingness",""),
        "momentum": d.get("momentum","") or f["form_trend"],
        "n_injuries": len(inj), "key_injuries": key_inj,
        "squad_notes": d.get("squad_notes",""),
        "warmup_assessment": d.get("warmup_assessment",""),
        "shape_verdict": d.get("shape_verdict",""),
        "n_news": len(nws), "n_sources": len(d.get("sources") or []),
        # --- derived (hard signals from results data) ---
        "last_match_date": f["last_match_date"], "rest_days_to_ref": f["rest_days_to_ref"],
        "form_last5": f["form_last5"], "form_last10": f["form_last10"],
        "ppg_last5": f["ppg_last5"], "gd_last10": f["gd_last10"],
        "form_trend_derived": f["form_trend"],
        "win_streak": f["win_streak"], "unbeaten_run": f["unbeaten_run"],
        "n_2026_warmups": f["n_2026_warmups"], "warmup_results": f["warmup_results"],
    })
    for x in inj:
        injuries.append({"team": team, "player": x.get("player",""),
                         "issue": x.get("issue",""), "status": x.get("status",""),
                         "source_url": x.get("source_url","")})
    for x in nws:
        news.append({"team": team, "date": x.get("date",""),
                     "category": x.get("category",""), "headline": x.get("headline",""),
                     "source_url": x.get("source_url","")})
    for x in kps:
        keyplayers.append({"team": team, "key_player_note": x})

def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

write("data/team_state.csv", state)
write("data/team_injuries.csv", injuries)
write("data/team_news.csv", news)
write("data/team_key_players.csv", keyplayers)

# ---- report ----
N = len(state)
print(f"team_state.csv:       {N} teams")
print(f"team_injuries.csv:    {len(injuries)} injury/doubt rows  "
      f"({sum(1 for r in injuries if r['source_url'])} with source)")
print(f"team_news.csv:        {len(news)} news rows  "
      f"({sum(1 for r in news if r['source_url'])} with source)")
print(f"team_key_players.csv: {len(keyplayers)} key-player rows")
print("\ncoverage of team_state fields:")
for c in ("head_coach","recent_coach_change","base_formation","qualification_path",
          "momentum","key_injuries","shape_verdict"):
    pop = sum(1 for r in state if str(r[c]).strip())
    print(f"  {c:24s} {pop:2d}/{N}")
changed = sum(1 for r in state
              if r["recent_coach_change"] and not r["recent_coach_change"].lower().startswith(("no ","none","no recent","no change")))
print(f"\nteams with an actual coach change in the last ~year: {changed}/{N}")
