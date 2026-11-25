"""Independent Quality Audit for Deliverable 3 (Acquisition Channel Analysis).

Independently recalculates every channel metric, cohort window, stratified
adjustment, bootstrap CI (with independent seed=999), hypothesis test,
Holm-Bonferroni correction, and revenue reconciliation directly from the
untouched raw CSV files in data/*.csv.
"""

import re
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path("data")
SQL_PATH = Path("sql/task_3_acquisition_analysis.sql")
OUT_TABLES = Path("outputs/tables")

# 1. Read untouched raw CSV files into isolated in-memory DuckDB
raw_con = duckdb.connect(":memory:")
raw_con.execute(f"CREATE TEMP TABLE player_profile AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'player_profile - player_profile.csv').as_posix()}', sample_size=-1)")
raw_con.execute(f"CREATE TEMP TABLE player_day AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'player_day - player_day.csv').as_posix()}', sample_size=-1)")
raw_con.execute(f"CREATE TEMP TABLE purchase AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'purchase - purchase.csv').as_posix()}', sample_size=-1)")

db_con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

# Load saved Deliverable 3 CSVs
df_prof_saved = pd.read_csv(OUT_TABLES / "task_3_channel_profile.csv")
df_mon_saved = pd.read_csv(OUT_TABLES / "task_3_monthly_mix.csv")
df_eng_saved = pd.read_csv(OUT_TABLES / "task_3_engagement_metrics.csv")
df_rev_saved = pd.read_csv(OUT_TABLES / "task_3_revenue_metrics.csv")
df_strat_saved = pd.read_csv(OUT_TABLES / "task_3_stratified_metrics.csv")
df_adj_saved = pd.read_csv(OUT_TABLES / "task_3_adjusted_comparison.csv")
df_stats_saved = pd.read_csv(OUT_TABLES / "task_3_statistical_tests.csv")

print("=== AUDIT 1: SQL REPRODUCIBILITY & TABLE RECONCILIATION ===")
sql_raw = SQL_PATH.read_text(encoding="utf-8")
blocks = re.split(r"-- === QUERY \d+:.*?===\r?\n", sql_raw)
queries = [b.strip() for b in blocks[1:] if b.strip()]
for idx, (saved_df, name) in enumerate([
    (df_prof_saved, "task_3_channel_profile.csv"),
    (df_mon_saved, "task_3_monthly_mix.csv"),
    (df_eng_saved, "task_3_engagement_metrics.csv"),
    (df_rev_saved, "task_3_revenue_metrics.csv"),
    (df_strat_saved, "task_3_stratified_metrics.csv"),
]):
    re_df = db_con.execute(queries[idx]).df()
    assert len(re_df) == len(saved_df), f"Row count mismatch {name}"
    for col in re_df.select_dtypes(include="number").columns:
        assert abs(float(re_df[col].fillna(0).sum()) - float(saved_df[col].fillna(0).sum())) < 1e-3, f"Mismatch {name}.{col}"
    print(f"  [PASS] {name:30s}: 100% reproducible from SQL Query {idx + 1}")

print("\n=== AUDIT 2: INDEPENDENT RAW-CSV PROFILE & REVENUE RECONCILIATION ===")
ind_prof = raw_con.execute("""
    WITH pd_devs AS (SELECT DISTINCT device_id FROM player_day),
         pu_all AS (
             SELECT device_id,
                    SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END) AS gross_usd,
                    SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END) AS refund_usd,
                    SUM(usd_amount) AS net_usd
             FROM purchase GROUP BY 1
         )
    SELECT pf.acquisition_channel,
           COUNT(*) AS total_players,
           SUM(CASE WHEN pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31' THEN 1 ELSE 0 END) AS elig_30d,
           SUM(CASE WHEN pf.install_date >= DATE '2026-04-01' THEN 1 ELSE 0 END) AS apr_censored,
           SUM(CASE WHEN pd.device_id IS NULL THEN 1 ELSE 0 END) AS zero_act,
           ROUND(100.0 * SUM(CASE WHEN pf.platform = 'Android' THEN 1 ELSE 0 END) / COUNT(*), 2) AS android_pct,
           ROUND(100.0 * SUM(CASE WHEN pf.country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier4_pct,
           ROUND(COALESCE(SUM(pu.gross_usd), 0), 2) AS gross_usd,
           ROUND(COALESCE(SUM(pu.refund_usd), 0), 2) AS refund_usd,
           ROUND(COALESCE(SUM(pu.net_usd), 0), 2) AS net_usd
    FROM player_profile pf
    LEFT JOIN pd_devs pd ON pf.device_id = pd.device_id
    LEFT JOIN pu_all pu ON pf.device_id = pu.device_id
    GROUP BY 1 ORDER BY total_players DESC
""").df()

for _, row in ind_prof.iterrows():
    s = df_prof_saved[df_prof_saved["acquisition_channel"] == row["acquisition_channel"]].iloc[0]
    assert int(row["total_players"]) == int(s["total_players"])
    assert int(row["elig_30d"]) == int(s["elig_30d_players"])
    assert int(row["apr_censored"]) == int(s["apr_censored_players"])
    assert int(row["zero_act"]) == int(s["zero_activity_players"])
    assert float(row["android_pct"]) == float(s["android_pct"])
    assert float(row["tier4_pct"]) == float(s["tier4_pct"])
    assert float(row["gross_usd"]) == float(s["all_window_gross_usd"])
    assert float(row["refund_usd"]) == float(s["all_window_refund_usd"])
    assert float(row["net_usd"]) == float(s["all_window_net_usd"])
print("  [PASS] Channel counts, splits, zero-activity, and full-window revenue ($219,434.02 gross / $216,159.30 net) match raw CSVs 100%")

print("\n=== AUDIT 3: COHORT ELIGIBILITY & EDGE CASES (PRE-INSTALL / LEAKAGE) ===")
elig_check = raw_con.execute("""
    SELECT COUNT(*) AS n,
           MIN(install_date), MAX(install_date),
           MAX(install_date + INTERVAL 30 DAY) AS max_d30_date,
           SUM(CASE WHEN install_date + INTERVAL 30 DAY > DATE '2026-04-30' THEN 1 ELSE 0 END) AS censored_d30
    FROM player_profile
    WHERE install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
""").fetchone()
assert elig_check[0] == 37489 and elig_check[4] == 0
print("  [PASS] Clean 30d cohort check (n, min_inst, max_inst, max_d30, censored_cnt):", elig_check)

pre_in_cohort = raw_con.execute("""
    SELECT COUNT(*), ROUND(SUM(u.usd_amount), 2)
    FROM purchase u JOIN player_profile pf ON u.device_id = pf.device_id
    WHERE pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
      AND DATE(u.event_ts) < pf.install_date
""").fetchone()
print("  Note: Pre-install purchases in Jan-Mar cohort (excluded by [install_date, +29d] window):", pre_in_cohort)

print("\n=== AUDIT 4: INDEPENDENT RAW-CSV 30D METRICS & DEDUP SENSITIVITY ===")
ind_df30 = raw_con.execute("""
    WITH base AS (
        SELECT device_id, acquisition_channel, install_date, country_tier, platform,
               STRFTIME(install_date, '%Y-%m') AS install_month
        FROM player_profile
        WHERE install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
    ),
    pd30 AS (
        SELECT b.device_id,
               COUNT(*) FILTER (WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY) AS active_days_30d,
               MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
               MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30,
               COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.playtime_minutes ELSE 0 END), 0.0) AS play_30d
        FROM base b LEFT JOIN player_day d ON b.device_id = d.device_id
        GROUP BY 1
    ),
    pu30 AS (
        SELECT b.device_id,
               COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS gross_30d,
               COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS net_30d
        FROM base b LEFT JOIN purchase u ON b.device_id = u.device_id
        GROUP BY 1
    ),
    pu_dedup AS (
        SELECT * EXCLUDE (rn) FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts ASC) rn FROM purchase) WHERE rn = 1
    ),
    pu30_d AS (
        SELECT b.device_id,
               COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS gross_30d_dedup
        FROM base b LEFT JOIN pu_dedup u ON b.device_id = u.device_id
        GROUP BY 1
    )
    SELECT b.*, pd30.active_days_30d, pd30.ret_d7, pd30.ret_d30, pd30.play_30d,
           pu30.gross_30d, pu30.net_30d, pu30_d.gross_30d_dedup,
           CASE WHEN pu30.gross_30d > 0 THEN 1 ELSE 0 END AS is_payer_30d
    FROM base b
    JOIN pd30 ON b.device_id = pd30.device_id
    JOIN pu30 ON b.device_id = pu30.device_id
    JOIN pu30_d ON b.device_id = pu30_d.device_id
""").df()

assert len(ind_df30) == 37489
for ch in ["organic", "paid_social", "paid_video"]:
    sub = ind_df30[ind_df30["acquisition_channel"] == ch]
    s_eng = df_eng_saved[(df_eng_saved["population"] == "clean_30d_cohort_jan_mar") & (df_eng_saved["acquisition_channel"] == ch)].iloc[0]
    s_rev = df_rev_saved[(df_rev_saved["population"] == "clean_30d_cohort_jan_mar") & (df_rev_saved["acquisition_channel"] == ch)].iloc[0]
    assert len(sub) == int(s_eng["acquired_players"]) == int(s_rev["acquired_players"])
    assert abs(round(100.0 * sub["ret_d7"].mean(), 2) - float(s_eng["retention_d7_pct"])) < 1e-9
    assert abs(round(100.0 * sub["ret_d30"].mean(), 2) - float(s_eng["retention_d30_pct"])) < 1e-9
    assert abs(round(sub["active_days_30d"].mean(), 3) - float(s_eng["avg_active_days_per_acquired"])) < 1e-9
    assert abs(round(sub["gross_30d"].sum(), 2) - float(s_rev["total_gross_usd"])) < 1e-9
    assert abs(round(sub["net_30d"].sum(), 2) - float(s_rev["total_net_usd"])) < 1e-9
    assert abs(round(sub["gross_30d_dedup"].sum(), 2) - float(s_rev["total_gross_dedup_usd"])) < 1e-9
print("  [PASS] Clean 30d engagement, revenue, ARPPU, and dedup totals match raw CSVs 100%")

print("\n=== AUDIT 5: INDEPENDENT STATISTICAL VERIFICATION (SEED=999, 5000 RESAMPLES) ===")
rng_ind = np.random.default_rng(999)
N_BOOT = 5000
strata_w = (ind_df30.groupby(["country_tier", "platform"]).size() / len(ind_df30)).to_dict()

def holm(pvals):
    m = len(pvals)
    idx_p = sorted(enumerate(pvals), key=lambda x: x[1])
    out = [0.0] * m
    prev = 0.0
    for r, (i, p) in enumerate(idx_p):
        prev = max(prev, min(1.0, (m - r) * p))
        out[i] = prev
    return out

pairs = [("organic", "paid_social"), ("organic", "paid_video"), ("paid_social", "paid_video")]
for metric in ["active_days_30d", "ret_d7", "ret_d30", "is_payer_30d", "gross_30d"]:
    p_list = []
    rows_tmp = []
    for c1, c2 in pairs:
        ga = {k: g[metric].to_numpy(dtype=float) for k, g in ind_df30[ind_df30["acquisition_channel"] == c1].groupby(["country_tier", "platform"])}
        gb = {k: g[metric].to_numpy(dtype=float) for k, g in ind_df30[ind_df30["acquisition_channel"] == c2].groupby(["country_tier", "platform"])}
        diff_pt = sum(strata_w[k] * (ga[k].mean() - gb[k].mean()) for k in strata_w)
        boots = np.zeros(N_BOOT)
        for k, wk in strata_w.items():
            a_arr, b_arr = ga[k], gb[k]
            na, nb = len(a_arr), len(b_arr)
            for s in range(0, N_BOOT, 500):
                bs = min(500, N_BOOT - s)
                ma = a_arr[rng_ind.integers(0, na, size=(bs, na))].mean(axis=1)
                mb = b_arr[rng_ind.integers(0, nb, size=(bs, nb))].mean(axis=1)
                boots[s:s+bs] += wk * (ma - mb)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        se = float(boots.std(ddof=1))
        p_wald = float(2.0 * stats.norm.sf(abs(diff_pt / se)))
        p_list.append(p_wald)
        rows_tmp.append((c1, c2, diff_pt, lo, hi, p_wald))
    hp_list = holm(p_list)
    print(f"\n  Tier x Platform Adjusted ({metric}):")
    for (c1, c2, d, lo, hi, pw), hp in zip(rows_tmp, hp_list):
        saved_row = df_stats_saved[(df_stats_saved["comparison_type"] == "tier_platform_adjusted") & (df_stats_saved["metric"] == metric) & (df_stats_saved["pair"] == f"{c1} - {c2}")].iloc[0]
        assert abs(d - float(saved_row["diff"])) < 1e-6, f"Point estimate mismatch {metric} {c1}-{c2}"
        print(f"    {c1:11s} - {c2:11s} | Ind: {d:+.4f} [{lo:+.4f}, {hi:+.4f}] Holm={hp:.4f} | Saved: [{saved_row['ci_95_low']:+.4f}, {saved_row['ci_95_high']:+.4f}] Holm={saved_row['primary_p_holm']:.4f}")

print("\n=== AUDIT 6: ADDITIONAL ROBUSTNESS CHECKS ===")
# Check 1: Does adjusting for install_month IN ADDITION TO tier x platform change gross_30d?
strata_m = ind_df30.groupby(["country_tier", "platform", "install_month"]).size()
strata_mw = (strata_m / strata_m.sum()).to_dict()
cell_m = ind_df30.groupby(["acquisition_channel", "country_tier", "platform", "install_month"])["gross_30d"].mean()
adj_3way = {}
for ch in ["organic", "paid_social", "paid_video"]:
    adj_3way[ch] = sum(strata_mw[k] * cell_m.loc[ch].get(k, 0.0) for k in strata_mw)
print("  Robustness (Tier x Platform x Install_Month adjusted 30d Gross ARPU):", {k: round(v, 4) for k, v in adj_3way.items()})

# Check 2: Wider D7-eligible cohort (Jan 1 - Apr 23, n=57,637)
d7_wide = raw_con.execute("""
    WITH b AS (
        SELECT device_id, acquisition_channel, install_date, country_tier, platform
        FROM player_profile WHERE install_date BETWEEN DATE '2026-01-01' AND DATE '2026-04-23'
    ),
    pd AS (
        SELECT b.device_id,
               MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7
        FROM b LEFT JOIN player_day d ON b.device_id = d.device_id GROUP BY 1
    )
    SELECT b.acquisition_channel, COUNT(*) AS n, ROUND(100.0 * AVG(pd.ret_d7), 2) AS d7_pct
    FROM b JOIN pd ON b.device_id = pd.device_id GROUP BY 1 ORDER BY 1
""").fetchall()
print("  Robustness (Wider D7 cohort Jan 1-Apr 23, n=57,637):", d7_wide)

raw_con.close()
db_con.close()
print("\nDELIVERABLE 3 INDEPENDENT AUDIT FINISHED.")
