# Deliverable 4 — Independent Quality Audit

**Audit Scope:** Independent verification of Deliverable 4 (*"Predict which players are about to churn"*) directly against the untouched raw CSV files (`data/*.csv`), compared against `sql/task_4_churn_analysis.sql`, `src/task_4_churn_analysis.py`, all 8 CSV tables (`outputs/tables/task_4_*.csv`), all 4 charts (`outputs/charts/task_4_*.png`), `reports/deliverable_4_report.md`, and intactness of Deliverables 1–3.  
**Audit Script:** `src/audit_deliverable_4.py` (executed with exit code `0`, all assertions passed).

---

## 1. Overall PASS / FAIL Summary

| # | Audit Check | Result | Original Reported | Independently Recalculated | Difference | Explanation |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **DuckDB & Raw CSV Integrity** | **PASS** | 5 tables (`80,295 / 667,435 / 15,426 / 489,892 / 647,623`) | Identical across all 5 CSVs | `0` | `outputs/telemetry.duckdb` matches untouched raw CSVs 100%. |
| **2** | **Churn Definition Evidence (`Mar 15`)** | **PASS** | 7 recency buckets (`n=42,706`) | Identical counts & rates (`15.73%` at 0d → `51.95%` at 31+d) | `0.00%` | Independently verified from raw `player_profile` & `player_day` CSVs. |
| **3** | **Snapshot Counts & Zero Right-Censoring** | **PASS** | Train `20,025`, Val `26,886`, Test `38,644` (max label `2026-04-30`) | Identical (`n=85,555` total, 0 censored) | `0` | Every snapshot has full 14-day future window (`snap_date + 14d <= 2026-04-30`), `0` duplicate `device_id`s per split, `0` negative install ages. |
| **4** | **Target Leakage & Split Disjointness** | **PASS** | Strictly past features (`<= T`); `20,129` unseen Test players | `0 / 32` feature columns changed after deleting all future telemetry `> 2026-03-02` | `0` (`atol=1e-4`) | Proves zero future leakage across `player_day`, `purchase`, `currency_spend`, and `-8h` aligned `ad_view`; entry/label windows between splits do not overlap. |
| **5** | **EDA Segments & Age-Tier Confounding** | **PASS** | Overall & segmented churn in `task_4_eda_segments.csv` | Identical across Train, Val, Test | `0.00%` | Stratified check confirms Tier 4 matches Tiers 1–3 within every `install_age_bucket` (`3.94%`, `12.22%`, `20.11%`, `35.20%`). |
| **6** | **Model Metrics (`ROC-AUC`, `PR-AUC`, `Brier`)** | **PASS** | LR `0.7467 / 0.3830 / 0.1366`; DT `0.7330 / 0.3711 / 0.1356`; HGB `0.7580 / 0.4121 / 0.1321` | LR & DT identical (`0.0000`); HGB `0.7579 / 0.4121 / 0.1321` | `0.0000` (LR/DT), `0.0001` (HGB) | Independently re-trained from raw-CSV splits; LR & DT match to 4 decimals (`0.0001` HGB difference is OpenMP float histogram rounding). |
| **7** | **Feature Summary, LR Coefs & Subgroups** | **PASS** | 29 univariate features, 35 LR coefs, 15 subgroup rows | Identical (`<= 1e-4`) | `0` | Multicollinearity verified (`r(act_30d, sess_30d) = 0.920`), explaining LR `act_30d` sign reversal. |
| **8** | **Top-K Thresholds & 72 Cost Scenarios** | **PASS** | Top 5/10/20/30/50% TP/FP & 72 scenario rows | Identical TP/FP counts & net values | `0` / `$0.00` | Verified all confusion matrices, wasted-offer counts, and `saved - cost = net` equations. |
| **9** | **Charts Match CSV Tables** | **PASS** | 4 PNG charts (`task_4_*.png`) | Visually inspected | `0` | Fixed earlier Panel C title & y-limit clipping (`36.6%` bar now cleanly inside `0–42%`); all 4 charts match CSVs. |
| **10** | **Deliverables 1–3 & Raw CSVs Intact** | **PASS** | Deliverables 1–3 reports & audits untouched | Verified present & untouched | `0` | No prior Deliverable 1–3 outputs or raw CSVs were overwritten. |

---

## 2. Key Audit Checks & Diagnostic Notes

1. **Leakage Proof by Destructive Test:**  
   In `src/audit_deliverable_4.py`, we cloned the raw CSVs in memory, ran `DELETE` on all `player_day`, `purchase`, `currency_spend`, and `-8h` aligned `ad_view` rows dated strictly after `2026-03-02`, and re-ran `sql/task_4_churn_analysis.sql`. Every single feature column for all `20,025` Train rows matched identically (`atol = 1e-4` for SQL 4-decimal `DOUBLE` rounding).
2. **Chart Bug Caught & Fixed During Audit:**  
   Initial inspection of `outputs/charts/task_4_eda_churn_drivers.png` revealed that Panel C had a misleading subtitle (`"New Installs Churn Faster in First Week"`) contradicting the bars (`0–7d = 4.5%` vs. `91+d = 36.6%`) and `ylim(0, 32)` clipped the `36.6%` bar. Both were corrected in `src/task_4_churn_analysis.py` and the pipeline was re-executed cleanly.
3. **SQL Determinism Fix:**  
   Adding `ORDER BY e.split_name, e.device_id` to `sql/task_4_churn_analysis.sql` eliminated DuckDB parallel hash-join row-order variance across runs, stabilizing `HistGradientBoosting` metrics (`ROC-AUC = 0.7580`, `PR-AUC = 0.4121`).
4. **Honest Limitations Verified in Report:**  
   - Upper-tail overconfidence (`p >= 0.67` yields `51.7%` actual churn, causing `-$101.25` in the `$0.50 / $5 / 15%` scenario).
   - Weakest discrimination on `91+d` veterans (`AUC = 0.6241`, `Brier = 0.2320`).
   - Causal offer lift ($s$), offer cost ($c$), and ad-revenue LTV ($V$) are absent from telemetry and explicitly flagged as assumptions requiring an A/B holdout.
