"""Phase 3.4 Statistical Check: Stratified adjustments, Bootstrap CIs, and Hypothesis Tests."""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

# Materialize player-level 30d dataset for clean equal-window cohort (installs 2026-01-01..2026-03-31)
# Note: 37,489 players (small enough for fast numpy bootstrap, computed cleanly in DuckDB first!)
df30 = con.execute("""
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
               COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.playtime_minutes ELSE 0 END), 0.0) AS play_30d,
               COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.session_count ELSE 0 END), 0) AS sess_30d
        FROM base b LEFT JOIN player_day d ON b.device_id = d.device_id
        GROUP BY 1
    ),
    pu30 AS (
        SELECT b.device_id,
               COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS gross_30d,
               COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS net_30d
        FROM base b LEFT JOIN purchase u ON b.device_id = u.device_id
        GROUP BY 1
    )
    SELECT b.*, pd30.active_days_30d, pd30.ret_d7, pd30.ret_d30, pd30.play_30d, pd30.sess_30d,
           pu30.gross_30d, pu30.net_30d,
           CASE WHEN pu30.gross_30d > 0 THEN 1 ELSE 0 END AS is_payer_30d
    FROM base b
    JOIN pd30 ON b.device_id = pd30.device_id
    JOIN pu30 ON b.device_id = pu30.device_id
""").df()

print("Clean 30d-eligible cohort size:", len(df30))
print(df30.groupby("acquisition_channel")[["ret_d7", "ret_d30", "active_days_30d", "play_30d", "is_payer_30d", "gross_30d", "net_30d"]].mean())

# Check stratified means across (country_tier x platform) using overall cohort weights (Direct Standardization)
print("\n=== DIRECT STANDARDIZATION (Adjusted for country_tier x platform) ===")
strata_weights = df30.groupby(["country_tier", "platform"]).size() / len(df30)
for metric in ["active_days_30d", "ret_d7", "ret_d30", "play_30d", "is_payer_30d", "gross_30d", "net_30d"]:
    cell_means = df30.groupby(["acquisition_channel", "country_tier", "platform"])[metric].mean()
    adj = {}
    for ch in ["organic", "paid_social", "paid_video"]:
        adj[ch] = float((cell_means.loc[ch] * strata_weights).sum())
    print(f"  {metric:16s} -> organic={adj['organic']:.4f}, paid_social={adj['paid_social']:.4f}, paid_video={adj['paid_video']:.4f}")

# Pairwise Bootstrap CIs (Unadjusted AND Tier*Platform Adjusted!)
rng = np.random.default_rng(42)
N_BOOT = 2000

def boot_unadj(a, b):
    diffs = np.empty(N_BOOT)
    na, nb = len(a), len(b)
    for i in range(N_BOOT):
        sa = a[rng.integers(0, na, na)]
        sb = b[rng.integers(0, nb, nb)]
        diffs[i] = sa.mean() - sb.mean()
    return float(a.mean() - b.mean()), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))

def boot_adj(df, ch_a, ch_b, col):
    strata = df.groupby(["country_tier", "platform"]).size()
    w = (strata / strata.sum()).to_dict()
    groups_a = {k: g[col].to_numpy() for k, g in df[df["acquisition_channel"] == ch_a].groupby(["country_tier", "platform"])}
    groups_b = {k: g[col].to_numpy() for k, g in df[df["acquisition_channel"] == ch_b].groupby(["country_tier", "platform"])}
    pt = sum(w[k] * (groups_a[k].mean() - groups_b[k].mean()) for k in w)
    diffs = np.zeros(N_BOOT)
    for k, wk in w.items():
        ga, gb = groups_a[k], groups_b[k]
        na, nb = len(ga), len(gb)
        ma = ga[rng.integers(0, na, (N_BOOT, na))].mean(axis=1)
        mb = gb[rng.integers(0, nb, (N_BOOT, nb))].mean(axis=1)
        diffs += wk * (ma - mb)
    return float(pt), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float(2 * min((diffs <= 0).mean(), (diffs >= 0).mean()))

pairs = [("organic", "paid_social"), ("organic", "paid_video"), ("paid_social", "paid_video")]
print("\n=== PAIRWISE TESTS (UNADJUSTED) ===")
for m in ["active_days_30d", "ret_d7", "ret_d30", "play_30d", "is_payer_30d", "gross_30d"]:
    print(f"\nMetric: {m}")
    for c1, c2 in pairs:
        a = df30.loc[df30["acquisition_channel"] == c1, m].to_numpy()
        b = df30.loc[df30["acquisition_channel"] == c2, m].to_numpy()
        diff, lo, hi = boot_unadj(a, b)
        t_stat, p_welch = stats.ttest_ind(a, b, equal_var=False)
        u_stat, p_mwu = stats.mannwhitneyu(a, b, alternative="two-sided")
        print(f"  {c1:11s} - {c2:11s}: diff={diff:+.4f}, 95%CI=[{lo:+.4f}, {hi:+.4f}], Welch p={p_welch:.4g}, MWU p={p_mwu:.4g}")

print("\n=== PAIRWISE TESTS (TIER x PLATFORM ADJUSTED) ===")
for m in ["active_days_30d", "ret_d7", "ret_d30", "play_30d", "is_payer_30d", "gross_30d"]:
    print(f"\nAdjusted Metric: {m}")
    for c1, c2 in pairs:
        diff, lo, hi, p_boot = boot_adj(df30, c1, c2, m)
        print(f"  {c1:11s} - {c2:11s}: adj_diff={diff:+.4f}, 95%CI=[{lo:+.4f}, {hi:+.4f}], boot_p={p_boot:.4g}")

con.close()
