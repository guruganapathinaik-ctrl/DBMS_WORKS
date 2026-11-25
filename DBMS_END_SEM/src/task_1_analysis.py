"""Deliverable 1: SQL Execution, Validation, and Chart Generation.

Executes sql/task_1a..1d against outputs/telemetry.duckdb (read-only),
saves outputs/tables/task_1*.csv, validates totals/denominators/reconciliation,
and generates four charts in outputs/charts/.
"""

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
SQL_DIR = Path("sql")
OUT_TABLES = Path("outputs/tables")
OUT_CHARTS = Path("outputs/charts")
OUT_TABLES.mkdir(parents=True, exist_ok=True)
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")

con = duckdb.connect(str(DB_PATH), read_only=True)


def run_sql_to_df(sql_filename: str, csv_filename: str) -> pd.DataFrame:
    """Execute a SQL script via DuckDB, save aggregated output to CSV, and return DataFrame."""
    sql_text = (SQL_DIR / sql_filename).read_text(encoding="utf-8")
    df = con.execute(sql_text).df()
    df.to_csv(OUT_TABLES / csv_filename, index=False)
    print(f"Executed {sql_filename} -> {csv_filename} ({len(df)} rows)")
    return df


# ---------------------------------------------------------------------------
# 1. Execute all 4 SQL scripts & save CSVs
# ---------------------------------------------------------------------------
df_1a = run_sql_to_df("task_1a_daily_health.sql", "task_1a_daily_health.csv")
df_1b = run_sql_to_df("task_1b_retention.sql", "task_1b_retention.csv")
df_1c = run_sql_to_df("task_1c_spender_behaviour.sql", "task_1c_spender_behaviour.csv")
df_1d = run_sql_to_df("task_1d_ad_engagement.sql", "task_1d_ad_engagement.csv")

# ---------------------------------------------------------------------------
# 2. Validate calculations, denominators, joins, and revenue reconciliation
# ---------------------------------------------------------------------------
print("\n=== VALIDATION CHECKS ===")
total_dau_sum = int(df_1a["dau"].sum())
assert total_dau_sum == 667435, f"DAU sum mismatch: {total_dau_sum}"

gross_sum = round(float(df_1a["gross_positive_usd"].sum()), 2)
refund_sum = round(float(df_1a["refund_negative_usd"].sum()), 2)
net_sum = round(float(df_1a["net_revenue_usd"].sum()), 2)
gross_dedup_sum = round(float(df_1a["gross_positive_dedup_usd"].sum()), 2)
net_dedup_sum = round(float(df_1a["net_dedup_usd"].sum()), 2)

assert gross_sum == 219434.02, f"Gross mismatch: {gross_sum}"
assert refund_sum == -3274.72, f"Refund mismatch: {refund_sum}"
assert net_sum == 216159.30, f"Net mismatch: {net_sum}"
assert round(gross_sum + refund_sum, 2) == net_sum
assert gross_dedup_sum == 217593.22, f"Gross dedup mismatch: {gross_dedup_sum}"
assert net_dedup_sum == 214343.48, f"Net dedup mismatch: {net_dedup_sum}"

cohort_sum = int(df_1b["cohort_size"].sum())
assert cohort_sum == 64295, f"Cohort sum mismatch: {cohort_sum}"

ad_views_sum = int(df_1d["total_ad_views"].sum())
ad_pdays_sum = int(df_1d["ad_watching_player_days"].sum())
assert ad_views_sum == 647623, f"Ad views sum mismatch: {ad_views_sum}"
assert ad_pdays_sum == 392949, f"Ad player-days sum mismatch: {ad_pdays_sum}"
assert int(df_1d["cap5_player_days"].sum() + df_1d["cap8_player_days"].sum()) == ad_pdays_sum
assert int(df_1d.loc[df_1d["is_outage_day"] == 1, "total_ad_views"].sum()) == 0

print("  [PASS] Task 1A DAU sum == 667,435 (0 row multiplication)")
print(f"  [PASS] Task 1A Revenue reconciled: Gross=${gross_sum:,.2f}, Refunds=${refund_sum:,.2f}, Net=${net_sum:,.2f} (Dedup Net=${net_dedup_sum:,.2f})")
print(f"  [PASS] Task 1B Weekly cohort sizes sum == {cohort_sum:,} (all 2026-01-01..2026-04-30 installs)")
print(f"  [PASS] Task 1D Ad views sum == {ad_views_sum:,}, player-days == {ad_pdays_sum:,}, March 5-6 outage == 0 views")

# ---------------------------------------------------------------------------
# 3. Print key aggregated summaries for verification & report writing
# ---------------------------------------------------------------------------
print("\n=== TASK 1A PLATFORM SUMMARY ===")
plat_summary = con.execute("""
    WITH pd AS (
        SELECT p.platform, COUNT(*) AS active_player_days, COUNT(DISTINCT d.device_id) AS active_players
        FROM player_day d JOIN player_profile p ON d.device_id = p.device_id
        GROUP BY 1
    ),
    pu AS (
        SELECT p.platform,
               ROUND(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 2) AS gross_usd,
               ROUND(SUM(CASE WHEN u.usd_amount < 0 THEN u.usd_amount ELSE 0 END), 2) AS refund_usd,
               ROUND(SUM(u.usd_amount), 2) AS net_usd,
               COUNT(DISTINCT CASE WHEN u.usd_amount > 0 THEN u.device_id END) AS unique_payers
        FROM purchase u JOIN player_profile p ON u.device_id = p.device_id
        GROUP BY 1
    )
    SELECT pd.platform, pd.active_player_days, pd.active_players,
           ROUND(pd.active_player_days / 120.0, 1) AS avg_dau,
           pu.unique_payers, pu.gross_usd, pu.refund_usd, pu.net_usd,
           ROUND(pu.gross_usd / pd.active_player_days, 4) AS overall_arpdau_gross,
           ROUND(pu.net_usd / pd.active_player_days, 4) AS overall_arpdau_net
    FROM pd JOIN pu ON pd.platform = pu.platform ORDER BY 1
""").df()
print(plat_summary.to_string(index=False))

print("\n=== TASK 1B RETENTION TABLE ===")
print(df_1b[["cohort_week", "cohort_start_date", "cohort_end_date", "cohort_size",
             "retention_d1_pct", "retention_d7_pct", "retention_d14_pct", "retention_d30_pct"]].to_string(index=False))

print("\n=== TASK 1C SPENDER SUMMARY ===")
print(df_1c.to_string(index=False))

print("\n=== TASK 1D AD ENGAGEMENT SUMMARY ===")
ad_overall = con.execute("""
    WITH pd AS (
        SELECT device_id, DATE(event_ts - INTERVAL 8 HOUR) AS gdate,
               MAX(ad_daily_cap) AS cap, MAX(ad_daily_count) AS max_cnt
        FROM ad_view GROUP BY 1, 2
    )
    SELECT cap,
           COUNT(*) AS ad_player_days,
           SUM(CASE WHEN max_cnt >= cap THEN 1 ELSE 0 END) AS hit_cap_days,
           ROUND(100.0 * SUM(CASE WHEN max_cnt >= cap THEN 1 ELSE 0 END) / COUNT(*), 4) AS hit_cap_pct
    FROM pd GROUP BY 1 ORDER BY 1
""").df()
print(ad_overall.to_string(index=False))

ad_status = con.execute("""
    SELECT status, COUNT(*) AS events,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ad_view), 2) AS pct_events,
           SUM(reward_amount) AS total_reward_granted
    FROM ad_view GROUP BY 1 ORDER BY 2 DESC
""").df()
print("\nAd status breakdown:\n", ad_status.to_string(index=False))

ad_placement = con.execute("""
    SELECT placement, COUNT(*) AS events,
           ROUND(100.0 * SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) / COUNT(*), 2) AS completion_pct,
           ROUND(100.0 * SUM(CASE WHEN status='abandoned' THEN 1 ELSE 0 END) / COUNT(*), 2) AS abandonment_pct,
           ROUND(100.0 * SUM(CASE WHEN status='started' THEN 1 ELSE 0 END) / COUNT(*), 2) AS started_only_pct
    FROM ad_view GROUP BY 1 ORDER BY 2 DESC
""").df()
print("\nAd placement breakdown:\n", ad_placement.to_string(index=False))

# ---------------------------------------------------------------------------
# 4. Generate 4 Charts (from small aggregated DataFrames only)
# ---------------------------------------------------------------------------

# CHART 1: daily_health.png
df_1a["metric_date"] = pd.to_datetime(df_1a["metric_date"])
fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
colors = {"Android": "#1f77b4", "iOS": "#ff7f0e"}

for plat, grp in df_1a.groupby("platform"):
    axes[0].plot(grp["metric_date"], grp["dau"], label=plat, color=colors[plat], linewidth=1.8)
    axes[1].plot(grp["metric_date"], grp["net_revenue_usd"], label=f"{plat} (Net)", color=colors[plat], linewidth=1.5, alpha=0.85)
    axes[2].plot(grp["metric_date"], grp["arpdau_net_usd"], label=f"{plat} Net ARPDAU", color=colors[plat], linewidth=1.5)

axes[0].set_title("Daily Active Users (DAU) by Platform", fontsize=12, fontweight="bold")
axes[0].set_ylabel("DAU (Players)")
axes[0].legend(loc="upper left")

axes[1].set_title("Daily Net Revenue (USD) by Platform (Spikes = Sale Days)", fontsize=12, fontweight="bold")
axes[1].set_ylabel("Net Revenue ($)")
axes[1].legend(loc="upper left")

axes[2].set_title("Daily Net ARPDAU (USD) by Platform", fontsize=12, fontweight="bold")
axes[2].set_ylabel("ARPDAU ($)")
axes[2].set_xlabel("Date (2026-01-01 to 2026-04-30)")
axes[2].legend(loc="upper right")
axes[2].xaxis.set_major_locator(mdates.DayLocator(interval=14))
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

fig.suptitle("Deliverable 1A: Daily Health Metrics by Platform", fontsize=14, fontweight="bold", y=0.995)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "daily_health.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 2: retention_heatmap.png
ret_heat = df_1b.copy()
ret_heat["label"] = (
    pd.to_datetime(ret_heat["cohort_week"]).dt.strftime("%Y-%m-%d")
    + " (n="
    + ret_heat["cohort_size"].map(lambda x: f"{x:,}")
    + ")"
)
mat = ret_heat.set_index("label")[["retention_d1_pct", "retention_d7_pct", "retention_d14_pct", "retention_d30_pct"]]
mat.columns = ["Day 1 (%)", "Day 7 (%)", "Day 14 (%)", "Day 30 (%)"]

fig, ax = plt.subplots(figsize=(9, 8))
sns.heatmap(
    mat,
    annot=True,
    fmt=".1f",
    cmap="YlGnBu",
    linewidths=0.5,
    cbar_kws={"label": "Retention Rate (%)"},
    ax=ax,
    mask=mat.isna(),
)
ax.set_facecolor("#eeeeee")
ax.set_title("Deliverable 1B: Weekly Cohort Retention Heatmap\n(Grey = Incomplete Observation Window as of 2026-04-30)", fontsize=12, fontweight="bold")
ax.set_xlabel("Days Since Install")
ax.set_ylabel("Install Week Cohort (Size)")
fig.tight_layout()
fig.savefig(OUT_CHARTS / "retention_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 3: spender_analysis.png
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Panel A: Revenue Concentration (Payers Only vs All Players)
conc_payers = df_1c[df_1c["section"] == "1_concentration_payers_only_raw"].copy()
conc_all = df_1c[df_1c["section"] == "2_concentration_all_players_raw"].copy()
labels_pct = ["Top 1%", "Top 10%", "Top 50%"]
x = np.arange(len(labels_pct))
w = 0.35
b1 = axes[0].bar(x - w / 2, conc_payers["gross_share_pct"].values, width=w, label="Payers Only (n=11,054)", color="#2b5c8f")
b2 = axes[0].bar(x + w / 2, conc_all["gross_share_pct"].values, width=w, label="All Players (n=80,295)", color="#f28e2b")
axes[0].set_xticks(x)
axes[0].set_xticklabels(labels_pct)
axes[0].set_ylim(0, 112)
axes[0].set_ylabel("Share of Gross Revenue (%)")
axes[0].set_title("Revenue Concentration", fontweight="bold")
axes[0].legend(fontsize=8)
for bar in list(b1) + list(b2):
    h = bar.get_height()
    axes[0].text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=8)

# Panel B: Time to First Purchase (2026 Installs, Payers Only)
ttfp_2026 = df_1c[(df_1c["section"] == "5_time_to_first_purchase_2026_installs") & (df_1c["metric"] != "Never purchased")].copy()
order_buckets = ["Pre-install anomaly (<0d)", "Day 0 (install day)", "Days 1-3", "Days 4-7", "Days 8-14", "Days 15-30", "Days 31-60", "61+ days"]
ttfp_2026["metric"] = pd.Categorical(ttfp_2026["metric"], categories=order_buckets, ordered=True)
ttfp_2026 = ttfp_2026.sort_values("metric")
axes[1].barh(ttfp_2026["metric"].astype(str), ttfp_2026["net_share_pct"].fillna(0), color="#4e79a7")
axes[1].invert_yaxis()
axes[1].set_xlabel("Share of 2026 Payers (%)")
axes[1].set_title("Time to First Purchase\n(2026 Installs; 86.23% Overall Never Pay)", fontweight="bold")
for idx, val in enumerate(ttfp_2026["net_share_pct"].fillna(0)):
    axes[1].text(val + 0.5, idx, f"{val:.1f}%", va="center", fontsize=8)
axes[1].set_xlim(0, max(ttfp_2026["net_share_pct"].fillna(0)) + 8)

# Panel C: Repeat Purchase Gap Distribution (Aggregated in DuckDB)
gap_hist = con.execute("""
    WITH g AS (
        SELECT EXTRACT(EPOCH FROM (event_ts - LAG(event_ts) OVER (PARTITION BY device_id ORDER BY event_ts))) / 86400.0 AS gap_days
        FROM (SELECT DISTINCT purchase_id, device_id, event_ts, usd_amount FROM purchase WHERE usd_amount > 0)
    )
    SELECT
        CASE
            WHEN gap_days < 1 THEN '< 1 day'
            WHEN gap_days < 3 THEN '1-3 days'
            WHEN gap_days < 7 THEN '3-7 days'
            WHEN gap_days < 14 THEN '7-14 days'
            WHEN gap_days < 30 THEN '14-30 days'
            ELSE '30+ days'
        END AS bucket,
        COUNT(*) AS n
    FROM g
    WHERE gap_days IS NOT NULL
    GROUP BY 1
""").df()
gap_order = ["< 1 day", "1-3 days", "3-7 days", "7-14 days", "14-30 days", "30+ days"]
gap_hist["bucket"] = pd.Categorical(gap_hist["bucket"], categories=gap_order, ordered=True)
gap_hist = gap_hist.sort_values("bucket")
axes[2].bar(gap_hist["bucket"].astype(str), gap_hist["n"], color="#59a14f")
axes[2].set_title("Repeat Purchase Gap (Deduped IDs)", fontweight="bold")
axes[2].set_ylabel("Consecutive Purchase Pairs")
axes[2].tick_params(axis="x", rotation=30)
for idx, val in enumerate(gap_hist["n"]):
    axes[2].text(idx, val + 15, f"{val:,}", ha="center", fontsize=8)

fig.suptitle("Deliverable 1C: Spender Behaviour & Concentration", fontsize=14, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "spender_analysis.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# CHART 4: ad_engagement.png
df_1d["game_date"] = pd.to_datetime(df_1d["game_date"])
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

# Panel A: Daily Ad Views (Highlighting March 5-6 Outage)
axes[0].plot(df_1d["game_date"], df_1d["total_ad_views"], color="#1f77b4", linewidth=1.8, label="Daily Ad Views (-8h aligned)")
outage_dates = df_1d[df_1d["is_outage_day"] == 1]["game_date"]
for od in outage_dates:
    axes[0].axvline(od, color="#d62728", linestyle="--", alpha=0.8)
axes[0].annotate("March 5-6 Outage\n(0 events logged)", xy=(pd.Timestamp("2026-03-05"), 500),
                 xytext=(pd.Timestamp("2026-01-22"), 9000),
                 arrowprops=dict(arrowstyle="->", color="#d62728"),
                 color="#d62728", fontsize=9, fontweight="bold")
axes[0].set_title("Daily Rewarded Ad Views", fontweight="bold")
axes[0].set_ylabel("Total Ad Views")
axes[0].xaxis.set_major_locator(mdates.DayLocator(interval=28))
axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

# Panel B: Cap Hit Rate by Daily Cap (5 vs 8)
bars_cap = axes[1].bar(ad_overall["cap"].astype(str).map(lambda c: f"Cap = {c}"), ad_overall["hit_cap_pct"], color=["#4e79a7", "#e15759"], width=0.5)
axes[1].set_title("Player-Days Reaching Daily Cap (%)", fontweight="bold")
axes[1].set_ylabel("% of Ad-Watching Player-Days")
axes[1].set_ylim(0, max(ad_overall["hit_cap_pct"]) * 1.35)
for bar, (_, row_c) in zip(bars_cap, ad_overall.iterrows()):
    h = bar.get_height()
    axes[1].text(bar.get_x() + bar.get_width() / 2, h + 0.03,
                 f"{h:.2f}%\n({int(row_c['hit_cap_days']):,} / {int(row_c['ad_player_days']):,})",
                 ha="center", va="bottom", fontsize=9)

# Panel C: Completion vs Abandonment by Placement
x_p = np.arange(len(ad_placement))
axes[2].barh(x_p, ad_placement["completion_pct"], label="Completed (%)", color="#59a14f")
axes[2].barh(x_p, ad_placement["abandonment_pct"], left=ad_placement["completion_pct"], label="Abandoned (%)", color="#edc948")
axes[2].barh(x_p, ad_placement["started_only_pct"], left=ad_placement["completion_pct"] + ad_placement["abandonment_pct"], label="Started Only (%)", color="#bab0ac")
axes[2].set_yticks(x_p)
axes[2].set_yticklabels(ad_placement["placement"])
axes[2].set_xlim(0, 105)
axes[2].set_xlabel("Share of Ad Events (%)")
axes[2].set_title("Ad Status Breakdown by Placement", fontweight="bold")
axes[2].legend(loc="lower right", fontsize=8)

fig.suptitle("Deliverable 1D: Rewarded Ad Engagement & Telemetry Outage", fontsize=14, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "ad_engagement.png", dpi=150, bbox_inches="tight")
plt.close(fig)

con.close()
print("\nAll 4 Deliverable 1 charts saved to outputs/charts/.")
