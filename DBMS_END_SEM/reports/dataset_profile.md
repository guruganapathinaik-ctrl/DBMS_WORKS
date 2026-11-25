# Phase 1: Dataset Profile

**Project:** DBMS Lab End-Sem Assignment (Live-Service Mobile Game Analytics)  
**Scope:** Phase 1 — Initial Dataset Exploration (read-only profiling via Python + DuckDB)  
**Source Data Window:** `2026-01-01` to `2026-04-30` (120 calendar days)

---

## 1. High-Level Overview (In Simple Terms)

Think of these five CSV files as five connected spreadsheets from a mobile game's server logs:

| Table Name | Original File in `data/` | File Size | Total Rows | Unique `device_id`s | Average Rows per Player | What One Row Represents |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `player_profile` | `player_profile - player_profile.csv` | 4,067,006 B (~3.88 MiB) | 80,295 | 80,295 | 1.00 | One player/device account and its signup attributes |
| `player_day` | `player_day - player_day.csv` | 21,249,206 B (~20.26 MiB) | 667,435 | 79,181 | 8.43 | Daily activity summary for one player on one day |
| `purchase` | `purchase - purchase.csv` | 982,782 B (~959.75 KiB) | 15,426 | 11,054 | 1.40 | One real-money in-app purchase (or refund) event |
| `currency_spend` | `currency_spend - currency_spend.csv` | 33,343,030 B (~31.80 MiB) | 489,892 | 73,216 | 6.69 | One event where a player spent in-game currency |
| `ad_view` | `ad_view - ad_view.csv` | 43,319,839 B (~41.31 MiB) | 647,623 | 74,042 | 8.75 | One rewarded-video ad interaction |

> **Beginner Tip — What is `device_id`?**  
> Each player account in this dataset is identified by a numeric `device_id`. Notice that `player_profile` has 80,295 rows and 80,295 unique `device_id`s — meaning every row is a distinct device ID.

Exact summary CSV outputs generated in `outputs/tables/`:
- `outputs/tables/row_counts.csv`
- `outputs/tables/missing_values.csv`
- `outputs/tables/duplicate_checks.csv`

---

## 2. Column Schemas & Data Types

All schemas and data types below were inferred automatically by DuckDB (`read_csv_auto(..., sample_size=-1)`) across the full files, without assuming column names or types beforehand.

### 2.1 `player_profile` (80,295 rows, 8 columns)
| Column | Data Type | Null Count | Null % | Summary / Observed Values |
| --- | --- | ---: | ---: | --- |
| `device_id` | `BIGINT` | 0 | 0.0% | Unique device identifier |
| `original_device_id` | `BIGINT` | 77,084 | 96.001% | Populated for 3,211 rows (4.00%) linked to an earlier device |
| `install_date` | `DATE` | 0 | 0.0% | Range: `2025-05-27` to `2026-04-30` |
| `platform` | `VARCHAR` | 0 | 0.0% | `Android` (57,136; 71.16%), `iOS` (23,159; 28.84%) |
| `country` | `VARCHAR` | 0 | 0.0% | 18 distinct countries (top: India 6,616; Egypt 6,573; Indonesia 6,483) |
| `country_tier` | `BIGINT` | 0 | 0.0% | Integer `1`–`4`: Tier 4 (32,554), Tier 1 (18,596), Tier 3 (15,081), Tier 2 (14,064) |
| `acquisition_channel` | `VARCHAR` | 0 | 0.0% | `paid_video` (34,036), `organic` (24,554), `paid_social` (21,705) |
| `first_purchase_date` | `DATE` | 69,241 | 86.2333% | Range: `2026-01-01` to `2026-04-30`; non-null for 11,054 payers (13.77%) |

### 2.2 `player_day` (667,435 rows, 6 columns)
| Column | Data Type | Null Count | Null % | Summary / Observed Values |
| --- | --- | ---: | ---: | --- |
| `device_id` | `BIGINT` | 0 | 0.0% | 79,181 distinct devices |
| `activity_date` | `BIGINT` | 0 | 0.0% | Integer `YYYYMMDD`: `20260101` to `20260430` (all 120 days valid) |
| `player_level` | `BIGINT` | 0 | 0.0% | Min `2`, Max `39` |
| `session_count` | `BIGINT` | 0 | 0.0% | Min `1`, Max `18` |
| `playtime_minutes` | `DOUBLE` | 0 | 0.0% | Min `0.0`, Max `239.8` |
| `app_version` | `VARCHAR` | 0 | 0.0% | 5 versions: `4.6.1`, `4.7.0`, `4.7.2`, `4.8.0`, `4.8.1` |

### 2.3 `purchase` (15,426 rows, 7 columns)
| Column | Data Type | Null Count | Null % | Summary / Observed Values |
| --- | --- | ---: | ---: | --- |
| `purchase_id` | `VARCHAR` | 0 | 0.0% | Transaction ID (e.g., `TX000004535`); 15,304 distinct values (122 duplicates!) |
| `device_id` | `BIGINT` | 0 | 0.0% | 11,054 distinct paying devices |
| `event_ts` | `TIMESTAMP` | 0 | 0.0% | `2026-01-01 06:58:57` to `2026-04-30 23:59:56` (120 distinct days) |
| `pack_name` | `VARCHAR` | 0 | 0.0% | 6 packs: `starter_pouch` (4,254), `small_pouch` (3,853), `medium_chest` (3,280), `large_chest` (2,242), `vault` (1,245), `mega_vault` (552) |
| `usd_amount` | `DOUBLE` | 0 | 0.0% | Range `-99.99` to `99.99` (includes 228 negative rows) |
| `currency_granted` | `BIGINT` | 0 | 0.0% | Range `-11,000` to `11,000` (includes 228 negative rows) |
| `sale_flag` | `BIGINT` | 0 | 0.0% | `0` (9,353 rows; 60.63%) or `1` (6,073 rows; 39.37%) |

### 2.4 `currency_spend` (489,892 rows, 10 columns)
| Column | Data Type | Null Count | Null % | Summary / Observed Values |
| --- | --- | ---: | ---: | --- |
| `device_id` | `BIGINT` | 0 | 0.0% | 73,216 distinct devices |
| `event_ts` | `TIMESTAMP` | 0 | 0.0% | `2026-01-01 06:00:33` to `2026-04-30 23:59:56` (120 distinct days) |
| `spend_type` | `VARCHAR` | 0 | 0.0% | `free` (452,299), `subscription` (28,660), `paid` (8,933) |
| `currency_type` | `VARCHAR` | 0 | 0.0% | `GRIND` (274,101), `SOCIAL` (117,041), `PREMIUM` (98,750) |
| `currency_value` | `BIGINT` | 0 | 0.0% | Min `0`, Max `75,809,670` (contains 277 zeros and 233 extreme outliers `> 37,000`) |
| `spend_category` | `VARCHAR` | 0 | 0.0% | 8 categories (`event_entry`, `energy_refill`, `career_boost`, `pet`, `build_item`, `decor`, `outfit`, `speed_up`) |
| `player_level` | `BIGINT` | 0 | 0.0% | Min `2`, Max `39` |
| `premium_balance` | `BIGINT` | 0 | 0.0% | Min `9`, Max `1,046` |
| `social_balance` | `BIGINT` | 0 | 0.0% | Min `19`, Max `2,731` |
| `grind_balance` | `BIGINT` | 0 | 0.0% | Min `127`, Max `16,621` |

### 2.5 `ad_view` (647,623 rows, 8 columns)
| Column | Data Type | Null Count | Null % | Summary / Observed Values |
| --- | --- | ---: | ---: | --- |
| `device_id` | `BIGINT` | 0 | 0.0% | 74,042 distinct devices |
| `event_ts` | `TIMESTAMP` | 0 | 0.0% | `2026-01-01 14:00:20` to `2026-05-01 07:59:56` *(+8h offset vs other tables!)* |
| `status` | `VARCHAR` | 0 | 0.0% | `completed` (531,074), `abandoned` (84,420), `started` (32,129) |
| `placement` | `VARCHAR` | 0 | 0.0% | 5 placements (`speedup_offer`, `event_boost`, `currency_topup`, `reward_wheel`, `home_banner_optin`) |
| `reward_type` | `VARCHAR` | 0 | 0.0% | `GRIND` (285,135), `SPEEDUP_TOKEN` (154,673), `SOCIAL` (143,185), `PREMIUM` (64,630) |
| `reward_amount` | `BIGINT` | 0 | 0.0% | `0` for all `started`/`abandoned` rows; `1` to `899` for `completed` rows |
| `ad_daily_count` | `BIGINT` | 0 | 0.0% | Min `1`, Max `8` |
| `ad_daily_cap` | `BIGINT` | 0 | 0.0% | `5` (485,871 rows; 75.02%) or `8` (161,752 rows; 24.98%) |

---

## 3. Alignment with Assignment PDF Description

| Aspect | PDF Description | Observed in Actual Data | Match? |
| --- | --- | --- | --- |
| Player count | `~80,000 players` | `80,295` rows in `player_profile` | Yes |
| Active player-days | `~667,000 active player-days` across 120 days (`2026-01-01` to `2026-04-30`) | `667,435` rows across 120 days (`20260101` to `20260430`) | Yes |
| `player_day.activity_date` format | Stored as integer `YYYYMMDD` | `BIGINT` (`20260101`–`20260430`), 0 invalid dates | Yes |
| Install volume trend | "Install volume is not flat across this window" | Confirmed: ~2.2k/mo in Jun–Dec 2025, ~9.5k/mo in Jan–Feb 2026, 18,209 in Mar 2026, 26,806 in Apr 2026 | Yes |
| `country_tier` | `1–4` (Tier 1 highest) | Exact integers `1`, `2`, `3`, `4` across 18 countries (each country maps to exactly 1 tier) | Yes |
| `first_purchase_date` | Null if never purchased | Null for 69,241 non-payers; populated and matches `purchase` for all 11,054 payers | Yes |
| `currency_spend` categories | `spend_type`: `paid/free/subscription`; `currency_type`: `PREMIUM/SOCIAL/GRIND` | Exact match on all values | Yes |
| `ad_view` statuses & caps | `started/completed/abandoned`; daily cap varies by player | Exact status values; cap is `5` or `8` | Yes |
| **Exceptions / Differences** | Five CSVs inside `csv/` named `player_profile.csv`, etc. | Located inside `data/` with `<name> - <name>.csv` filenames; `ad_view.reward_type` also includes `SPEEDUP_TOKEN` (not mentioned in the 3-currency summary); `ad_view.event_ts` extends to `2026-05-01` due to a +8h shift | Partial (imperfections documented in `data_quality_report.md`) |
