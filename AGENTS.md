# Agent handoff

You are continuing work on a **2026 World Cup match-prediction model**. This repo is the shared workspace; it was set up on a laptop and you are likely running inside an isolated VM.

## What already exists (verified, trust it)

- `data/team_match_log.csv` - one row per WC26 team per match, last 4 years (2022-06-07 → 2026-06-07). **Start here.**
- `data/matches.csv` - canonical match-level table.
- `data/team_summary.csv` - per-team aggregates.
- `data/*_raw.csv` - raw source pulls from martj42/international_results.
- `build_dataset.py` - regenerates all of the above from the raw files (stdlib only). Re-run if you change the schema.
- `index.html` - the WC26 fixtures + bracket (all 104 matches, group structure, knockout feeders) encoded as data. Good source for the tournament structure to simulate.

Read `README.md` for the full data dictionary and verification notes.

## The goal

Build the prediction model. Pull in / use the historical scores already collected, engineer features, fit a goals model (Poisson / Dixon-Coles or an Elo/SPI rating), and simulate the tournament to produce score predictions and advancement probabilities. Keep everything reproducible and **verify your work against known results** before trusting it.

## Rules of the road

- Do not fabricate data. If a field (injuries, xG) is not in the source, say so. The `notes` column is reserved for enrichment.
- Keep the dataset rebuildable: changes to schema go through `build_dataset.py`, not hand edits.
- Commit your work in small, described steps. Branch off `main`.
