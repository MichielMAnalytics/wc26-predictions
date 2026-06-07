# Scorito WK 2026 — scoring rules used by the model

Researched June 2026 from scorito.com / blog.scorito.com and multiple Dutch poule
sources (cited below). The score-prediction game ("WK-Poule") is what the model
optimises. **Confirm the exact numbers in the live app** before submitting — a few
knockout sub-values were not publicly published and are inferred from the 1.5× pattern.

## Match score prediction (the core)

| round | exact score | correct toto (outcome) |
|---|---|---|
| Group stage | **45** | **30** |
| Round of 32 | 90 | 60 |
| Round of 16 | 135 | 90¹ |
| Quarter-final | 180 | 120¹ |
| Semi-final | 225 | 150¹ |
| Final | 270 | 180¹ |

- Scoring is binary-tiered: exact score → exact pts; else correct outcome → toto pts; else 0. **No goal-difference tier, no partial credit.**
- **exact : toto = 1.5 in every round.** This is why the EV-optimal *scoreline choice* is the same regardless of round (only the magnitude scales).
- **Penalty shootouts do NOT count** — the predicted/awarded score is the result after 120 minutes (incl. extra time).
- ¹ Toto values for R16–final were not explicitly published for 2026; inferred from the consistent 1.5× ratio. R32 (90/60) is confirmed.

## Other components

- **Group standings:** 25 points per correctly predicted final position (×4 = max 100/group). Auto-derived from your match predictions.
- **Champion (world champion correct):** 250 points.
- **Country advances from group:** 50; advances **with correct position:** 75 (EK 2024 proxy; 2026 detail unconfirmed).
- **Topscorers:** you pick scorers per phase; points per goal by position — group stage Forward 8 / Midfielder 16 / Defender-GK 32, scaling by round on the same 1×→3× ladder. (8/16/32 is the WK 2026 family; EK 2024 used 16/32/64 — verify in-app.)

## How the model uses this

Predicting score *s* for a match has expected value
`EV(s) = exact·P(s) + toto·(P(outcome(s)) − P(s)) = toto·P(outcome(s)) + (exact−toto)·P(s)`.
At the group stage that's **`30·P(outcome) + 15·P(exact score)`**. The model enumerates the
scoreline grid from the Dixon-Coles probability matrix and picks the argmax. Because
exact = 1.5·toto everywhere, the chosen scoreline is round-invariant; rounds only scale
the points. Group standings, the bracket and the champion pick follow from those scorelines.

## Sources
- https://blog.scorito.com/spellen/wk-poule-spel/ , https://blog.scorito.com/wk-2026/wk-2026-voorspellingen
- https://pouletips.nl/wk-2026/scorito/ , https://pouletips.nl/blog/scorito-wk-2026-uitgelegd/
- https://www.regeljelease.nl/scorito-wk-poule , https://ekvoetbal.nl/scorito-tips-ek-2024/ (EK 2024 proxy for country/topscorer detail)
