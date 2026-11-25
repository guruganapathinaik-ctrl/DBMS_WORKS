# Mobile Game Analytics: From Player Behaviour to Predictive Intelligence

**DBMS Lab End-Semester Analytics Project** — An end-to-end SQL, DuckDB, and Python analytics investigation covering player telemetry profiling, daily health, cohort retention, monetisation decomposition (Simpson's Paradox), acquisition channel causal/confounding evaluation, and 14-day player churn prediction.

---

## 1. Project Overview

This project analyses **120 days of production-style live-service mobile game telemetry** (`2026-01-01` to `2026-04-30`) across **80,295 player accounts** and **667,435 active player-days** to answer a core product & studio objective: **how to grow revenue without increasing marketing spend**.

Before any modelling or KPI reporting, Phase 1 conducts a full data-quality audit across all five telemetry tables (`player_profile`, `player_day`, `purchase`, `currency_spend`, `ad_view`), uncovering and documenting critical telemetry issues (an `+8h` timezone offset and a 2-day outage in `ad_view`, unreliable `original_device_id` linkages, duplicate `purchase_id`s, refund rows, unmatched purchase dates, and extreme `currency_value` outliers). All four analytical deliverables are implemented in reproducible SQL and Python and verified by independent raw-CSV audit scripts.

---

## 2. Objectives

1. **Data Quality & Schema Integrity:** Profile all telemetry tables, establish safe join patterns, and document analytical decisions.
2. **Deliverable 1 — Player Behaviour & SQL Health:** Measure daily active users (DAU), gross/net revenue, ARPDAU, mature weekly cohort retention, spender concentration, and rewarded-ad cap engagement.
3. **Deliverable 2 — ARPDAU Deep Dive:** Explain why overall ARPDAU dropped `-16.32%` between January and April while every country tier improved.
4. **Deliverable 3 — Acquisition Channel Evaluation:** Compare `organic`, `paid_social`, and `paid_video` on engagement and revenue while adjusting for demographic and censoring bias.
5. **Deliverable 4 — Predictive Churn Modelling:** Predict which currently active players (`active in last 7 days`) will stop playing over the next 14 days, and evaluate targeting trade-offs for live-ops retention offers.

---

## 3. Dataset Description

> **Privacy Notice:** Raw player-level CSVs (`data/*.csv`) and the local DuckDB database (`outputs/telemetry.duckdb`) are intentionally excluded from GitHub and submission archives via `.gitignore`. See [data/README.md](data/README.md) for details.

| Table | Rows | Unique `device_id`s | Granularity |
| --- | ---: | ---: | --- |
| `player_profile` | 80,295 | 80,295 | One row per player/device account (`install_date`, `platform`, `country_tier`, `acquisition_channel`) |
| `player_day` | 667,435 | 79,181 | One row per active `(device_id, activity_date)` (`player_level`, `session_count`, `playtime_minutes`) |
| `purchase` | 15,426 | 11,054 | Real-money IAP transactions and negative refund rows (`usd_amount`, `pack_name`, `sale_flag`) |
| `currency_spend` | 489,892 | 73,216 | In-game currency spend events (`PREMIUM`, `SOCIAL`, `GRIND`) |
| `ad_view` | 647,623 | 74,042 | Rewarded-video ad interactions (`status`, `ad_daily_count`, `ad_daily_cap`) |

---

## 4. Technology Stack

- **Database & Query Engine:** DuckDB (`2.0.1`), SQL (CTEs, window functions, `FULL OUTER JOIN`, date alignment)
- **Data Analysis & Statistics:** Python (`3.12`), Pandas (`3.1.1`), NumPy (`2.5.5`), SciPy (`1.18.1`)
- **Predictive Modelling:** scikit-learn (`1.9.1`) — `DummyClassifier`, `LogisticRegression`, `DecisionTreeClassifier`, `HistGradientBoostingClassifier`
- **Visualisation:** Matplotlib (`3.11.2`), Seaborn (`0.13.2`)

---

## 5. Project Folder Structure

```text
DBMS_END_SEM/
├── DBMS-LAB-END-SEM.pdf            # Assignment brief
├── README.md                       # Project documentation
├── requirements.txt                # Python dependencies
├── .gitignore                      # Excludes raw data, telemetry.duckdb, temp/cache files
├── data/
│   └── README.md                   # Schema & exclusion policy (raw CSVs kept local only)
├── notebooks/                      # Reserved for interactive notebooks (unused; all pipelines in src/ & sql/)
├── outputs/
│   ├── README.md                   # Output & DuckDB exclusion policy
│   ├── charts/                     # 16 generated PNG visualisations (Deliverables 1-4)
│   └── tables/                     # 28 aggregated summary CSV tables (zero player-level IDs)
├── presentation/
│   └── README.md                   # Presentation folder documentation (Gamma PPTX status)
├── reports/
│   ├── analytical_decisions.md     # Phase 1 documented data-quality rules
│   ├── dataset_profile.md          # Table schemas & volume profile
│   ├── data_quality_report.md      # 8 verified telemetry anomalies
│   ├── table_relationships.md      # ER diagram, keys & join safety rules
│   ├── deliverable_1_report.md     # Deliverable 1 report + deliverable_1_audit.md
│   ├── deliverable_2_report.md     # Deliverable 2 report + deliverable_2_audit.md
│   ├── deliverable_3_report.md     # Deliverable 3 report + deliverable_3_audit.md
│   ├── deliverable_4_report.md     # Deliverable 4 report + deliverable_4_audit.md
│   ├── final_project_inventory.md  # Complete file & deliverable inventory
│   └── final_submission_audit.md   # Final pre-submission PASS/FAIL/WARNING audit
├── sql/
│   ├── phase1_quality_checks.sql
│   ├── task_1a_daily_health.sql
│   ├── task_1b_retention.sql
│   ├── task_1c_spender_behaviour.sql
│   ├── task_1d_ad_engagement.sql
│   ├── task_2_arpdau_deep_dive.sql
│   ├── task_3_acquisition_analysis.sql
│   └── task_4_churn_analysis.sql
└── src/
    ├── build_duckdb.py             # Builds local outputs/telemetry.duckdb from data/*.csv
    ├── phase1_*.py / phase3_*.py / phase4_*.py
    ├── task_1_analysis.py          # Runs Deliverable 1 SQL + charts
    ├── task_2_deep_dive.py         # Runs Deliverable 2 SQL + Kitagawa decomposition + charts
    ├── task_3_analysis.py          # Runs Deliverable 3 SQL + bootstrap CIs + Holm tests + charts
    ├── task_4_churn_analysis.py    # Runs Deliverable 4 SQL + ML models + scenarios + charts
    └── audit_deliverable_{1..4}.py # Independent raw-CSV validation scripts
```

---

## 6. Deliverables Summary & Key Findings

### Deliverable 1 — Exploratory SQL Analysis (`reports/deliverable_1_report.md`)
- **Daily Health:** `667,435` active player-days across 120 days (Android avg DAU `3,821.5`; iOS avg DAU `1,740.5`). Gross positive revenue `$219,434.02`, refunds `-$3,274.72`, net raw revenue `$216,159.30` (`$214,343.48` deduplicating 122 `purchase_id` pairs).
- **Retention Funnel (mature 2026 cohorts):** Day 1 `47.68%`, Day 7 `25.48%`, Day 14 `19.50%`, Day 30 `13.91%`.
- **Spender Concentration:** `86.23%` (`69,241 / 80,295`) never purchased. Among the `11,054` payers, the Top 10% (`1,106` payers) generated `47.79%` of gross revenue.
- **Rewarded Ads:** `-8h` timestamp shift aligns `100.00%` of `647,623` ad rows with `player_day`; March 5–6 had a 2-day logging outage (`0` ads). Overall cap-hit rate is `0.9604%`.

### Deliverable 2 — ARPDAU Deep Dive (`reports/deliverable_2_report.md`)
- Comparing **Jan 1–30** vs. **Apr 1–30, 2026**: active player-days grew `+243.26%` (`82,381 → 282,781`) and gross revenue grew `+187.25%` (`$29,383.67 → $84,404.41`), yet weighted gross ARPDAU fell **`-16.32%`** (`$0.3567 → $0.2985`; net `-16.49%`).
- **Simpson's Paradox:** Every `country_tier` improved (`Tier 1 +7.03%`, `Tier 2 +8.50%`, `Tier 3 +13.50%`, `Tier 4 +1.97%`). Symmetric Kitagawa decomposition proves within-tier monetisation added **`+$0.0240`**, while Tier 4's surge (`17.65% → 45.99%` of player-days via `paid_video`) subtracted **`-$0.0822`**, explaining the exact `-$0.0582` drop.
- **Recommendation:** Replace blended ARPDAU with tier-stratified ARPDAU reporting.

### Deliverable 3 — Acquisition Channel Quality (`reports/deliverable_3_report.md`)
- Evaluated on the uncensored **Jan 1–Mar 31, 2026** 30-day cohort (`n = 37,489`).
- **Confounding Removed:** `paid_video` appears worst unadjusted (`$1.55` gross ARPU) solely due to Tier 4 (`71.09%`) and Android (`81.35%`) mix. After `country_tier × platform` standardization:
  - **Organic:** `7.079` active days, `25.86%` D7, `13.72%` D30, `$2.17` gross / `$2.13` net ARPU.
  - **Paid Social:** `6.865` active days, `25.34%` D7, `14.42%` D30, `$1.99` gross / `$1.97` net ARPU.
  - **Paid Video:** `6.774` active days, `24.52%` D7, `13.82%` D30, `$2.06` gross / `$2.04` net ARPU.
- `organic` holds a small engagement advantage (`p < 0.0001`), `paid_social` vs. `paid_video` adjusted revenue is statistically indistinguishable, and `organic` vs. `paid_social` adjusted revenue is inconclusive (`Holm p = 0.4497`). Do not reallocate UA budget without missing CPI and ad-revenue data.

### Deliverable 4 — Player Churn Prediction (`reports/deliverable_4_report.md`)
- Predicts 14-day inactivity (`0` active days in `[T+1, T+14]`) for players active in `[T-6, T]` using leak-free out-of-time splits: Train (`2026-03-02`, `n=20,025`), Validation (`2026-03-23`, `n=26,886`), Test (`2026-04-16`, `n=38,644`, `7,238` churners = `18.73%`).
- **Selected Model:** Calibrated **Logistic Regression (`C=1.0`)** achieves **`ROC-AUC = 0.7467`**, **`PR-AUC = 0.3830`** (`2.04×` random), and **`Brier = 0.1366`** (`ROC-AUC = 0.7852` on `20,129` unseen Test players).
- **Targeting Trade-Offs (Test Set):**
  - Top 5% (`1,933`): `931` caught, `48.16%` precision, `12.86%` recall
  - Top 10% (`3,865`): `1,735` caught, `44.89%` precision, `23.97%` recall
  - **Top 20% (`7,729`, Recommended Default):** **`3,071` caught**, **`39.73%` precision**, **`42.43%` recall**
  - Top 30% (`11,593`): `4,206` caught, `36.28%` precision, `58.11%` recall
- **Recommendation:** Validate causal lift with a randomized A/B holdout on the Top 20% tier before scaling live-ops offer spend.

---

## 7. Installation & Execution

> **Prerequisite:** Place the five original CSV files in `data/` before running scripts locally (see [data/README.md](data/README.md)).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build local DuckDB database (outputs/telemetry.duckdb)
python src/build_duckdb.py

# 3. Run Deliverables 1–4
python src/task_1_analysis.py
python src/task_2_deep_dive.py
python src/task_3_analysis.py
python src/task_4_churn_analysis.py

# 4. Run independent raw-CSV quality audits
python src/audit_deliverable_1.py
python src/audit_deliverable_2.py
python src/audit_deliverable_3.py
python src/audit_deliverable_4.py
```

---

## 8. Key Limitations

- **Missing Finance / Marketing Inputs:** No CPI, channel ad spend, or rewarded-ad revenue exists in telemetry, preventing exact UA profitability (`LTV / CPI`) or retention offer ROI conclusions.
- **Observational Telemetry Only:** Churn risk scores identify players likely to lapse, **not** whether an offer will save them; randomized experiments are required for causal lift.
- **Model Weaknesses:** Churn discrimination drops among long-tenure `91+ day` active players (`ROC-AUC = 0.6241`), and upper-tail probabilities (`>= 0.67`) slightly overpredict observed churn (`51.7%`).
- **Right-Censoring & Legacy History:** Mid/late-April cohorts lack full 30-day maturity; 2025 legacy installs lack pre-`2026-01-01` transaction logs.

---

## 9. Academic Disclaimer

This repository was developed as an academic end-semester DBMS Lab analytics project at **National Institute of Technology Warangal**. All raw player-level datasets and local DuckDB database files are excluded from version control for data privacy and repository hygiene.
