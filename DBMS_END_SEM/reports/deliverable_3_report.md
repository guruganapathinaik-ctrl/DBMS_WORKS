# Deliverable 3: Acquisition Channel Quality & Statistical Analysis

**Question Investigated:** *"Is one acquisition channel (`organic`, `paid_social`, `paid_video`) better than another?"*  
**SQL Script:** `sql/task_3_acquisition_analysis.sql`  
**Python Analysis & Statistical Script:** `src/task_3_analysis.py`

---

## Executive Summary (In Simple Language)

1. **The Apparent Loser (`paid_video`) Is an Illusion (Confounding Artefact):**  
   If you compare channels naively, `paid_video` looks **38%–39% worse on 30-day revenue per player** (`$1.55` vs. `$2.50` organic and `$2.25` paid_social) and **4.3–4.5 percentage points lower on payer conversion**. However, that gap is almost entirely caused by **where and when `paid_video` bought players**: `paid_video` surged 12.5× in March–April heavily in **Tier 4 countries (71.1%)** and on **Android (81.4%)**, whereas `organic` and `paid_social` are mostly Tier 1–3 (~82%) and ~36% iOS. Once we adjust for `country_tier × platform`, **`paid_video`'s 30-day Gross ARPU jumps from `$1.55` to `$2.06`** — statistically indistinguishable from `paid_social` (`$1.99`, `Holm p = 0.92`) and `organic` (`$2.17`, `Holm p = 0.92`).
2. **Real Engagement Advantage for `organic` — Statistically Significant, Commercially Small:**  
   Even after adjusting for `country_tier × platform`, **`organic` players stay slightly more engaged** in their first 30 days (`7.08` active days vs. `6.86` `paid_social` and `6.77` `paid_video`; `Holm p < 0.001`), with ~`10–14` extra minutes of total playtime over 30 days. However, `+0.21` to `+0.30` extra active days per month (`+3.1%` to `+4.5%`, Cohen's $d \approx 0.07–0.09$) is **too small to justify shifting UA budget by itself**.
3. **Genuine-Looking Difference Too Small for This Sample to Resolve (`organic` vs. `paid_social` Revenue):**  
   `organic` and `paid_social` share nearly identical Tier/Platform mixes (~18% Tier 4, ~64% Android), yet `organic` earns `+$0.25` higher 30-day Gross ARPU (`$2.50` vs. `$2.25` unadjusted; `+$0.18` adjusted). Because **~87% of players pay `$0` and a few spend `$100+`**, revenue has high variance: the 95% bootstrap CI (`[-$0.03, +$0.53]` unadjusted; `[-$0.07, +$0.43]` adjusted) crosses zero (`Holm p = 0.081` unadjusted, `0.450` adjusted). Even with ~12,000 players per channel, the sample cannot conclusively prove this ~9–11% revenue difference.
4. **Budget Recommendation:** **Do NOT shift UA budget based on player quality alone.** Across paid channels (`paid_social` vs. `paid_video`), adjusted player quality is practically identical (`$1.99` vs. `$2.06` ARPU, `14.4%` vs. `13.8%` D30 retention). Because **Cost Per Install (CPI)** and **ad revenue** are absent from telemetry, budget decisions must wait for CPI comparisons (`LTV / CPI`).

---

## Phase 3.1 — Channel Exploration & Confounding Factors

**Tables:** `outputs/tables/task_3_channel_profile.csv`, `outputs/tables/task_3_monthly_mix.csv`  
**Chart:** `outputs/charts/task_3_channel_mix.png`

| Channel | Total Players (`n=80,295`) | Share | Pre-2026 Installs | Jan–Mar (30d-Eligible) | Apr (Censored) | Tier 4 Share | Android Share | Zero-Activity Players | All-Window Net Revenue |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`paid_video`** | 34,036 | 42.39% | 2,443 | **13,030** | **18,563 (54.5%)** | **71.09%** | **81.35%** | 755 (2.22%) | $55,308.56 |
| **`organic`** | 24,554 | 30.58% | 7,211 | **12,948** | 4,395 (17.9%) | **18.14%** | **63.55%** | 195 (0.79%) | $89,289.10 |
| **`paid_social`** | 21,705 | 27.03% | 6,346 | **11,511** | 3,848 (17.7%) | **17.98%** | **63.79%** | 164 (0.76%) | $71,561.64 |
| **Total** | **80,295** | **100%** | **16,000** | **37,489** | **26,806** | — | — | **1,114** | **$216,159.30** |

### Why Naive Comparisons Across All 80,295 Players Are Badly Biased
1. **Severe Right-Censoring:** **54.5% (`18,563`)** of `paid_video` players installed in April 2026 and did not yet have 30 days to be observed by `2026-04-30`, artificially crushing naive `paid_video` D30 retention (`5.31%`) and lifetime ARPU (`$1.65`).
2. **Pre-2026 Legacy History Missing:** `29.4%` of `organic` and `29.2%` of `paid_social` installed in 2025 (vs. only `7.2%` of `paid_video`), so their 2026 activity reflects surviving older players rather than equal Day-0 cohorts.
3. **Country-Tier & Platform Confounding:** Starting March 2026, `paid_video` scaled rapidly in **Tier 4** (`78.0%` in Mar, `82.3%` in Apr) and **Android** (`84.0%` in Mar, `85.2%` in Apr). Since Tier 4 spends ~3.5× less than Tier 1 and Android spends ~2× less than iOS, pooling tiers blames the channel for the market mix.

**Clean Evaluation Cohort Selected:** All players installed **`2026-01-01` through `2026-03-31` (`n = 37,489`)**, where **100% of players have a complete 30-day observation window** (`install_date + 30 days <= 2026-04-30`), including inactive players (`0` active days) in every denominator.

---

## Phase 3.2 — Engagement Comparison (Clean 30-Day Cohort, `n = 37,489`)

**Table:** `outputs/tables/task_3_engagement_metrics.csv`  
**Chart:** `outputs/charts/task_3_engagement_comparison.png`

| Channel | Acquired Players | Day 7 Retention | Day 30 Retention | Active Days in 30d (Per Acquired) | Active Days (Per Active) | Playtime Mins in 30d (Per Acquired) | Sessions in 30d (Per Acquired) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`organic`** | 12,948 | **26.39%** | 13.75% | **7.074** | 7.084 | **148.00** | **26.49** |
| **`paid_social`** | 11,511 | 25.58% | **14.43%** | 6.862 | 6.876 | 137.39 | 25.01 |
| **`paid_video`** | 13,030 | 24.56% | 13.53% | 6.824 | 6.835 | 135.15 | 24.84 |

*Note on Naive vs. Clean Comparison:* On the naive all-80,295 sample, `paid_video` showed `5.31%` D30 retention and `4.928` active days per acquired player solely due to April censoring; in the equal-window 30d cohort, `paid_video` D30 retention (`13.53%`) is virtually identical to `organic` (`13.75%`)!

---

## Phase 3.3 — Real-Money Revenue Comparison (Clean 30-Day Cohort, `n = 37,489`)

**Table:** `outputs/tables/task_3_revenue_metrics.csv`  
**Chart:** `outputs/charts/task_3_revenue_comparison.png`

| Channel | Acquired Players | Paying Players (30d) | Payer Conv. (%) | Gross 30d Revenue | Refunds (30d) | Net 30d Revenue | Gross ARPU (All Acquired) | Net ARPU (All Acquired) | Dedup Gross ARPU | ARPPU (Payers Only) | Top 10% Player Share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`organic`** | 12,948 | 1,723 | 13.31% | $32,331.47 | -$674.71 | $31,656.76 | **$2.4970** | $2.4449 | $2.4627 | **$18.76** | 96.95% |
| **`paid_social`** | 11,511 | 1,514 | 13.15% | $25,848.14 | -$340.82 | $25,507.32 | **$2.2455** | $2.2159 | $2.2167 | **$17.07** | 97.07% |
| **`paid_video`** | 13,030 | 1,154 | 8.86% | $20,157.47 | -$189.82 | $19,967.65 | **$1.5470** | $1.5324 | $1.5418 | **$17.47** | 100.00% |

- **Zero-Inflated & Skewed Distribution:** Median (`p50`) 30-day revenue is **`$0.00`** in all three channels; `p90` is `$4.99` (`organic`, `paid_social`) and `$0.00` (`paid_video` unadjusted); `p99` is `$56.03` / `$49.99` / `$49.99`, with max single-player 30d spend reaching `$219.94` / `$201.97` / `$209.97`.
- **Duplicate `purchase_id` Sensitivity:** Deduplicating `purchase_id` reduces 30d Gross ARPU by only `$0.005–$0.034` (`<1.4%`) and leaves every channel comparison unchanged.

---

## Phase 3.4 — Statistical Analysis, Confidence Intervals & Stratified Adjustment

**Tables:** `outputs/tables/task_3_adjusted_comparison.csv`, `outputs/tables/task_3_statistical_tests.csv`, `outputs/tables/task_3_stratified_metrics.csv`  
**Chart:** `outputs/charts/task_3_confidence_intervals.png`

### Why We Used Bootstrap CIs + Mann-Whitney U + Holm Correction
- Because revenue is **~87–91% zeros** and strongly right-skewed, standard t-tests alone can misstate p-values if normality fails, while Mann-Whitney U tests rank distributions (sensitive to payer % ties).
- **Player-level bootstrap 95% confidence intervals (4,000 resamples)** estimate the exact sampling uncertainty of the **mean difference** (including ARPU) without assuming normality, and **Holm-Bonferroni correction** controls the family-wise error rate across all 3 pairwise tests per metric.
- **Direct Standardization (`country_tier × platform`)** re-weights every channel to the same 8-cell (`4 tiers × 2 platforms`) population distribution of the full `37,489` cohort, isolating true player quality from demographic mix.

### Unadjusted vs. Adjusted Headline Results

| Metric | Comparison (`A - B`) | Unadjusted Diff [95% Boot CI] | Unadj. Holm $p$ | **Adjusted Diff [95% Boot CI]** (`Tier × Platform`) | **Adj. Holm $p$** | Interpretation |
| --- | --- | --- | ---: | --- | ---: | --- |
| **Active Days (30d)** | `organic - paid_social` | **+0.212** `[+0.138, +0.285]` | `<0.0001` | **+0.214** `[+0.135, +0.296]` | `<0.0001` | Real, small edge (`+3.1%`, $d=0.07$) |
| **Active Days (30d)** | `organic - paid_video` | **+0.251** `[+0.179, +0.321]` | `<0.0001` | **+0.305** `[+0.226, +0.390]` | `<0.0001` | Real, small edge (`+4.5%`, $d=0.09$) |
| **Active Days (30d)** | `paid_social - paid_video` | +0.039 `[-0.034, +0.112]` | `0.294` | **+0.091** `[+0.006, +0.175]` | `0.037` | Stat. sig. adjusted, tiny (`+1.3%`) |
| **Day 7 Retention** | `organic - paid_social` | +0.81 pp `[-0.28, +1.94 pp]` | `0.152` | +0.52 pp `[-0.65, +1.70 pp]` | `0.416` | Inconclusive (too small for sample) |
| **Day 7 Retention** | `organic - paid_video` | **+1.83 pp** `[+0.78, +2.88 pp]` | `0.002` | +1.34 pp `[+0.19, +2.57 pp]` | `0.082` | Shrinks after adj.; Holm-NS (`0.082`) |
| **Day 30 Retention** | `organic - paid_social` | -0.68 pp `[-1.57, +0.14 pp]` | `0.251` | -0.70 pp `[-1.61, +0.25 pp]` | `0.436` | No proven difference |
| **Day 30 Retention** | `paid_social - paid_video` | +0.90 pp `[+0.02, +1.76 pp]` | `0.127` | +0.60 pp `[-0.44, +1.59 pp]` | `0.483` | No proven difference |
| **30d Payer Conv.** | `organic - paid_video` | **+4.45 pp** `[+3.70, +5.21 pp]` | `<0.0001` | **+0.72 pp** `[-0.18, +1.60 pp]` | `0.361` | **Artefact!** Shrinks 84% after adj. |
| **30d Gross ARPU** | `organic - paid_video` | **+$0.950** `[+$0.687, +$1.206]` | `<0.0001` | **+$0.118** `[-$0.206, +$0.432]` | `0.934` | **Artefact!** Shrinks 88% after adj. |
| **30d Gross ARPU** | `paid_social - paid_video` | **+$0.699** `[+$0.447, +$0.949]` | `<0.0001` | **-$0.067** `[-$0.394, +$0.253]` | `0.934` | **Artefact!** Reverses sign after adj. |
| **30d Gross ARPU** | `organic - paid_social` | +$0.252 `[-$0.033, +$0.535]` | `0.081` | +$0.185 `[-$0.070, +$0.429]` | `0.450` | Plausible real edge, **underpowered** |

### Answering the Two Core Methodological Questions
1. **Which obvious comparison is badly misleading (an artefact)?**  
   **`paid_video` vs. `organic` / `paid_social` on unadjusted revenue (`$1.55` vs. `$2.50`/`$2.25`) and payer conversion (`8.86%` vs. `13.31%`/`13.15%`).** Nearly 88% of that gap disappears once stratified by `country_tier × platform` (adjusted 30d Gross ARPU: `organic $2.17`, `paid_video $2.06`, `paid_social $1.99`). Within Tier 4 (`$1.10` vs. `$1.07` `paid_social` vs. `$1.02` `organic`) and Tier 1 (`$3.44` vs. `$3.26` `paid_social` vs. `$3.83` `organic`), `paid_video` performs right in line with `paid_social`.
2. **Which genuine-looking difference is too small for this sample to resolve?**  
   **`organic` vs. `paid_social` on 30-day Gross ARPU (`+$0.25` unadjusted / `+$0.18` adjusted, ~9–11%) and Day 7 retention (`+0.81 pp` / `+0.52 pp`).** Because `organic` beats `paid_social` consistently on active days (`+0.214` days, `p < 0.0001`) and playtime (`+10.3` mins, `p < 0.0001`), a small real revenue edge (~`$0.18`) is plausible, **but the high variance of heavy-tailed IAP revenue makes the 95% CI cross zero (`[-$0.07, +$0.43]`)** at `n ≈ 12,000` per channel.
3. **What would we need to prove a channel difference is *real* rather than a collection artefact?**  
   (a) **Geo/platform-matched randomized holdouts or A/B channel tests** (controlling unmeasured confounders like creative targeting, app-store placement, or campaign optimization shift over time), (b) **larger sample sizes** (to narrow the `±$0.26` ARPU confidence interval width), and (c) **marketing spend / CPI logs** to rule out bid-tier selection bias (e.g., buying cheaper low-intent inventory in March–April).

---

## Phase 3.5 — Business Recommendation

1. **Which channel brings better-quality players?**  
   - **`organic`** brings slightly higher-engagement players (`+3.1%` to `+4.5%` more active days and `+7.5%` to `+10.4%` more playtime in 30 days), which is statistically significant even after adjustment.
   - Between the two **paid** channels (**`paid_social` vs. `paid_video`**), **adjusted player quality is virtually identical** (`$1.99` vs. `$2.06` 30d Gross ARPU; `11.78%` vs. `11.26%` payer conversion; `14.42%` vs. `13.82%` D30 retention).
2. **Are differences large enough to move budget over?**  
   - **No.** A `+0.09` to `+0.30` active-day difference (~3%–4% engagement) and statistically unresolved `$0.07–$0.18` ARPU gaps are **not large enough commercially to justify shifting budget on player quality alone** — especially since `organic` isn't a directly biddable channel anyway.
3. **Should the UA team shift budget toward `paid_social` or `paid_video`?**  
   - **Hold off on cutting `paid_video`!** Cutting `paid_video` based on naive blended ARPU (`$1.55`) would be a major error caused by Tier 4 confounding.
   - **Missing Data Needed:** The dataset contains **zero CPI / marketing spend** and **zero rewarded-ad revenue**.
   - **Actionable Rule:** Shift budget **only after comparing `LTV / CPI` within matching `(country_tier, platform)` cells**: allocate incremental spend to whichever channel (`paid_video` vs. `paid_social`) delivers a **lower CPI per equivalent-tier install** (or higher `(30d Net IAP + Ad Revenue) - CPI` contribution margin).
