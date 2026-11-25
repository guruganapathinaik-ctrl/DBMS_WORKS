"""Deliverable 3: Acquisition Channel Quality & Statistical Analysis.

Executes sql/task_3_acquisition_analysis.sql against outputs/telemetry.duckdb,
computes unadjusted and (country_tier x platform) stratified bootstrap 95% CIs,
Welch t-tests, Mann-Whitney U tests, two-proportion Z-tests, Holm-Bonferroni
corrections, effect sizes, reconciles revenue totals, and generates 4 charts.
"""

import re
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

DB_PATH = Path("outputs/telemetry.duckdb")
SQL_PATH = Path("sql/task_3_acquisition_analysis.sql")
OUT_TABLES = Path("outputs/tables")
OUT_CHARTS = Path("outputs/charts")
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")

sql_raw = SQL_PATH.read_text(encoding="utf-8")
blocks = re.split(r"-- === QUERY \d+:.*?===\r?\n", sql_raw)
queries = [b.strip() for b in blocks[1:] if b.strip()]
assert len(queries) == 6, f"Expected 6 SQL blocks, found {len(queries)}"

con = duckdb.connect(str(DB_PATH), read_only=True)
df_profile = con.execute(queries[0]).df()
df_monthly = con.execute(queries[1]).df()
df_engage = con.execute(queries[2]).df()
df_rev = con.execute(queries[3]).df()
df_strat = con.execute(queries[4]).df()
df30 = con.execute(queries[5]).df()
con.close()

# Save SQL-derived tables
df_profile.to_csv(OUT_TABLES / "task_3_channel_profile.csv", index=False)
df_monthly.to_csv(OUT_TABLES / "task_3_monthly_mix.csv", index=False)
df_engage.to_csv(OUT_TABLES / "task_3_engagement_metrics.csv", index=False)
df_rev.to_csv(OUT_TABLES / "task_3_revenue_metrics.csv", index=False)
df_strat.to_csv(OUT_TABLES / "task_3_stratified_metrics.csv", index=False)

# ---------------------------------------------------------------------------
# 1. Reconciliation Checks
# ---------------------------------------------------------------------------
assert int(df_profile["total_players"].sum()) == 80295
assert round(float(df_profile["all_window_gross_usd"].sum()), 2) == 219434.02
assert round(float(df_profile["all_window_refund_usd"].sum()), 2) == -3274.72
assert round(float(df_profile["all_window_net_usd"].sum()), 2) == 216159.30
assert len(df30) == 37489, f"Expected 37,489 30d-eligible players, got {len(df30)}"
assert int(df_engage[df_engage["population"] == "clean_30d_cohort_jan_mar"]["acquired_players"].sum()) == 37489
assert int(df_rev[df_rev["population"] == "all_80295_full_window"]["acquired_players"].sum()) == 80295
assert round(float(df_rev[df_rev["population"] == "all_80295_full_window"]["total_gross_usd"].sum()), 2) == 219434.02
assert round(float(df_rev[df_rev["population"] == "all_80295_full_window"]["total_net_usd"].sum()), 2) == 216159.30
print("[PASS] All player counts and purchase revenue totals reconciled to 100% precision.")

# ---------------------------------------------------------------------------
# 2. Pairwise Statistical Tests & Bootstrap CIs (Unadjusted & Adjusted)
# ---------------------------------------------------------------------------
rng = np.random.default_rng(2026)
N_BOOT = 4000
CHANNELS = ["organic", "paid_social", "paid_video"]
PAIRS = [("organic", "paid_social"), ("organic", "paid_video"), ("paid_social", "paid_video")]

METRICS = [
    ("active_days_30d", "Active Days (First 30d)", "continuous"),
    ("ret_d7", "Day 7 Retention Rate", "binary"),
    ("ret_d30", "Day 30 Retention Rate", "binary"),
    ("play_30d", "Playtime Mins (First 30d)", "continuous"),
    ("is_payer_30d", "30-Day Payer Conversion", "binary"),
    ("gross_30d", "30-Day Gross ARPU ($)", "skewed_revenue"),
    ("net_30d", "30-Day Net ARPU ($)", "skewed_revenue"),
]

# Precompute strata weights (country_tier x platform) on full 30d cohort
strata_counts = df30.groupby(["country_tier", "platform"]).size()
strata_w = (strata_counts / strata_counts.sum()).to_dict()


def holm_adjust(pvals: list[float]) -> list[float]:
    """Apply Holm-Bonferroni step-down multiple-testing correction."""
    m = len(pvals)
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    adj = [0.0] * m
    prev_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        val = min(1.0, (m - rank) * p)
        prev_max = max(prev_max, val)
        adj[orig_idx] = prev_max
    return adj


def two_prop_ztest(a: np.ndarray, b: np.ndarray) -> float:
    p_pool = (a.sum() + b.sum()) / (len(a) + len(b))
    se = np.sqrt(p_pool * (1 - p_pool) * (1.0 / len(a) + 1.0 / len(b)))
    if se == 0:
        return 1.0
    z = (a.mean() - b.mean()) / se
    return float(2.0 * stats.norm.sf(abs(z)))


# Adjusted channel means table
adj_rows = []
for m_col, m_label, m_type in METRICS:
    unadj_means = df30.groupby("acquisition_channel")[m_col].mean().to_dict()
    cell_means = df30.groupby(["acquisition_channel", "country_tier", "platform"])[m_col].mean()
    adj_means = {ch: float((cell_means.loc[ch] * pd.Series(strata_w)).sum()) for ch in CHANNELS}
    for ch in CHANNELS:
        adj_rows.append({
            "metric": m_col,
            "metric_label": m_label,
            "acquisition_channel": ch,
            "unadjusted_mean": round(float(unadj_means[ch]), 6),
            "tier_platform_adjusted_mean": round(adj_means[ch], 6),
        })
df_adj = pd.DataFrame(adj_rows)
df_adj.to_csv(OUT_TABLES / "task_3_adjusted_comparison.csv", index=False)

# Pairwise Statistical Tests (both Unadjusted and Tier x Platform Adjusted)
stat_rows = []
for m_col, m_label, m_type in METRICS:
    # Unadjusted
    raw_p_primary = []
    temp_unadj = []
    for c1, c2 in PAIRS:
        a = df30.loc[df30["acquisition_channel"] == c1, m_col].to_numpy(dtype=float)
        b = df30.loc[df30["acquisition_channel"] == c2, m_col].to_numpy(dtype=float)
        diff = float(a.mean() - b.mean())
        rel_pct = round(100.0 * diff / b.mean(), 2) if b.mean() != 0 else np.nan
        # Vectorized bootstrap in batches to keep memory low
        boot_diffs = np.empty(N_BOOT)
        na, nb = len(a), len(b)
        for start in range(0, N_BOOT, 500):
            bs = min(500, N_BOOT - start)
            sa = a[rng.integers(0, na, size=(bs, na))].mean(axis=1)
            sb = b[rng.integers(0, nb, size=(bs, nb))].mean(axis=1)
            boot_diffs[start:start + bs] = sa - sb
        ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])
        _, p_welch = stats.ttest_ind(a, b, equal_var=False)
        _, p_mwu = stats.mannwhitneyu(a, b, alternative="two-sided")
        p_prop = two_prop_ztest(a, b) if m_type == "binary" else np.nan
        # Cohen's d
        pooled_sd = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
        cohens_d = float(diff / pooled_sd) if pooled_sd > 0 else 0.0

        # Choose primary parametric/non-parametric p-value for Holm correction
        p_primary = float(p_prop) if m_type == "binary" else float(p_welch)
        raw_p_primary.append(p_primary)
        temp_unadj.append({
            "comparison_type": "unadjusted",
            "metric": m_col,
            "metric_label": m_label,
            "pair": f"{c1} - {c2}",
            "mean_a": round(float(a.mean()), 6),
            "mean_b": round(float(b.mean()), 6),
            "diff": round(diff, 6),
            "ci_95_low": round(float(ci_lo), 6),
            "ci_95_high": round(float(ci_hi), 6),
            "rel_diff_pct": rel_pct,
            "cohens_d": round(cohens_d, 4),
            "primary_p_raw": p_primary,
            "welch_p": round(float(p_welch), 8),
            "mwu_p": round(float(p_mwu), 8),
            "two_prop_z_p": round(float(p_prop), 8) if not np.isnan(p_prop) else np.nan,
        })
    holm_u = holm_adjust(raw_p_primary)
    for row, hp in zip(temp_unadj, holm_u):
        row["primary_p_holm"] = round(hp, 8)
        row["sig_holm_0_05"] = bool(hp < 0.05)
        row["ci_excludes_zero"] = bool((row["ci_95_low"] > 0) or (row["ci_95_high"] < 0))
        stat_rows.append(row)

    # Tier x Platform Adjusted (Direct Standardization Bootstrap)
    raw_p_adj = []
    temp_adj = []
    for c1, c2 in PAIRS:
        ga_dict = {k: g[m_col].to_numpy(dtype=float) for k, g in df30[df30["acquisition_channel"] == c1].groupby(["country_tier", "platform"])}
        gb_dict = {k: g[m_col].to_numpy(dtype=float) for k, g in df30[df30["acquisition_channel"] == c2].groupby(["country_tier", "platform"])}
        mean_a = sum(strata_w[k] * ga_dict[k].mean() for k in strata_w)
        mean_b = sum(strata_w[k] * gb_dict[k].mean() for k in strata_w)
        diff_adj = float(mean_a - mean_b)
        rel_pct = round(100.0 * diff_adj / mean_b, 2) if mean_b != 0 else np.nan

        boot_diffs = np.zeros(N_BOOT)
        for k, wk in strata_w.items():
            ga, gb = ga_dict[k], gb_dict[k]
            na, nb = len(ga), len(gb)
            for start in range(0, N_BOOT, 500):
                bs = min(500, N_BOOT - start)
                ma = ga[rng.integers(0, na, size=(bs, na))].mean(axis=1)
                mb = gb[rng.integers(0, nb, size=(bs, nb))].mean(axis=1)
                boot_diffs[start:start + bs] += wk * (ma - mb)
        ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])
        se_boot = float(boot_diffs.std(ddof=1))
        p_boot = float(2.0 * min((boot_diffs <= 0).mean(), (boot_diffs >= 0).mean()))
        p_wald = float(2.0 * stats.norm.sf(abs(diff_adj / se_boot))) if se_boot > 0 else 1.0
        raw_p_adj.append(p_wald)
        temp_adj.append({
            "comparison_type": "tier_platform_adjusted",
            "metric": m_col,
            "metric_label": m_label,
            "pair": f"{c1} - {c2}",
            "mean_a": round(float(mean_a), 6),
            "mean_b": round(float(mean_b), 6),
            "diff": round(diff_adj, 6),
            "ci_95_low": round(float(ci_lo), 6),
            "ci_95_high": round(float(ci_hi), 6),
            "rel_diff_pct": rel_pct,
            "cohens_d": np.nan,
            "primary_p_raw": round(p_wald, 8),
            "welch_p": np.nan,
            "mwu_p": np.nan,
            "two_prop_z_p": round(p_boot, 8),
        })
    holm_a = holm_adjust(raw_p_adj)
    for row, hp in zip(temp_adj, holm_a):
        row["primary_p_holm"] = round(hp, 8)
        row["sig_holm_0_05"] = bool(hp < 0.05)
        row["ci_excludes_zero"] = bool((row["ci_95_low"] > 0) or (row["ci_95_high"] < 0))
        stat_rows.append(row)

df_stats = pd.DataFrame(stat_rows)
df_stats.to_csv(OUT_TABLES / "task_3_statistical_tests.csv", index=False)

print("\n=== HEADLINE STATISTICAL TESTS (CLEAN 30D COHORT, N=37,489) ===")
cols_show = ["comparison_type", "metric", "pair", "diff", "ci_95_low", "ci_95_high", "primary_p_holm", "sig_holm_0_05"]
print(df_stats[df_stats["metric"].isin(["active_days_30d", "ret_d7", "ret_d30", "is_payer_30d", "gross_30d"])][cols_show].to_string(index=False))

# ---------------------------------------------------------------------------
# 3. Generate 4 Charts (from small aggregated DataFrames only)
# ---------------------------------------------------------------------------
ch_colors = {"organic": "#2ca02c", "paid_social": "#1f77b4", "paid_video": "#ff7f0e"}

# CHART 1: task_3_channel_mix.png (Confounding Factors: Installs Over Time & Tier/Platform Mix)
fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))

# Panel A: Monthly Installs by Channel
piv_m = df_monthly.pivot(index="install_month", columns="acquisition_channel", values="installs").fillna(0)
piv_m = piv_m[["organic", "paid_social", "paid_video"]]
x_m = np.arange(len(piv_m))
w_m = 0.26
for idx, ch in enumerate(["organic", "paid_social", "paid_video"]):
    axes[0].bar(x_m + (idx - 1) * w_m, piv_m[ch].values, width=w_m, label=ch, color=ch_colors[ch])
axes[0].set_xticks(x_m)
axes[0].set_xticklabels(piv_m.index, rotation=20)
axes[0].set_ylabel("Installed Players")
axes[0].set_title("Install Volume by Channel & Month\n(Paid Video Surged 12.5x in Mar-Apr)", fontweight="bold")
axes[0].legend()

# Panel B: Confounder Shares (Tier 4 % and Android %) across Channels (All 80,295)
prof_ord = df_profile.set_index("acquisition_channel").loc[["organic", "paid_social", "paid_video"]]
x_c = np.arange(3)
w_c = 0.34
b_t4 = axes[1].bar(x_c - w_c / 2, prof_ord["tier4_pct"].values, width=w_c, label="Tier 4 Share (%)", color="#9467bd")
b_an = axes[1].bar(x_c + w_c / 2, prof_ord["android_pct"].values, width=w_c, label="Android Share (%)", color="#8c564b")
axes[1].set_xticks(x_c)
axes[1].set_xticklabels(["organic", "paid_social", "paid_video"])
axes[1].set_ylim(0, 100)
axes[1].set_ylabel("Share of Channel Players (%)")
axes[1].set_title("Severe Demographic Confounding Across Channels\n(Paid Video Is Heavily Tier 4 & Android)", fontweight="bold")
axes[1].legend()
for bar in list(b_t4) + list(b_an):
    h = bar.get_height()
    axes[1].text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=9)

fig.suptitle("Deliverable 3: Acquisition Channel Composition & Confounding Factors", fontsize=13.5, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_3_channel_mix.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 2: task_3_engagement_comparison.png (Unadjusted vs Adjusted Engagement)
fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
eng_panels = [
    ("active_days_30d", "Active Days in First 30d\n(Organic +3% Higher)", "Active Days"),
    ("ret_d7", "Day 7 Retention Rate\n(Share Active Day 7)", "Rate (0-1)"),
    ("ret_d30", "Day 30 Retention Rate\n(Share Active Day 30)", "Rate (0-1)"),
]
for ax, (m_col, title, ylab) in zip(axes, eng_panels):
    sub = df_adj[df_adj["metric"] == m_col].set_index("acquisition_channel").loc[["organic", "paid_social", "paid_video"]]
    x_e = np.arange(3)
    w_e = 0.35
    b1 = ax.bar(x_e - w_e / 2, sub["unadjusted_mean"], width=w_e, label="Unadjusted (30d Cohort)", color="#4e79a7")
    b2 = ax.bar(x_e + w_e / 2, sub["tier_platform_adjusted_mean"], width=w_e, label="Tier x Platform Adjusted", color="#59a14f")
    ax.set_xticks(x_e)
    ax.set_xticklabels(["organic", "paid_social", "paid_video"])
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel(ylab)
    top_v = max(sub["unadjusted_mean"].max(), sub["tier_platform_adjusted_mean"].max())
    ax.set_ylim(0, top_v * 1.25)
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        lbl = f"{h:.2f}" if m_col == "active_days_30d" else f"{100*h:.1f}%"
        ax.text(bar.get_x() + bar.get_width() / 2, h + top_v * 0.02, lbl, ha="center", va="bottom", fontsize=8)
axes[0].legend(loc="lower right", fontsize=8)
fig.suptitle("Deliverable 3: 30-Day Engagement Comparison (Jan-Mar Eligible Cohort, n=37,489)", fontsize=13.5, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_3_engagement_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 3: task_3_revenue_comparison.png (Artefact Exposed: Unadjusted vs Tier-Stratified & Adjusted ARPU)
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))

# Panel A: Unadjusted vs Adjusted 30d Gross ARPU
sub_rev = df_adj[df_adj["metric"] == "gross_30d"].set_index("acquisition_channel").loc[["organic", "paid_social", "paid_video"]]
x_r = np.arange(3)
w_r = 0.35
b_u = axes[0].bar(x_r - w_r / 2, sub_rev["unadjusted_mean"], width=w_r, label="Unadjusted 30d ARPU ($)", color="#e15759")
b_a = axes[0].bar(x_r + w_r / 2, sub_rev["tier_platform_adjusted_mean"], width=w_r, label="Tier x Platform Adjusted ($)", color="#59a14f")
axes[0].set_xticks(x_r)
axes[0].set_xticklabels(["organic", "paid_social", "paid_video"])
axes[0].set_ylabel("30-Day Gross ARPU ($)")
axes[0].set_ylim(0, 3.0)
axes[0].set_title("Unadjusted vs. Adjusted 30-Day Gross ARPU\n(Paid Video Deficit Shrinks 88% After Adjustment)", fontweight="bold")
axes[0].legend()
for bar in list(b_u) + list(b_a):
    h = bar.get_height()
    axes[0].text(bar.get_x() + bar.get_width() / 2, h + 0.05, f"${h:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

# Panel B: 30d Gross ARPU Within Each Country Tier
tier_arpu = df30.groupby(["country_tier", "acquisition_channel"])["gross_30d"].mean().unstack()
tier_arpu = tier_arpu[["organic", "paid_social", "paid_video"]]
x_t = np.arange(4)
w_t = 0.26
for idx, ch in enumerate(["organic", "paid_social", "paid_video"]):
    bars = axes[1].bar(x_t + (idx - 1) * w_t, tier_arpu[ch].values, width=w_t, label=ch, color=ch_colors[ch])
    for bar in bars:
        h = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2, h + 0.06, f"${h:.2f}", ha="center", va="bottom", fontsize=7.5)
axes[1].set_xticks(x_t)
axes[1].set_xticklabels(["Tier 1", "Tier 2", "Tier 3", "Tier 4"])
axes[1].set_ylim(0, 4.4)
axes[1].set_ylabel("30-Day Gross ARPU ($)")
axes[1].set_title("30-Day Gross ARPU Inside Each Country Tier\n(Channels Perform Similarly Within Every Tier)", fontweight="bold")
axes[1].legend()

fig.suptitle("Deliverable 3: Revenue Comparison — Separating True Quality from Mix Artefacts", fontsize=13.5, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_3_revenue_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 4: task_3_confidence_intervals.png (Pairwise 95% Bootstrap CIs: Unadjusted vs Adjusted)
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Panel A: Active Days 30d Pairwise Differences (95% CI)
# Panel B: Gross 30d ARPU Pairwise Differences (95% CI)
for ax, m_col, xlabel, title in [
    (axes[0], "active_days_30d", "Difference in Active Days (30d)", "Engagement: Active Days (30d) Pairwise 95% CIs"),
    (axes[1], "gross_30d", "Difference in 30d Gross ARPU ($)", "Revenue: 30d Gross ARPU Pairwise 95% CIs"),
]:
    sub_s = df_stats[df_stats["metric"] == m_col].copy()
    sub_s["label"] = sub_s["pair"] + "\n(" + sub_s["comparison_type"].map({"unadjusted": "Unadjusted", "tier_platform_adjusted": "Tier x Plat Adj."}) + ")"
    sub_s = sub_s.iloc[::-1].reset_index(drop=True)
    y_pos = np.arange(len(sub_s))
    for i, row in sub_s.iterrows():
        col = "#2ca02c" if row["sig_holm_0_05"] else "#7f7f7f"
        ax.errorbar(
            row["diff"], i,
            xerr=[[row["diff"] - row["ci_95_low"]], [row["ci_95_high"] - row["diff"]]],
            fmt="o", color=col, ecolor=col, elinewidth=2.2, capsize=4, markersize=7
        )
        sig_txt = "Sig (Holm p<0.05)" if row["sig_holm_0_05"] else "Not Sig"
        ax.text(row["ci_95_high"] + (0.01 if m_col == "active_days_30d" else 0.03), i,
                f"{row['diff']:+.3f} ({sig_txt})", va="center", fontsize=8, color=col)
    ax.axvline(0, color="#d62728", linestyle="--", linewidth=1.2)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sub_s["label"], fontsize=8.5)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontweight="bold")
    xlim_lo, xlim_hi = ax.get_xlim()
    ax.set_xlim(xlim_lo - 0.05, xlim_hi + (0.28 if m_col == "active_days_30d" else 0.90))

fig.suptitle("Deliverable 3: 95% Bootstrap Confidence Intervals (Green = Significant After Holm Correction; Grey = Crosses 0)", fontsize=12.5, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_3_confidence_intervals.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print("\nAll Deliverable 3 CSVs and charts generated successfully.")
