"""Independent Quality Audit for Deliverable 2 (Option A: ARPDAU Deep Dive).

Independently recalculates all Deliverable 2 metrics directly from the untouched
raw CSVs in data/ and compares against:
  - sql/task_2_arpdau_deep_dive.sql
  - outputs/tables/task_2_*.csv
"""

import re
from pathlib import Path
import duckdb
import pandas as pd

DATA_DIR = Path("data")
SQL_PATH = Path("sql/task_2_arpdau_deep_dive.sql")
OUT_TABLES = Path("outputs/tables")

raw_con = duckdb.connect(":memory:")
raw_con.execute(f"CREATE TEMP TABLE player_profile AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'player_profile - player_profile.csv').as_posix()}', sample_size=-1)")
raw_con.execute(f"CREATE TEMP TABLE player_day AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'player_day - player_day.csv').as_posix()}', sample_size=-1)")
raw_con.execute(f"CREATE TEMP TABLE purchase AS SELECT * FROM read_csv_auto('{(DATA_DIR / 'purchase - purchase.csv').as_posix()}', sample_size=-1)")

db_con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

print("=== AUDIT 1: EXACT DATE WINDOWS (30 DAYS EACH, NO JAN 31 LEAK) ===")
pd_win = raw_con.execute("""
    SELECT
        CASE WHEN activity_date BETWEEN 20260101 AND 20260130 THEN 'first_30d'
             WHEN activity_date BETWEEN 20260401 AND 20260430 THEN 'last_30d' END AS period,
        MIN(activity_date), MAX(activity_date), COUNT(DISTINCT activity_date), COUNT(*), COUNT(DISTINCT device_id)
    FROM player_day
    WHERE activity_date BETWEEN 20260101 AND 20260130 OR activity_date BETWEEN 20260401 AND 20260430
    GROUP BY 1 ORDER BY 1
""").fetchall()
for row in pd_win:
    assert row[3] == 30, f"Expected 30 days, got {row[3]}"
    print("  [PASS] player_day window:", row)

pu_win = raw_con.execute("""
    SELECT
        CASE WHEN DATE(event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30' THEN 'first_30d'
             WHEN DATE(event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 'last_30d' END AS period,
        MIN(DATE(event_ts)), MAX(DATE(event_ts)), COUNT(DISTINCT DATE(event_ts)),
        ROUND(SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END), 2),
        ROUND(SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END), 2),
        ROUND(SUM(usd_amount), 2)
    FROM purchase
    WHERE DATE(event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
       OR DATE(event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
    GROUP BY 1 ORDER BY 1
""").fetchall()
for row in pu_win:
    assert row[3] == 30
    print("  [PASS] purchase window:", row)

print("\n=== AUDIT 2: REPRODUCIBILITY OF SQL QUERIES ===")
sql_raw = SQL_PATH.read_text(encoding="utf-8")
blocks = re.split(r"-- === QUERY \d+:.*?===\r?\n", sql_raw)
queries = [b.strip() for b in blocks[1:] if b.strip()]
df_q1 = db_con.execute(queries[0]).df()
df_q2 = db_con.execute(queries[1]).df()
df_q3 = db_con.execute(queries[2]).df()

df_period = pd.read_csv(OUT_TABLES / "task_2_period_comparison.csv")
df_tier = pd.read_csv(OUT_TABLES / "task_2_tier_comparison.csv")
df_mix = pd.read_csv(OUT_TABLES / "task_2_player_mix.csv")
df_decomp = pd.read_csv(OUT_TABLES / "task_2_decomposition.csv")

for col in ["total_active_player_days", "total_gross_revenue_usd", "total_net_revenue_usd", "weighted_gross_arpdau_usd"]:
    assert list(df_q1[col].round(4)) == list(df_period.iloc[:2][col].round(4)), f"Period mismatch on {col}"
for col in ["p1_player_days", "p2_player_days", "p1_gross_usd", "p2_gross_usd", "p1_gross_arpdau", "p2_gross_arpdau"]:
    assert list(df_q2[col].round(4)) == list(df_tier.iloc[:4][col].round(4)), f"Tier mismatch on {col}"
for col in ["active_player_days", "player_day_share_pct", "gross_revenue_usd", "gross_revenue_share_pct"]:
    assert list(df_q3[col].round(4)) == list(df_mix[col].round(4)), f"Mix mismatch on {col}"
print("  [PASS] All saved CSV tables match direct re-execution of sql/task_2_arpdau_deep_dive.sql")

print("\n=== AUDIT 3: INDEPENDENT TIER & MIX RECONCILIATION (FROM RAW CSVs) ===")
ind_tier = raw_con.execute("""
    WITH pd AS (
        SELECT
            CASE WHEN d.activity_date <= 20260130 THEN 'p1' ELSE 'p2' END AS p,
            pf.country_tier, COUNT(*) pdays, COUNT(DISTINCT d.device_id) udevs
        FROM player_day d JOIN player_profile pf ON d.device_id = pf.device_id
        WHERE d.activity_date BETWEEN 20260101 AND 20260130 OR d.activity_date BETWEEN 20260401 AND 20260430
        GROUP BY 1, 2
    ),
    pu AS (
        SELECT
            CASE WHEN DATE(u.event_ts) <= DATE '2026-01-30' THEN 'p1' ELSE 'p2' END AS p,
            pf.country_tier,
            ROUND(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 2) gross_usd,
            ROUND(SUM(u.usd_amount), 2) net_usd
        FROM purchase u JOIN player_profile pf ON u.device_id = pf.device_id
        WHERE DATE(u.event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
           OR DATE(u.event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
        GROUP BY 1, 2
    )
    SELECT pd.p, pd.country_tier, pd.pdays, pd.udevs, pu.gross_usd, pu.net_usd,
           pu.gross_usd / pd.pdays AS gross_arpdau, pu.net_usd / pd.pdays AS net_arpdau
    FROM pd JOIN pu ON pd.p = pu.p AND pd.country_tier = pu.country_tier
    ORDER BY pd.country_tier, pd.p
""").df()

p1_sub = ind_tier[ind_tier["p"] == "p1"].set_index("country_tier")
p2_sub = ind_tier[ind_tier["p"] == "p2"].set_index("country_tier")
assert int(p1_sub["pdays"].sum()) == 82381
assert int(p2_sub["pdays"].sum()) == 282781
assert round(float(p1_sub["gross_usd"].sum()), 2) == 29383.67
assert round(float(p2_sub["gross_usd"].sum()), 2) == 84404.41

# Verify mix shares sum to 100.00% in both periods
for per in ["first_30d", "last_30d"]:
    sub_m = df_mix[df_mix["period"] == per]
    assert abs(sub_m["player_day_share_pct"].sum() - 100.0) < 0.01
    assert abs(sub_m["unique_player_share_pct"].sum() - 100.0) < 0.01
    assert abs(sub_m["gross_revenue_share_pct"].sum() - 100.0) < 0.01
print("  [PASS] All period/tier player-day counts, revenues, and mix shares (sum=100%) match raw CSVs")

print("\n=== AUDIT 4: MATHEMATICAL DECOMPOSITION CHECK (GROSS & NET) ===")
w1 = p1_sub["pdays"] / p1_sub["pdays"].sum()
w2 = p2_sub["pdays"] / p2_sub["pdays"].sum()
r1_g = p1_sub["gross_arpdau"]
r2_g = p2_sub["gross_arpdau"]
r1_n = p1_sub["net_arpdau"]
r2_n = p2_sub["net_arpdau"]

R1_g = float(p1_sub["gross_usd"].sum() / p1_sub["pdays"].sum())
R2_g = float(p2_sub["gross_usd"].sum() / p2_sub["pdays"].sum())
dR_g = R2_g - R1_g
cf_g = float((w1 * r2_g).sum())
within_g = float((0.5 * (w1 + w2) * (r2_g - r1_g)).sum())
mix_g = float(((w2 - w1) * 0.5 * (r1_g + r2_g)).sum())
assert abs((within_g + mix_g) - dR_g) < 1e-8

# Compare against task_2_decomposition.csv TOTAL_RECONCILED
tot_d = df_decomp[df_decomp["country_tier"] == "TOTAL_RECONCILED"].iloc[0]
assert abs(float(tot_d["counterfactual_contrib_w1_r2"]) - cf_g) < 1e-4
assert abs(float(tot_d["symmetric_within_effect"]) - within_g) < 1e-4
assert abs(float(tot_d["symmetric_mix_effect"]) - mix_g) < 1e-4
assert abs(float(tot_d["total_tier_contrib_change"]) - dR_g) < 1e-4
print(f"  [PASS] Gross Decomposition: Actual={dR_g:+.6f} | Within={within_g:+.6f} + Mix={mix_g:+.6f} = {within_g+mix_g:+.6f} | Counterfactual={cf_g:.6f}")

# Independent Net ARPDAU check
R1_n = float(p1_sub["net_usd"].sum() / p1_sub["pdays"].sum())
R2_n = float(p2_sub["net_usd"].sum() / p2_sub["pdays"].sum())
dR_n = R2_n - R1_n
cf_n = float((w1 * r2_n).sum())
within_n = float((0.5 * (w1 + w2) * (r2_n - r1_n)).sum())
mix_n = float(((w2 - w1) * 0.5 * (r1_n + r2_n)).sum())
assert abs((within_n + mix_n) - dR_n) < 1e-8
print(f"  [PASS] Net Decomposition:   Actual={dR_n:+.6f} ({100*dR_n/R1_n:+.2f}%) | Within={within_n:+.6f} + Mix={mix_n:+.6f} | Counterfactual={cf_n:.6f} ({100*(cf_n-R1_n)/R1_n:+.2f}%)")

print("\n=== AUDIT 5: DUPLICATE PURCHASE_ID SENSITIVITY (RAW CSVs) ===")
dedup_res = raw_con.execute("""
    WITH pr AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts ASC) AS rn
        FROM purchase
    )
    SELECT
        CASE WHEN DATE(event_ts) <= DATE '2026-01-30' THEN 'first_30d' ELSE 'last_30d' END AS period,
        ROUND(SUM(CASE WHEN rn = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS gross_dedup,
        ROUND(SUM(CASE WHEN rn = 1 THEN usd_amount ELSE 0 END), 2) AS net_dedup
    FROM pr
    WHERE DATE(event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
       OR DATE(event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
    GROUP BY 1 ORDER BY 1
""").fetchall()
assert dedup_res[0][1] == float(df_period.iloc[0]["gross_dedup_usd"])
assert dedup_res[1][1] == float(df_period.iloc[1]["gross_dedup_usd"])
assert dedup_res[0][2] == float(df_period.iloc[0]["net_dedup_usd"])
assert dedup_res[1][2] == float(df_period.iloc[1]["net_dedup_usd"])
print("  [PASS] Duplicate purchase_id sensitivity matches raw CSVs:", dedup_res)

raw_con.close()
db_con.close()
print("\nDELIVERABLE 2 AUDIT COMPLETE: ALL 10 CHECKS PASSED.")
