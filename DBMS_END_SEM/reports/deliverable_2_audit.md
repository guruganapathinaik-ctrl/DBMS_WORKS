# Deliverable 2 — Independent Quality Audit

**Audit Scope:** Independent recalculation and verification of Deliverable 2 (Option A: *"ARPDAU is falling. Fix it."*) directly from the untouched raw CSV files (`data/*.csv`) compared against `sql/task_2_arpdau_deep_dive.sql`, `src/task_2_deep_dive.py`, all four CSV tables (`outputs/tables/task_2_*.csv`), all four PNG charts (`outputs/charts/task_2_*.png`), and `reports/deliverable_2_report.md`.  
**Audit Script:** `src/audit_deliverable_2.py` (executed with exit code `0`; all 10 checks passed).

---

## 1. Overall Verdict: PASS (All 10 Criteria Verified)

| # | Audit Criterion | Status | Verified Evidence |
| --- | --- | --- | --- |
| **1** | **Exact Jan & Apr 30-day windows** | **PASS** | `first_30d`: exact `2026-01-01` to `2026-01-30` (`30` days, excludes Jan 31); `last_30d`: exact `2026-04-01` to `2026-04-30` (`30` days) in both `player_day` and `purchase`. |
| **2** | **Gross revenue & active player-days** | **PASS** | Independent raw-CSV sums match 100%: Period 1 = `$29,383.67` gross (`-$456.76` refunds, `$28,926.91` net) over `82,381` player-days (`22,999` unique players); Period 2 = `$84,404.41` gross (`-$1,478.94` refunds, `$82,925.47` net) over `282,781` player-days (`73,756` unique players). Zero row multiplication or confusion between players and player-days. |
| **3** | **Weighted ARPDAU vs. Daily Avg ARPDAU** | **PASS** | Weighted Gross ARPDAU = `total_gross / total_player_days` (`$0.3567` → `$0.2985`, `-16.32%`). Daily Avg Gross ARPDAU is reported separately (`$0.3583` → `$0.2963`, `-17.31%`). |
| **4** | **All four `country_tier` calculations** | **PASS** | Independent raw recalculation matches all 4 tiers: Tier 1 `+7.03%`, Tier 2 `+8.50%`, Tier 3 `+13.50%`, Tier 4 `+1.97%` (gross); Net ARPDAU also rose in every tier (`+5.34%`, `+10.87%`, `+13.63%`, `+0.57%`). |
| **5** | **Player composition denominators** | **PASS** | `player_day_share_pct`, `unique_player_share_pct`, and `gross_revenue_share_pct` each sum cleanly to `100.00%` in both periods. Tier 4 player-day share rose from `17.65%` to `45.99%` (`+28.33 pp`), driven by `paid_video` (`79.80%` of Apr Tier 4 activity). |
| **6** | **Simpson's Paradox math & counterfactual** | **PASS** | Counterfactual fixed-Jan-weight Gross ARPDAU = `$0.3851` (`+$0.0284` / `+7.97%` vs Jan). Independent Net ARPDAU check confirms identical direction: counterfactual Net = `$0.3780` (`+7.65%`). |
| **7** | **Exact decomposition reconciliation** | **PASS** | 2-term symmetric Kitagawa: Within `+$0.024004` + Mix `-$0.082204` = `-$0.058200` (exact zero residual). 3-term Jan-baseline: Within `+$0.028427` + Mix `-$0.077781` + Interaction `-$0.008847` = `-$0.058200`. Net decomposition also reconciles (`+$0.022374 + (-$0.080260) = -$0.057886`). |
| **8** | **Duplicate `purchase_id` sensitivity** | **PASS** | Independent raw deduplication matches `task_2_period_comparison.csv`: `$29,188.90` → `$83,647.92` gross (`-16.51%` ARPDAU), `$28,732.14` → `$82,188.97` net. |
| **9** | **Charts match result tables** | **PASS** | Visual inspection of all 4 PNGs confirms exact consistency with CSV tables (`$0.52→$0.56`, `$0.38→$0.41`, `$0.23→$0.27`, `$0.16→$0.16`, `$0.36→$0.30`; mix shares `34.5%→20.4%`, `17.7%→46.0%`; waterfall `+$0.0240 - $0.0822 = -$0.0582`). |
| **10** | **100% SQL reproducibility** | **PASS** | Re-running `sql/task_2_arpdau_deep_dive.sql` reproduced all saved CSVs identically (`0` discrepancy). |

---

## 2. Assessment of Business Recommendation
- **Evidence Alignment:** The recommendation correctly concludes that monetisation did **not** deteriorate (`+2.0%` to `+13.5%` inside tiers; total revenue `+187.25%`) and warns leadership not to stop Tier 4 acquisition solely because blended ARPDAU dropped.
- **Volume vs. Profitability Distinction:** The report explicitly distinguishes **acquisition volume** (Tier 4 `paid_video` scaling DAU `+243%` and gross revenue `+187%`) from **acquisition profitability**, accurately naming the two missing inputs from the telemetry extract (**marketing CPI / spend by tier & channel** and **rewarded-ad revenue**) and defining the exact decision threshold (`IAP Net LTV + Ad LTV > CPI`).

---

## 3. Corrections Made
- **Calculations / SQL / CSVs / Charts:** **0 errors found** — no recalculation or rerun required.
- **Markdown Table Formatting (`reports/deliverable_2_report.md`):** Fixed a single cell separator typo in Section 3 (`14.87% | 14.37%` → `14.87% → 14.37%` for Tier 2).

---

## 4. Final Validated Metrics
- **Overall Gross ARPDAU:** `$0.3567` (Jan 1–30) → `$0.2985` (Apr 1–30), **`-16.32%`** (`-$0.0582`); Net ARPDAU: `$0.3511` → `$0.2932` (`-16.49%`).
- **Counterfactual Fixed-Weight Gross ARPDAU:** **`$0.3851`** (`+7.97%` improvement).
- **Exact Symmetric Decomposition:** Within-Tier **`+$0.0240`** + Mix-Shift **`-$0.0822`** = **`-$0.0582`** (`100%` reconciled).
- **Tier Growth:** Tier 1 (`+7.03%`), Tier 2 (`+8.50%`), Tier 3 (`+13.50%`), Tier 4 (`+1.97%`).
- **Mix Shift:** Tier 4 share of active player-days rose from `17.65%` to `45.99%` (`+28.33 pp`), while Tiers 1 & 2 still supply `59.61%` of April gross revenue.
