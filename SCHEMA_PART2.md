# Part 2 schema — recent team developments

> Status: **populated (qualitative layer), 2026-06-07 snapshot.** The coach / form /
> injuries / news / momentum layer is collected for all 48 teams; see the tables below.
> Still open: full 26-man squad rosters (we have 3–5 *key players* per team, not the
> complete roster) and per-player club-season stat lines.
>
> What was built (`build_team_state.py` + `build_part2.py`, from cited research in
> `data/part2_raw/<team>.json`):
> | file | rows | grain |
> |---|---|---|
> | `team_state.csv` | 48 | one row per team — derived form + researched coach/qual/momentum/shape verdict |
> | `team_injuries.csv` | 77 | one row per injury/doubt/suspension (100% cited) |
> | `team_news.csv` | 144 | one row per dated news item (100% cited) |
> | `team_key_players.csv` | 232 | one row per key-player note |
> | `team_state_form.csv` | 48 | derived-only form/warm-up signals (no external calls) |
>
> Rules followed: scripted + cached (raw research JSON per team under `data/part2_raw/`),
> no fabrication (honest blanks — injuries found for 36/48, the rest left empty), every
> injury and news row carries a real `source_url`. The original schema design follows.

Goal: per participating team, a super-detailed snapshot of the state going **into**
the 2026 tournament — form, squad, injuries, manager/tactics, qualification path,
key players, momentum, off-pitch news.

Grain decision: a **hybrid of three long tables**, not one-file-per-team. Long tables
are tidy, diff-friendly, and join cleanly to the Part 1 data on `team` (the martj42
spelling, the existing key in `team_summary.csv` / `team_match_log.csv`).

---

## 1. `team_state.csv` — one row per team (48 rows)

Scalar / summary snapshot. `snapshot_date` makes it reproducible and timestamps the
"as of" moment (form and injuries change weekly).

| column | type | meaning | candidate source |
|---|---|---|---|
| `team` | str | martj42 spelling (join key to Part 1) | — |
| `team_display` | str | wall-chart name | Part 1 `team_summary` |
| `wc_group` | str | 2026 group A–L | Part 1 |
| `snapshot_date` | date | "as of" date for everything in the row | — |
| `fifa_rank` | int | FIFA/Coca-Cola world ranking | fifa.com / api-football |
| `fifa_points` | float | ranking points | fifa.com |
| `manager` | str | head coach name | transfermarkt / Wikipedia |
| `manager_since` | date | appointment date | transfermarkt / Wikipedia |
| `manager_nationality` | str | | transfermarkt |
| `base_formation` | str | most-used XI shape, e.g. `4-3-3` | transfermarkt / whoscored |
| `tactical_notes` | str | short free-text style summary | match reports |
| `form_last10` | str | W/D/L string, most recent first, e.g. `WWDLW…` | Part 1 `team_match_log` (derivable now) |
| `form_points_last10` | int | points in last 10 | Part 1 (derivable now) |
| `gf_last10` / `ga_last10` | int | goals for/against, last 10 | Part 1 (derivable now) |
| `qual_path` | str | how they qualified (group win / playoff / host) | Wikipedia |
| `qual_pld/w/d/l/gf/ga` | int | qualification record | Wikipedia / api-football |
| `qual_convincingness` | str | qualitative: dominant / comfortable / scraped / host | derived + reports |
| `momentum` | str | rising / steady / declining (qualitative, justified) | derived + reports |
| `key_absences` | str | headline injuries/suspensions (free text; detail in table 3) | transfermarkt |
| `squad_market_value_eur` | int | total squad value | transfermarkt |
| `avg_squad_age` | float | | transfermarkt |
| `caps_concentration` | float | share of caps in core XI (experience proxy) | derived |
| `notes` | str | anything else material | — |

Several `*_last10` / `qual_*` fields are **already derivable from Part 1** without any
new source — compute them in a build step, don't re-collect.

## 2. `squad_roster.csv` — one row per player per team (~26 × 48 ≈ 1,250 rows)

The current/expected squad and each player's club-season form.

| column | type | meaning | source |
|---|---|---|---|
| `team` | str | join key | — |
| `snapshot_date` | date | | — |
| `player` | str | full name | transfermarkt / api-football |
| `position` | str | GK/DF/MF/FW (+ detailed) | transfermarkt |
| `age` | int | | transfermarkt |
| `caps` / `intl_goals` | int | international caps / goals | transfermarkt / Wikipedia |
| `club` | str | current club | transfermarkt |
| `club_league` | str | club competition | transfermarkt |
| `market_value_eur` | int | | transfermarkt |
| `season_apps` / `season_goals` / `season_assists` | int | club-season form (2025/26) | fbref/api-football |
| `season_minutes` | int | club minutes (fitness/role proxy) | api-football |
| `is_probable_starter` | bool | expected XI | reports (qualitative) |
| `status` | str | fit / injured / doubt / suspended | transfermarkt injuries |
| `notes` | str | | — |

## 3. `team_news.csv` — one row per dated news/event item (variable rows)

Time-stamped material developments: injury updates, squad announcements, manager
remarks, off-pitch events. Keeps free-text out of the structured tables and is
append-only so the history of the run-in is preserved.

| column | type | meaning |
|---|---|---|
| `team` | str | join key |
| `date` | date | event date |
| `category` | str | injury / suspension / squad / manager / tactical / offpitch / form |
| `headline` | str | one line |
| `detail` | str | paragraph |
| `source_url` | str | citation (required — no uncited claims) |
| `impact` | str | high / medium / low (qualitative) |

---

## Sources for Part 2 (to be added to SOURCES.md when collection starts)

- **transfermarkt** (squads, market values, ages, injuries, managers) — scrape; keyless
  but rate-limited; cache raw HTML/JSON. Check ToS.
- **api-football** (squads, player season stats, coaches, injuries, FIFA-style rank) —
  paid plan needed for current-season (2025/26) and 2026 data (free = 2022–2024 only;
  see Part 1 note). The `/players`, `/injuries`, `/coachs`, `/squads` endpoints fit here.
- **Wikipedia** (qualification paths, squad announcement lists) — keyless.
- **fifa.com** (official world ranking) — keyless.

## Already-derivable now (no new source)

`form_*`, `qual_*` record, and basic momentum can be computed from Part 1's
`team_match_log.csv`. A future `build_team_state.py` should fill those columns first,
then external collection layers add squad/injury/manager/value fields on top.
