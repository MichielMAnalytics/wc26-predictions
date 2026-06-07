#!/usr/bin/env python3
"""
Out-of-sample backtest of the Dixon-Coles model. Proves predictive skill before we
trust the 2026 predictions. Strictly time-separated: for each test set we refit the
model on matches strictly BEFORE the test period.

Metrics:
  - RPS (ranked probability score, ordered H/D/A; lower=better) vs a climatology baseline
  - multiclass log-loss
  - outcome accuracy vs "pick the Elo favourite"
  - calibration table (predicted vs observed)
  - Scorito group-scoring points: model optimal pick vs naive strategies

Test sets: a recent holdout (2025-01-01..2026-06-07) and two real-tournament replays
(World Cup 2022, Euro 2024).
Requires numpy, scipy.
"""
import sys, math
from datetime import date
import numpy as np
sys.path.insert(0, "model")
import dc as DC
from elo import compute_ratings
from scorito import optimal_pick, score_points, outcome

def rps(p, obs_idx):           # p=[pH,pD,pA], ordered; obs_idx in {0,1,2}
    o = [0,0,0]; o[obs_idx] = 1
    c1 = (p[0]-o[0]); c2 = (p[0]+p[1]-o[0]-o[1])
    return 0.5*(c1*c1 + c2*c2)

def oidx(hs, as_): return 0 if hs>as_ else (1 if hs==as_ else 2)

def elo_wdl(elo, h, a, neutral):
    """Simple Elo-implied H/D/A baseline (logistic + flat draw share)."""
    HA = 0 if neutral else 100
    d = (elo.get(h,1500)+HA) - elo.get(a,1500)
    p_home_exp = 1/(1+10**(-d/400))           # expected score in [0,1]
    pdraw = 0.26
    pH = p_home_exp*(1-pdraw); pA = (1-p_home_exp)*(1-pdraw)
    return [pH, pdraw, pA]

def evaluate(train_rows, test_rows, ref, label, elo):
    params = DC.fit_dc(train_rows, ref=ref)
    base = np.array([0.0,0.0,0.0])
    for r in test_rows: base[oidx(r["hs"],r["as"])] += 1
    base = base/base.sum()                    # climatology from the test set (generous baseline)
    m_rps=e_rps=b_rps=0.0; m_ll=0.0; acc=elo_acc=0; n=0
    pts_model=pts_11=pts_fav=pts_mode=0
    calib = {}                                # bucket model P(home win)
    for r in test_rows:
        M = DC.score_matrix(params, r["home"], r["away"], r["neutral"])
        pH,pD,pA = DC.outcome_probs(M); p=[pH,pD,pA]
        oi = oidx(r["hs"],r["as"]); n+=1
        m_rps += rps(p, oi); b_rps += rps(list(base), oi)
        ep = elo_wdl(elo, r["home"], r["away"], r["neutral"]); e_rps += rps(ep, oi)
        m_ll += -math.log(max(p[oi],1e-12))
        if max(range(3),key=lambda k:p[k])==oi: acc+=1
        if max(range(3),key=lambda k:ep[k])==oi: elo_acc+=1
        # scorito
        actual=(r["hs"],r["as"])
        pick,_ = optimal_pick(M,"group")
        pts_model += score_points(pick, actual, "group")
        pts_11    += score_points((1,1), actual, "group")
        # favourite 2-1/1-0 toward higher-prob outcome's modal goals -> use model modal score as a "mode" strat
        mode = np.unravel_index(M.argmax(), M.shape)
        pts_mode  += score_points((int(mode[0]),int(mode[1])), actual, "group")
        fav = (2,1) if pH>=pA else (1,2)
        pts_fav   += score_points(fav, actual, "group")
        b = round(pH,1); calib.setdefault(b,[0,0]); calib[b][0]+=1; calib[b][1]+=(oi==0)
    print(f"\n=== {label}  (train {len(train_rows)} matches -> test {n}) ===")
    print(f"  RPS   model {m_rps/n:.4f} | Elo {e_rps/n:.4f} | climatology {b_rps/n:.4f}   (lower better)")
    print(f"  logloss model {m_ll/n:.4f}")
    print(f"  outcome acc   model {acc/n:.3f} | Elo-favourite {elo_acc/n:.3f}")
    print(f"  Scorito pts/match (group 45/30): model {pts_model/n:.2f} | model-mode {pts_mode/n:.2f} "
          f"| always 1-1 {pts_11/n:.2f} | fav 2-1 {pts_fav/n:.2f}")
    skill = 1 - (m_rps/n)/(b_rps/n)
    print(f"  RPS skill vs climatology: {skill*100:.1f}%")
    return {"label":label,"n":n,"rps":m_rps/n,"rps_base":b_rps/n,"acc":acc/n,
            "scorito":pts_model/n}

def tournament(name_filters, t0, t1, label):
    allrows = DC.load_internationals(date(2010,1,1), t1)
    train = [r for r in allrows if r["date"] < t0]
    test  = [r for r in allrows if t0 <= r["date"] <= t1
             and any(f in r["tournament"].lower() for f in name_filters)]
    elo,_,_,_ = compute_ratings(ref=t0)
    return evaluate(train, test, t0, label, elo)

if __name__ == "__main__":
    # 1) recent holdout
    allrows = DC.load_internationals(date(2010,1,1), date(2026,6,7))
    cut = date(2025,1,1)
    train = [r for r in allrows if r["date"] < cut]
    test  = [r for r in allrows if r["date"] >= cut]
    test_comp = [r for r in test if "friendly" not in r["tournament"].lower()]
    elo,_,_,_ = compute_ratings(ref=cut)
    evaluate(train, test, cut, "Holdout 2025-01-01..2026-06-07 (ALL internationals)", elo)
    evaluate(train, test_comp, cut, "Holdout 2025+ (COMPETITIVE only)", elo)
    # 2) real tournament replays
    tournament(["fifa world cup"], date(2022,11,20), date(2022,12,18), "World Cup 2022 replay")
    tournament(["uefa euro"], date(2024,6,14), date(2024,7,14), "Euro 2024 replay")
    print("\n(note: tournament replays score every match at group 45/30 for comparability)")
