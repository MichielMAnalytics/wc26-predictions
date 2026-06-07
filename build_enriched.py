#!/usr/bin/env python3
"""
Merge all enrichment layers onto the canonical matches.csv -> matches_enriched.csv,
one wide row per match, joined by match_id. Blanks where a source has no data
(never fabricated). Also prints per-field coverage (% of 1850 matches populated).

Layers (run their fetchers first; all are cached so this is offline):
  matches.csv                 spine (martj42): result, scorers, city/country/neutral
  statsbomb_match_stats.csv   xG/shots/SoT/corners/fouls/cards/passes  (173 matches)
  apifootball_context.csv     stage/round, stadium, referee, HT/ET/pen  (654 matches)

stdlib only.
"""
import csv
from collections import OrderedDict

def load(path, key="match_id"):
    try:
        return {r[key]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
    except FileNotFoundError:
        return {}

matches = list(csv.DictReader(open("data/matches.csv", encoding="utf-8")))
sb  = load("data/statsbomb_match_stats.csv")
af  = load("data/apifootball_context.csv")

# columns contributed by each enrichment layer (with a source prefix kept clear)
SB_COLS = ["sb_stage","home_xg","away_xg","home_shots","away_shots","home_sot","away_sot",
           "home_corners","away_corners","home_fouls","away_fouls","home_yellow","away_yellow",
           "home_red","away_red","home_passes","away_passes"]
AF_COLS = ["af_competition","af_round","venue_name","venue_city","referee",
           "ht_home","ht_away","et_home","et_away","pen_home","pen_away"]

out = []
for m in matches:
    row = OrderedDict(m)
    del row["notes"]                       # move notes to the end
    s = sb.get(m["match_id"], {})
    a = af.get(m["match_id"], {})
    for c in SB_COLS: row[c] = s.get(c, "")
    for c in AF_COLS: row[c] = a.get(c, "")
    row["notes"] = m.get("notes", "")
    out.append(row)

cols = list(out[0].keys())
with open("data/matches_enriched.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)

# ---- coverage report ----
N = len(out)
print(f"matches_enriched.csv: {N} rows, {len(cols)} columns\n")
print("per-field coverage (non-blank / total):")
ENRICH = SB_COLS + AF_COLS
for c in ENRICH:
    pop = sum(1 for r in out if str(r[c]) != "")
    print(f"  {c:16s} {pop:5d}  {100*pop/N:5.1f}%")
print(f"\n  any StatsBomb stats: {sum(1 for r in out if r['home_xg']!=''):5d}  {100*sum(1 for r in out if r['home_xg']!='')/N:5.1f}%")
print(f"  any api-football ctx: {sum(1 for r in out if r['af_round']!=''):5d}  {100*sum(1 for r in out if r['af_round']!='')/N:5.1f}%")
print(f"  either enrichment:    {sum(1 for r in out if r['home_xg']!='' or r['af_round']!=''):5d}  "
      f"{100*sum(1 for r in out if r['home_xg']!='' or r['af_round']!='')/N:5.1f}%")
