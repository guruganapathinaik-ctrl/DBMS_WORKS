# Deliverable 2 (Option A): "ARPDAU is falling. Fix it." — Deep-Dive Report

**Question Investigated:** Why did overall ARPDAU drop roughly **16%** between the first 30 days (`2026-01-01` to `2026-01-30`) and the last 30 days (`2026-04-01` to `2026-04-30`), even though **every single `country_tier` (1, 2, 3, and 4) stayed flat or improved**?  
**SQL Script:** `sql/task_2_arpdau_deep_dive.sql`  
**Python Script:** `src/task_2_deep_dive.py`

---

## Executive Summary (In Simple Language)

**Nothing broke in game monetisation.** The apparent 16.3% drop in overall ARPDAU is a textbook statistical illusion called **Simpson's Paradox**.

- Inside **every single country tier**, players are actually spending **more** per active day in April than in January:
  - Tier 1: **+7.03%**, Tier 2: **+8.50%**, Tier 3: **+13.50%**, Tier 4: **+1.97%**.
- If the mix of countries had stayed the same as January, overall Gross ARPDAU would have **risen +7.97%** (from `$0.3567` to `$0.3851`).
- Instead, a massive surge in **`paid_video` marketing in Tier 4 countries** expanded Tier 4 from **17.65%** of daily player activity in January to **45.99%** in April. Because Tier 4 players naturally spend less per day (`$0.16` vs. `$0.56` in Tier 1), giving Tier 4 nearly half the weight pulled the blended average down by **`-16.32%`** — even while total gross revenue nearly **tripled (+187.25%)** from `$29,383.67` to `$84,404.41`.

---

## 1. Period Comparison (First 30 Days vs. Last 30 Days)

**Table:** `outputs/tables/task_2_period_comparison.csv`

| Metric | First 30d (`Jan 1–30`) | Last 30d (`Apr 1–30`) | % Change |
| --- | ---: | ---: | ---: |
| **Total Active Player-Days** (`player_day` rows) | 82,381 | 282,781 | **+243.26%** |
| **Unique Active Players** (`COUNT(DISTINCT device_id)`) | 22,999 | 73,756 | **+220.69%** |
| **Gross Positive Purchase Revenue** | $29,383.67 | $84,404.41 | **+187.25%** |
| **Refunds (Negative Amounts)** | -$456.76 | -$1,478.94 | +223.79% |
| **Net Revenue (`Gross + Refunds`)** | $28,926.91 | $82,925.47 | **+186.67%** |
| **Weighted Gross ARPDAU** (`Total Gross / Total Player-Days`) | **$0.3567** | **$0.2985** | **-16.32%** |
| **Weighted Net ARPDAU** (`Total Net / Total Player-Days`) | **$0.3511** | **$0.2932** | **-16.49%** |
| **Daily Average Gross ARPDAU** (`Mean of 30 daily ratios`) | $0.3583 | $0.2963 | -17.31% |
| **Daily Average Net ARPDAU** (`Mean of 30 daily ratios`) | $0.3530 | $0.2914 | -17.45% |

> **Beginner Note — Weighted ARPDAU vs. Daily Average ARPDAU:**  
> *Weighted ARPDAU* adds up all 30 days of revenue and divides by all 30 days of player-days (`$84,404.41 / 282,781 = $0.2985`). *Daily Average ARPDAU* computes ARPDAU separately for each of the 30 days and averages those 30 numbers (`$0.2963`). They differ slightly because days with larger DAU carry more weight in the weighted metric. Both confirm the ~16–17% overall decline.

> **Sensitivity Check (Duplicate `purchase_id`s):** Excluding duplicate `purchase_id` rows yields `$29,188.90` gross (`$0.3543` ARPDAU) in Period 1 and `$83,647.92` gross (`$0.2958` ARPDAU) in Period 2 — a **`-16.51%`** decline, confirming the finding is unaffected by duplicate IDs.

---

## 2. Country Tier Analysis (Tiers 1, 2, 3, and 4)

**Table:** `outputs/tables/task_2_tier_comparison.csv`  
**Charts:** `outputs/charts/task_2_arpdau_comparison.png`, `outputs/charts/task_2_tier_trends.png`

| Country Tier | Jan Player-Days | Apr Player-Days | Jan Gross Revenue | Apr Gross Revenue | Jan Gross ARPDAU | Apr Gross ARPDAU | Gross % Change | Net % Change | Direction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| **Tier 1** *(US, DE, AU, UK, CA)* | 28,397 | 57,821 | $14,864.58 | $32,393.89 | $0.5235 | **$0.5602** | **+7.03%** | +5.34% | **Improved** |
| **Tier 2** *(FR, KR, JP, NL)* | 21,469 | 43,988 | $8,059.61 | $17,917.76 | $0.3754 | **$0.4073** | **+8.50%** | +10.87% | **Improved** |
| **Tier 3** *(MX, TR, PL, BR)* | 17,972 | 50,927 | $4,203.04 | $13,517.58 | $0.2339 | **$0.2654** | **+13.50%** | +13.63% | **Improved** |
| **Tier 4** *(IN, EG, ID, PH, VN)* | 14,543 | 130,045 | $2,256.44 | $20,575.18 | $0.1552 | **$0.1582** | **+1.97%** | +0.57% | **Improved / Flat** |
| **All Tiers (Blended)** | **82,381** | **282,781** | **$29,383.67** | **$84,404.41** | **$0.3567** | **$0.2985** | **-16.32%** | **-16.49%** | **Declined (Paradox)** |

Every single tier grew in active player-days, grew in revenue, and **improved (or held steady) in both Gross and Net ARPDAU**.

---

## 3. Player Composition & Channel Mix Shift

**Table:** `outputs/tables/task_2_player_mix.csv`  
**Chart:** `outputs/charts/task_2_player_mix.png`

| Country Tier | Jan Share of Player-Days | Apr Share of Player-Days | Share Shift (pp) | Jan Share of Gross Revenue | Apr Share of Gross Revenue | Paid Video Share (Jan → Apr) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Tier 1** | 34.47% | 20.45% | **-14.02 pp** | 50.59% | 38.38% | 14.25% → 14.19% |
| **Tier 2** | 26.06% | 15.56% | **-10.51 pp** | 27.43% | 21.23% | 14.87% → 14.37% |
| **Tier 3** | 21.82% | 18.01% | **-3.81 pp** | 14.30% | 16.02% | 15.11% → 37.07% |
| **Tier 4** | **17.65%** | **45.99%** | **+28.33 pp** | **7.68%** | **24.38%** | **15.24% → 79.80%** |

- In January, high-monetising **Tiers 1 & 2** represented **60.53%** of daily player activity and **78.02%** of revenue.
- By April, **Tier 4** grew **8.9×** in player-days (`14,543` → `130,045`), driven overwhelmingly by **`paid_video`** (`2,217` → `103,779` player-days = **79.80%** of April Tier 4 activity). Meanwhile, Tiers 1 & 2 still carried **59.61%** of total gross revenue despite shrinking to **36.00%** of player-days.

---

## 4. Mathematical Proof of Simpson's Paradox (Exact Decomposition)

**Table:** `outputs/tables/task_2_decomposition.csv`  
**Chart:** `outputs/charts/task_2_decomposition.png`

Overall ARPDAU is simply a weighted average of the four tier ARPDAUs:
$$\text{ARPDAU}_{\text{overall}} = \sum_{i=1}^{4} w_i \cdot r_i$$
where $w_i$ is Tier $i$'s share of active player-days ($\sum w_i = 1$) and $r_i$ is Tier $i$'s weighted Gross ARPDAU.

### A. Counterfactual Fixed-Weight Calculation
What would April's overall Gross ARPDAU have been if the **country-tier mix had stayed fixed at January weights ($w_1$)**, while using April's tier ARPDAUs ($r_2$)?
$$\text{ARPDAU}_{\text{counterfactual}} = \sum_{i=1}^{4} w_{i,\text{Jan}} \cdot r_{i,\text{Apr}} = \mathbf{\$0.3851}$$
Instead of falling `-16.32%`, overall ARPDAU would have **increased by `+$0.0284` (`+7.97%`)**!

### B. Exact 2-Term Symmetric Kitagawa Decomposition (Zero Residual)
Using average weights $\bar{w}_i = \frac{w_{i,1} + w_{i,2}}{2}$ and average rates $\bar{r}_i = \frac{r_{i,1} + r_{i,2}}{2}$, the total ARPDAU change ($\Delta R = -\$0.0582$) splits cleanly into two exact pieces:
$$\Delta R = \underbrace{\sum_{i=1}^{4} \bar{w}_i (r_{i,2} - r_{i,1})}_{\text{Within-Tier Performance Effect}} + \underbrace{\sum_{i=1}^{4} (w_{i,2} - w_{i,1}) \bar{r}_i}_{\text{Composition / Mix-Shift Effect}}$$

| Country Tier | Within-Tier Effect ($) | Mix-Shift Effect ($) | Total Tier Contribution ($) |
| --- | ---: | ---: | ---: |
| Tier 1 | +$0.0101 | -$0.0760 | -$0.0659 |
| Tier 2 | +$0.0066 | -$0.0411 | -$0.0345 |
| Tier 3 | +$0.0063 | -$0.0095 | -$0.0032 |
| Tier 4 | +$0.0010 | +$0.0444 | +$0.0454 |
| **TOTAL (Exact Sum)** | **+$0.0240** | **-$0.0822** | **-$0.0582** |

- **3-Term Jan-Baseline Check (exact reconciliation):** Within-Tier (`+$0.0284`) + Mix Shift (`-$0.0778`) + Interaction (`-$0.0088`) = **`-$0.0582`** (`$0.2985 - $0.3567`).
- **Interpretation:** Within-tier monetisation added **`+$0.0240`** per DAU, but the shift in country mix subtracted **`-$0.0822`** per DAU — **3.4× larger** in the opposite direction!

---

## 5. Business Recommendation & Missing Inputs

1. **What actually caused the decline?** Not monetisation decay. Every tier improved (`+2.0%` to `+13.5%`). The `-16.3%` overall ARPDAU drop is purely a **denominator/mix effect** from scaling `paid_video` user acquisition in Tier 4 (plus moderate growth in Tier 3) much faster than in Tiers 1–2.
2. **Which tiers carry revenue?** **Tiers 1 & 2** remain the revenue backbone (**59.6%** of April gross revenue from **36.0%** of player-days), while Tier 4 contributes **24.4%** of gross revenue from **46.0%** of player-days.
3. **Is there any evidence of monetisation deterioration?** **No.** In fact, gross revenue grew **+187.25%** (`$29.4k` → `$84.4k`) and every tier's ARPDAU rose.
4. **Should the company change acquisition strategy? (Reasoning with Missing Data):**
   - **Do NOT pause Tier 4 UA merely because blended ARPDAU fell** — evaluating user acquisition using blended ARPDAU is a classic mistake.
   - **Missing inputs we need before shifting budget:** This telemetry extract deliberately excludes **(a) Marketing Cost Per Install (CPI) / ad spend by tier and channel**, and **(b) Rewarded-Ad revenue** (which could be significant in Tier 4 where `paid_video` players watch many ads).
   - **Decision Rule for Leadership:** Keeping Tier 4 `paid_video` scaling is **profitable and worth doing if and only if** Tier 4 `(IAP Net LTV + Ad LTV) > Tier 4 CPI` (and beats the marginal ROI of buying more Tier 1/2 installs). Stop reporting a single blended ARPDAU on executive dashboards; report **tier-stratified ARPDAU** alongside total contribution profit.
