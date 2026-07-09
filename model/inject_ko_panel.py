#!/usr/bin/env python3
"""
Embed the CURRENT knockout-round picks into index.html as a panel under the bracket
legend. Bracket & champion stay LOCKED (Spain); this panel shows the live round's
match-score predictions + that round's top-scorer picks. Phase-aware: prefers the
latest round file present (QF > R32). Idempotent (refreshes KO_PICKS in place).
"""
import json, re, os

# pick the most recent phase available
if os.path.exists("data/predictions/_qf_picks.json"):
    ko = json.load(open("data/predictions/_qf_picks.json", encoding="utf-8"))
    games = ko["qf"]; label = "Quarter-finals"; gcol = "Quarter-finals — predicted scores"
    note = "R32 went 13/16 outcomes (3 exact) · R16 done · bracket &amp; champion locked (Spain)."
else:
    ko = json.load(open("data/predictions/_ko_picks.json", encoding="utf-8"))
    games = ko["r32"]; label = "Round of 32"; gcol = "Round of 32 — predicted scores (actual fixtures)"
    note = "Bracket &amp; champion are locked since 7 Jun (pick: Spain) — only the round scores &amp; scorers update."

payload = {"games": games, "top4": ko["top4"], "label": label, "gcol": gcol, "note": note}
blob = "const KO_PICKS = " + json.dumps(payload, ensure_ascii=False) + ";"
render = (
  "(()=>{const el=document.getElementById('kopanel');if(!el||typeof KO_PICKS==='undefined')return;"
  "const g=KO_PICKS.games.map(m=>`<div class='tsrow'><span class='pl'>${m.home}</span>"
  "<span class='val'>${m.pred}</span><span class='tm' style='margin-left:8px'>${m.away}</span></div>`).join('');"
  "const s=KO_PICKS.top4.map((p,i)=>`<div class='tsrow'><span class='rk'>${i+1}</span>"
  "<span class='pl'>${p.player}</span> <span class='tm'>${p.team} · ${p.pos}</span></div>`).join('');"
  "el.innerHTML=`<div class='tshead'>\\uD83D\\uDD13 ${KO_PICKS.label} — our picks</div><div class='tsgrid'>`"
  "+`<div class='tscol'><h4>${KO_PICKS.gcol}</h4>${g}</div>`"
  "+`<div class='tscol'><h4>Top 4 scorers (this round)</h4>${s}`"
  "+`<div class='note'>${KO_PICKS.note}</div></div></div>`;})();"
)

html = open("index.html", encoding="utf-8").read()
if 'id="kopanel"' not in html:
    html = html.replace('<div class="tspanel" id="tspanel"></div>',
                        '<div class="tspanel" id="kopanel"></div>\n        <div class="tspanel" id="tspanel"></div>', 1)
if "const KO_PICKS" not in html:
    anchor = "const save = ()=>localStorage.setItem(LS, JSON.stringify(state));"
    html = html.replace(anchor, anchor + "\n" + blob + "\n" + render, 1)
else:
    html = re.sub(r"const KO_PICKS = \{.*?\};", blob, html, count=1, flags=re.S)
open("index.html", "w", encoding="utf-8").write(html)
print(f"KO panel -> {label}: {len(games)} games + top4")
