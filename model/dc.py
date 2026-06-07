#!/usr/bin/env python3
"""
Dixon-Coles bivariate-Poisson goals model for international matches.

log lambda_for = mu + atk[team] - def[opp] + home*(team is home & not neutral)
with the Dixon-Coles low-score dependence correction (rho), fit by weighted MLE.
Weights = time-decay (half-life) x competition importance. Attack/defence are
ridge-regularised (handles sparse teams; pins the scale).

Reusable module: import and call fit_dc(train_rows, ...) -> params dict, and
score_matrix(params, home, away, neutral) -> 2D prob grid over scorelines.

Run directly to fit on all internationals in the window and save data/model/dc_params.json.
Requires numpy, scipy.
"""
import csv, json, os, math
from datetime import date, datetime
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

REF_DATE = date(2026, 6, 7)
WINDOW_START = date(2018, 1, 1)
MAXG = 10                      # max goals per side in the scoreline grid

def parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def is_num(s): return s not in ("", "NA", None)

def comp_weight(t):
    t = t.lower()
    if "friendly" in t: return 0.5
    if "fifa world cup" in t and "qual" not in t: return 1.0
    if any(k in t for k in ["uefa euro","copa am","african cup of nations","afc asian cup",
                            "gold cup","confederations"]) and "qual" not in t: return 1.0
    if "nations league" in t: return 0.9
    if "qualif" in t: return 0.9
    return 0.8

def load_internationals(window_start=WINDOW_START, ref=REF_DATE, path="data/results_raw.csv"):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = parse_date(r["date"])
            if d < window_start or d > ref: continue
            if not (is_num(r["home_score"]) and is_num(r["away_score"])): continue
            rows.append({"date": d, "home": r["home_team"], "away": r["away_team"],
                         "hs": int(r["home_score"]), "as": int(r["away_score"]),
                         "neutral": r["neutral"] == "TRUE", "tournament": r["tournament"]})
    return rows

def fit_dc(rows, ref=REF_DATE, half_life_days=730, ridge=2.0, min_matches=6, verbose=False):
    # team universe: those with >= min_matches; rare teams -> shared "OTHER"
    cnt = {}
    for r in rows: cnt[r["home"]] = cnt.get(r["home"],0)+1; cnt[r["away"]] = cnt.get(r["away"],0)+1
    teams = sorted(t for t,c in cnt.items() if c >= min_matches)
    tidx = {t:i for i,t in enumerate(teams)}
    OTHER = len(teams)
    def idx(t): return tidx.get(t, OTHER)
    nteam = len(teams) + 1

    hi = np.array([idx(r["home"]) for r in rows]); ai = np.array([idx(r["away"]) for r in rows])
    hs = np.array([r["hs"] for r in rows], float); as_ = np.array([r["as"] for r in rows], float)
    notneut = np.array([0.0 if r["neutral"] else 1.0 for r in rows])
    age = np.array([(ref - r["date"]).days for r in rows], float)
    w = (0.5 ** (age/half_life_days)) * np.array([comp_weight(r["tournament"]) for r in rows])

    # Stack into directed observations (2 per match): team scores `goals` vs `opp`.
    obs_team = np.concatenate([hi, ai])
    obs_opp  = np.concatenate([ai, hi])
    obs_g    = np.concatenate([hs, as_])
    obs_hf   = np.concatenate([notneut, np.zeros_like(notneut)])   # home-field active only for home obs, non-neutral
    obs_w    = np.concatenate([w, w])

    # --- Part 1: convex weighted Poisson MLE for mu, home, atk, def, with analytic gradient ---
    # param vector p = [mu, home, atk(nteam), def(nteam)]
    def split(p): return p[0], p[1], p[2:2+nteam], p[2+nteam:2+2*nteam]
    def nll_grad(p):
        mu, home, atk, dfn = split(p)
        eta = mu + atk[obs_team] - dfn[obs_opp] + home*obs_hf
        eta = np.clip(eta, -8, 4)
        lam = np.exp(eta)
        ll = obs_g*eta - lam
        nll = -np.sum(obs_w*ll) + ridge*(np.sum(atk**2)+np.sum(dfn**2))
        r = obs_w*(obs_g - lam)                      # d ll/d eta * w
        g = np.zeros_like(p)
        g[0] = -np.sum(r)                            # mu
        g[1] = -np.sum(r*obs_hf)                     # home
        gatk = np.zeros(nteam); np.add.at(gatk, obs_team, -r); gatk += 2*ridge*atk
        gdef = np.zeros(nteam); np.add.at(gdef, obs_opp,  r);  gdef += 2*ridge*dfn
        g[2:2+nteam] = gatk; g[2+nteam:2+2*nteam] = gdef
        return nll, g

    p0 = np.zeros(2 + 2*nteam); p0[0] = math.log(1.3); p0[1] = 0.25
    res = minimize(nll_grad, p0, jac=True, method="L-BFGS-B", options={"maxiter":2000})
    mu, home, atk, dfn = split(res.x)

    # --- Part 2: 1D MLE for rho given fitted lambdas (DC low-score correction) ---
    lh = np.exp(np.clip(mu + atk[hi] - dfn[ai] + home*notneut, -8, 4))
    la = np.exp(np.clip(mu + atk[ai] - dfn[hi], -8, 4))
    m00=(hs==0)&(as_==0); m01=(hs==0)&(as_==1); m10=(hs==1)&(as_==0); m11=(hs==1)&(as_==1)
    def rho_nll(rho):
        rho = rho[0]; tau = np.ones_like(lh)
        tau[m00]=1-lh[m00]*la[m00]*rho; tau[m01]=1+lh[m01]*rho
        tau[m10]=1+la[m10]*rho;         tau[m11]=1-rho
        tau=np.clip(tau,1e-9,None)
        return -np.sum(w*np.log(tau))
    rr = minimize(rho_nll, [-0.05], method="L-BFGS-B", bounds=[(-0.18,0.18)])
    rho = float(rr.x[0])

    params = {"mu":float(mu), "home":float(home), "rho":rho,
              "teams":teams, "atk":{t:float(atk[i]) for t,i in tidx.items()},
              "def":{t:float(dfn[i]) for t,i in tidx.items()},
              "atk_other":float(atk[OTHER]), "def_other":float(dfn[OTHER]),
              "half_life_days":half_life_days, "ridge":ridge, "n_matches":len(rows),
              "converged":bool(res.success)}
    if verbose: print(f"  fit: {len(rows)} matches, {nteam} teams, mu={mu:.3f} home={home:.3f} rho={rho:.3f}, conv={res.success}")
    return params

def _lams(params, home, away, neutral):
    a = params["atk"]; d = params["def"]
    ah = a.get(home, params["atk_other"]); dh = d.get(home, params["def_other"])
    aa = a.get(away, params["atk_other"]); da = d.get(away, params["def_other"])
    lh = math.exp(params["mu"] + ah - da + params["home"]*(0 if neutral else 1))
    la = math.exp(params["mu"] + aa - dh)
    return min(lh,30), min(la,30)

def score_matrix(params, home, away, neutral=False, maxg=MAXG):
    """Return (maxg+1 x maxg+1) matrix P[i,j] = P(home i, away j)."""
    lh, la = _lams(params, home, away, neutral)
    ph = poisson.pmf(np.arange(maxg+1), lh)
    pa = poisson.pmf(np.arange(maxg+1), la)
    M = np.outer(ph, pa)
    rho = params["rho"]
    M[0,0] *= 1 - lh*la*rho
    M[0,1] *= 1 + lh*rho
    M[1,0] *= 1 + la*rho
    M[1,1] *= 1 - rho
    M = np.clip(M, 0, None)
    return M / M.sum()

def outcome_probs(M):
    """P(home win), P(draw), P(away win) from a score matrix."""
    n = M.shape[0]
    h = sum(M[i,j] for i in range(n) for j in range(n) if i>j)
    d = sum(M[i,i] for i in range(n))
    a = sum(M[i,j] for i in range(n) for j in range(n) if i<j)
    return h, d, a

if __name__ == "__main__":
    rows = load_internationals()
    print(f"training internationals {WINDOW_START}..{REF_DATE}: {len(rows)}")
    params = fit_dc(rows, verbose=True)
    json.dump(params, open("data/model/dc_params.json","w"))
    # sanity: a few expected scorelines
    print(f"mu={params['mu']:.3f} home={params['home']:.3f} rho={params['rho']:.3f}")
    for h,a,neu in [("Argentina","Brazil",True),("Spain","France",True),
                    ("Germany","Scotland",False),("Brazil","Haiti",True)]:
        M = score_matrix(params,h,a,neu); ph,pd,pa = outcome_probs(M)
        lh,la = _lams(params,h,a,neu)
        ij = np.unravel_index(M.argmax(), M.shape)
        print(f"  {h} v {a} (neutral={neu}): xG {lh:.2f}-{la:.2f} | W/D/L {ph:.2f}/{pd:.2f}/{pa:.2f} | most-likely {ij[0]}-{ij[1]} ({M.max():.3f})")
