"""Deliverable 2 (Option A): Simpson's Paradox & ARPDAU Deep Dive.

Executes all queries in sql/task_2_arpdau_deep_dive.sql against outputs/telemetry.duckdb,
performs exact mathematical decomposition (Kitagawa 3-term & symmetric 2-term + counterfactual),
validates full reconciliation, saves 4 CSV tables and 4 charts.
"""

import re
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns

DB_PATH = Path("outputs/telemetry.duckdb")
SQL_PATH = Path("sql/task_2_arpdau_deep_dive.sql")
OUT_TABLES = Path("outputs/tables")
OUT_CHARTS = Path("outputs/charts")
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")

# Parse SQL blocks from sql/task_2_arpdau_deep_dive.sql
sql_raw = SQL_PATH.read_text(encoding="utf-8")
blocks = re.split(r"-- === QUERY \d+:.*?===\r?\n", sql_raw)
queries = [b.strip() for b in blocks[1:] if b.strip()]
assert len(queries) == 4, f"Expected 4 queries in SQL file, found {len(queries)}"

con = duckdb.connect(str(DB_PATH), read_only=True)
df_period = con.execute(queries[0]).df()
df_tier = con.execute(queries[1]).df()
df_mix = con.execute(queries[2]).df()
df_daily_tier = con.execute(queries[3]).df()
con.close()

# ---------------------------------------------------------------------------
# 1. Enrich task_2_period_comparison.csv with Period Change Row
# ---------------------------------------------------------------------------
p1 = df_period[df_period["period"] == "first_30d"].iloc[0]
p2 = df_period[df_period["period"] == "last_30d"].iloc[0]

pct_row = {
    "period": "pct_change_p1_to_p2",
    "start_date": p1["start_date"],
    "end_date": p2["end_date"],
    "num_days": 0,
    "total_active_player_days": round(100.0 * (p2["total_active_player_days"] - p1["total_active_player_days"]) / p1["total_active_player_days"], 2),
    "unique_active_players": round(100.0 * (p2["unique_active_players"] - p1["unique_active_players"]) / p1["unique_active_players"], 2),
    "total_gross_revenue_usd": round(100.0 * (p2["total_gross_revenue_usd"] - p1["total_gross_revenue_usd"]) / p1["total_gross_revenue_usd"], 2),
    "total_refund_usd": round(100.0 * (p2["total_refund_usd"] - p1["total_refund_usd"]) / p1["total_refund_usd"], 2),
    "total_net_revenue_usd": round(100.0 * (p2["total_net_revenue_usd"] - p1["total_net_revenue_usd"]) / p1["total_net_revenue_usd"], 2),
    "gross_dedup_usd": round(100.0 * (p2["gross_dedup_usd"] - p1["gross_dedup_usd"]) / p1["gross_dedup_usd"], 2),
    "net_dedup_usd": round(100.0 * (p2["net_dedup_usd"] - p1["net_dedup_usd"]) / p1["net_dedup_usd"], 2),
    "weighted_gross_arpdau_usd": round(100.0 * (p2["weighted_gross_arpdau_usd"] - p1["weighted_gross_arpdau_usd"]) / p1["weighted_gross_arpdau_usd"], 2),
    "weighted_net_arpdau_usd": round(100.0 * (p2["weighted_net_arpdau_usd"] - p1["weighted_net_arpdau_usd"]) / p1["weighted_net_arpdau_usd"], 2),
    "weighted_gross_dedup_arpdau_usd": round(100.0 * (p2["weighted_gross_dedup_arpdau_usd"] - p1["weighted_gross_dedup_arpdau_usd"]) / p1["weighted_gross_dedup_arpdau_usd"], 2),
    "daily_avg_gross_arpdau_usd": round(100.0 * (p2["daily_avg_gross_arpdau_usd"] - p1["daily_avg_gross_arpdau_usd"]) / p1["daily_avg_gross_arpdau_usd"], 2),
    "daily_avg_net_arpdau_usd": round(100.0 * (p2["daily_avg_net_arpdau_usd"] - p1["daily_avg_net_arpdau_usd"]) / p1["daily_avg_net_arpdau_usd"], 2),
}
df_period_out = pd.concat([df_period, pd.DataFrame([pct_row])], ignore_index=True)
df_period_out.to_csv(OUT_TABLES / "task_2_period_comparison.csv", index=False)

# ---------------------------------------------------------------------------
# 2. Enrich task_2_tier_comparison.csv with Overall Total row
# ---------------------------------------------------------------------------
tot_p1_pd = int(p1["total_active_player_days"])
tot_p2_pd = int(p2["total_active_player_days"])
tot_p1_gr = float(p1["total_gross_revenue_usd"])
tot_p2_gr = float(p2["total_gross_revenue_usd"])
tot_p1_rf = float(p1["total_refund_usd"])
tot_p2_rf = float(p2["total_refund_usd"])
tot_p1_nt = float(p1["total_net_revenue_usd"])
tot_p2_nt = float(p2["total_net_revenue_usd"])
r1_all_g = tot_p1_gr / tot_p1_pd
r2_all_g = tot_p2_gr / tot_p2_pd
r1_all_n = tot_p1_nt / tot_p1_pd
r2_all_n = tot_p2_nt / tot_p2_pd

total_tier_row = {
    "country_tier": "All Tiers (Overall)",
    "p1_player_days": tot_p1_pd,
    "p2_player_days": tot_p2_pd,
    "p1_unique_players": int(p1["unique_active_players"]),
    "p2_unique_players": int(p2["unique_active_players"]),
    "p1_gross_usd": tot_p1_gr,
    "p2_gross_usd": tot_p2_gr,
    "p1_refund_usd": tot_p1_rf,
    "p2_refund_usd": tot_p2_rf,
    "p1_net_usd": tot_p1_nt,
    "p2_net_usd": tot_p2_nt,
    "p1_gross_arpdau": round(r1_all_g, 6),
    "p2_gross_arpdau": round(r2_all_g, 6),
    "gross_arpdau_diff_usd": round(r2_all_g - r1_all_g, 6),
    "gross_arpdau_pct_change": round(100.0 * (r2_all_g - r1_all_g) / r1_all_g, 2),
    "p1_net_arpdau": round(r1_all_n, 6),
    "p2_net_arpdau": round(r2_all_n, 6),
    "net_arpdau_pct_change": round(100.0 * (r2_all_n - r1_all_n) / r1_all_n, 2),
    "tier_direction": "Declined (Simpson Paradox)",
}
df_tier_out = pd.concat([df_tier, pd.DataFrame([total_tier_row])], ignore_index=True)
df_tier_out.to_csv(OUT_TABLES / "task_2_tier_comparison.csv", index=False)

# Verify tier totals equal overall totals (zero row loss or multiplication)
assert int(df_tier["p1_player_days"].sum()) == tot_p1_pd
assert int(df_tier["p2_player_days"].sum()) == tot_p2_pd
assert round(float(df_tier["p1_gross_usd"].sum()), 2) == tot_p1_gr
assert round(float(df_tier["p2_gross_usd"].sum()), 2) == tot_p2_gr

# ---------------------------------------------------------------------------
# 3. Enrich task_2_player_mix.csv with Period-over-Period percentage-point shifts
# ---------------------------------------------------------------------------
mix_p1 = df_mix[df_mix["period"] == "first_30d"].set_index("country_tier")
mix_p2 = df_mix[df_mix["period"] == "last_30d"].set_index("country_tier")
df_mix["player_day_share_pp_change"] = df_mix["country_tier"].map(
    lambda t: round(float(mix_p2.loc[t, "player_day_share_pct"] - mix_p1.loc[t, "player_day_share_pct"]), 4)
)
df_mix["revenue_share_pp_change"] = df_mix["country_tier"].map(
    lambda t: round(float(mix_p2.loc[t, "gross_revenue_share_pct"] - mix_p1.loc[t, "gross_revenue_share_pct"]), 4)
)
df_mix.to_csv(OUT_TABLES / "task_2_player_mix.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Mathematical Decomposition (Kitagawa 3-term & 2-term + Counterfactual)
# ---------------------------------------------------------------------------
decomp_rows = []
for _, row in df_tier.iterrows():
    w1 = float(row["p1_player_days"]) / tot_p1_pd
    w2 = float(row["p2_player_days"]) / tot_p2_pd
    r1 = float(row["p1_gross_usd"]) / float(row["p1_player_days"])
    r2 = float(row["p2_gross_usd"]) / float(row["p2_player_days"])

    dw = w2 - w1
    dr = r2 - r1
    w_bar = 0.5 * (w1 + w2)
    r_bar = 0.5 * (r1 + r2)

    # 3-term exact (Jan weights baseline)
    within_jan_w = w1 * dr
    mix_jan_r = dw * r1
    interaction = dw * dr
    # 2-term symmetric exact (zero residual)
    sym_within = w_bar * dr
    sym_mix = dw * r_bar

    decomp_rows.append({
        "country_tier": str(row["country_tier"]),
        "w1_jan_share": round(w1, 6),
        "w2_apr_share": round(w2, 6),
        "delta_w_share": round(dw, 6),
        "r1_jan_arpdau": round(r1, 6),
        "r2_apr_arpdau": round(r2, 6),
        "delta_r_arpdau": round(dr, 6),
        "counterfactual_contrib_w1_r2": round(w1 * r2, 6),
        "within_effect_jan_w": round(within_jan_w, 6),
        "mix_effect_jan_r": round(mix_jan_r, 6),
        "interaction_effect": round(interaction, 6),
        "symmetric_within_effect": round(sym_within, 6),
        "symmetric_mix_effect": round(sym_mix, 6),
        "total_tier_contrib_change": round(w2 * r2 - w1 * r1, 6),
    })

df_decomp = pd.DataFrame(decomp_rows)
sum_w1 = df_decomp["w1_jan_share"].sum()
sum_w2 = df_decomp["w2_apr_share"].sum()
cf_arpdau = df_decomp["counterfactual_contrib_w1_r2"].sum()
within_3 = df_decomp["within_effect_jan_w"].sum()
mix_3 = df_decomp["mix_effect_jan_r"].sum()
inter_3 = df_decomp["interaction_effect"].sum()
sym_within_tot = df_decomp["symmetric_within_effect"].sum()
sym_mix_tot = df_decomp["symmetric_mix_effect"].sum()
actual_delta = r2_all_g - r1_all_g

assert abs(sum_w1 - 1.0) < 1e-4
assert abs(sum_w2 - 1.0) < 1e-4
assert abs((within_3 + mix_3 + inter_3) - actual_delta) < 1e-4, "3-term decomposition failed to reconcile!"
assert abs((sym_within_tot + sym_mix_tot) - actual_delta) < 1e-4, "2-term symmetric decomposition failed to reconcile!"

tot_decomp_row = {
    "country_tier": "TOTAL_RECONCILED",
    "w1_jan_share": round(sum_w1, 6),
    "w2_apr_share": round(sum_w2, 6),
    "delta_w_share": round(sum_w2 - sum_w1, 6),
    "r1_jan_arpdau": round(r1_all_g, 6),
    "r2_apr_arpdau": round(r2_all_g, 6),
    "delta_r_arpdau": round(actual_delta, 6),
    "counterfactual_contrib_w1_r2": round(cf_arpdau, 6),
    "within_effect_jan_w": round(within_3, 6),
    "mix_effect_jan_r": round(mix_3, 6),
    "interaction_effect": round(inter_3, 6),
    "symmetric_within_effect": round(sym_within_tot, 6),
    "symmetric_mix_effect": round(sym_mix_tot, 6),
    "total_tier_contrib_change": round(actual_delta, 6),
}
df_decomp_out = pd.concat([df_decomp, pd.DataFrame([tot_decomp_row])], ignore_index=True)
df_decomp_out.to_csv(OUT_TABLES / "task_2_decomposition.csv", index=False)

print("=== DELIVERABLE 2 VALIDATION & SUMMARY ===")
print("\nPeriod Comparison:\n", df_period_out[["period", "total_active_player_days", "unique_active_players", "total_gross_revenue_usd", "total_net_revenue_usd", "weighted_gross_arpdau_usd", "daily_avg_gross_arpdau_usd"]].to_string(index=False))
print("\nTier Comparison:\n", df_tier_out[["country_tier", "p1_player_days", "p2_player_days", "p1_gross_usd", "p2_gross_usd", "p1_gross_arpdau", "p2_gross_arpdau", "gross_arpdau_pct_change", "tier_direction"]].to_string(index=False))
print("\nDecomposition Totals:")
print(f"  Jan Actual ARPDAU:                ${r1_all_g:.4f}")
print(f"  Apr Actual ARPDAU:                ${r2_all_g:.4f} (Change: ${actual_delta:+.4f}, {100*actual_delta/r1_all_g:+.2f}%)")
print(f"  Counterfactual Apr (Jan weights): ${cf_arpdau:.4f} (Change: ${cf_arpdau - r1_all_g:+.4f}, {100*(cf_arpdau-r1_all_g)/r1_all_g:+.2f}%)")
print(f"  3-term: Within=${within_3:+.4f} + Mix=${mix_3:+.4f} + Interaction=${inter_3:+.4f} = ${within_3+mix_3+inter_3:+.4f}")
print(f"  2-term Symmetric: Within=${sym_within_tot:+.4f} + Mix=${sym_mix_tot:+.4f} = ${sym_within_tot+sym_mix_tot:+.4f}")

# ---------------------------------------------------------------------------
# 5. Generate 4 Charts
# ---------------------------------------------------------------------------

# CHART 1: task_2_arpdau_comparison.png
fig, ax = plt.subplots(figsize=(10, 5.5))
tiers_labels = ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Overall\n(All Tiers)"]
p1_vals = list(df_tier["p1_gross_arpdau"]) + [r1_all_g]
p2_vals = list(df_tier["p2_gross_arpdau"]) + [r2_all_g]
pcts = list(df_tier["gross_arpdau_pct_change"]) + [pct_row["weighted_gross_arpdau_usd"]]

x = np.arange(len(tiers_labels))
w = 0.35
b1 = ax.bar(x - w / 2, p1_vals, width=w, label="First 30 Days (Jan 1-30)", color="#4e79a7")
b2 = ax.bar(x + w / 2, p2_vals, width=w, label="Last 30 Days (Apr 1-30)", color="#f28e2b")
ax.axvline(3.5, color="#888888", linestyle="--", linewidth=1)
ax.set_xticks(x)
ax.set_xticklabels(tiers_labels, fontsize=10)
ax.set_ylabel("Weighted Gross ARPDAU ($)")
ax.set_ylim(0, max(p2_vals) * 1.24)
ax.set_title("Simpson's Paradox: Every Country Tier Improved, Yet Overall ARPDAU Fell 16.3%", fontsize=12, fontweight="bold")
ax.legend()

for i, (bar1, bar2, pct) in enumerate(zip(b1, b2, pcts)):
    ax.text(bar1.get_x() + bar1.get_width() / 2, bar1.get_height() + 0.008, f"${bar1.get_height():.2f}", ha="center", va="bottom", fontsize=8.5)
    ax.text(bar2.get_x() + bar2.get_width() / 2, bar2.get_height() + 0.008, f"${bar2.get_height():.2f}", ha="center", va="bottom", fontsize=8.5)
    col = "#2ca02c" if pct > 0 else "#d62728"
    top_y = max(bar1.get_height(), bar2.get_height()) + 0.045
    ax.text(x[i], top_y, f"{pct:+.1f}%", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color=col)

fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_2_arpdau_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 2: task_2_tier_trends.png
df_daily_tier["dt"] = pd.to_datetime(df_daily_tier["dt"])
df_daily_tier = df_daily_tier.sort_values(["country_tier", "dt"])
df_daily_tier["arpdau_7d_ma"] = df_daily_tier.groupby("country_tier")["gross_arpdau"].transform(lambda s: s.rolling(7, min_periods=1).mean())
overall_daily = df_daily_tier.groupby("dt", as_index=False).agg({"dau": "sum", "gross_usd": "sum"})
overall_daily["arpdau"] = overall_daily["gross_usd"] / overall_daily["dau"]
overall_daily["arpdau_7d_ma"] = overall_daily["arpdau"].rolling(7, min_periods=1).mean()

fig, ax = plt.subplots(figsize=(12, 5.5))
tier_palette = {1: "#1f77b4", 2: "#2ca02c", 3: "#ff7f0e", 4: "#9467bd"}
for t in [1, 2, 3, 4]:
    sub = df_daily_tier[df_daily_tier["country_tier"] == t]
    ax.plot(sub["dt"], sub["arpdau_7d_ma"], label=f"Tier {t} (7d avg)", color=tier_palette[t], linewidth=1.8)
ax.plot(overall_daily["dt"], overall_daily["arpdau_7d_ma"], label="Overall Blended ARPDAU (7d avg)", color="#d62728", linewidth=2.6, linestyle="--")

ax.axvspan(pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-30"), color="#4e79a7", alpha=0.08, label="First 30d Window")
ax.axvspan(pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-30"), color="#f28e2b", alpha=0.08, label="Last 30d Window")
ax.set_title("7-Day Rolling Gross ARPDAU by Country Tier vs. Overall Blended ARPDAU", fontsize=12, fontweight="bold")
ax.set_ylabel("Gross ARPDAU ($)")
ax.set_xlabel("Date (2026)")
ax.xaxis.set_major_locator(mdates.DayLocator(interval=14))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.legend(ncol=2, loc="upper right", fontsize=8.5)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_2_tier_trends.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 3: task_2_player_mix.png
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
periods_lbl = ["First 30d\n(Jan 1-30)", "Last 30d\n(Apr 1-30)"]
tier_names = ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]
tier_cols = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd"]

# Panel A: Active Player-Day Share (%)
pd_shares = df_mix.pivot(index="period", columns="country_tier", values="player_day_share_pct").loc[["first_30d", "last_30d"]]
bottom = np.zeros(2)
for t, tname, col in zip([1, 2, 3, 4], tier_names, tier_cols):
    vals = pd_shares[t].values
    axes[0].bar(periods_lbl, vals, bottom=bottom, label=tname, color=col, width=0.5)
    for i, v in enumerate(vals):
        axes[0].text(i, bottom[i] + v / 2, f"{v:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=9.5)
    bottom += vals
axes[0].set_title("Active Player-Day Mix Shift\n(Tier 4 Surged from 17.7% to 46.0%)", fontweight="bold")
axes[0].set_ylabel("Share of Active Player-Days (%)")
axes[0].set_ylim(0, 105)
axes[0].legend(loc="upper right", fontsize=8.5)

# Panel B: Gross Revenue Share (%)
rev_shares = df_mix.pivot(index="period", columns="country_tier", values="gross_revenue_share_pct").loc[["first_30d", "last_30d"]]
bottom_r = np.zeros(2)
for t, tname, col in zip([1, 2, 3, 4], tier_names, tier_cols):
    vals = rev_shares[t].values
    axes[1].bar(periods_lbl, vals, bottom=bottom_r, label=tname, color=col, width=0.5)
    for i, v in enumerate(vals):
        axes[1].text(i, bottom_r[i] + v / 2, f"{v:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=9.5)
    bottom_r += vals
axes[1].set_title("Gross Revenue Mix Shift\n(Tiers 1 & 2 Still Carry 59.6% of Revenue)", fontweight="bold")
axes[1].set_ylabel("Share of Gross Revenue (%)")
axes[1].set_ylim(0, 105)

fig.suptitle("Deliverable 2: Player-Day & Revenue Composition by Country Tier", fontsize=13, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_2_player_mix.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 4: task_2_decomposition.png (Waterfall of Symmetric Decomposition + Counterfactual)
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))

# Panel A: Waterfall from Jan ARPDAU -> Within-Tier Effect -> Mix Effect -> Apr ARPDAU
labels_wf = ["Jan\nARPDAU", "Within-Tier\nMonetisation\n(+Effect)", "Country-Tier\nMix Shift\n(-Effect)", "Apr\nARPDAU"]
steps = [r1_all_g, sym_within_tot, sym_mix_tot, r2_all_g]
bottoms_wf = [0, r1_all_g, r1_all_g + sym_within_tot + sym_mix_tot, 0]
heights_wf = [r1_all_g, sym_within_tot, abs(sym_mix_tot), r2_all_g]
cols_wf = ["#4e79a7", "#2ca02c", "#d62728", "#f28e2b"]

bars_wf = axes[0].bar(labels_wf, heights_wf, bottom=bottoms_wf, color=cols_wf, width=0.55)
axes[0].set_ylabel("Gross ARPDAU ($)")
axes[0].set_ylim(0, 0.44)
axes[0].set_title(f"Symmetric Kitagawa Decomposition\n(Exact Reconciliation: +${sym_within_tot:.4f} - ${abs(sym_mix_tot):.4f} = -${abs(actual_delta):.4f})", fontweight="bold")
annots = [f"${r1_all_g:.4f}", f"+${sym_within_tot:.4f}", f"-${abs(sym_mix_tot):.4f}", f"${r2_all_g:.4f}"]
for i, (b, txt) in enumerate(zip(bars_wf, annots)):
    y_top = bottoms_wf[i] + heights_wf[i]
    axes[0].text(b.get_x() + b.get_width() / 2, y_top + 0.008, txt, ha="center", va="bottom", fontweight="bold", fontsize=9.5)

# Panel B: Tier-by-Tier Decomposition Contribution
t_lbls = [f"Tier {t}" for t in df_decomp["country_tier"]]
x_d = np.arange(len(t_lbls))
w_d = 0.35
b_w = axes[1].bar(x_d - w_d / 2, df_decomp["symmetric_within_effect"], width=w_d, label="Within-Tier Effect ($)", color="#2ca02c")
b_m = axes[1].bar(x_d + w_d / 2, df_decomp["symmetric_mix_effect"], width=w_d, label="Mix-Shift Effect ($)", color="#d62728")
axes[1].axhline(0, color="black", linewidth=0.8)
axes[1].set_xticks(x_d)
axes[1].set_xticklabels(t_lbls)
axes[1].set_ylabel("Contribution to Overall ARPDAU Change ($)")
axes[1].set_title("Tier-Level Breakdown of Within vs. Mix Effects", fontweight="bold")
axes[1].legend(fontsize=8.5)
for bar in list(b_w) + list(b_m):
    val = bar.get_height()
    va = "bottom" if val >= 0 else "top"
    offset = 0.002 if val >= 0 else -0.002
    axes[1].text(bar.get_x() + bar.get_width() / 2, val + offset, f"{val:+.3f}", ha="center", va=va, fontsize=8)

fig.tight_layout()
fig.savefig(OUT_CHARTS / "task_2_decomposition.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print("\nAll 4 Deliverable 2 CSVs and 4 charts generated successfully.")
