# Analytical Decisions & Data-Quality Policy

**Project:** DBMS Lab End-Sem Assignment  
**Purpose:** Document every data-quality issue discovered in Phase 1, the verified evidence behind it, our provisional analytical rules for Deliverables 1–5, and what is proven by data versus what still requires an assumption.  
**Data Source:** Verified via DuckDB against `outputs/telemetry.duckdb` (built read-only from the five untouched CSVs in `data/`).

---

## Summary Table: What Is Proven vs. What Requires an Assumption

| Topic | Supported Directly by Data Evidence | Still Requires an Analytical Assumption |
| --- | --- | --- |
| **1. Revenue & Refunds** | Exact split between positive purchases (`$219,434.02`), negative rows (`-$3,274.72`), and net (`$216,159.30`); all 224 players with negative rows also have positive rows. | Whether negative rows are refunds/chargebacks belonging to this window or prior-window purchases (none share a `purchase_id` with positive rows in our window). |
| **1b. Duplicate `purchase_id`s** | 122 `purchase_id`s appear twice with identical `device_id`, `pack_name`, `usd_amount`, and `sale_flag` on the same calendar day (`2.6`–`1,071.9` mins apart, median `286.36` mins). | Whether these 122 pairs are accidental billing/logging retries (should be deduplicated) or distinct legitimate repeat purchases that suffered a `purchase_id` generator collision. |
| **2. Player Identity (`original_device_id`)** | `original_device_id` linkages conflict heavily with real player continuity (1 self-link, 112 chains, 94.21% different countries, 49.33% reversed install dates, 1,425 same-day overlaps). | Keeping `device_id` as the player unit assumes any true multi-device players in the remaining ~3,211 pairs are safer to leave unmerged than to falsely merge ~94% mismatched pairs. |
| **3. Purchase vs. `player_day` Joins** | 2,663 purchases (`$36,242.20` gross / `$33,592.03` net) occur on dates with no `player_day` row for that device; all 2,663 devices appear in `player_day` on other dates. | Why `player_day` is missing on the purchase date (e.g., billing settlement lag vs. offline/web purchase vs. incomplete daily telemetry). |
| **4. Pre-Install Purchases** | 114 purchases (`$1,652.86` across 110 devices) occur 1–4 days before `install_date`; 0 of them have a `player_day` row on the purchase date; only 6 have `original_device_id`. | Whether `install_date` was recorded late (attribution delay/reinstall) or the purchase timestamp is backdated; flagging keeps them auditable. |
| **5a. `ad_view` +8-Hour Offset** | Raw `ad_view.event_ts` spans `14:00`–`07:59` next day (vs. `06:00`–`23:59` in `purchase` & `currency_spend`); `-8h` matches `player_day.activity_date` on **100.00% (647,623/647,623)** of rows vs. 48.94% raw, and aligns the `07:59:56` clamp with `23:59:56`. | While `-8h` is overwhelmingly supported by alignment evidence, we preserve original timestamps and apply `-8h` only as a documented analytical transformation after verifying. |
| **5b. March 5–6 `ad_view` Outage** | Zero `ad_view` events occur between `2026-03-05 07:59:56` (raw) and `2026-03-07 14:00:14` (raw) — a 54.01-hour gap — while `player_day` stays normal (`4,994` and `4,979` active players). | Excluding March 5–6 from ad-rate/cap denominators assumes players still had normal ad behavior that went unlogged rather than ads being turned off in-game. |
| **6. Extreme `currency_spend` Values** | 233 rows jump cleanly above normal max (`5,864`) to `37,716`–`75,809,670`, and **100% (233/233)** exceed the player's own balance at event time, inflating total spend >11×. | Whether the 233 rows are unit-scaling corruption (e.g., ×1,000/×10,000) or pure garbage; provisional rule keeps them unremoved and uses medians/flags for robustness. |
| **7. March–April Install Surge** | Installs surge from ~9.5k/mo (Jan–Feb) to 18,209 (Mar) and 26,806 (Apr), driven by `paid_video` in Tier 4 countries (62.7% Tier 4 in Apr); only 37,489 of 64,295 window installs are observable at Day 30. | Assuming right-censored cohorts (installed too late to reach Day 7/14/30 by `2026-04-30`) must be excluded (`NULL`/NA) from mature milestone cells rather than treated as 0% retained. |

---

## Detailed Analysis of All 7 Analytical Decisions

### 1. Revenue, Refunds, and Duplicate `purchase_id`s (`purchase`)

- **Evidence Observed:**
  - Total rows: `15,426` across `15,304` distinct `purchase_id`s and `11,054` unique `device_id`s.
  - **Gross positive purchases (`usd_amount > 0`):** `15,198` rows totaling **`$219,434.02`**.
  - **Negative purchases (`usd_amount < 0`):** `228` rows totaling **`-$3,274.72`** (`-1.49%` of gross). Every one of the `224` devices with a negative transaction also has at least one positive transaction in the dataset, though none of the negative `purchase_id`s match any positive `purchase_id` in the window.
  - **Net revenue (raw):** `$219,434.02 + (-$3,274.72)` = **`$216,159.30`**.
  - **Duplicate `purchase_id`s:** `122` `purchase_id`s appear twice (`244` rows total, `122` excess rows = `0.79%`). In **all 122 pairs**, `device_id`, `pack_name`, `usd_amount`, and `sale_flag` are identical and both events occur on the same calendar day (`2.6` to `1,071.9` minutes apart; median `286.36` minutes). `120` pairs are positive (`$1,840.80` excess) and `2` pairs are negative (`-$24.98` excess), yielding `$1,815.82` net excess.
  - **Deduplicated comparison (keeping earliest `event_ts` per `purchase_id`):** Gross positive = **`$217,593.22`**, Refunds = **`-$3,249.74`**, Net = **`$214,343.48`**.
- **Provisional Treatment:**
  - Report **gross positive (`$219,434.02`)**, **negative refunds (`-$3,274.72`)**, and **net (`$216,159.30`)** separately.
  - **Do not auto-delete** the 122 duplicate `purchase_id` rows yet because they have distinct timestamps hours apart and could reflect either an ID-generation collision or retry logging; instead, report both raw and deduplicated figures (documented in `outputs/tables/purchase_reconciliation.csv`).
- **Limitation:** Because negative rows do not share `purchase_id`s with positive rows, we cannot link a specific refund back to its exact original purchase timestamp (for example, when studying `sale_flag` or repeat purchase gaps).

---

### 2. Player Identity (`device_id` vs. `original_device_id`)

- **Evidence Observed:**
  - `player_profile` has `80,295` unique `device_id`s. Only `3,211` rows (`4.00%`) have `original_device_id` populated.
  - Structural checks prove that `original_device_id` cannot be trusted as a clean 1-to-1 device-transfer key:
    - `1` self-link (`device_id = 125989` points to `125989`).
    - `112` chained links (`A -> B -> C`).
    - `3,025 / 3,211` (`94.21%`) linked pairs have **different countries** (almost identical to random pairing across 18 countries!).
    - `1,348 / 3,211` (`41.98%`) have **different platforms**.
    - `1,584 / 3,211` (`49.33%`) have `new.install_date < old.install_date` (meaning the "new" device installed *before* the "original" device).
    - `1,425` non-self pairs (`44.39%`) are active on the **exact same calendar day** in `player_day`.
- **Provisional Treatment:**
  - Use **`device_id` as the primary player unit** across all analyses.
  - **Do not merge** `original_device_id` records.
- **Limitation:** If a small subset of those `3,211` pairs truly represent the same human player switching devices, keeping `device_id` separate could slightly overcount unique players (by at most ~4%) and split a small fraction of player lifetimes. However, merging them blindly would corrupt `country_tier`, `platform`, and `acquisition_channel` analyses.

---

### 3. Purchase and Activity Joins (`purchase` vs. `player_day`)

- **Evidence Observed:**
  - Out of `15,426` purchase rows, **`12,763` (`$182,567.27` net)** match a `(device_id, activity_date)` row in `player_day`.
  - The remaining **`2,663` purchase rows (`17.26%`, `$36,242.20` gross / `$33,592.03` net)** occur on calendar dates when that `device_id` has **no row in `player_day`** (even though 100% of those `device_id`s appear in `player_day` on other dates — `633` were active 1 day prior and `555` 1 day after).
- **Provisional Treatment:**
  - **Never `INNER JOIN purchase` to `player_day`** on `(device_id, date)`.
  - For daily health metrics (Deliverable 1a), aggregate `player_day` (for DAU) and `purchase` (for daily revenue & daily buyers) **separately by date and `device_id`**, then combine via `FULL OUTER JOIN` or `LEFT JOIN` from a date/platform spine, and always check denominators (`Daily Buyers / DAU` vs. payers active in `player_day` that day).
- **Limitation:** In Deliverable 1a ("Share of active players who made a purchase that day"), a small number of purchasers on a given day do not appear in that day's `player_day` count; we must report clearly how the numerator and denominator align.

---

### 4. Purchases Dated Before `install_date`

- **Evidence Observed:**
  - `114` purchase rows (`0.74%`, across `110` distinct `device_id`s, totaling **`$1,652.86`** gross and net — all positive) have `DATE(event_ts) < player_profile.install_date`.
  - All `114` occur **1 to 4 days before** `install_date` (`min = -4` days, `max = -1` day).
  - **0 out of 114** have a `player_day` row on that purchase date, and only `6` of the `114` have `original_device_id` populated.
- **Provisional Treatment:**
  - **Retain and flag** these `114` records (`is_pre_install_purchase = TRUE`) rather than silently deleting them from revenue totals.
  - For **time-to-first-purchase** calculations (Deliverable 1c), report how negative `first_purchase_date - install_date` values (`-4` to `-1` days for `110` players) are handled (either clamped to Day 0 or reported separately as an anomaly bucket).
- **Limitation:** These rows likely reflect late install attribution or minor clock skew on `install_date`, not fake revenue.

---

### 5. Advertisement Timestamps (`+8h` Offset) & March 5–6 Outage (`ad_view`)

- **Evidence Observed (Timezone Offset):**
  - `purchase.event_ts` and `currency_spend.event_ts` strictly occupy hours **`06:00` to `23:59`** (0 events between `00:00` and `05:59`), and both have a batching spike at **`23:59:56`** (`374` and `12,224` rows respectively).
  - `ad_view.event_ts` strictly occupies hours **`14:00` to `07:59` next day** (0 events between `08:00` and `13:59`), and has an identical batching spike at **`07:59:56`** (`16,507` rows = `23:59:56 + 8 hours`).
  - Testing integer-hour shifts against `player_day.activity_date`:
    - Raw (`+0h`): `316,957 / 647,623` match (**48.94%**) — more than half fail!
    - `-6h`: `90.76%` match
    - `-7h`: `95.42%` match
    - **`-8h`**: **`647,623 / 647,623` match (100.00%)** — and shifts `2026-01-01 14:00`..`2026-05-01 07:59` cleanly into `2026-01-01`..`2026-04-30`!
- **Evidence Observed (March 5–6 Outage):**
  - After aligning to game days (`-8h`), `ad_view` has **0 events on `2026-03-05` and `2026-03-06`**.
  - The exact gap runs from `2026-03-05 07:59:56` raw (`2026-03-04 23:59:56` aligned) to `2026-03-07 14:00:14` raw (`2026-03-07 06:00:14` aligned) — **`54.01` hours** of complete silence, while `player_day` recorded `4,994` and `4,979` active players on those two days.
- **Provisional Treatment:**
  - **Preserve original timestamps** in the base table (`outputs/telemetry.duckdb`).
  - Because the `100.00%` `player_day` match + `23:59:56 -> 07:59:56` clamp alignment provides strong evidence of an `+8h` logging timezone offset, apply `event_ts - INTERVAL 8 HOUR` explicitly in derived SQL views when grouping `ad_view` by game date (Deliverable 1d), and document the transformation clearly.
  - Treat `2026-03-05` and `2026-03-06` as a **telemetry outage** (flag and exclude from daily average ad-view rates rather than treating them as zero-ad days).
- **Limitation:** Because hours `00:00–05:59` have no events in `purchase` or `currency_spend`, `-8h`, `-9h`, and `-10h` all give 100% date matching; `-8h` is uniquely pinned by the exact `07:59:56` vs. `23:59:56` clamp alignment (`23:59:56 + 8h = 07:59:56`).

---

### 6. Extreme `currency_spend.currency_value` Anomalies

- **Evidence Observed:**
  - Across `489,892` spend events, normal values (`1` to `10,000`) never exceed `263` (`PREMIUM`), `635` (`SOCIAL`), or `5,864` (`GRIND`).
  - There are **0 rows** between `5,865` and `37,715`, and then **233 rows (`0.048%`)** jump from `37,716` up to `75,809,670`.
  - **100% (233 / 233)** of these extreme values exceed the player's own currency balance recorded on the very same row (`premium_balance`, `social_balance`, or `grind_balance`), proving they are corrupted/scaled telemetry values rather than real in-game spends.
  - Impact on means: `GRIND` mean jumps from `521.0` (excl. extremes) to `5,804.67` (raw); `PREMIUM` mean jumps from `28.69` to `410.02`; `SOCIAL` mean jumps from `65.96` to `827.40`.
  - Additionally, `277` rows (`240` `PREMIUM`, `37` `SOCIAL`) have `currency_value = 0`.
- **Provisional Treatment:**
  - **Do not delete or cap** the raw `currency_value` records in the source data.
  - Flag `currency_value > 10000` (or `> balance`) and `currency_value = 0`; use **medians / percentiles** or explicitly filtered sensitivity views whenever summarizing spend volume.
- **Limitation:** Without knowing the exact scaling bug behind the 233 outliers, raw sums of `currency_value` are unusable for economy-balance conclusions unless flagged/excluded in sensitivity checks.

---

### 7. March–April Install Surge & Observation Window Censoring (`player_profile`, `player_day`)

- **Evidence Observed:**
  - Monthly installs shift dramatically in both volume and composition:
    - `2025 (pre-window)`: `16,000` installs (`17.1%` Tier 4; `15.3%` `paid_video`)
    - `2026-01`: `9,809` installs (`18.1%` Tier 4; `1,480` `paid_video`)
    - `2026-02`: `9,471` installs (`21.8%` Tier 4; `1,774` `paid_video`)
    - `2026-03`: `18,209` installs (`50.3%` Tier 4; `9,776` `paid_video`)
    - `2026-04`: `26,806` installs (`62.7%` Tier 4; `18,563` `paid_video`)
  - Meanwhile, Tier 1 (`~3,200–3,330/mo`), Tier 2 (`~2,270–2,540/mo`), and `organic` (`~4,000–4,500/mo`) remain stable.
  - Among the `64,295` players installed inside the window (`>= 2026-01-01`), observation ends on `2026-04-30`, meaning only:
    - `63,353` (`98.5%`) can reach **Day 1** (`install_date <= 2026-04-29`)
    - `57,637` (`89.6%`) can reach **Day 7** (`install_date <= 2026-04-23`)
    - `51,151` (`79.6%`) can reach **Day 14** (`install_date <= 2026-04-16`)
    - `37,489` (`58.3%`) can reach **Day 30** (`install_date <= 2026-03-31`)
- **Provisional Treatment:**
  - In retention cohort tables (Deliverable 1b), only include players whose **full milestone date (`install_date + N days <= 2026-04-30`) falls inside the observation window** in the denominator for day `N` (and leave recent incomplete cohort cells blank/`NULL`, documenting the exact maturity rule).
  - Never pool early and late weeks blindly without stratifying by `country_tier` and `acquisition_channel` (critical for Deliverables 2a and 3).
- **Limitation:** For the most recent weekly cohorts (late April 2026), Day 14 and Day 30 retention cannot yet be observed; conclusions about the newest Tier 4 `paid_video` surge must rely on Day 1 / Day 7 retention or earlier March cohorts.
