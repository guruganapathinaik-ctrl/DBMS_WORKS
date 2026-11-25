# Deliverable 1 — Independent Quality Audit

**Audit Scope:** Independent review and recalculation of Tasks 1A, 1B, 1C, and 1D directly from the untouched raw CSV files (`data/*.csv`) compared against `sql/task_1*.sql`, `outputs/tables/task_1*.csv`, `outputs/charts/*.png`, and `reports/deliverable_1_report.md`.  
**Audit Script:** `src/audit_deliverable_1.py` (executed and passed with exit code `0`).

---

## 1. Executive Summary (Pass / Fail by Task)

| Task | Status | Summary |
| --- | --- | --- |
| **Task 1A — Daily Health** | **PASS** *(minor report clarification added)* | DAU (`667,435` sum), Gross (`$219,434.02`), Refunds (`-$3,274.72`), Net (`$216,159.30`), ARPDAU, and platform splits match raw CSVs 100%. Clarified DAU-weighted vs. unweighted daily mean payer % in `deliverable_1_report.md`. |
| **Task 1B — Retention Cohorts** | **PASS** | All `64,295` 2026-window installs accounted for (`0` pre-install activity rows), exact `install_date + N` definitions verified, and incomplete cells properly masked (`NULL`). |
| **Task 1C — Spender Behaviour** | **PASS** *(tie note added)* | Revenue concentration (both payers-only and all-players), `first_purchase_date` alignment (`100%`), never-purchased (`86.23%`), and `LAG()` repeat gaps match raw CSVs. Added explicit tie-sensitivity note at `$49.99` (`605` payers tied at the 10% boundary). |
| **Task 1D — Ad Engagement** | **PASS** | `-8h` offset validated (`0` cap variations, `0` cap violations, `100%` `player_day` match), `392,949` player-days / `647,623` ad views / `3,774` cap hits (`0.9604%`) verified, and March 5–6 outage flagged. |

---

## 2. Detailed 12-Point Audit Checklist

| # | Audit Criterion | Result | Verification Evidence |
| --- | --- | --- | --- |
| **1** | **All PDF Deliverable 1 requirements satisfied** | **PASS** | All four sub-deliverables (1a daily health by day & platform, 1b weekly cohort grid + one-line rule, 1c concentration + TTFP + never-pay + `LAG` repeat gap, 1d cap-hit by cap + daily plot/outage + team advice + DQ note) are present with SQL, CSVs, charts, and write-up. |
| **2** | **DAU and revenue denominators** | **PASS** | `SUM(dau) == 667,435` (exact `player_day` row count). ARPDAU divides by `NULLIF(dau, 0)`. Clarified in report that DAU-weighted payer share is `1.68%` (Android) / `3.47%` (iOS) vs. unweighted daily mean `1.74%` / `3.44%`. |
| **3** | **Platform-wise revenue and ARPDAU** | **PASS** | Independent raw-CSV recalculation matches identically: Android Gross `$113,593.75`, Refunds `-$1,655.88`, Net `$111,937.87` (`$0.2441` Net ARPDAU); iOS Gross `$105,840.27`, Refunds `-$1,618.84`, Net `$104,221.43` (`$0.4990` Net ARPDAU). |
| **4** | **Cohort sizes and Day 1/7/14/30 definitions** | **PASS** | Cohort base is `player_profile` (`install_date >= 2026-01-01`, total `64,295`, including the `1,014` installs with 0 `player_day` rows). Active return on Day `N` checks exact `act_date = install_date + INTERVAL N DAY`. Independent raw recalculation on sample cohorts (`2026-01-05`, `2026-03-23`, `2026-04-13`, `2026-04-27`) matches 100%. |
| **5** | **Incomplete retention windows handled** | **PASS** | Cells where `MAX(install_date) + N > 2026-04-30` are set to `NULL` (greyed out in `retention_heatmap.png`), avoiding downward bias in recent April cohorts (e.g., raw unmasked `2026-04-27` D1 would falsely drop to `35.19%`). |
| **6** | **Top 1%, 10%, 50% spender population & ranking** | **PASS** | Reports both **payers only (`n=11,054`)** and **all players (`n=80,295`)** using `ROW_NUMBER()`. Audit revealed `605` payers tied at `$49.99` at the Top 10% cutoff (`ROW_NUMBER` headcount `n=1,106` -> `47.79%`; `RANK` incl. all ties `n=1,667` -> `60.57%`). Documented in `deliverable_1_report.md`. |
| **7** | **Time-to-first-purchase & repeat-purchase intervals** | **PASS** | `player_profile.first_purchase_date` matches `MIN(DATE(purchase.event_ts))` for `100%` of `80,295` players. Stratified by `2026` installs (`n=64,295`) vs all installs (`n=80,295`) to isolate pre-window censoring. Repeat gaps computed via `LAG(event_ts)` on positive purchases, reported both raw (`14.98d` median) and deduped (`15.26d` median). |
| **8** | **Ad cap-hit denominator** | **PASS** | Denominator is `ad-watching player-days` (`392,949` total: `294,861` for cap=5, `98,088` for cap=8), yielding `3,756` (`1.2738%`) and `18` (`0.0184%`), overall `3,774 / 392,949` (`0.9604%`). |
| **9** | **Support for `-8h` ad timestamp correction** | **PASS** | Strongly validated: raw timestamps produce `8,212` mid-day cap changes and `147` cap violations (`> cap`); `-8h` gives `0` mid-day cap changes, `0` cap violations, `MAX(ad_daily_count) == COUNT(*)` on `100%` of `392,949` player-days, and `100%` match to `player_day.activity_date`. |
| **10** | **Duplicate `purchase_id` consistency** | **PASS** | Preserved in primary totals (`$219,434.02` gross / `$216,159.30` net) with consistent sensitivity columns/metrics across 1A and 1C (`$217,593.22` gross / `$214,343.48` net; `2,539` vs `2,476` repeat buyers). |
| **11** | **Join safety (no missing records / row multiplication)** | **PASS** | Task 1A pre-aggregates `player_day` and `purchase` independently before `FULL OUTER JOIN`, preserving all `2,663` unmatched purchases (`$33,592.03` net) with `0` DAU duplication (`SUM(dau) == 667,435`). |
| **12** | **100% reproducibility from saved SQL scripts** | **PASS** | Re-executing `sql/task_1a..1d` reproduced `outputs/tables/task_1a..1d.csv` with identical row counts, column schemas, and numeric sums (`0.0000` difference). |

---

## 3. Corrections Made During Audit
- **SQL & CSV files:** **Zero calculation errors found** — no SQL files or CSV outputs needed modification.
- **Report clarifications (`reports/deliverable_1_report.md`):**
  1. Added **DAU-weighted payer share** (`Android: 1.68% all / 1.43% matched`, `iOS: 3.47% all / 2.86% matched`) alongside the unweighted daily mean (`1.74% / 1.47%` and `3.44% / 2.85%`) in Task 1A.
  2. Added an explicit note on the **`$49.99` spend tie cluster (`605` payers)** at the Top 10% payer cutoff in Task 1C (`47.79%` by strict `ROW_NUMBER` headcount vs `60.57%` if all ties are included via `RANK()`).

---

## 4. Final Validated Metrics (Reference Baseline for Deliverable 2+)
- **Players:** `80,295` total (`64,295` installed in `2026-01-01..2026-04-30`; `16,000` in `2025`).
- **Active Player-Days:** `667,435` (`458,578` Android, `208,857` iOS).
- **Revenue:** `$219,434.02` gross positive, `-$3,274.72` refunds, **`$216,159.30` net raw** (`$214,343.48` net if deduplicating `122` `purchase_id`s).
- **Retention (2026 mature cohorts):** D1 `47.68%`, D7 `25.48%`, D14 `19.50%`, D30 `13.91%`.
- **Spenders:** `13.77%` (`11,054`) ever purchase; `86.23%` (`69,241`) never purchase; repeat median gap `14.98d` raw (`15.26d` dedup).
- **Ads:** `647,623` ad views across `392,949` ad-watching player-days (`118` active days; March 5–6 outage = `0` views); overall cap-hit rate `0.9604%` (`1.2738%` at cap=5, `0.0184%` at cap=8).

---

## 5. Remaining Limitations
1. **Unlinked `original_device_id` (`3,211` rows):** Kept separate as `device_id` due to severe telemetry conflicts (`94.21%` country mismatch, `1,425` same-day overlaps).
2. **Unmatched refunds (`228` rows):** Refund `purchase_id`s cannot be linked back to original positive purchases.
3. **Right-censoring on late-April cohorts:** Day 14 and Day 30 retention cannot be observed for mid/late-April installs within the `2026-04-30` window.
4. **Pre-window purchases for 2025 installs:** Legacy 2025 players lack pre-`2026-01-01` transaction history.
