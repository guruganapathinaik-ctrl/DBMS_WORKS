# Final Project Inventory (`DBMS_END_SEM`)

**Audit Timestamp:** 2026-11-25 16:40 IST  
**Project Root:** `C:\Users\G G NAIK\Documents\DBMS_END_SEM`

---

## 1. Directory & File Inventory

| Folder / File | Item Count | Status | Notes |
| --- | ---: | --- | --- |
| `DBMS-LAB-END-SEM.pdf` | 1 | Present | Original assignment brief (7 pages) |
| `data/` | 5 CSVs + `README.md` | **Excluded from Git/ZIP** | Untouched raw player-level CSVs (~103 MiB total) |
| `sql/` | 8 `.sql` files | Complete | `phase1_quality_checks.sql`, `task_1a..1d`, `task_2`, `task_3`, `task_4` |
| `src/` | 19 `.py` files | Complete | Phase 1–4 exploration, `build_duckdb.py`, `task_1..4`, `audit_deliverable_1..4.py`, plus `build_presentation.py` (earlier automated draft) |
| `outputs/tables/` | 28 `.csv` files | Complete (Safe) | Aggregated tables only — 0 player-level IDs |
| `outputs/charts/` | 16 `.png` files | Complete | 4 charts per deliverable (Deliverables 1–4) |
| `outputs/telemetry.duckdb` | 1 `.duckdb` | **Excluded from Git/ZIP** | Local DuckDB copy of all 5 tables |
| `reports/` | 14 `.md` files | Complete | 4 Phase-1 reports, 4 Deliverable reports, 4 Audit reports, plus `final_project_inventory.md` & `final_submission_audit.md` |
| `notebooks/` | 0 files | Empty | Unused; all reproducible code resides in `sql/` and `src/` |
| `presentation/` | `README.md` (+ local draft) | **WARNING** | Gamma PPTX (`DBMS_END.pptx`, previously observed `1,224,915` B) is **not currently present**; earlier auto-generated `Mobile_Game_Analytics_Executive_Readout.pptx` is excluded via `.gitignore` |
| `.tmp/` | Temp artifacts | **Excluded from Git/ZIP** | DuckDB temp storage, temporary chart/slide renders, temp remote clone |

---

## 2. Deliverable Artifacts Breakdown

- **Deliverable 1 (SQL Analysis):**
  - SQL: `sql/task_1a_daily_health.sql`, `sql/task_1b_retention.sql`, `sql/task_1c_spender_behaviour.sql`, `sql/task_1d_ad_engagement.sql`
  - Python: `src/task_1_analysis.py`, `src/audit_deliverable_1.py`
  - Tables: `task_1a_daily_health.csv`, `task_1b_retention.csv`, `task_1c_spender_behaviour.csv`, `task_1d_ad_engagement.csv`
  - Charts: `daily_health.png`, `retention_heatmap.png`, `spender_analysis.png`, `ad_engagement.png`
  - Reports: `reports/deliverable_1_report.md`, `reports/deliverable_1_audit.md`

- **Deliverable 2 (ARPDAU Deep Dive):**
  - SQL: `sql/task_2_arpdau_deep_dive.sql`
  - Python: `src/task_2_deep_dive.py`, `src/audit_deliverable_2.py`
  - Tables: `task_2_period_comparison.csv`, `task_2_tier_comparison.csv`, `task_2_player_mix.csv`, `task_2_decomposition.csv`
  - Charts: `task_2_arpdau_comparison.png`, `task_2_tier_trends.png`, `task_2_player_mix.png`, `task_2_decomposition.png`
  - Reports: `reports/deliverable_2_report.md`, `reports/deliverable_2_audit.md`

- **Deliverable 3 (Acquisition Channel Analysis):**
  - SQL: `sql/task_3_acquisition_analysis.sql`
  - Python: `src/task_3_analysis.py`, `src/phase3_explore.py`, `src/phase3_stats_check.py`, `src/audit_deliverable_3.py`
  - Tables: `task_3_channel_profile.csv`, `task_3_monthly_mix.csv`, `task_3_engagement_metrics.csv`, `task_3_revenue_metrics.csv`, `task_3_stratified_metrics.csv`, `task_3_adjusted_comparison.csv`, `task_3_statistical_tests.csv`
  - Charts: `task_3_channel_mix.png`, `task_3_engagement_comparison.png`, `task_3_revenue_comparison.png`, `task_3_confidence_intervals.png`
  - Reports: `reports/deliverable_3_report.md`, `reports/deliverable_3_audit.md`

- **Deliverable 4 (Churn Prediction):**
  - SQL: `sql/task_4_churn_analysis.sql`
  - Python: `src/task_4_churn_analysis.py`, `src/phase4_explore.py`, `src/phase4_feature_check.py`, `src/audit_deliverable_4.py`
  - Tables: `task_4_churn_definition_evidence.csv`, `task_4_eda_segments.csv`, `task_4_feature_summary.csv`, `task_4_model_comparison.csv`, `task_4_feature_importance.csv`, `task_4_threshold_analysis.csv`, `task_4_subgroup_errors.csv`, `task_4_cost_value_scenarios.csv`
  - Charts: `task_4_eda_churn_drivers.png`, `task_4_model_evaluation.png`, `task_4_targeting_tradeoffs.png`, `task_4_cost_value_heatmap.png`
  - Reports: `reports/deliverable_4_report.md`, `reports/deliverable_4_audit.md`

---

## 3. Issues & Environment Findings Noted During Inspection

1. **Missing Gamma PPTX:** `presentation/DBMS_END.pptx` was observed earlier (`4:19 PM`) but is absent from `presentation/` during this final audit; must be copied manually by the user before final submission.
2. **Parent Drive `.git` Directory:** `C:\.git` exists at the system root (`NT SERVICE/TrustedInstaller`), triggering `dubious ownership` warnings when running `git` directly in `DBMS_END_SEM` without a local repo. Pushing via a clean clone of `DBMS_LAB_WORKS` avoids touching `C:\.git`.
3. **Public GitHub Target Repository:** `https://github.com/guruganapathinaik-ctrl/DBMS_LAB_WORKS` is public (`private = False`) and already contains `DBMS_LA1.pdf`–`DBMS_LA4.pdf` and `README.md` at commit `c68e946`. Therefore this project must be placed inside a dedicated `DBMS_END_SEM/` folder while preserving existing files and history.
