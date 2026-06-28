#!/usr/bin/env python3
"""
Knockout Monte-Carlo from the ACTUAL Round-of-32 bracket, using the retrained model
(refit on the group stage). Gives each surviving team's probability of reaching each
round and winning the cup. Output: data/model/sim_ko_probs.csv. Requires numpy.
"""
import sys, csv, json
from collections import defaultdict
import numpy as np
sys.path.insert(0, "model")
import tournament as T

def run(n=20000, seed=7):
    params = T.load_params()
    _, ko = T.parse_structure()
    r32 = json.load(open("data/predictions/r32_actual.json"))
    rng = np.random.default_rng(seed)
    order = ([k for k in ko if k.startswith("R32")] + [k for k in ko if k.startswith("R16")] +
             [k for k in ko if k.startswith("QF")] + [k for k in ko if k.startswith("SF")] + ["TP","FINAL"])
    RND = {"r32":"R32","r16":"R16","qf":"QF","sf":"SF","final":"final","tp":"TP"}
    STAGES = ["R16","QF","SF","final","champion"]
    plays = defaultdict(lambda: np.zeros(len(STAGES)))  # times team plays R16/QF/SF/final, wins title
    SI = {s:i for i,s in enumerate(STAGES)}
    for _ in range(n):
        winners = {}
        for sid in order:
            if sid not in ko: continue
            k = ko[sid]
            if sid.startswith("R32-"): a,b = r32[sid]
            else:
                a = winners.get(k["h"][2:]) if k["h"].startswith("W:") else None
                b = winners.get(k["a"][2:]) if k["a"].startswith("W:") else None
            if not a or not b: continue
            rnd = RND[k["round"]]
            if rnd in SI:                       # both teams "play" this round
                plays[a][SI[rnd]] += 1; plays[b][SI[rnd]] += 1
            w = T.ko_winner(params, a, b, rng)
            winners[sid] = w
            if sid == "FINAL": plays[w][SI["champion"]] += 1
    rows = []
    for t, c in plays.items():
        rows.append({"team": t,
                     "p_reach_R16": round(c[0]/n,3), "p_reach_QF": round(c[1]/n,3),
                     "p_reach_SF": round(c[2]/n,3), "p_final": round(c[3]/n,3),
                     "p_champion": round(c[4]/n,3)})
    rows.sort(key=lambda r:-r["p_champion"])
    with open("data/model/sim_ko_probs.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"sim_ko_probs.csv: {len(rows)} surviving teams, {n} sims")
    for r in rows[:12]:
        print(f"  {r['team']:14s} QF {r['p_reach_QF']*100:4.0f}%  SF {r['p_reach_SF']*100:4.0f}%  "
              f"F {r['p_final']*100:4.0f}%  champ {r['p_champion']*100:4.1f}%")
    return rows

if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv)>1 else 20000)
