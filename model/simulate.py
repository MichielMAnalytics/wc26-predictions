#!/usr/bin/env python3
"""
Monte-Carlo simulation of the 2026 World Cup using the Dixon-Coles model.
Runs N tournaments and reports each team's probability of reaching each stage and
winning the cup. Output: data/model/sim_team_probs.csv.
Requires numpy. Usage: python simulate.py [N]
"""
import sys, csv
import numpy as np
sys.path.insert(0, "model")
import tournament as T
from adjust import load_adjustments

def run(n=20000, seed=12345, use_adj=True):
    params = T.load_params()
    T.ADJ = load_adjustments() if use_adj else None
    print(f"availability/form adjustments: {'ON' if T.ADJ else 'OFF'}")
    groups, ko = T.parse_structure()
    teams = [t for g in groups.values() for t in g["teams"]]
    assert len(teams) == 48, f"got {len(teams)} teams"
    rng = np.random.default_rng(seed)
    STAGES = ["group","R32","R16","QF","SF","final","champion"]
    SIDX = {s:i for i,s in enumerate(STAGES)}
    counts = {t: np.zeros(len(STAGES)) for t in teams}
    champs = {t:0 for t in teams}; finals = {t:0 for t in teams}; gw = {t:0 for t in teams}
    for _ in range(n):
        reached, winners = T.simulate_once(params, groups, ko, rng)
        for t, st in reached.items():
            for k in range(st+1):                     # reached stage st => reached all <= st
                counts[t][k] += 1
        champ = winners.get("FINAL")
        if champ is not None: champs[champ] += 1
        fin = winners.get("SF1"), winners.get("SF2")
        for f in fin:
            if f is not None: finals[f] += 1
    rows = []
    for t in teams:
        c = counts[t]/n
        rows.append({"team":t,
                     "p_advance_R32": round(c[SIDX["R32"]],3),
                     "p_reach_R16": round(c[SIDX["R16"]],3),
                     "p_reach_QF": round(c[SIDX["QF"]],3),
                     "p_reach_SF": round(c[SIDX["SF"]],3),
                     "p_final": round(finals[t]/n,3),
                     "p_champion": round(champs[t]/n,3)})
    rows.sort(key=lambda r:-r["p_champion"])
    with open("data/model/sim_team_probs.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"simulated {n} tournaments -> data/model/sim_team_probs.csv")
    print(f"\n{'team':22s} {'R32':>6} {'R16':>6} {'QF':>6} {'SF':>6} {'Final':>6} {'Champ':>6}")
    for r in rows[:16]:
        print(f"{r['team']:22s} {r['p_advance_R32']:6.2f} {r['p_reach_R16']:6.2f} "
              f"{r['p_reach_QF']:6.2f} {r['p_reach_SF']:6.2f} {r['p_final']:6.2f} {r['p_champion']:6.2f}")
    tot = sum(champs.values())
    print(f"\nchampion prob sums to {sum(r['p_champion'] for r in rows):.3f} (sanity ~1.0)")
    return rows

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    run(n)
