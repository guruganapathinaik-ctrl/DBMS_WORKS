# Data Directory (`data/`)

## Privacy & Repository Exclusion Policy

The original player-level CSV datasets are **intentionally excluded** from GitHub and the submission archive (`.gitignore`) to avoid publishing player-level telemetry and large (~103 MiB) raw data files.

## Expected Local Files (Required to Re-Run Pipelines)

Place the five untouched assignment CSV files in this directory before executing `src/build_duckdb.py` or the `src/audit_deliverable_*.py` scripts:

1. `player_profile - player_profile.csv` (`80,295` rows — account metadata)
2. `player_day - player_day.csv` (`667,435` rows — daily activity summaries)
3. `purchase - purchase.csv` (`15,426` rows — real-money transactions & refunds)
4. `currency_spend - currency_spend.csv` (`489,892` rows — in-game currency spends)
5. `ad_view - ad_view.csv` (`647,623` rows — rewarded-video ad interactions)

If an academic evaluator requires the raw telemetry files, supply them separately through the approved course submission channel rather than committing them to a public GitHub repository.
