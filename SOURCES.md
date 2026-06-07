# Sources & licensing

Every data source used in this repo, what it provides, how it's pulled, and its
licence/terms. Raw pulls are cached under `data/` (see each row) so builds are
repeatable offline. Nothing here is fabricated; fields with no source are left blank.

| source | provides | files / cache | how pulled | licence / terms |
|---|---|---|---|---|
| **martj42/international_results** | the spine: every men's international (date, teams, score, tournament, city/country/neutral) + goalscorers + shootouts | `data/results_raw.csv`, `goalscorers_raw.csv`, `shootouts_raw.csv` → `matches.csv`, `team_match_log.csv`, `team_summary.csv`, `deep_history.csv`, `h2h.csv` | `build_dataset.py`, `build_extras.py` (raw committed) | Open data, CC0-style community dataset. Attribution kept. Personal/non-commercial use. |
| **StatsBomb open-data** | shot-level **xG**, shots, shots-on-target, corners, fouls, yellow/red cards, passes; + stage, match week, stadium, referee | raw events `data/statsbomb_raw/events/` (gitignored, 560 MB, re-downloadable), match indexes `data/statsbomb_raw/matches/` (committed) → `statsbomb_match_stats.csv` | `fetch_statsbomb.py` (GitHub raw, keyless) | **CC BY-NC-SA 4.0**. Free for non-commercial use **with attribution to StatsBomb**. Covers WC 2022, AFCON 2023, Copa América 2024, Euro 2024 (173 in-window matches). |
| **api-football (API-Sports v3)** | match **context**: competition + stage/round (+matchday), stadium name, venue city, referee, halftime score, extra-time + penalty breakdown | `data/apifootball_raw/fixtures_*.json` (committed) → `apifootball_context.csv` | `fetch_apifootball.py`, key in gitignored `.env` | Commercial API. **Free plan = 100 req/day AND data only for seasons 2022–2024.** → the entire 2026 WC qualifying cycle (tagged season 2026) and 2025 tournaments are **not retrievable without a paid plan**. 654 matches covered. |
| **football-data.org** | scores/lineups for WC + Euro only (free tier) | not used | — | Free tier with key; only 13 competitions, **no qualifiers/NL/Copa/AFCON/friendlies and no xG** → redundant with StatsBomb here, so not pulled. Key held for future use. |
| **FBref / StatsBomb (via fbref)** | would add broad xG/shots beyond the 4 majors | — (not used) | — | **Blocked from this VM**: FBref returns Cloudflare 403 to datacenter IPs. Not a reliable source from here; documented gap. |
| `BBC_WC_26_WALL_CHART.pdf` | the 2026 fixtures/bracket reference for `index.html` | committed locally | — | **BBC copyright.** Reference only, do not redistribute. |

## API keys

Keys live in `.env` (gitignored, never committed). To rebuild the API layers, create
`.env` with:

```
APIFOOTBALL_KEY=...
FOOTBALLDATA_KEY=...
```

## Attribution notes

- **StatsBomb**: "Data provided by StatsBomb" — required by their CC BY-NC-SA licence.
- **martj42/international_results**: community open dataset, attribution kept in README.

## Known gaps (honesty over completeness)

- **xG** exists only for the 173 big-tournament matches (StatsBomb). Qualifiers,
  Nations League, and friendlies have no xG from a reliable source reachable here.
- **api-football context** stops at season 2024 on the free plan → no stage/venue/referee
  for the 2025–2026 WC qualifiers without upgrading the plan.
- **Attendance** is not populated anywhere — neither StatsBomb's match index nor
  api-football's fixture payload includes it; Wikipedia/Wikidata would be the source.
- **Lineups / injuries / managers** are Part 2 (see `SCHEMA_PART2.md`), not yet collected.
