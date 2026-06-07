#!/usr/bin/env python3
"""
Embed the top-scorer predictions into index.html so the 'How it works' modal shows
them. Reads data/predictions/_topscorers.json (from model/topscorers.py), injects a
TOPSCORERS const + a render snippet that fills the #topscorers div. Idempotent.
Run after topscorers.py; then model/build_public.py to publish.
"""
import json
ts = json.load(open("data/predictions/_topscorers.json", encoding="utf-8"))
html = open("index.html", encoding="utf-8").read()

if "const TOPSCORERS" not in html:
    anchor = "const save = ()=>localStorage.setItem(LS, JSON.stringify(state));"
    blob = "const TOPSCORERS = " + json.dumps(ts, ensure_ascii=False) + ";"
    render = (
      "(()=>{const el=document.getElementById('topscorers');if(!el||typeof TOPSCORERS==='undefined')return;"
      "const gb=TOPSCORERS.golden_boot.map((p,i)=>`${i+1}. <b>${p.player}</b> (${p.team}) — ${p.exp_goals.toFixed(1)} xG`).join('<br>');"
      "const sc=TOPSCORERS.scorito.map(p=>`${p.player} (${p.team}, ${p.pos})`).join(' · ');"
      "el.innerHTML=`<div style='opacity:.85;margin-bottom:4px'>Golden Boot — most goals:</div>${gb}`"
      "+`<div style='opacity:.85;margin:8px 0 4px'>Best Scorito picks (goals × position points — defenders/mids score 2–4× per goal):</div>${sc}`;})();")
    html = html.replace(anchor, anchor + "\n" + blob + "\n" + render, 1)
    open("index.html", "w", encoding="utf-8").write(html)
    print("injected TOPSCORERS into index.html")
else:
    # refresh the const value in place
    import re
    new = "const TOPSCORERS = " + json.dumps(ts, ensure_ascii=False) + ";"
    html = re.sub(r"const TOPSCORERS = \{.*?\};", new, html, count=1, flags=re.S)
    open("index.html", "w", encoding="utf-8").write(html)
    print("refreshed TOPSCORERS const in index.html")
