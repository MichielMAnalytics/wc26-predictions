# WC2026 Predictions

Tools and data for predicting the 2026 FIFA World Cup (USA / Canada / Mexico, 11 Jun - 19 Jul 2026).

Two things live here:

1. **`index.html`** - a fill-in wall chart (clone of the BBC chart) for entering score predictions. Live standings per group, an auto-advancing knockout bracket, saves to your browser. Open the file directly or serve the folder (`python3 -m http.server 8777`).
2. **`data/`** - a verified historical-form dataset for all 48 qualified teams, covering the 4 years before the tournament. This is the training base for a match-prediction model.

---

## The dataset (`data/`)

Window: **2022-06-07 → 2026-06-07** (4 years back from the brief date of 7 Jun 2026), played matches only.

Built from **[martj42/international_results](https://github.com/martj42/international_results)** (`results.csv`, `goalscorers.csv`, `shootouts.csv`), the standard open dataset of every men's international since 1872 — the **spine**. Layered on top: StatsBomb open-data (xG/shots) and api-football (match context). Raw pulls are cached for reproducibility. See **[SOURCES.md](SOURCES.md)** for every source + licence.

| file | rows | grain | built by |
|---|---|---|---|
| `matches.csv` | 1,850 | one row per match (canonical) | `build_dataset.py` |
| `team_match_log.csv` | 2,351 | one row per WC26 team per match (long / model-ready) | `build_dataset.py` |
| `team_summary.csv` | 48 | per-team aggregate over the window | `build_dataset.py` |
| `deep_history.csv` | 3,590 | one row per match, **8-year** window (2018-06-07→2026-06-07), for rating stability | `build_extras.py` |
| `h2h.csv` | 335 | head-to-head record for every pair of WC48 teams that met in the 4yr window | `build_extras.py` |
| `statsbomb_match_stats.csv` | 173 | per-match xG/shots/cards (StatsBomb, 4 major tournaments) | `fetch_statsbomb.py` |
| `apifootball_context.csv` | 654 | per-match stage/venue/referee/HT-ET-pen (api-football) | `fetch_apifootball.py` |
| `openfootball_match_extra.csv` | 124 | attendance + starting XI + subs (WC 2022 + 2018, CC0) | `parse_openfootball.py` |
| `match_lineups.csv` | 3,663 | long: one row per (match, team, player) with started/captain | `parse_openfootball.py` |
| `matches_enriched.csv` | 1,850 | **wide model-ready table**: matches.csv + all enrichment, joined by `match_id` | `build_enriched.py` |
| `MANIFEST.json` | - | build metadata + counts | `build_dataset.py` |

A match between two WC26 teams appears once in `matches.csv` and twice in `team_match_log.csv` (once from each team's perspective), which is why the long table has more rows.

### Rebuild order

```bash
python3 build_dataset.py      # spine: matches / team_match_log / team_summary (stdlib)
python3 build_extras.py        # deep_history.csv + h2h.csv (stdlib)
python3 fetch_statsbomb.py     # statsbomb_match_stats.csv (downloads ~560MB events, cached)
python3 fetch_apifootball.py   # apifootball_context.csv (needs .env key; free plan = 100/day)
python3 parse_openfootball.py  # openfootball_match_extra.csv + match_lineups.csv (stdlib, CC0)
python3 build_enriched.py      # matches_enriched.csv + coverage report (stdlib)
```

`fetch_statsbomb.py` needs no key. `fetch_apifootball.py` reads `APIFOOTBALL_KEY` from a gitignored `.env`. Both cache raw pulls so re-runs are offline/free.

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

### `matches_enriched.csv` (the wide table — start here for richness)

Everything in `matches.csv` plus, joined on `match_id` (blank where no source has it):

**StatsBomb columns** (prefix `home_`/`away_`, 173 matches): `sb_stage`, `home_xg`/`away_xg`, `home_shots`/`away_shots`, `home_sot`/`away_sot` (shots on target), `home_corners`/`away_corners`, `home_fouls`/`away_fouls`, `home_yellow`/`away_yellow`, `home_red`/`away_red`, `home_passes`/`away_passes`. xG and shots **exclude penalty shootouts** (period 5) so they reflect 0–120′ play; goal counts reconcile 173/173 to the real scoreline (incl. own goals).

**api-football context columns** (654 matches): `af_competition`, `af_round` (stage + matchday, e.g. `Group Stage - 1`, `Final`), `venue_name` (stadium), `venue_city`, `referee`, `ht_home`/`ht_away` (halftime), `et_home`/`et_away` (extra-time score, 34 matches), `pen_home`/`pen_away` (shootout score, 26 matches).

**openfootball columns** (63 WC 2022 matches): `attendance`, `home_xi`/`away_xi` (the 11 starters, `;`-joined), `has_lineups` flag. Full per-player detail (starters + subs + captain, WC 2022 **and** 2018) lives in `match_lineups.csv`.

### `deep_history.csv` and `h2h.csv`

`deep_history.csv` mirrors the match-level columns over an 8-year window with an `in_4y_window` flag (TRUE subset == the 1,850 canonical matches). `h2h.csv`: `team_a, team_b, played, a_wins, draws, b_wins, a_goals, b_goals, last_meeting, last_score, last_tournament` (record always from `team_a`'s perspective; pairs sorted alphabetically).

### Enrichment coverage (% of 1,850 matches with the field populated)

| field group | matches | coverage | source |
|---|---|---|---|
| xG / shots / cards (StatsBomb) | 173 | 9.4% | WC22, AFCON23, Copa24, Euro24 |
| stage / venue / referee / HT (api-football) | 654 | 35.4% | comps in seasons 2022–2024 |
| extra-time score | 34 | 1.8% | — |
| shootout score | 26 | 1.4% | — |
| attendance (openfootball) | 63 | 3.4% | WC 2022 only |
| starting XI / lineups (openfootball) | 63 | 3.4% | WC 2022 (+ WC 2018 in deep table) |
| **either enrichment layer** | **661** | **35.7%** | — |

---

## Part 2 — team state going into the tournament (2026-06-07 snapshot)

How in-shape each of the 48 teams is, four days before kickoff. Built in two layers:
**derived** hard signals from the match data (free, 100% covered) + **researched**
qualitative info (coach changes, injuries, news, momentum), every claim cited.

| file | rows | grain | built by |
|---|---|---|---|
| `team_state.csv` | 48 | per-team snapshot: derived form + coach/qualification/momentum/shape verdict | `build_part2.py` |
| `team_injuries.csv` | 77 | one row per injury / doubt / suspension — **100% cited** | `build_part2.py` |
| `team_news.csv` | 144 | one row per dated news item — **100% cited** | `build_part2.py` |
| `team_key_players.csv` | 232 | one row per key-player note | `build_part2.py` |
| `team_state_form.csv` | 48 | derived-only: last5/10 form, 2026 warm-up results, streaks, rest days | `build_team_state.py` |

Per-team research is cached as `data/part2_raw/<team>.json` (coach, qualification path,
injuries, key players, warm-up read, momentum, shape verdict, news — all with source URLs).
Coverage: head coach 48/48, qualification 48/48, shape verdict 48/48, **23/48 teams had a
coach change in the last year**, injuries found for 36/48 (the rest honest blanks). Build:
`python3 build_team_state.py && python3 build_part2.py`. Full 26-man rosters are the one
remaining Part 2 gap (we have 3–5 key players/team). See [SCHEMA_PART2.md](SCHEMA_PART2.md).

---

## Verification

Output is checked, not assumed.

**Spine (`build_dataset.py`):**
- date range within window; **0** rows with NA scores; **0** rows without a WC26 team
- coverage re-counted independently from raw vs the fresh martj42 master: **1,850/1,850** played WC48 internationals captured, **0** duplicate `match_id`. Cache is byte-identical to the current martj42 master.
- per-team counts sit in a plausible 37-68 range (Netherlands 49; small FAs like Haiti/Curaçao/New Zealand at 37; CONCACAF/Asian sides higher from Gold/Asian Cups)
- scorelines spot-checked: 2022 WC Final Argentina 3-3 France (so Argentina) ✓; Euro 2024 Final Spain 2-1 England ✓; Copa América 2024 Final Argentina 1-0 Colombia ✓

**Extras (`build_extras.py`):** `deep_history` 4yr subset == 1,850; `h2h` integrity `a_wins+draws+b_wins == played` for all 335 pairs; spot-checks Argentina 4-1 Brazil (2025-03-25), Spain 5-4 France ✓

**StatsBomb (`fetch_statsbomb.py`):** 173/173 matches have non-empty stats for both sides; derived goals reconcile **173/173** to the real scoreline after excluding shootout penalties (period 5) and crediting own goals; xG spot-checks match known values (WC22 final 2.76–2.27). Penalty-shootout shots were initially (and incorrectly) inflating xG — caught and fixed.

**api-football (`fetch_apifootball.py`):** stage/venue/referee/HT verified against known finals (WC22 Lusail, ref Marciniak, HT 2-0, pens 4-2; Euro24 Olympiastadion Berlin; Copa24 Hard Rock).

---

## Known gaps (honesty over completeness)

- **xG / shots** only for the 173 big-tournament matches (StatsBomb open data). FBref, which would extend xG to qualifiers/friendlies, is **Cloudflare-blocked from this VM's datacenter IP** (403).
- **api-football context stops at season 2024** on the free plan, so the **2025–2026 WC qualifying cycle** (CONMEBOL/UEFA/AFC/CONCACAF/OFC) and 2025 tournaments have no stage/venue/referee. A paid plan would unlock them.
- **Attendance** and **lineups** cover only WC 2022 (openfootball, CC0); WC 2018 lineups are in the deep table. Other competitions have neither — openfootball is WC-finals-only, and the 2026 qualifiers aren't in it. Wikipedia/Wikidata would be the source for the rest.
- **Injuries / managers** are **Part 2** (see [SCHEMA_PART2.md](SCHEMA_PART2.md)), not yet collected. The `notes` column is reserved.

## Next steps

- **Part 2 — recent team developments**: schema designed in [SCHEMA_PART2.md](SCHEMA_PART2.md) (form, squad, injuries, manager/tactics, qualification path, momentum). Not yet collected.
- **Prediction model** (after data is locked): rolling-form + Elo/SPI features off `team_match_log.csv` / `deep_history.csv`; a Poisson / Dixon-Coles goals model; Monte-Carlo the bracket encoded in `index.html`.

## Sources & licensing

Full table in **[SOURCES.md](SOURCES.md)**. In short: match spine = martj42/international_results (open, attribution); xG = **StatsBomb open data (CC BY-NC-SA, attribution required)**; context = api-football (commercial, free tier); `BBC_WC_26_WALL_CHART.pdf` is BBC copyright (reference only, do not redistribute). API keys live in a gitignored `.env`.
