# Deliverable 3 — Independent Quality Audit

**Audit Scope:** Independent verification of Deliverable 3 (*"Is one acquisition channel better than another?"*) directly against the untouched raw CSV files (`data/player_profile - player_profile.csv`, `data/player_day - player_day.csv`, `data/purchase - purchase.csv`), compared against `sql/task_3_acquisition_analysis.sql`, `src/task_3_analysis.py`, all 7 CSV tables (`outputs/tables/task_3_*.csv`), all 4 charts (`outputs/charts/task_3_*.png`), and `reports/deliverable_3_report.md`.  
**Audit Script:** `src/audit_deliverable_3.py` (executed with exit code `0`).

---

## 1. Overall PASS / FAIL Summary

| # | Audit Check | Result | Original Reported | Independently Recalculated | Difference | Explanation |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **SQL Reproducibility** | **PASS** | 5 CSVs from SQL queries | Identical 5 tables | `0.000` | Re-executing Queries 1–5 in `sql/task_3_acquisition_analysis.sql` reproduced `task_3_*.csv` identically. |
| **2** | **Channel Counts & Mix (`n=80,295`)** | **PASS** | `paid_video` 34,036 (42.39%); `organic` 24,554 (30.58%); `paid_social` 21,705 (27.03%) | Identical | `0` | Matches raw `player_profile` CSV 100%; `paid_video` is 71.09% Tier 4 & 81.35% Android vs ~18% & ~64% for the other two. |
| **3** | **All-Window Revenue Reconciliation** | **PASS** | Gross `$219,434.02`, Refunds `-$3,274.72`, Net `$216,159.30` | Identical | `$0.00` | Matches raw `purchase` CSV to the cent across all 3 channels; 0 row multiplication. |
| **4** | **Check D: Cohort Eligibility (`Jan 1–Mar 31`)** | **PASS** | `n=37,489`, max D30 `2026-04-30`, 0 censored | `n=37,489`, 0 censored | `0` | Every included player has a full 30-day window (`2026-03-31 + 30d = 2026-04-30`); inactive players included in all denominators. |
| **5** | **Engagement Metrics (30d Cohort)** | **PASS** | `organic` 7.074d / 26.39% D7 / 13.75% D30; `paid_social` 6.862d / 25.58% / 14.43%; `paid_video` 6.824d / 24.56% / 13.53% | Identical | `0.000` | Matches raw `player_day` CSV identically; per-acquired vs per-active denominators kept cleanly separated. |
| **6** | **Revenue & Dedup Sensitivity (30d Cohort)** | **PASS** | `organic` $2.4970 ($2.4627 dedup); `paid_social` $2.2455 ($2.2167 dedup); `paid_video` $1.5470 ($1.5418 dedup) | Identical | `$0.0000` | Matches raw `purchase` CSV and `purchase_id` deduplication rule consistently. Note: 69 pre-install purchases ($998.31) before `install_date` fall outside `[install_date, +29d]`. |
| **7** | **Check A: Organic Engagement Advantage** | **PASS** | Adj. active days: `organic` 7.079, `paid_social` 6.865, `paid_video` 6.774; diffs `+0.214`, `+0.305`, `+0.091` | Identical point estimates; `seed=999` CIs `[+0.135,+0.293]`, `[+0.221,+0.384]`, `[+0.008,+0.175]` | `0.000` pt est (`≤0.004` MC CI width) | Both seeds yield identical Holm significance (`<0.0001`, `<0.0001`, `0.033` vs `0.037`). Confirmed genuine, statistically significant, commercially small (~3–4%). |
| **8** | **Check B: Paid Video Artefact Explanation** | **PASS** | Unadj. `$1.547` → Tier×Plat Adj. `$2.056` (`paid_video` vs `paid_social` `$1.989`, `organic` `$2.174`) | Identical; 3-way (+`install_month`) gives `organic` $2.165, `paid_social` $2.096, `paid_video` $2.050 | `0.000` | Confirmed: Tier 4 (71.1%), Android (81.4%), and April censoring (54.5%) explain virtually the entire raw deficit. |
| **9** | **Check C: Organic vs. Paid Social Revenue** | **PASS** | Adj. diff `+$0.1849`, 95% CI `[-0.0699, +0.4286]`, Holm `p=0.4497` | `+$0.1849`, 95% CI `[-0.0681, +0.4479]`, Holm `p=0.4691` | `0.000` diff (`±0.019` MC CI) | Both seeds cross zero cleanly and yield identical inconclusive result (`Holm p ≈ 0.45–0.47`). |
| **10** | **Charts Match CSV Tables** | **PASS** | 4 PNG charts (`task_3_*.png`) | Visually verified | `0` | All bars, error bars, labels, and legends match `task_3_*.csv` tables with zero clipping. |

---

## 2. Deep-Dive on Specific High-Priority Checks

### Check A — Organic Engagement Advantage
- **Original (`seed=2026`, 4,000 resamples):** Adjusted active days = `7.0790` (`organic`), `6.8648` (`paid_social`), `6.7741` (`paid_video`).
- **Independent (`seed=999`, 5,000 resamples):** Identical adjusted means; `organic - paid_social = +0.2143` (`95% CI [+0.1349, +0.2931]`, Holm `p < 0.0001`), `organic - paid_video = +0.3050` (`95% CI [+0.2212, +0.3840]`, Holm `p < 0.0001`), `paid_social - paid_video = +0.0907` (`95% CI [+0.0081, +0.1753]`, Holm `p = 0.0332`).
- **Verdict:** Reproducible and valid. Effect sizes are tiny (Cohen's $d = 0.07–0.09$).

### Check B — Paid Video Revenue Artefact
- Naive all-80,295 gross ARPU (`$1.6468`) suffers from 54.5% April right-censoring.
- Even in the clean 30d cohort (`Jan–Mar`), unadjusted `paid_video` (`$1.5470`) is depressed because March `paid_video` shifted to 78.0% Tier 4 and 84.0% Android.
- Controlling for `country_tier × platform` raises `paid_video` to `$2.0558` (vs. `$1.9891` `paid_social`, `$2.1740` `organic`). Adding `install_month` as a third stratification factor (`country_tier × platform × install_month`) yields virtually the same parity (`organic $2.1652`, `paid_social $2.0958`, `paid_video $2.0499`).

### Check C — Organic vs. Paid Social Inconclusive Revenue
- Adjusted difference is `+$0.1849` (`+9.30%`), but because ~87% of players spend `$0` and variance is extreme (skewed by whales up to `$219.94`), the independent 5,000-resample 95% CI is `[-$0.0681, +$0.4479]` (`Holm p = 0.4691`), matching the saved `[-$0.0699, +$0.4286]` (`Holm p = 0.4497`). The difference may exist, but the sample cannot resolve it.

### Check D & E — Cohort Eligibility, Pre-Install Boundary & Robustness
- `2026-01-01` to `2026-03-31` (`n = 37,489`) guarantees `install_date + 30d <= 2026-04-30` for 100% of players (`0` leakage, `0` censoring).
- Checking Day 7 retention on the wider `Jan 1–Apr 23` cohort (`n = 57,637`) confirms the exact same channel ordering (`organic 26.31%`, `paid_social 25.43%`, `paid_video 24.84%`).
- `69` pre-install purchase rows (`$998.31`) for Jan–Mar installs occurred 1–4 days before `install_date` and are appropriately excluded from the post-install `[0, 29d]` window.

---

## 3. Corrections, Limitations & Business Recommendation Assessment

- **Corrections Required:** **None.** Every calculation, statistical test, CI, Holm correction, CSV, chart, and number in `reports/deliverable_3_report.md` is verified accurate.
- **Business Recommendation Assessment:** **Justified.** The recommendation properly separates **player quality** (tiny `+3%` organic engagement advantage; near-identical adjusted quality between `paid_social` and `paid_video`) from **acquisition profitability**, explicitly refusing to recommend budget shifts or penalize `paid_video` without missing **CPI / ad spend** and **rewarded-ad revenue** data.
- **Remaining Limitations:**
  1. **No CPI / marketing spend data:** Prevents ROI or payback calculations.
  2. **No rewarded-ad revenue:** `paid_video`'s heavy Tier 4 player base generates ad views whose financial value sits outside player telemetry.
  3. **Observational data:** Even after `country_tier × platform × install_month` adjustment, unmeasured campaign/creative targeting shifts cannot be ruled out without randomized holdouts.
