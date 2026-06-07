#!/usr/bin/env python3
"""
Parse openfootball/worldcup (Football.TXT, CC0 public domain) for fields no other
source here provides: ATTENDANCE and STARTING XI / subs, plus referee + AET/pen flags.

Source: https://github.com/openfootball/worldcup  (more/<year>_full.txt)
Scope: World Cup FINALS only (the repo is WC-only). In our 4-year window that's
WC 2022 (the 2026 finals are unplayed). WC 2018 is parsed too for the 8-year
deep-history window. Raw files cached under data/openfootball_raw/ (committed, ~110KB).

Outputs:
  data/openfootball_match_extra.csv  one row per match: attendance, aet, pen score,
                                     referee, home_xi/away_xi (11 names ;-joined),
                                     home_subs/away_subs
  data/match_lineups.csv             long: one row per (match, team, player) with
                                     started / sub_on_min / captain / yellow / red

No fabrication: a starting XI is only emitted if exactly 11 starters parse; otherwise
that side's XI is left blank and counted in the report.

stdlib only. Run build_dataset.py first (needs matches.csv to join).
"""
import csv, re, os
from datetime import date

RAW = "data/openfootball_raw"
FILES = {2018: f"{RAW}/2018_full.txt", 2022: f"{RAW}/2022_full.txt"}
MONTHS = {m:i for i,m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],1)}
NAME_MAP = {"USA":"United States"}          # openfootball -> martj42 (only differ in WC48)
def mj(t): return NAME_MAP.get(t, t)

# date line:  "Sun Nov 20 19:00 UTC+3 @ Al Bayt Stadium, Al Khor, Att: 67372"
RE_DATE = re.compile(r"^[A-Z][a-z]{2}\s+([A-Z][a-z]{2})\s+(\d{1,2})\b.*?(?:Att:\s*([\d ]+))?$")
# score line: "  Argentina v France  3-3 a.e.t., 4-2 pen."
RE_SCORE = re.compile(r"^\s+(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)(.*)$")
RE_PEN   = re.compile(r"(\d+)-(\d+)\s*pen")

def clean_players(text):
    """From a team lineup blob, return (starters[list], subs[list], captain, yellows, reds)."""
    # capture subs: "(72' NAME)" / "(120+1' NAME)", stripping any [Y]/[R]/[c] tags
    subs = [re.sub(r"\s*\[[^\]]*\]", "", m).strip()
            for m in re.findall(r"\(\d+(?:\+\d+)?'\s*([^)]+)\)", text)]
    captain, yellows, reds = "", [], []
    # captain marker [c] attaches to the immediately-preceding name
    for m in re.finditer(r"([A-Z][\w’'-]+(?:\s+[A-Z][\w’'.-]+)*)\s*\[c\]", text):
        captain = m.group(1).strip()
    # remove sub parentheticals, then bracket annotations
    base = re.sub(r"\([^)]*\)", " ", text)
    base = re.sub(r"\[[^\]]*\]", " ", base)
    base = re.sub(r"\s+", " ", base).strip()      # collapse newlines + runs of spaces
    base = base.replace(" - ", ", ")              # position separators -> commas
    starters = [p.strip(" ,") for p in base.split(",")]
    starters = [p for p in starters if p and not p.isspace()]
    return starters, subs, captain

def parse_file(year, path):
    txt = open(path, encoding="utf-8").read()
    lines = txt.split("\n")
    matches = []
    i = 0
    while i < len(lines):
        dm = RE_DATE.match(lines[i].strip()) if "@" in lines[i] and "Att" in lines[i] else None
        # only treat as a match header if the NEXT non-empty line is a score line
        if dm and i+1 < len(lines):
            sm = RE_SCORE.match(lines[i+1])
            if sm:
                mon, day, att = dm.group(1), int(dm.group(2)), dm.group(3)
                d = date(year, MONTHS[mon], day)
                home, away = mj(sm.group(1).strip()), mj(sm.group(2).strip())
                rest = sm.group(5)
                aet = "a.e.t" in rest
                penm = RE_PEN.search(rest)
                pen_h = pen_a = ""
                if penm: pen_h, pen_a = penm.group(1), penm.group(2)
                # collect this block until the next date header / EOF
                j = i+2; block = []
                while j < len(lines):
                    if "@" in lines[j] and "Att" in lines[j] and RE_DATE.match(lines[j].strip()):
                        break
                    block.append(lines[j]); j += 1
                btxt = "\n".join(block)
                ref = ""
                rm = re.search(r"Refs:\s*([^\n(]+)", btxt)
                if rm: ref = rm.group(1).strip().rstrip(",")
                # team lineup blobs: "Home: ... " up to next "Team:" / "Refs:" / "Penalties:"
                def grab(team):
                    pat = re.compile(re.escape(team)+r":\s*(.+?)(?=\n[A-Z][^\n:]*:|\nRefs:|\nPenalties:|\Z)", re.S)
                    m = pat.search(btxt)
                    return m.group(1) if m else ""
                # use the ORIGINAL (unmapped) names as they appear in the file
                oh, oa = sm.group(1).strip(), sm.group(2).strip()
                hb, ab = grab(oh), grab(oa)
                hs, hsub, hcap = clean_players(hb) if hb else ([],[],"")
                as_, asub, acap = clean_players(ab) if ab else ([],[],"")
                matches.append({
                    "date": d.isoformat(), "home": home, "away": away,
                    "att": (att or "").replace(" ","").strip(), "aet": aet,
                    "pen_h": pen_h, "pen_a": pen_a, "ref": ref,
                    "hs": hs, "hsub": hsub, "hcap": hcap,
                    "as": as_, "asub": asub, "acap": acap,
                })
                i = j; continue
        i += 1
    return matches

# ---- join to deep_history.csv (8yr superset; same match_id scheme as matches.csv,
#      so 2018 WC matches resolve too and the ids stay consistent across both tables) ----
mrows = {}
for r in csv.DictReader(open("data/deep_history.csv", encoding="utf-8")):
    mrows[(r["date"], frozenset((r["home_team"], r["away_team"])))] = r

extra, lineups, unmatched, bad_xi = [], [], [], 0
for year, path in FILES.items():
    if not os.path.exists(path): continue
    for m in parse_file(year, path):
        rec = mrows.get((m["date"], frozenset((m["home"], m["away"]))))
        if not rec:
            unmatched.append((m["date"], m["home"], m["away"])); continue
        mid = rec["match_id"]
        swap = (rec["home_team"] == m["away"])      # align to canonical home/away
        hs, as_ = (m["as"], m["hs"]) if swap else (m["hs"], m["as"])
        hsub, asub = (m["asub"], m["hsub"]) if swap else (m["hsub"], m["asub"])
        hcap, acap = (m["acap"], m["hcap"]) if swap else (m["hcap"], m["acap"])
        ph, pa = (m["pen_a"], m["pen_h"]) if swap else (m["pen_h"], m["pen_a"])
        # only emit XI if exactly 11 parsed (honesty guard)
        hx = hs if len(hs)==11 else []
        ax = as_ if len(as_)==11 else []
        if hs and len(hs)!=11: bad_xi += 1
        if as_ and len(as_)!=11: bad_xi += 1
        extra.append({
            "match_id": mid, "date": rec["date"],
            "home_team": rec["home_team"], "away_team": rec["away_team"],
            "attendance": m["att"], "extra_time": "TRUE" if m["aet"] else "FALSE",
            "pen_home": ph, "pen_away": pa, "referee": m["ref"],
            "home_xi": "; ".join(hx), "away_xi": "; ".join(ax),
            "home_subs": "; ".join(hsub), "away_subs": "; ".join(asub),
            "home_captain": hcap, "away_captain": acap,
        })
        for side, xi, subs, cap in (("home",hx,hsub,hcap),("away",ax,asub,acap)):
            team = rec[f"{side}_team"]
            subset = set(subs)
            for p in xi:
                lineups.append({"match_id":mid,"date":rec["date"],"team":team,
                                "player":p,"started":"TRUE",
                                "is_captain":"TRUE" if p==cap else "FALSE"})
            for p in subs:
                lineups.append({"match_id":mid,"date":rec["date"],"team":team,
                                "player":p,"started":"FALSE","is_captain":"FALSE"})

extra.sort(key=lambda r:(r["date"], r["home_team"]))
with open("data/openfootball_match_extra.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(extra[0].keys())); w.writeheader(); w.writerows(extra)
lineups.sort(key=lambda r:(r["date"], r["team"], r["started"]=="FALSE"))
with open("data/match_lineups.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(lineups[0].keys())); w.writeheader(); w.writerows(lineups)

print(f"openfootball_match_extra.csv: {len(extra)} matches")
print(f"match_lineups.csv:            {len(lineups)} player-rows")
print(f"  with attendance: {sum(1 for r in extra if r['attendance'])}")
print(f"  with full XI both sides: {sum(1 for r in extra if r['home_xi'] and r['away_xi'])}")
print(f"  sides where XI != 11 (left blank): {bad_xi}")
print(f"  unmatched vs matches.csv: {len(unmatched)} {unmatched[:6]}")
