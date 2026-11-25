# Deliverable 4: Player Churn Prediction — Technical & Live-Ops Report

**Question Investigated:** *"Predict which currently active players will stop playing in the next 14 days."*  
**SQL Pipeline:** `sql/task_4_churn_analysis.sql`  
**Python Modelling & Evaluation Script:** `src/task_4_churn_analysis.py`  
**Exploratory Scripts:** `src/phase4_explore.py`, `src/phase4_feature_check.py`

---

## Executive Summary (In Simple Language)

1. **Who We Predict & What "Churn" Means:**  
   We predict 14-day inactivity (`churn_14d = 1` if a player logs **zero active days** during `[T+1, T+14]`) for **currently active players** — defined as players installed on or before prediction date $T$ who played **at least once in the past 7 days (`[T-6, T]`)**. Data evidence as of `2026-03-15` shows players active in the last 7 days have a `15.7%–25.5%` 14-day lapse rate (versus `31.1%–52.0%` for players already dormant 8–31+ days), making 7-day-active players the right reachable population for live-ops re-engagement offers.
2. **How Well the Model Works:**  
   Using strictly past features (`<= T`) and an out-of-time **Train (`2026-03-02`, n=20,025) → Validation (`2026-03-23`, n=26,886) → Test (`2026-04-16`, n=38,644)** split, our selected **Logistic Regression (`C=1.0`)** achieves **`ROC-AUC = 0.7467`** and **`PR-AUC = 0.3830`** on the Test set (`18.73%` base churn rate — a **2.04× lift in PR-AUC** over random guessing and far above the recency-only rule `ROC-AUC = 0.5680`, `PR-AUC = 0.2180`). On **20,129 completely unseen Test players** never present in Train or Validation, performance is even stronger (`ROC-AUC = 0.7852`, `PR-AUC = 0.3973`).
3. **Why Logistic Regression Beats More Complex Alternatives Here:**  
   A `HistGradientBoosting` ensemble raises Test `ROC-AUC` only modestly to `0.7580` (`+0.0113`) and `PR-AUC` to `0.4121` (`+0.0291`), while a shallow `Decision Tree` scores lower (`0.7330` / `0.3711`). Logistic Regression provides clean probability calibration (`Brier = 0.1366`) and transparent drivers without black-box complexity. (Class-balanced Logistic Regression achieves the same ranking `0.7468` but breaks probability calibration, inflating `Brier` to `0.2091`.)
4. **Targeting Effectiveness & Wasted Offers (Test Cohort, n=38,644, 7,238 Actual Churners):**  
   - **Top 5% Riskiest (`1,933` offers):** Catches **`931` true churners** (`12.86%` recall) at **`48.16%` precision** (`2.57×` lift), wasting **`1,002` offers (`51.84%`)**.
   - **Top 10% Riskiest (`3,865` offers):** Catches **`1,735` true churners** (`23.97%` recall) at **`44.89%` precision** (`2.40×` lift), wasting **`2,130` offers (`55.11%`)**.
   - **Top 20% Riskiest (`7,729` offers):** Catches **`3,071` true churners** (`42.43%` recall) at **`39.73%` precision** (`2.12×` lift), wasting **`4,658` offers (`60.27%`)**.
   - **Top 30% Riskiest (`11,593` offers):** Catches **`4,206` true churners** (`58.11%` recall) at **`36.28%` precision** (`1.94×` lift), wasting **`7,387` offers (`63.72%`)**.
   - **Sending to Everyone (`38,644` offers):** Wastes **`31,406` offers (`81.27%`)**.
5. **Crucial Business Caveat:**  
   The model predicts **who is likely to stop playing**, NOT **who will respond to an offer**. Telemetry contains no offer cost, no causal uplift from past offers, and no ad revenue per player. Live-ops should deploy targeting using an **A/B randomized holdout** before scaling spend.

---

## 1. Setup: Churn Definition, Eligibility & Leak-Free Snapshots

**Evidence Table:** `outputs/tables/task_4_churn_definition_evidence.csv`  
**Chart:** `outputs/charts/task_4_eda_churn_drivers.png` (Top-Left Panel)

### A. Data-Driven Churn Definition (`as_of = 2026-03-15`, `n = 42,706` installed players)

Rather than picking an arbitrary rule, we inspected return rates after `2026-03-15` across recency buckets (`player_profile` + `player_day`, reserving `[Mar 16–Mar 29]` as the 14-day window and `[Mar 30–Apr 30]` to check late returns):

| Days Since Last Activity (`as of Mar 15`) | Players | Returned in Next 14d (%) | **14-Day Churn Rate (%)** | Missed 14d, Returned Later (Mar 30–Apr 30) (%) |
| --- | ---: | ---: | ---: | ---: |
| **0d (active today)** | 5,974 | 84.27% | **15.73%** | 14.06% |
| **1–3d** | 11,160 | 80.65% | **19.35%** | 16.53% |
| **4–7d** | 8,483 | 74.51% | **25.49%** | 21.29% |
| **8–14d** | 7,495 | 68.91% | **31.09%** | 26.00% |
| **15–30d** | 5,991 | 60.14% | **39.86%** | 30.21% |
| **31+d** | 2,668 | 48.05% | **51.95%** | 36.47% |
| **Never active** *(no `player_day` row `<= Mar 15`)* | 935 | 70.80% | **29.20%** | 18.07% |

- **Why `churn_14d = 0 active days in [T+1, T+14]`:** The brief asks to predict players who *"will stop playing in the next 14 days."* Requiring zero activity across all 14 future days matches the exact 2-week window and distinguishes genuine lapses from normal multi-day gaps between sessions.
- **Why "Currently Active" = `>= 1 active day in [T-6, T]`:** Players active within the past 7 days are live in the app, reachable by live-ops messaging, and still retain a `74.5%–84.3%` baseline return rate. Including `15–31+d` dormant players would mostly predict "already-churned players staying gone" (`40%–52%` lapse) rather than preventing active-player churn. (And `Never active` players have 0 telemetry history to score.)
- **Limitation of a 14-Day Window:** Roughly `14%–21%` of active-7d players who miss `[T+1, T+14]` return later in `[T+15, T+46]`, so `churn_14d` measures **14-day inactivity**, not necessarily permanent account deletion.

### B. Snapshot Design, Zero Right-Censoring & Leakage Guards

Because the dataset spans `2026-01-01` to `2026-04-30`, the **latest possible prediction date** with a complete 14-day future window is **`2026-04-16`** (`[2026-04-17, 2026-04-30]`). We construct three strictly chronological snapshots in `sql/task_4_churn_analysis.sql`:

| Split | Prediction Date ($T$) | Active Entry Window (`[T-6, T]`) | Future Label Window (`[T+1, T+14]`) | Eligible Players ($n$) | Actual Churners | **Churn Rate (%)** | Overlap Note |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| **Train** | `2026-03-02` | Feb 24 – Mar 02 | Mar 03 – Mar 16 | **20,025** | 4,104 | **20.49%** | Disjoint from Val entry (`Mar 17`) |
| **Validation** | `2026-03-23` | Mar 17 – Mar 23 | Mar 24 – Apr 06 | **26,886** | 5,220 | **19.42%** | Disjoint from Test entry (`Apr 10`) |
| **Test** | `2026-04-16` | Apr 10 – Apr 16 | Apr 17 – Apr 30 | **38,644** | 7,238 | **18.73%** | **`20,129` unseen players** (52.1%) |

- **Exclusions:** Players installed after $T$ (`install_date > T`), players with 0 active days in `[T-6, T]`, and dates after `2026-04-16` (where the full 14-day future outcome is censored).
- **Respecting Phase 1 Data-Quality Rules:**
  - `device_id` is the primary player unit (`original_device_id` is never merged).
  - `ad_view.event_ts` uses the verified **`-8h` game-date alignment** (`DATE(event_ts - INTERVAL 8 HOUR)`). Furthermore, all three snapshots' 14-day ad windows (`Feb 17–Mar 02`, `Mar 10–Mar 23`, `Apr 03–Apr 16`) cleanly avoid the **March 5–6 `ad_view` outage**.
  - `currency_spend` filters out the 233 corrupted outliers (`currency_value <= 10,000`) when summing `clean_currency_spent_14d`.
  - All 32 engineered features strictly enforce `date <= T` (independently verified by deleting all telemetry `> T` and confirming 0/32 feature columns change).

---

## 2. Exploratory Analysis: Segments & Churn Drivers

**Tables:** `outputs/tables/task_4_eda_segments.csv`, `outputs/tables/task_4_feature_summary.csv`  
**Chart:** `outputs/charts/task_4_eda_churn_drivers.png`

### A. Segment Churn Rates (Test Set, `2026-04-16`, `n = 38,644`)

| Segment Type | Segment Value | Active Players | Churners | **Churn Rate (%)** |
| --- | --- | ---: | ---: | ---: |
| **Overall** | All Active Players | 38,644 | 7,238 | **18.73%** |
| **Platform** | Android | 27,616 | 4,881 | 17.67% |
| | iOS | 11,028 | 2,357 | 21.37% |
| **Country Tier** | Tier 1 | 8,765 | 2,027 | 23.13% |
| | Tier 2 | 6,566 | 1,523 | 23.20% |
| | Tier 3 | 7,106 | 1,440 | 20.26% |
| | Tier 4 | 16,207 | 2,248 | **13.87%** |
| **Channel** | `organic` | 11,715 | 2,572 | 21.95% |
| | `paid_social` | 10,074 | 2,363 | 23.46% |
| | `paid_video` | 16,855 | 2,303 | **13.66%** |
| **Install Age** | `0–7d (New)` | 6,367 | 284 | **4.46%** |
| | `8–30d` | 12,518 | 1,479 | **11.81%** |
| | `31–90d` | 12,125 | 2,684 | **22.14%** |
| | `91+d (Veteran)` | 7,634 | 2,791 | **36.56%** |

> **Why Tier 4 & `paid_video` Look Lower in Blended Churn (Another Composition Effect):**  
> Just like in Deliverables 2 and 3, **install-age mix** drives the blended gap! Because `paid_video` surged in Tier 4 during March–April, `63.0%` of `0–7d` new active players on April 16 are in Tier 4, where recent installs play frequently (`2.11` active days in the last 7d) and have only a `4.46%` chance of logging zero days over the next 2 weeks. Conversely, `91+d` veterans average only `1.28` active days in the past 7d (long-tail occasional players) and lapse at `36.56%`. When stratified inside each `install_age_bucket`, **Tier 4 churns at nearly the exact same rate as Tiers 1–3**:
> - `0–7d`: Tier 1 `3.29%`, Tier 2 `6.72%`, Tier 3 `6.10%`, Tier 4 `3.94%`
> - `8–30d`: Tier 1 `11.54%`, Tier 2 `10.85%`, Tier 3 `11.34%`, Tier 4 `12.22%`
> - `31–90d`: Tier 1 `23.34%`, Tier 2 `23.33%`, Tier 3 `22.25%`, Tier 4 `20.11%`
> - `91+d`: Tier 1 `36.57%`, Tier 2 `36.80%`, Tier 3 `37.38%`, Tier 4 `35.20%`

### B. Churned vs. Retained Activity Patterns (Validation Set, `n = 26,886`)

| Feature (Strictly `<= T`) | Mean (Retained, `y=0`) | Mean (Churned, `y=1`) | Univariate ROC-AUC | Direction |
| --- | ---: | ---: | ---: | --- |
| `install_age_days` | 53.08 days | **102.29 days** | **0.7084** | Older install age → Higher 14d lapse |
| `days_since_last_purchase_filled` | 47.75 days | **93.78 days** | 0.7005 | Proxies `install_age_days` for ~87% non-payers |
| `sess_14d` | **10.54** | 7.05 | **0.6447** | More sessions → Lower churn |
| `level_as_of` | 9.21 | **12.06** | 0.6381 | Higher level (correlates with age) → Higher lapse |
| `play_14d` | **58.88 min** | 37.48 min | 0.6376 | More playtime → Lower churn |
| `ad_views_14d` | **2.82** | 1.65 | 0.6285 | More rewarded ads → Lower churn |
| `act_14d` | **2.74 days** | 2.09 days | 0.6245 | More active days → Lower churn |
| `spend_events_14d` | **2.08** | 1.35 | 0.6060 | More currency spends → Lower churn |
| `days_since_last_activity` | 2.16 days | **2.60 days** | 0.5637 | Longer recency gap → Higher churn |
| `is_payer_lifetime` | 13.0% | 12.7% | 0.5014 | Weak univariate signal once active-7d conditioned |

---

## 3. Predictive Modelling & Out-of-Time Evaluation

**Tables:** `outputs/tables/task_4_model_comparison.csv`, `outputs/tables/task_4_feature_importance.csv`  
**Chart:** `outputs/charts/task_4_model_evaluation.png`

### A. Model Comparison on Validation (`n=26,886`) & Test (`n=38,644`)

We evaluated all models on the out-of-time Test set (`2026-04-16`), plus the **`20,129` completely unseen Test players** who never appeared in Train or Validation. Because churn is imbalanced (`18.73%`), default `threshold = 0.50` severely under-predicts churners; therefore we report threshold-free ranking/calibration metrics (`ROC-AUC`, `PR-AUC`, `Brier Score`) alongside both `0.50` and the Validation-selected `opt-F1` threshold:

| Model | Test `ROC-AUC` | Test `PR-AUC` | Test `Brier` | Unseen-Player `ROC-AUC` | Unseen-Player `PR-AUC` | Test Prec / Rec / F1 (`@ 0.50`) | Test Prec / Rec / F1 (`@ Val Opt-F1`) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| **Baseline (Prior Dummy)** | 0.5000 | 0.1873 | 0.1525 | 0.5000 | 0.1451 | 0.00 / 0.00 / 0.00 | 0.187 / 1.000 / 0.316 |
| **Baseline (Recency Only)** | 0.5680 | 0.2180 | 0.1512 | 0.6003 | 0.1865 | 0.00 / 0.00 / 0.00 | 0.203 / 0.815 / 0.325 |
| **Logistic Regression (`C=1.0`) ★** | **0.7467** | **0.3830** | **0.1366** | **0.7852** | **0.3973** | 0.470 / 0.172 / 0.252 | **0.340 / 0.665 / 0.450** |
| **Logistic Regression (Balanced)** | 0.7468 | 0.3810 | 0.2091 | 0.7877 | 0.3976 | 0.332 / 0.688 / 0.448 | 0.340 / 0.661 / 0.449 |
| **Decision Tree (`depth=5`)** | 0.7330 | 0.3711 | 0.1356 | 0.7659 | 0.3810 | 0.609 / 0.055 / 0.102 | 0.330 / 0.665 / 0.441 |
| **HistGradientBoosting (`depth=4`)** | 0.7580 | 0.4121 | 0.1321 | 0.7964 | 0.4232 | 0.614 / 0.073 / 0.130 | 0.372 / 0.579 / 0.453 |

> **What Each Metric Tells Us (and Doesn't Tell Us):**  
> - **Accuracy alone is misleading:** A model that predicts "no churn" for everyone is **81.27% accurate** on Test yet catches **0 churners**!  
> - **ROC-AUC (`0.7467`)** measures how often a randomly chosen churner is scored higher than a randomly chosen retained player, independent of threshold.  
> - **PR-AUC (`0.3830` vs. `0.1873` random)** focuses directly on the positive (churner) class and reveals how well precision holds up as recall rises.  
> - **Brier Score (`0.1366`) & Calibration Curve** measure whether a predicted `30%` risk actually corresponds to `~30%` observed churn — essential for ROI breakeven thresholds (`p*`). Notice **`Logistic Regression (Balanced)` destroys calibration (`Brier = 0.2091`)** while offering zero AUC gain (`0.7468` vs `0.7467`), so we keep standard `Logistic Regression (C=1.0)` and adjust the decision threshold instead!
> - **Confusion Matrix (`Logistic Regression C=1.0` on Test, `n=38,644`):**  
>   - At `thr = 0.50`: `TP = 1,248`, `FP = 1,406`, `FN = 5,990`, `TN = 30,000` (conservative, `47.0%` precision, misses `82.8%` of churners).  
>   - At `Val opt-F1 = 0.2162`: `TP = 4,810`, `FP = 9,342`, `FN = 2,428`, `TN = 22,064` (catches `66.5%` of churners, `34.0%` precision).

### B. Feature Coefficients & Multicollinearity Check

In `outputs/tables/task_4_feature_importance.csv` (and `task_4_targeting_tradeoffs.png`), the strongest standardized log-odds predictors in `Logistic Regression (C=1.0)` are:
- **Increases Predicted Risk:** `install_age_days` (`+0.8156`, odds ratio `2.26×` per 1 SD), `act_30d` (`+0.6594`), `level_gain_14d` (`+0.2510`), `act_lifetime` (`+0.2424`).
- **Protects Against Churn:** `sess_30d` (`-0.6207`, OR `0.54×`), `play_30d` (`-0.4431`, OR `0.64×`), `sessions_per_active_day_30d` (`-0.2785`), `ad_views_14d` (`-0.2616`), `level_as_of` (`-0.2169`), `act_7d` (`-0.2058`), `act_14d` (`-0.1981`), `spend_events_14d` (`-0.1936`).

> **Important Statistical Note on `act_30d` (`+0.6594`):**  
> Marginally (univariate), higher `act_30d` **reduces** churn (`4.47` days retained vs. `3.62` churned). Its positive multivariate coefficient (`+0.6594`) is caused by **multicollinearity** (`r = 0.920` with `sess_30d`, `r = 0.831` with `play_30d`, `r = 0.669` with `act_14d`): *holding total 30-day sessions, playtime, and 14-day activity fixed*, spreading fewer sessions across more days (lower intensity) or having activity mostly 15–30 days ago rather than recently signals higher lapse risk.

### C. Where the Model Works Badly (Subgroup Error & Calibration Audit)

**Table:** `outputs/tables/task_4_subgroup_errors.csv`

| Subgroup | Test $n$ | Actual Churn (%) | Mean Pred Prob (%) | `ROC-AUC` | `Brier Score` | Diagnostic Finding |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **`0–7d (New)`** | 6,367 | 4.46% | **9.68%** | **0.6774** | 0.0449 | Linear model overpredicts risk by `+5.22 pp` |
| **`8–30d`** | 12,518 | 11.81% | 12.14% | 0.6941 | 0.0993 | Best calibrated age tier (`+0.33 pp` gap) |
| **`31–90d`** | 12,125 | 22.14% | 21.24% | 0.6647 | 0.1631 | Slightly underpredicts (`-0.90 pp`) |
| **`91+d (Veteran)`** | 7,634 | 36.56% | **43.78%** | **0.6241** | **0.2320** | **Weakest segment**: lowest discrimination, overpredicts `+7.22 pp` |
| **Lifetime Payers (`1`)** | 5,328 | 20.42% | 23.34% | 0.7077 | 0.1539 | Harder to separate within payers (`0.708` vs `0.752` non-payers) |

1. **Temporal Base-Rate Drift (`20.49%` → `18.73%`):** Because Test has more young Tier-4 installs, predicted probabilities average `~20.9%` vs. `18.73%` actual.
2. **Upper-Tail Overconfidence:** In the top calibration bin (`predicted >= 0.50`, `n=2,654`), observed churn is **`47.02%`**, and at `p >= 0.67` (`n=903`), observed churn is **`51.72%`** (`467/903`), meaning raw linear log-odds slightly exaggerates extreme risk.
3. **Why `91+d` Veterans Are Hard (`AUC = 0.6241`):** Without external factors (content exhaustion, clan/social ties, competitor launches), two veterans who both logged in 1–2 days last week look nearly identical in 30-day telemetry yet diverge `~37%` vs `63%` in the next 14 days. (Tree-based `HistGradientBoosting` captures non-linear `install_age × activity` interactions better here, explaining its `+0.029` PR-AUC edge.)

---

## 4. Targeting Thresholds & Business Scenarios

**Tables:** `outputs/tables/task_4_threshold_analysis.csv`, `outputs/tables/task_4_cost_value_scenarios.csv`  
**Charts:** `outputs/charts/task_4_targeting_tradeoffs.png`, `outputs/charts/task_4_cost_value_heatmap.png`

### A. Targeting Performance Across Thresholds (Test Set, `n = 38,644`, `7,238` Churners)

| Targeting Rule | Prob Cutoff | Targeted Players | True Churners Caught (`TP`) | **Wasted Offers (`FP`)** | Wasted % (`1 - Prec`) | **Precision (%)** | **Recall (%)** | Lift vs. Random |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Top 5% Riskiest** | `0.5546` | 1,933 | 931 | 1,002 | 51.84% | **48.16%** | 12.86% | **2.57×** |
| **Top 10% Riskiest** | `0.4391` | 3,865 | 1,735 | 2,130 | 55.11% | **44.89%** | 23.97% | **2.40×** |
| **Top 20% Riskiest ★** | `0.3231` | 7,729 | **3,071** | **4,658** | 60.27% | **39.73%** | **42.43%** | **2.12×** |
| **Top 30% Riskiest** | `0.2527` | 11,593 | 4,206 | 7,387 | 63.72% | **36.28%** | 58.11% | **1.94×** |
| **Top 50% Riskiest** | `0.1599` | 19,322 | 5,775 | 13,547 | 70.11% | 29.89% | 79.79% | 1.60× |
| **Prob >= 0.50** | `0.5000` | 2,654 | 1,248 | 1,406 | 52.98% | 47.02% | 17.24% | 2.51× |
| **Target Everyone (No Model)** | `0.0000` | 38,644 | 7,238 | **31,406** | **81.27%** | 18.73% | 100.00% | 1.00× |

### B. Hypothetical Cost–Value Scenarios & Optimal Breakeven Threshold ($p^*$)

Because telemetry lacks real offer cost ($c$), causal save rate ($s$), and retained player value ($V$), we model expected net value across 18 combinations:
$$\text{Expected Net Value} = (\text{TP} \times s \times V) - (\text{Targeted} \times c), \qquad \text{Breakeven Risk } p^* = \frac{c}{s \times V}$$

Selected scenarios from `outputs/tables/task_4_cost_value_scenarios.csv` (Test cohort, `n = 38,644`):

| Offer Cost ($c$) | Retained Value ($V$) | Assumed Save Rate ($s$) | Breakeven $p^*$ | Optimal Threshold Net ($) | Top 20% Net ($) | Top 30% Net ($) | Target Everyone Net ($) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **$0.25** | $5.00 | 15% | `0.333` | **+$371.00** (`7,255` targeted) | **+$371.00** | +$256.25 | **-$4,232.50** |
| **$0.25** | $10.00 | 15% | `0.167` | **+$3,836.00** (`18,568` targeted) | +$2,674.25 | +$3,410.75 | +$1,196.00 |
| **$0.25** | $20.00 | 25% | `0.050` | **+$26,962.50** (`34,510` targeted) | +$13,422.75 | +$18,131.75 | +$26,529.00 |
| **$0.50** | $5.00 | 15% | `0.667` | **-$101.25** (`903` targeted)* | -$1,561.25 | -$2,642.00 | -$13,893.50 |
| **$0.50** | $10.00 | 15% | `0.333` | **+$742.00** (`7,255` targeted) | **+$742.00** | +$512.50 | **-$8,465.00** |
| **$0.50** | $10.00 | 25% | `0.200` | **+$4,942.50** (`15,445` targeted) | +$3,813.00 | +$4,718.50 | -$1,227.00 |
| **$1.00** | $10.00 | 25% | `0.400` | **+$377.00** (`4,898` targeted) | -$51.50 | -$1,078.00 | **-$20,549.00** |
| **$1.00** | $20.00 | 15% | `0.333` | **+$1,484.00** (`7,255` targeted) | **+$1,484.00** | +$1,025.00 | **-$16,930.00** |

*\*Note on the `-$101.25` edge case (`c=$0.50, V=$5.00, s=15%, p*=0.667`):* Because the model slightly overpredicts in the extreme tail (`p >= 0.67` actually churns at `51.7% < 66.7%`), even the highest-risk slice loses money when offers cost `$0.50` to save a `$5.00` player at `15%` save rate — **no offers should be sent** in that regime!

### C. Actionable Live-Ops Recommendation

1. **Default Targeting Band — Top 20% Riskiest (`p >= 0.3231`):**  
   Targets **`7,729` players** (`20.0%` of the active base), captures **`3,071` of `7,238` churners (`42.43%` recall)** at **`39.73%` precision (`2.12×` lift)**, and avoids **`26,748` wasted offers** compared to mass-sending. Under mid-range economics (`c=$0.50`, `V=$10`, `s=15%`), Top 20% turns an **`-$8,465` mass-campaign loss** into **`+$742` net gain** (matching the theoretical `p* = 0.333` optimum).
2. **Budget-Constrained vs. High-LTV Rule:**  
   - **Expensive offers (`$1.00+`) or low save-rate segments:** Restrict to **Top 5%–10%** (`p >= 0.44`, `45%–48%` precision) or **do not send** if `c / (s * V) > 0.52` (since even the riskiest deciles top out around `~48%–52%` empirical churn).  
   - **Cheap in-game currency offers (`~$0.00` marginal cash cost, watching out for economy inflation):** Expand to **Top 30%** (`p >= 0.25`, catches `58.1%` of churners) or **Top 50%** (`79.8%` recall).
3. **Mandatory Next Step — Randomized Holdout Experiment:**  
   Before rolling out globally, split the **Top 20% (`p >= 0.3231`)** into **Treatment (receives offer)** vs. **Control (no offer)** to measure true **causal save rate ($s$)**, incremental IAP + ad revenue ($V$), and economy cannibalization (since ~60% of targeted players would have stayed anyway).

---

## 5. What the Data Supports vs. What Requires Assumptions

| Supported Directly by Telemetry | Cannot Be Established Without New Data / Experiments |
| --- | --- |
| Exact 14-day inactivity rates for active-7d cohorts across `Mar 02`, `Mar 23`, `Apr 16` (`20.49%` → `18.73%`) | **Causal save rate ($s$)** of a re-engagement offer (requires an A/B holdout test) |
| Leak-free out-of-time ranking performance (`ROC-AUC = 0.7467`, `PR-AUC = 0.3830`) and `20,129` unseen-player generalization (`0.7852`) | **True marginal offer cost ($c$)** (cash discount vs. soft-currency economy dilution) |
| Exact precision, recall, TP, and wasted-offer FP counts at Top 5%/10%/20%/30%/50% | **Retained player LTV ($V$)** including **rewarded-ad revenue** (absent from telemetry) |
| Confounding proof that Tier 4's lower raw churn (`13.87%`) reflects younger `install_age_days`, not intrinsic retention superiority | Whether **veteran (`91+d`) churn** is driven by unmeasured content caps, social churn, or external competition |
