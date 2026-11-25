# Deliverable 1: Exploratory SQL Analysis Report

**Scope:** Tasks 1A, 1B, 1C, and 1D (using `outputs/telemetry.duckdb`, executed via `src/task_1_analysis.py`)  
**Window Covered:** `2026-01-01` to `2026-04-30` (120 days)  
**Primary Player Unit:** `device_id` (`80,295` total accounts in `player_profile`)

---

## Task 1A — Daily Health (By Date & Platform)

**SQL:** `sql/task_1a_daily_health.sql`  
**Output CSV:** `outputs/tables/task_1a_daily_health.csv` (240 rows = 120 days × 2 platforms)  
**Chart:** `outputs/charts/daily_health.png`

### What Each Metric Means (Beginner Explanation)
- **DAU (Daily Active Users):** How many unique players (`device_id`s) opened the game on that day, counted from `player_day`.
- **Gross Positive Revenue:** Total real-money sales (`usd_amount > 0`) on that day.
- **Refunds (Negative Amounts):** Total negative transactions (`usd_amount < 0`), kept separate so we don't confuse refunds with gross sales.
- **Net Revenue:** `Gross Positive Revenue + Refunds`.
- **ARPDAU (Average Revenue Per Daily Active User):** `Revenue / DAU` — on average, how much money each active player generates on that day.
- **% of Active Players Who Purchased:** Share of daily active players who bought something that day.

### Key Results & Platform Comparison

| Platform | Active Player-Days (120d Sum) | Avg DAU | DAU Range (Min–Max) | Unique Payers | Gross Positive Revenue | Refunds | Net Revenue | Overall Net ARPDAU | DAU-Weighted Payer Share (All / Matched) |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Android** | 458,578 | 3,821.5 | 1,118 – 8,269 | 6,177 | $113,593.75 | -$1,655.88 | **$111,937.87** | **$0.2441** | 1.68% / 1.43% *(daily mean: 1.74% / 1.47%)* |
| **iOS** | 208,857 | 1,740.5 | 671 – 2,873 | 4,877 | $105,840.27 | -$1,618.84 | **$104,221.43** | **$0.4990** | 3.47% / 2.86% *(daily mean: 3.44% / 2.85%)* |
| **Total** | **667,435** | **5,562.0** | — | **11,054** | **$219,434.02** | **-$3,274.72** | **$216,159.30** | **$0.3239** | — |

### Important Observations & Data-Quality Notes
1. **iOS players monetize at ~2× the rate of Android players:** Even though Android has more than double the DAU (`3,821.5` vs `1,740.5`), iOS produces nearly half of total net revenue (`$104.2k` vs `$111.9k`) because its overall Net ARPDAU (`$0.4990`) is more than double Android's (`$0.2441`).
2. **Android DAU surged dramatically while iOS grew gently:** Android DAU grew from `1,118` on Jan 1 to `8,269` on Apr 30 (driven by March–April Tier 4 `paid_video` installs), whereas iOS grew from `671` to `2,873`.
3. **Why we aggregate `player_day` and `purchase` separately before joining:** As found in Phase 1, `2,663` purchases (`$33,592.03` net) occur on dates where that player has no row in `player_day`. Using `FULL OUTER JOIN` on pre-aggregated `(metric_date, platform)` summaries ensures **zero revenue is dropped** (`$216,159.30` reconciles 100%) and **zero DAU rows are multiplied** (`SUM(dau) = 667,435`). We report both `paying_players_all / DAU` and `paying_players_matched_pd / DAU` for transparency.
4. **Duplicate `purchase_id` sensitivity:** If the `122` duplicate `purchase_id` rows (`+$1,840.80` positive, `-$24.98` negative) are excluded, total gross positive revenue is `$217,593.22` and net revenue is `$214,343.48` (a `-0.84%` difference).

---

## Task 1B — Retention Cohort Table

**SQL:** `sql/task_1b_retention.sql`  
**Output CSV:** `outputs/tables/task_1b_retention.csv` (18 weekly cohorts)  
**Chart:** `outputs/charts/retention_heatmap.png`

### Retention Rule & Denominator Explanation (In One Line + Simple Details)
- **One-line rule:** *Only players installed inside the observation window (`2026-01-01` to `2026-04-30`) are included, and a weekly cohort cell for Day `N` is shown only when 100% of that week's installs could reach Day `N` by `2026-04-30` (`cohort_end_date + N <= 2026-04-30`); incomplete weeks are left blank (`NULL`) so recent cohorts are never artificially penalized.*
- **Why the denominator matters:** Every player who installed in that week (`player_profile`) — including the `1,014` players from 2026 installs who never logged a single row in `player_day` — stays in `cohort_size` (the denominator). Excluding them would falsely inflate retention.

### Summary Cohort Grid

| Cohort Week | Date Range | Cohort Size | Day 1 (%) | Day 7 (%) | Day 14 (%) | Day 30 (%) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `2025-12-29` | Jan 01 – Jan 04 | 1,229 | 45.97% | 24.25% | 18.88% | 12.77% |
| `2026-01-05` | Jan 05 – Jan 11 | 2,199 | 46.48% | 26.78% | 19.15% | 13.69% |
| `2026-01-12` | Jan 12 – Jan 18 | 2,266 | 47.75% | 26.21% | 19.86% | 14.96% |
| `2026-01-19` | Jan 19 – Jan 25 | 2,234 | 47.72% | 24.53% | 18.62% | 12.67% |
| `2026-01-26` | Jan 26 – Feb 01 | 2,193 | 47.51% | 25.95% | 21.43% | 14.77% |
| `2026-02-02` | Feb 02 – Feb 08 | 2,335 | 48.05% | 26.85% | 20.77% | 14.60% |
| `2026-02-09` | Feb 09 – Feb 15 | 2,262 | 50.44% | 25.24% | 19.72% | 14.59% |
| `2026-02-16` | Feb 16 – Feb 22 | 2,269 | 47.25% | 23.89% | 19.48% | 14.50% |
| `2026-02-23` | Feb 23 – Mar 01 | 2,744 | 46.90% | 26.75% | 18.99% | 14.10% |
| `2026-03-02` | Mar 02 – Mar 08 | 3,241 | 47.58% | 24.22% | 19.56% | 13.33% |
| `2026-03-09` | Mar 09 – Mar 15 | 3,734 | 47.27% | 26.62% | 19.28% | 13.20% |
| `2026-03-16` | Mar 16 – Mar 22 | 4,337 | 47.43% | 25.27% | 19.18% | 13.72% |
| `2026-03-23` | Mar 23 – Mar 29 | 4,943 | 48.80% | 24.80% | 20.07% | 14.06% |
| `2026-03-30` | Mar 30 – Apr 05 | 5,365 | 46.15% | 26.37% | 19.24% | *Incomplete* |
| `2026-04-06` | Apr 06 – Apr 12 | 6,065 | 48.34% | 25.90% | 19.03% | *Incomplete* |
| `2026-04-13` | Apr 13 – Apr 19 | 6,551 | 47.63% | 24.29% | *Incomplete* | *Incomplete* |
| `2026-04-20` | Apr 20 – Apr 26 | 6,543 | 48.08% | *Incomplete* | *Incomplete* | *Incomplete* |
| `2026-04-27` | Apr 27 – Apr 30 | 3,785 | *Incomplete* | *Incomplete* | *Incomplete* | *Incomplete* |
| **Weighted Avg** | *(Mature cohorts)* | **64,295** | **47.68%** | **25.48%** | **19.50%** | **13.91%** |

- **Key Finding:** Despite install volume tripling from ~2,200/week in Jan–Feb to ~6,550/week in mid-April, **retention rates stayed remarkably stable** (~47.7% D1, ~25.5% D7, ~19.5% D14, ~13.9% D30). This shows the new March–April install surge is retaining about as well as earlier cohorts, even if monetization differs by tier.

---

## Task 1C — Spender Behaviour

**SQL:** `sql/task_1c_spender_behaviour.sql`  
**Output CSV:** `outputs/tables/task_1c_spender_behaviour.csv`  
**Chart:** `outputs/charts/spender_analysis.png`

### 1. Revenue Concentration (Using SQL Window Functions)
Because only `13.77%` (`11,054`) of the `80,295` players ever pay, ranking **payers only** vs **all players** gives very different (yet both defensible) numbers:

| Tier | Payers Only (`n = 11,054`) Gross Share | Payers Only Net Share | Payers Only (Deduped `purchase_id`) Gross Share | All Players (`n = 80,295`) Gross Share | All Players Net Share |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Top 1%** | **9.39%** (`n=111`, `$20,604.37`) | **9.44%** (`$20,407.45`) | 9.22% | **40.14%** (`n=803`, `$88,076.44`) | 40.41% |
| **Top 10%** | **47.79%** (`n=1,106`, `$104,872.15`) | **48.08%** (`$103,930.74`) | 47.64% | **96.66%** (`n=8,030`, `$212,114.57`) | 96.88% |
| **Top 50%** | **89.96%** (`n=5,527`, `$197,401.70`) | **90.23%** (`$195,035.65`) | 89.94% | **100.00%** (`n=40,148`, `$219,434.02`) | 100.01%* |

*\*Note on 100.01% Net Share for Top 50% of all players:* Two players (`105512` and `108769`) have net-negative balances (`-$4.99` and `-$19.99`, totaling `-$24.98`) caused by the two duplicate negative `purchase_id` refund rows (`TX000012322` and `TX000007101`). They rank below `$0.00` non-payers at the very bottom of the 80,295 list, so the top 50% sum (`$216,184.28`) slightly exceeds total net revenue (`$216,159.30`).  
*Note on Top 10% Tie Sensitivity:* At the exact Top 10% cutoff (`1,106th` payer), `605` paying players are tied at `$49.99` total spend (one `vault` pack). Using `ROW_NUMBER()` gives an exact 10% headcount (`n=1,106`, `47.79%` of gross revenue); including all tied `$49.99` players (`RANK() <= 1106`, `n=1,667` = `15.08%` of payers) would yield `60.57%`.

### 2. Share Who Never Purchase & Time-to-First-Purchase
- **Never purchased:** **`69,241 / 80,295` (`86.23%`)** never made a purchase (`86.97%` among 2026 installs, `83.28%` among 2025 legacy installs).
- **2026 Installs vs. All Payers:** We must separate `2026` installs (`8,379` payers) from `2025` installs (`2,675` payers) because `2025` players had no purchase logs before `2026-01-01`, artificially inflating `61+ days` (`27.58%` of all payers vs `8.58%` of 2026 payers).
- Among **2026-installed payers (`n = 8,379`)**:
  - **Pre-install anomaly (`<0 days`):** `1.31%` (`110` players, `-1` to `-4` days before `install_date`)
  - **Day 0 (Install day):** `7.61%` (`638` players)
  - **Days 1–3:** `14.26%` (`1,195` players)
  - **Days 4–7:** `14.32%` (`1,200` players) -> **~36.2%** convert in Days 0–7 (37.5% incl. pre-install)!
  - **Days 8–14:** `15.66%` (`1,312` players)
  - **Days 15–30:** `20.93%` (`1,754` players)
  - **Days 31–60:** `17.32%` (`1,451` players)
  - **61+ days:** `8.58%` (`719` players)

### 3. Repeat Purchase Gap (Using `LAG()` Window Function)
- **Raw positive purchases:** `2,539` repeat buyers (`4,144` consecutive gaps) -> **Mean `22.05` days**, **Median `14.98` days** (IQR: `5.73` – `32.02` days).
- **Deduplicated `purchase_id` sensitivity:** `2,476` repeat buyers (`4,024` gaps) -> **Mean `22.71` days**, **Median `15.26` days** (IQR: `6.37` – `32.82` days). Note how deduplicating removes `63` "fake" repeat buyers whose only repeat row was a duplicate `purchase_id`!

---

## Task 1D — Rewarded Advertisement Engagement

**SQL:** `sql/task_1d_ad_engagement.sql`  
**Output CSV:** `outputs/tables/task_1d_ad_engagement.csv` (120 calendar days)  
**Chart:** `outputs/charts/ad_engagement.png`

### 1. Validating the 8-Hour Timezone Offset Before Aligning
We preserved raw timestamps in `telemetry.duckdb` and checked event semantics first:
- Under raw `DATE(event_ts)`, `8,212` player-days appear to have `ad_daily_cap` change mid-day (`5` and `8`), `147` player-days exceed their cap (`COUNT(*) > ad_daily_cap`), and `51.06%` of rows fail to match `player_day.activity_date`.
- Under **`event_ts - INTERVAL 8 HOUR`**, **0** player-days change cap mid-day, **0** exceed their cap, `MAX(ad_daily_count) == COUNT(*)` on **100.00% (`392,949 / 392,949`)** of player-days, and **100.00% (`647,623 / 647,623`)** match `player_day.activity_date`.
- Therefore, applying `-8 hours` for game-day grouping is fully validated by event semantics.

### 2. Daily Cap Hit Rates (Broken Down by Cap Value)

| Daily Ad Cap | Ad-Watching Player-Days | Player-Days Hitting Cap | Cap-Hit Rate (%) |
| ---: | ---: | ---: | ---: |
| **Cap = 5** | 294,861 (75.04%) | 3,756 | **1.2738%** |
| **Cap = 8** | 98,088 (24.96%) | 18 | **0.0184%** |
| **Total** | **392,949** | **3,774** | **0.9604%** |

- **Note:** `ad_daily_count` increments on **all ad attempts** (`started`, `completed`, and `abandoned`), not just `completed` views (`1,404` of the `3,756` cap-5 days had all 5 completed).

### 3. Daily Ad Volume, Completion/Abandonment, & March 5–6 Outage
- **Daily volume:** `647,623` total ad views over 118 active logging days (average **`5,488.3` views/day**, growing from `1,576` on Jan 1 to `11,884` on Apr 29 as DAU climbed).
- **March 5–6 Logging Outage:** Exactly **0 ad views** were logged on `2026-03-05` and `2026-03-06` (`54.01` hours of silence between `2026-03-05 07:59:56` raw and `2026-03-07 14:00:14` raw), even though `player_day` showed normal active traffic (`4,994` and `4,979` active players). We flagged `is_outage_day = 1` and exclude those two days from daily ad averages.
- **Completion vs. Abandonment:** Overall, **`82.00%` (`531,074`)** of ad interactions are `completed` (granting all `127,669,794` reward units), **`13.04%` (`84,420`)** are `abandoned`, and **`4.96%` (`32,129`)** remain `started` only (`0` reward granted for abandoned/started). These rates are nearly identical (~`82.0%` completed, ~`13.0%` abandoned) across all 5 ad placements (`speedup_offer`, `event_boost`, `currency_topup`, `reward_wheel`, `home_banner_optin`).

### 4. Product Recommendation for the Team
- **Players are NOT routinely hitting the daily ad cap:** Less than **1% (`0.96%`)** of ad-watching player-days reach the cap (`1.27%` at cap=5, `0.02%` at cap=8). Raising the cap further (e.g., from 5 to 8 for everyone) would **not** meaningfully grow ad engagement because almost nobody reaches 5 ads/day today.
- **Where the real opportunity is:** Focus on (1) converting the **18.0%** of initiated ads that end in `abandoned` or `started` without completion (e.g., shorter video creatives / smoother SDK loading), (2) prompting more active players to watch at least 1 ad per day (`392,949` ad-watching days vs `667,435` total active player-days = `58.9%` ad participation), and (3) fixing the `+8h` clock mismatch and monitoring pipeline alerts so a 2-day outage like March 5–6 is caught immediately.
