#!/usr/bin/env python3
"""
Shared tournament structure: parse the 2026 groups + knockout bracket from index.html,
map 3-letter codes to dataset team names, and provide a single-tournament simulator.
Used by simulate.py (Monte Carlo) and predict.py (deterministic Scorito sheet).
"""
import re, json
import numpy as np
import dc as DC

HOSTS = {"Mexico", "United States", "Canada"}
ADJ = None          # optional {team:(d_atk,d_def)} availability/form nudges; set by caller

CODE2TEAM = {
 "MEX":"Mexico","RSA":"South Africa","KOR":"South Korea","CZE":"Czech Republic",
 "CAN":"Canada","BOS":"Bosnia and Herzegovina","QAT":"Qatar","SWI":"Switzerland",
 "BRA":"Brazil","MOR":"Morocco","HAI":"Haiti","SCO":"Scotland",
 "USA":"United States","PAR":"Paraguay","AUS":"Australia","TUR":"Turkey",
 "GER":"Germany","CUR":"Curaçao","IVC":"Ivory Coast","ECU":"Ecuador",
 "NED":"Netherlands","JPN":"Japan","SWE":"Sweden","TUN":"Tunisia",
 "BEL":"Belgium","EGY":"Egypt","IRN":"Iran","NZL":"New Zealand",
 "ESP":"Spain","CPV":"Cape Verde","SAU":"Saudi Arabia","URU":"Uruguay",
 "FRA":"France","SEN":"Senegal","IRQ":"Iraq","NOR":"Norway",
 "ARG":"Argentina","ALG":"Algeria","AUT":"Austria","JOR":"Jordan",
 "POR":"Portugal","DRC":"DR Congo","UZB":"Uzbekistan","COL":"Colombia",
 "ENG":"England","CRO":"Croatia","GHA":"Ghana","PAN":"Panama",
}

def parse_structure(path="index.html"):
    html = open(path, encoding="utf-8").read()
    groups = {}
    # group blocks: A:{teams:[...], m:[ ... ]}
    for gm in re.finditer(r"([A-L]):\{teams:\[([^\]]+)\],\s*m:\[(.*?)\]\}", html, re.S):
        g = gm.group(1)
        teams = [CODE2TEAM[c] for c in re.findall(r"'([A-Z]{3})'", gm.group(2))]
        matches = []
        for mm in re.finditer(r"\['([A-Z]{3})','([A-Z]{3})','[A-Z][a-z]{2}", gm.group(3)):
            matches.append((CODE2TEAM[mm.group(1)], CODE2TEAM[mm.group(2)]))
        groups[g] = {"teams": teams, "matches": matches}
    # KO entries
    ko = {}
    for km in re.finditer(r"'([A-Z0-9-]+)'\s*:\{r:'(\w+)',[^}]*?h:'([^']+)',\s*a:'([^']+)'\}", html):
        ko[km.group(1)] = {"round": km.group(2), "h": km.group(3), "a": km.group(4)}
    return groups, ko

def neutral_sides(home, away):
    """Return (home_team, away_team, neutral) applying host home-advantage."""
    if home in HOSTS and away not in HOSTS: return home, away, False
    if away in HOSTS and home not in HOSTS: return away, home, False  # host plays 'home'
    return home, away, True

def sample_score(params, a, b, rng):
    """Sample (ga, gb) for a vs b (a nominal home)."""
    h, aw, neu = neutral_sides(a, b)
    M = DC.score_matrix(params, h, aw, neu, adj=ADJ)
    flat = M.ravel(); idx = rng.choice(len(flat), p=flat/flat.sum())
    gi, gj = divmod(idx, M.shape[1])
    # map back to (a,b) order
    return (gi, gj) if h == a else (gj, gi)

def win_prob(params, a, b):
    h, aw, neu = neutral_sides(a, b)
    M = DC.score_matrix(params, h, aw, neu, adj=ADJ); pH,pD,pA = DC.outcome_probs(M)
    pa = pH if h == a else pA
    pb = pA if h == a else pH
    return pa, pD, pb

def ko_winner(params, a, b, rng):
    ga, gb = sample_score(params, a, b, rng)
    if ga > gb: return a
    if gb > ga: return b
    pa, _, pb = win_prob(params, a, b)         # ET/penalties ~ regulation strength
    return a if rng.random() < pa/(pa+pb) else b

def group_table(params, teams, matches, rng):
    pts = {t:0 for t in teams}; gf = {t:0 for t in teams}; ga = {t:0 for t in teams}
    for a, b in matches:
        x, y = sample_score(params, a, b, rng)
        gf[a]+=x; ga[a]+=y; gf[b]+=y; ga[b]+=x
        if x>y: pts[a]+=3
        elif y>x: pts[b]+=3
        else: pts[a]+=1; pts[b]+=1
    rank = sorted(teams, key=lambda t:(pts[t], gf[t]-ga[t], gf[t], rng.random()), reverse=True)
    info = {t:(pts[t], gf[t]-ga[t], gf[t]) for t in teams}
    return rank, info

def assign_thirds(third_slots, qualified_thirds, third_group, rng):
    """Bipartite-match the 8 best thirds to the 8 '3:XXXX' slots respecting eligibility.
    third_slots: list of (slot_id, eligible_groups_str). qualified_thirds: ordered best->worst."""
    # backtracking assignment
    slots = [(sid, set(elig)) for sid, elig in third_slots]
    result = {}
    used = set()
    def bt(i):
        if i == len(qualified_thirds): return True
        t = qualified_thirds[i]; g = third_group[t]
        for sid, elig in slots:
            if sid in used: continue
            if g in elig:
                used.add(sid); result[sid] = t
                if bt(i+1): return True
                used.discard(sid); del result[sid]
        return False
    if not bt(0):
        # fallback: assign in order ignoring eligibility (rare)
        free = [s for s,_ in slots]
        for t, s in zip(qualified_thirds, free): result[s] = t
    return result

def simulate_once(params, groups, ko, rng):
    """Return dict: team -> furthest stage int, plus 'champion','finalist','group_winner' sets."""
    STAGE = {"group":0,"R32":1,"R16":2,"QF":3,"SF":4,"final":5,"champion":6}
    reached = {}
    def mark(t, s):
        if STAGE[s] > reached.get(t, -1): reached[t] = STAGE[s]
    pos = {}                       # '1A','2A','3A'...
    third_info = {}; third_group = {}
    group_winner = set()
    for g, gd in groups.items():
        rank, info = group_table(params, gd["teams"], gd["matches"], rng)
        pos[f"1{g}"] = rank[0]; pos[f"2{g}"] = rank[1]; pos[f"3{g}"] = rank[2]
        group_winner.add(rank[0])
        for t in gd["teams"]: mark(t, "group")
        for t in (rank[0], rank[1]): mark(t, "R32")    # top2 advance
        third_info[rank[2]] = info[rank[2]]; third_group[rank[2]] = g
    # best 8 thirds
    thirds_ranked = sorted(third_info, key=lambda t:(third_info[t][0], third_info[t][1], third_info[t][2], rng.random()), reverse=True)
    qual_thirds = thirds_ranked[:8]
    for t in qual_thirds: mark(t, "R32")
    # third slots from ko (a-ref like '3:ABCDF')
    third_slots = []
    for sid, k in ko.items():
        if k["a"].startswith("3:"): third_slots.append((sid, k["a"][2:]))
    third_assign = assign_thirds(third_slots, qual_thirds, third_group, rng)

    def resolve(ref):
        if ref.startswith("W:"): return winners[ref[2:]]
        if ref.startswith("L:"): return losers[ref[2:]]
        if ref.startswith("3:"): return third_assign.get(cur_slot)   # handled inline
        return pos[ref]

    winners = {}; losers = {}
    # process KO in order
    order = [k for k in ko if k.startswith("R32")] + \
            [k for k in ko if k.startswith("R16")] + \
            [k for k in ko if k.startswith("QF")] + \
            [k for k in ko if k.startswith("SF")] + ["TP","FINAL"]
    rmap = {"r32":"R16","r16":"QF","qf":"SF","sf":"final","final":"champion","tp":None}
    for sid in order:
        if sid not in ko: continue
        k = ko[sid]
        cur_slot = sid
        a = third_assign[sid] if k["h"].startswith("3:") else (winners[k["h"][2:]] if k["h"].startswith("W:") else losers[k["h"][2:]] if k["h"].startswith("L:") else pos[k["h"]])
        b = third_assign[sid] if k["a"].startswith("3:") else (winners[k["a"][2:]] if k["a"].startswith("W:") else losers[k["a"][2:]] if k["a"].startswith("L:") else pos[k["a"]])
        if a is None or b is None: continue
        w = ko_winner(params, a, b, rng); l = b if w == a else a
        winners[sid] = w; losers[sid] = l
        nxt = rmap.get(k["round"])
        if k["round"] != "tp" and nxt: mark(w, nxt)
    return reached, winners

def load_params(path="data/model/dc_params.json"):
    return json.load(open(path))
