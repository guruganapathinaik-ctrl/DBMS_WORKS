# Phase 1: Data Quality Report

This report documents every data-quality issue, telemetry quirk, and anomaly discovered across the five CSV files during Phase 1 exploration.

---

## 1. Summary of Data Quality Findings

| Severity | Issue | Affected Table(s) | Exact Scope |
| --- | --- | --- | --- |
| **Critical** | `+8 hour` timezone offset in `ad_view.event_ts` | `ad_view` | 647,623 / 647,623 rows (100%) |
| **Critical** | 2-day telemetry outage (`2026-03-05` and `2026-03-06`) | `ad_view` | 2 full calendar days missing |
| **Critical** | `original_device_id` linkage conflicts & cycles | `player_profile` | 3,211 linked rows (1 self-link, 112 chains, 1,425 same-day overlaps) |
| **High** | Negative `usd_amount` and `currency_granted` (refunds/chargebacks) | `purchase` | 228 rows (1.48% of purchases) |
| **High** | Duplicate `purchase_id` values | `purchase` | 122 duplicate `purchase_id` groups (122 excess rows, 0.79%) |
| **High** | Extreme `currency_value` outliers (`37,716` to `75,809,670`) | `currency_spend` | 233 rows (0.048%) |
| **Medium** | Timestamp clamping at `23:59:56` / `07:59:56` | `purchase`, `currency_spend`, `ad_view` | ~2.4%–2.5% of rows in each event table |
| **Medium** | Purchases dated before `install_date` | `purchase`, `player_profile` | 114 purchase rows / 110 players |
| **Medium** | Purchases on dates without a matching `player_day` row | `purchase`, `player_day` | 2,663 purchase rows (17.26%) |
| **Low** | Zero `currency_value` spend events & zero-playtime active days | `currency_spend`, `player_day` | 277 spend rows; 45 player-days |
| **Low** | Players in `player_profile` with zero activity in any event table | `player_profile` | 1,114 players (1.39%) |

---

## 2. Detailed Issue Breakdown (Explained Simply)

### Issue 1: `ad_view.event_ts` Is Shifted Forward by +8 Hours (Critical)
- **What we observed:**
  - `player_day.activity_date` runs from `20260101` to `20260430`.
  - `purchase.event_ts` and `currency_spend.event_ts` both have hours strictly between `06:00` and `23:59` and end on `2026-04-30 23:59:56`.
  - In contrast, `ad_view.event_ts` starts at `2026-01-01 14:00:20` and ends at `2026-05-01 07:59:56` — **8 hours later**.
  - When joining `ad_view` to `player_day` using raw `DATE(event_ts)`, **330,666 out of 647,623 rows (51.06%) fail to match** an active day in `player_day`.
  - When we shift `ad_view.event_ts - INTERVAL 8 HOUR`, **647,623 out of 647,623 rows (100.00%) match** `(device_id, activity_date)` in `player_day`.
- **Why this matters:** Any daily ad-view chart, cap analysis, or join with `player_day` on raw `DATE(ad_view.event_ts)` will misassign half of all ad views to the next day and create a fake `2026-05-01` partial day.

### Issue 2: Complete 2-Day Logging Outage in `ad_view` (`2026-03-05` and `2026-03-06`) (Critical)
- **What we observed:**
  - After shifting `ad_view.event_ts` by `-8 hours` to align with game dates, `ad_view` has **0 events on `2026-03-05` and `2026-03-06`**.
  - Specifically, raw timestamps stop at `2026-03-05 07:59:56` (end of game day `2026-03-04`) and resume at `2026-03-07 14:00:14` (start of game day `2026-03-07`).
  - Meanwhile, `player_day`, `purchase`, and `currency_spend` all have normal daily activity on `2026-03-05` and `2026-03-06` (0 missing days).
- **Why this matters:** Directly explains the prompt in Deliverable 1(d) (*"comment on anything that looks off"*). Treating those two days as "0 ads watched" would distort weekly averages and ad-cap ratios; they represent a logging outage and should be excluded or flagged in time-series calculations.

### Issue 3: Unreliable / Noisy `original_device_id` Linkages (Critical)
- **What we observed:**
  - `3,211` rows in `player_profile` (4.00%) have `original_device_id` populated, and all `3,211` referenced IDs exist in `player_profile.device_id`.
  - However, closer inspection reveals severe inconsistencies if these are assumed to be the same human player switching phones:
    - **1 self-link:** `device_id = 125989` points to `original_device_id = 125989`.
    - **112 chained links (`A -> B -> C`):** A device points to another device that itself has an `original_device_id`.
    - **Random-looking demographic mismatches:** Across the 3,211 linked pairs, only **186 (5.79%)** share the same `country` (roughly 1/18, matching random assignment across 18 countries), only **1,863 (58.02%)** share `platform`, and only **1,097 (34.16%)** share `acquisition_channel`.
    - **Reversed install timelines:** **1,584 pairs (49.33%)** have `new.install_date < old.install_date` (the "new" device installed *before* the "original" device).
    - **Concurrent activity:** **2,803 pairs (87.29%)** have overlapping activity windows, **1,425 pairs (44.38%)** are active on the **exact same calendar day** in `player_day`, and **52 pairs** made purchases on both IDs.
- **Why this matters:** Blindly merging `device_id` and `original_device_id` would merge unrelated players across different countries, platforms, and acquisition channels. Before Deliverables 1–4, we must explicitly decide and document how to treat `original_device_id` (e.g., keep `device_id` as the primary analysis unit and treat `original_device_id` as noisy/broken telemetry rather than a clean player merge).

### Issue 4: Negative Purchases (`usd_amount < 0`) & Duplicate `purchase_id`s (High)
- **Negative purchases:** `228` rows (1.48%) have `usd_amount` between `-1.99` and `-99.99` and `currency_granted` between `-120` and `-11,000` (all 6 packs appear). None of these 228 `purchase_id`s match a positive `purchase_id` in the window (meaning if they are refunds/chargebacks, the original positive purchase ID either occurred before `2026-01-01` or uses a separate transaction ID).
- **Duplicate `purchase_id`:** `122` `purchase_id`s appear **twice** (`122` excess rows, 0.79%).
  - `120` pairs have two positive transactions with the same `purchase_id`, same `device_id`, same `pack_name`, and same `usd_amount`, occurring a few minutes to several hours apart on the same day (e.g., `TX000001520` at `21:08:45` and `21:52:30`).
  - `2` pairs (`TX000007101`, `TX000012322`) have two negative transactions with the same `purchase_id`.
- **Why this matters:** Counting duplicate `purchase_id`s inflates revenue and purchase frequency, while failing to decide whether negative rows represent refunds (net vs gross revenue) affects Deliverable 1(a), 1(c), and 2.

### Issue 5: Extreme `currency_spend.currency_value` Outliers & Zeros (High)
- **What we observed:**
  - Normal spend values (`1` to `10,000`) max out at `263` for `PREMIUM`, `635` for `SOCIAL`, and `5,864` for `GRIND`. Player balances never exceed `1,046` (`premium_balance`), `2,731` (`social_balance`), or `16,621` (`grind_balance`).
  - Yet **233 rows (0.048%)** jump abruptly into `37,716`–`75,809,670` (with **zero** rows between `5,865` and `37,715`). These occur across all three currencies and spend types.
  - Additionally, **277 rows (0.057%)** have `currency_value = 0` (mostly `PREMIUM` and `SOCIAL`).
- **Why this matters:** Including `75.8M` in averages or sums would completely distort in-game economy metrics.

### Issue 6: Timestamp Clamping at `23:59:56` (`07:59:56` in `ad_view`) (Medium)
- **What we observed:**
  - `purchase`: `374` rows (2.42%) have exact timestamp `23:59:56`.
  - `currency_spend`: `12,224` rows (2.50%) across all 120 days have exact timestamp `23:59:56`.
  - `ad_view`: `16,507` rows (2.55%) across 118 active days have exact timestamp `07:59:56` (which is `23:59:56 + 8 hours`).
  - This clustering also causes the small number of `(device_id, event_ts)` collisions in `currency_spend` (110 groups) and `ad_view` (253 groups, including 32 identical `(device_id, event_ts, status, placement)` groups).
- **Why this matters:** Events near midnight appear to have been clamped/batched to `23:59:56`, which makes sub-minute event ordering unreliable at day boundaries.

### Issue 7: Date & Activity Mismatches (`purchase` vs `player_profile` & `player_day`) (Medium)
- **Purchases before `install_date`:** `114` purchase rows occur on a date earlier than `player_profile.install_date`, and `110` players have `first_purchase_date < install_date`. Only `6` of those 114 purchases belong to rows with `original_device_id` populated, so this is not solely a linked-device issue.
- **Purchases without a `player_day` row on that date:** `2,663` out of `15,426` purchases (17.26%) occur on a calendar date where the player has no row in `player_day`. (All 2,663 transactions belong to players who *do* have `player_day` rows on other dates — `633` were active the day before and `555` the day after).
- **Why this matters:** For Deliverable 1(a) (*"Share of active players who made a purchase that day"*), joining `purchase` to `player_day` with an `INNER JOIN` on `(device_id, date)` would silently drop 17.26% of purchases!

### Issue 8: Minor / Clean Checks Worth Noting (Low)
- **Inactive `player_profile` accounts:** `1,114` players (1.39%) in `player_profile` have `0` rows in `player_day`, `purchase`, `currency_spend`, and `ad_view` during the 120-day window (expected for older 2025 installs who churned before 2026-01-01, or day-0 bounces).
- **Zero-playtime rows in `player_day`:** `45` rows have `playtime_minutes = 0.0` despite `session_count >= 1` (likely sub-30-second sessions rounded to 0.0).
- **Clean checks (no issues found):**
  - `0` exact full-row duplicates in any table.
  - `0` orphan `device_id`s in any child table.
  - `0` `currency_spend` or `ad_view` events before `install_date`.
  - `0` decreasing `player_level` values within a `device_id` in `player_day`.
  - `0` cases where `ad_daily_count > ad_daily_cap`, and `0` cases where `started`/`abandoned` ads granted `reward_amount > 0`.
  - `100%` consistency between `player_profile.first_purchase_date` and `MIN(DATE(purchase.event_ts))`.
