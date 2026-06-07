#!/usr/bin/env python3
"""
Parse full 26-man squads for all 48 teams from the cached Wikipedia
"2026 FIFA World Cup squads" wikitext -> data/squad_roster.csv.

Source: en.wikipedia.org (CC BY-SA). Raw cached at data/part2_raw/wiki_squads_raw.json.
Fields: team, player, position, age, caps, intl_goals, club. Honest blanks if missing.
stdlib only.
"""
import csv, json, re
from datetime import date

REF = date(2026, 6, 11)   # tournament start (Wikipedia ages computed to this date)
d = json.load(open("data/part2_raw/wiki_squads_raw.json", encoding="utf-8"))
wt = d["parse"]["wikitext"]

# dataset (martj42) spellings — Wikipedia headers mostly match; map the few that differ
NAME_MAP = {"Turkey":"Turkey", "Türkiye":"Turkey", "Republic of Ireland":"Ireland"}
WC48 = {r["team"] for r in csv.DictReader(open("data/team_summary.csv", encoding="utf-8"))}

# split wikitext into (country -> chunk) using === Country === headers
parts = re.split(r"\n===\s*([^=\n]+?)\s*===\n", wt)
# parts = [pre, name1, chunk1, name2, chunk2, ...]
sections = {}
for i in range(1, len(parts)-1, 2):
    sections[parts[i].strip()] = parts[i+1]

def val(body, key):
    m = re.search(r"\|\s*"+key+r"\s*=\s*([^|}\n]*)", body)
    return m.group(1).strip() if m else ""

def clean_link(s):
    m = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", s)
    s = m.group(1) if m else s
    s = s.replace("[[", "").replace("]]", "")     # strip any stray brackets (truncated links)
    return s.split("|")[-1].strip()

def age_from(body):
    m = re.search(r"birth date and age2\|\d+\|\d+\|\d+\|(\d+)\|(\d+)\|(\d+)", body)
    if not m: return ""
    y, mo, da = map(int, m.groups())
    a = REF.year - y - ((REF.month, REF.day) < (mo, da))
    return a

rows = []
unmatched_sections = []
for country, chunk in sections.items():
    team = NAME_MAP.get(country, country)
    if team not in WC48:
        # only keep the 48; skip stray sections (e.g. "References")
        if re.search(r"nat fs g player", chunk): unmatched_sections.append(country)
        continue
    # each player: split on the template delimiter so the body keeps caps/club that
    # appear AFTER the nested {{birth date and age2|...}} template
    pieces = chunk.split("{{nat fs g player")
    for piece in pieces[1:]:
        # cut at the end of this player's record (next template / list end)
        body = re.split(r"\{\{nat fs (?:g player|end|g manager|g start)", piece)[0]
        name = clean_link(val(body, "name"))
        if not name: continue
        rows.append({
            "team": team,
            "player": name,
            "position": val(body, "pos"),
            "age": age_from(body),
            "caps": val(body, "caps"),
            "intl_goals": val(body, "goals"),
            "club": clean_link(val(body, "club")),
        })

rows.sort(key=lambda r: (r["team"], r["position"], r["player"]))
with open("data/squad_roster.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

from collections import Counter
per_team = Counter(r["team"] for r in rows)
print(f"squad_roster.csv: {len(rows)} players, {len(per_team)} teams")
print(f"teams !=26 players: {[(t,n) for t,n in per_team.items() if n!=26]}")
print(f"missing WC48 teams: {WC48 - set(per_team)}")
if unmatched_sections: print(f"unmapped sections with players: {unmatched_sections}")
print(f"coverage: age {sum(1 for r in rows if r['age']!='')}/{len(rows)}, "
      f"caps {sum(1 for r in rows if r['caps'])}/{len(rows)}, "
      f"club {sum(1 for r in rows if r['club'])}/{len(rows)}")
