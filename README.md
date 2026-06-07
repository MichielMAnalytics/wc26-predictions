# WC2026 Predictions

Tools and data for predicting the 2026 FIFA World Cup (USA / Canada / Mexico, 11 Jun - 19 Jul 2026).

Two things live here:

1. **`index.html`** - a fill-in wall chart (clone of the BBC chart) for entering score predictions. Live standings per group, an auto-advancing knockout bracket, saves to your browser. Open the file directly or serve the folder (`python3 -m http.server 8777`).
2. **`data/`** - a verified historical-form dataset for all 48 qualified teams, covering the 4 years before the tournament. This is the training base for a match-prediction model.

---

## The dataset (`data/`)

Window: **2022-06-07 → 2026-06-07** (4 years back from the brief date of 7 Jun 2026), played matches only.

Built from **[martj42/international_results](https://github.com/martj42/international_results)** (`results.csv`, `goalscorers.csv`, `shootouts.csv`), the standard open dataset of every men's international since 1872. Raw pulls are kept as `*_raw.csv` for reproducibility. Rebuild everything with `python3 build_dataset.py` (stdlib only, no dependencies).

| file | rows | grain |
|---|---|---|
| `matches.csv` | 1,850 | one row per match (canonical) |
| `team_match_log.csv` | 2,351 | one row per WC26 team per match (long / model-ready) |
| `team_summary.csv` | 48 | per-team aggregate over the window |
| `MANIFEST.json` | - | build metadata + counts |

A match between two WC26 teams appears once in `matches.csv` and twice in `team_match_log.csv` (once from each team's perspective), which is why the long table has more rows.

### `team_match_log.csv` (start here for modelling)

One row = one team's match. This is the "Netherlands played 49 games → 49 rows" view.

| column | meaning |
|---|---|
| `team` / `team_display` / `wc_group` | dataset name / wall-chart name / 2026 group (A-L) |
| `date` / `days_ago` | match date / days before 2026-06-07 |
| `opponent` / `opponent_is_wc26` | opponent, and whether they're also a 2026 team |
| `venue` / `is_home_record` | home / away / neutral, and whether team was the listed home side |
| `gf` / `ga` / `goal_diff` | goals for / against / difference, from this team's view |
| `result` / `points` | W/D/L and 3/1/0 |
| `went_to_shootout` / `shootout_won` | knockout shootout flags |
| `tournament` / `competition_type` / `is_competitive` | raw competition / coarse bucket / friendly-vs-not |
| `city` / `country` / `neutral` | where it was played |
| `scorers` | this team's goals, e.g. `Memphis Depay 23' (pen); Cody Gakpo 67'` |
| `match_id` / `notes` | join key to `matches.csv` / reserved (see Enrichment) |

### `matches.csv` (match-level)

`match_id, date, days_ago, home_team, away_team, home_score, away_score, total_goals, goal_difference, result (H/D/A), winner, loser, went_to_shootout, shootout_winner, tournament, competition_type, is_competitive, city, country, neutral, home_is_host, wc26_home, wc26_away, both_wc26, home_scorers, away_scorers, notes`

`competition_type` buckets the raw `tournament` into: `World Cup`, `WC Qualifier`, `Continental Cup`, `Continental Qualifier`, `Nations League`, `Friendly`, `Other`. The raw string is always preserved.

---

## Verification

`build_dataset.py` output was checked, not assumed:

- date range within window; **0** rows with NA scores; **0** rows without a WC26 team
- per-team counts sit in a plausible 37-68 range (Netherlands 49; small FAs like Haiti/Curaçao/New Zealand at 37; CONCACAF/Asian sides higher from Gold/Asian Cups)
- scorelines spot-checked against known results:
  - 2022 WC Final: Argentina 3-3 France, shootout Argentina (Messi pen, Di María) ✓
  - Euro 2024 Final: Spain 2-1 England (N. Williams, Oyarzabal) ✓
  - Copa América 2024 Final: Argentina 1-0 Colombia (Lautaro 112') ✓

---

## Enrichment / known gaps (the `notes` column)

- **Injuries / suspensions / line-ups are NOT in this source.** There is no reliable bulk feed for historical squad availability. The `notes` column is reserved for it. To add it, enrich a subset per match from a per-fixture source (e.g. transfermarkt match pages) rather than fabricating anything.
- The source is goals/results only. No xG, possession, or shot data. Those would need a second source (e.g. FBref / StatsBomb open data) joined on `date + teams`.

## Next steps (prediction model)

Suggested direction, not done yet:
1. Feature engineering off `team_match_log.csv`: rolling form (last N games points/GF/GA), Elo or SPI-style rating updated per match, rest days, home/neutral, competitive-vs-friendly weighting, opponent strength.
2. Model: Poisson / bivariate-Poisson on goals, or Dixon-Coles, to get scoreline probabilities → feed group tables and the bracket.
3. Simulate the tournament (Monte Carlo) using the 2026 fixtures + bracket structure already encoded in `index.html`.

## Sources & licensing

- Match data: **martj42/international_results** (GitHub). Open data; attribution kept here. Non-commercial / personal use.
- `BBC_WC_26_WALL_CHART.pdf` is BBC copyright, kept locally as a reference only. Do not redistribute publicly.
- Fixtures/times in `index.html` were transcribed from that wall chart (kick-offs in BST).
