#!/usr/bin/env python3
"""
Scorito scoring + optimal-pick helpers (shared by backtest and the final predictions).

Scorito WK 2026 match scoring (researched, cited in SCORITO_RULES.md):
  exact score  -> EXACT points   (group 45)
  correct toto -> TOTO points    (group 30)   [outcome right, score wrong]
  else 0.
Knockout rounds scale exact/toto by round multiplier (R32 2x, R16 3x, QF 4x, SF 5x, F 6x
relative to a 15-point unit; group = 45/30). Penalties do NOT count: use the 120' result.

Optimal pick: predicting score s gives expected points
  EV(s) = EXACT*P(s) + TOTO*(P(outcome(s)) - P(s))
        = TOTO*P(outcome(s)) + (EXACT-TOTO)*P(s)
so we enumerate the score grid and take the argmax. (For the group stage that's
30*P(outcome) + 15*P(exact).)
"""
import numpy as np

# exact/toto by round. Group = 45/30; knockouts scale (Scorito: final ~3x group exact via R32 base).
ROUND_POINTS = {
    "group": (45, 30),
    "R32":   (90, 60),
    "R16":   (135, 90),
    "QF":    (180, 120),
    "SF":    (225, 150),
    "final": (270, 180),
}

def outcome(i, j):
    return "H" if i > j else ("A" if i < j else "D")

def optimal_pick(M, rnd="group"):
    """Return ((i,j), expected_points) maximizing Scorito EV for score matrix M."""
    exact, toto = ROUND_POINTS[rnd]
    n = M.shape[0]
    # P(outcome) lookup
    pH = sum(M[i,j] for i in range(n) for j in range(n) if i>j)
    pD = float(np.trace(M))
    pA = sum(M[i,j] for i in range(n) for j in range(n) if i<j)
    P = {"H":pH, "D":pD, "A":pA}
    best, bestev = (0,0), -1.0
    for i in range(n):
        for j in range(n):
            ev = toto*P[outcome(i,j)] + (exact-toto)*M[i,j]
            if ev > bestev:
                bestev, best = ev, (i,j)
    return best, bestev

def score_points(pred, actual, rnd="group"):
    exact, toto = ROUND_POINTS[rnd]
    if pred == actual: return exact
    if outcome(*pred) == outcome(*actual): return toto
    return 0
