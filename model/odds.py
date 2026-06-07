#!/usr/bin/env python3
"""
Bookmaker-odds layer: convert the cached CBS Sports WC2026 odds (american) into
vig-free implied probabilities (champion + group-winner), and expose a market-implied
strength per team for the model's adjustment layer.

Output: data/model/market_odds.csv. Importable: market_strength() -> {team: z-score}.
"""
import csv, json, math
from statistics import mean, pstdev

RAW = "data/odds_raw/cbs_odds_2026.json"

def american_to_prob(a):
    a = float(a)
    return 100.0/(a+100.0) if a > 0 else (-a)/((-a)+100.0)

def load():
    return json.load(open(RAW, encoding="utf-8"))

def implied():
    d = load()
    # outright (de-vig across all 48)
    raw = {t: american_to_prob(o) for t, o in d["outright"].items()}
    s = sum(raw.values())
    p_champ = {t: raw[t]/s for t in raw}                 # vig-free champion prob
    # group winner (de-vig within each group)
    p_gw = {}; group_of = {}
    for g, teams in d["group_winner"].items():
        rr = {t: american_to_prob(o) for t, o in teams.items()}
        ss = sum(rr.values())
        for t in teams: p_gw[t] = rr[t]/ss; group_of[t] = g
    return p_champ, p_gw, group_of

def market_strength():
    """Per-team market strength z-score, blending champion (global) + group-winner (context)."""
    p_champ, p_gw, group_of = implied()
    # log-strength signals
    champ_log = {t: math.log(max(p_champ[t], 1e-5)) for t in p_champ}
    gw_log    = {t: math.log(max(p_gw[t], 1e-4)) for t in p_gw}
    def z(d):
        vals = list(d.values()); m = mean(vals); sd = pstdev(vals) or 1.0
        return {k: (v-m)/sd for k, v in d.items()}
    zc, zg = z(champ_log), z(gw_log)
    # combine (champion carries overall class; group-winner the within-group picture)
    return {t: 0.5*zc.get(t,0)+0.5*zg.get(t,0) for t in p_champ}

if __name__ == "__main__":
    p_champ, p_gw, group_of = implied()
    rows = []
    d = load()
    for t in sorted(p_champ, key=lambda x:-p_champ[x]):
        rows.append({"team":t,"group":group_of.get(t,""),
                     "outright_american":d["outright"][t],
                     "p_champion_market":round(p_champ[t],4),
                     "p_groupwin_market":round(p_gw.get(t,0),4)})
    with open("data/model/market_odds.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("market_odds.csv: 48 teams")
    print(f"\noverround (outright sum of raw implied): "
          f"{sum(american_to_prob(o) for o in d['outright'].values())*100:.0f}%  (vig removed)")
    # compare to model sim
    try:
        sim={r["team"]:float(r["p_champion"]) for r in csv.DictReader(open("data/model/sim_team_probs.csv"))}
    except FileNotFoundError:
        sim={}
    print(f"\n{'team':14s} {'market':>7} {'model':>7}  divergence")
    for r in rows[:14]:
        m=sim.get(r['team'],0)
        print(f"{r['team']:14s} {r['p_champion_market']*100:6.1f}% {m*100:6.1f}%  {('model high' if m>r['p_champion_market']+0.01 else 'market high' if r['p_champion_market']>m+0.01 else '~')}")
