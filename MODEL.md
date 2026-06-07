# The prediction model

A goals model + tournament simulation built to **maximise Scorito WK 2026 points**.
Everything is reproducible from the dataset; run order at the bottom.

## Pipeline

```
results_raw (martj42)
   ├─ model/elo.py        World-Football-Elo for all 312 intl teams      -> data/model/ratings.csv
   ├─ model/dc.py         time+competition-weighted Dixon-Coles MLE      -> data/model/dc_params.json
   │                      log λ_for = μ + atk[t] − def[opp] + home·(home & not neutral), + DC ρ
   ├─ model/backtest.py   strict time-split validation (skill proof)
   ├─ model/tournament.py parse 2026 groups+bracket from index.html; single-tournament simulator
   ├─ model/odds.py       vig-free bookmaker implied probs (CBS Sports)  -> data/model/market_odds.csv
   ├─ model/adjust.py     bounded injury/momentum + market nudges        -> data/model/adjustments.csv
   ├─ model/simulate.py   N-tournament Monte Carlo (adj-aware)           -> data/model/sim_team_probs.csv
   ├─ model/predict.py    EV-optimal Scorito picks + bracket + champion  -> data/predictions/*.csv
   ├─ model/topscorers.py expected goals per player -> Golden Boot +
   │                      Scorito position-weighted picks                -> data/predictions/topscorers.csv
   └─ model/write_report.py (+ fill_sheet/inject_topscorers/build_public) -> SCORITO_PREDICTIONS.md, index.html
```

## Why this design

- **Dixon-Coles** gives a full **scoreline probability matrix**, which is exactly what
  Scorito needs (exact-score + outcome points). Fit by weighted MLE on all internationals
  2018–2026; weights = time-decay (2-year half-life) × competition importance
  (friendlies 0.5, qualifiers/NL 0.9, finals 1.0). Attack/defence are ridge-regularised so
  sparse teams shrink to the mean; ρ corrects the low-score dependence. The Poisson part is
  fit with an **analytic gradient** (convex, reliable), ρ by a separate 1-D MLE.
- **Elo** is a transparent strength backbone and an independent backtest baseline.
- **Monte Carlo** handles the 48-team format: group tables, the 8 best third-placed teams,
  bipartite assignment of thirds to the bracket's eligibility slots, then knockouts (draws
  resolved by regulation win-probability ≈ extra-time/penalties). Host nations
  (USA/Canada/Mexico) get home advantage.
- **Scorito optimiser**: predicting score *s* has EV `30·P(outcome(s)) + 15·P(exact s)`
  (group). Because exact:toto = 1.5 every round, the optimal scoreline is round-invariant —
  the model enumerates the grid and takes the argmax. This is why most picks are 1-0/0-1:
  the outcome (toto) dominates and a 1-goal favourite win is the modal exact score.

## Backtest (out-of-sample, strict time separation)

| test set | RPS (model) | RPS (climatology) | skill | outcome acc | Scorito pts/match |
|---|---|---|---|---|---|
| Recent holdout 2025-01→2026-06 (1274 matches) | 0.168 | 0.228 | **+26%** | 0.60 | 19.85 |
| …competitive only (879) | 0.163 | 0.232 | **+30%** | 0.62 | 20.75 |
| Euro 2024 replay (51) | 0.188 | 0.222 | +15% | 0.53 | 18.24 |
| World Cup 2022 replay (64) | 0.224 | 0.233 | +4% | 0.47 | 15.00 |

- Model beats the Elo baseline on RPS on the holdout (0.168 vs 0.173) and beats naive
  Scorito strategies (19.85 vs 8.15 for "always 1-1", 18.83 for the modal score).
- WC 2022 was an upset-heavy outlier (Saudi 2-1 Argentina, Japan over Germany & Spain,
  Morocco to the semis); ~4% skill there is honest, not a bug. 64-match tournaments are
  high variance — deep-run picks are **edges, not certainties**.

## Availability/form adjustment (Part 2 edge)

`model/adjust.py` folds the Part 2 research into the goals model as **small, capped**
(±0.20 log-space) nudges to each team's attack/defence: a forward/mid ruled OUT costs
attack in proportion to his share of the squad's international goals; a regular
defender/GK OUT costs defence; momentum rising/declining ±0.03. Doubts barely count
(×0.25). It can't be backtested (Part 2 is a current snapshot) so it stays a disciplined
prior — but it's the edge over entrants using results only. Effect: Brazil (Rodrygo,
Militão, Estêvão, Neymar) and Japan dip; healthy, rising Morocco rises.

## Market layer (bookmaker odds)

`model/odds.py` turns cached CBS Sports WC2026 odds (outright + group-winner, american)
into **vig-free implied probabilities** (`data/odds_raw/cbs_odds_2026.json` is the cached
scrape). Two uses:
1. A **market-strength z-score** (champion + group-winner) feeds `adjust.py` as a bounded
   attack/defence nudge (±0.18), pulling per-match picks toward consensus. This fixed real
   model quirks: it underrated France/England/Germany and overrated Morocco/Japan/Colombia.
2. A **50/50 blend** of model-sim and market implied probs is the recommended title view,
   and the **champion bet + bracket advancement** use that blended strength (so the bracket
   advances genuinely strong teams and the 250-pt champion bet maximises P(champion)).
   Predicted *scorelines* stay EV-optimal independently (Scorito lets score & advancer differ).

## Headline 2026 outputs (blended model + market, 30k sims)

- **Champion pick (bet): Spain** (blended 15%), then Argentina (12%), France (10%),
  England (10%), Portugal/Brazil (~8%). Model and market agree Spain is the safest title bet.
- Full submission in [SCORITO_PREDICTIONS.md](SCORITO_PREDICTIONS.md); raw tables in
  `data/predictions/`, `data/model/sim_team_probs.csv`, `data/model/market_odds.csv`.

## Reproduce

```bash
python3 build_dataset.py && python3 build_extras.py        # data spine (if not built)
.venv/bin/python model/elo.py                              # ratings.csv
.venv/bin/python model/dc.py                               # dc_params.json
.venv/bin/python model/backtest.py                         # validation numbers
.venv/bin/python model/odds.py                             # market_odds.csv (from cached odds)
.venv/bin/python model/adjust.py                           # adjustments.csv (injury+market)
.venv/bin/python model/simulate.py 30000                   # sim_team_probs.csv
.venv/bin/python model/predict.py                          # data/predictions/*
.venv/bin/python model/write_report.py                     # SCORITO_PREDICTIONS.md
```
(venv needs `numpy scipy pandas` — pinned in the model commit.)

## Limitations / next gains

- The injury/form layer is a capped prior, not fit from data (no historical availability to
  learn from). Name-matching injury news to roster surnames is imperfect; unmatched OUTs get a
  small generic attack penalty.
- xG (StatsBomb, 173 matches) could replace goals in the fit where available for sharper rates.
- Market odds now included (CBS Sports, cached) but it's a one-off snapshot — re-pull near
  kickoff for live movement. Only outright + group-winner were available, not per-match 1X2.
- Top-scorer model uses career international scoring rate (no club-season form feed), so
  it's age-decayed to avoid over-rating veterans; a player's *recent* club form isn't in it.
  Golden Boot pick: Mbappé, then Kane. Scorito (position-weighted) surfaces attacking
  defenders/mids (Hakimi, Kimmich, Davies, James Rodríguez) as value.
