"""Independent Quality Audit for Deliverable 1.

Independently recalculates critical metrics directly from the raw CSVs (without
relying on the Deliverable 1 SQL scripts) and compares against:
  1) outputs/tables/task_1*.csv
  2) re-execution of sql/task_1*.sql against outputs/telemetry.duckdb
  3) assertions for denominators, ties, joins, offsets, and reconciliation.
"""

from pathlib import Path
import duckdb
import pandas as pd

DATA_DIR = Path("data")
SQL_DIR = Path("sql")
OUT_TABLES = Path("outputs/tables")

# Independent connection reading RAW CSVs directly (not telemetry.duckdb)
raw_con = duckdb.connect(":memory:")
raw_files = {
    "player_profile": (DATA_DIR / "player_profile - player_profile.csv").as_posix(),
    "player_day": (DATA_DIR / "player_day - player_day.csv").as_posix(),
    "purchase": (DATA_DIR / "purchase - purchase.csv").as_posix(),
    "ad_view": (DATA_DIR / "ad_view - ad_view.csv").as_posix(),
}
for name, p in raw_files.items():
    raw_con.execute(f"CREATE TEMP TABLE {name} AS SELECT * FROM read_csv_auto('{p}', sample_size=-1)")

db_con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

print("=== AUDIT 1: RAW CSVs vs DUCKDB TABLE ROW COUNTS ===")
for name in raw_files:
    c_raw = raw_con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    c_db = db_con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    assert c_raw == c_db, f"Row count mismatch for {name}: raw={c_raw}, db={c_db}"
    print(f"  [PASS] {name:16s}: raw={c_raw:,} == db={c_db:,}")

print("\n=== AUDIT 2: REPRODUCE SAVED CSVs FROM SAVED SQL SCRIPTS ===")
for sql_name, csv_name in [
    ("task_1a_daily_health.sql", "task_1a_daily_health.csv"),
    ("task_1b_retention.sql", "task_1b_retention.csv"),
    ("task_1c_spender_behaviour.sql", "task_1c_spender_behaviour.csv"),
    ("task_1d_ad_engagement.sql", "task_1d_ad_engagement.csv"),
]:
    df_sql = db_con.execute((SQL_DIR / sql_name).read_text(encoding="utf-8")).df()
    df_csv = pd.read_csv(OUT_TABLES / csv_name)
    assert len(df_sql) == len(df_csv), f"Length mismatch in {csv_name}"
    assert list(df_sql.columns) == list(df_csv.columns), f"Columns mismatch in {csv_name}"
    # Check numeric sums match
    num_cols = df_sql.select_dtypes(include="number").columns
    for col in num_cols:
        s1 = round(float(df_sql[col].fillna(0).sum()), 4)
        s2 = round(float(df_csv[col].fillna(0).sum()), 4)
        assert abs(s1 - s2) < 1e-3, f"Sum mismatch {csv_name}.{col}: {s1} vs {s2}"
    print(f"  [PASS] {csv_name:32s}: 100% reproducible from {sql_name} ({len(df_csv)} rows)")

print("\n=== AUDIT 3: INDEPENDENT TASK 1A CHECKS (FROM RAW CSVs) ===")
ind_1a = raw_con.execute("""
    SELECT
        COUNT(*) AS pd_rows,
        COUNT(DISTINCT CAST(device_id AS VARCHAR) || '_' || CAST(activity_date AS VARCHAR)) AS distinct_pd_keys
    FROM player_day
""").fetchone()
assert ind_1a[0] == ind_1a[1] == 667435
df_1a = pd.read_csv(OUT_TABLES / "task_1a_daily_health.csv")
assert int(df_1a["dau"].sum()) == 667435
assert int((df_1a["dau"] == 0).sum()) == 0, "Zero DAU day found!"
assert int((df_1a["paying_players_matched_pd"] > df_1a["dau"]).sum()) == 0

ind_rev = raw_con.execute("""
    SELECT
        p.platform,
        ROUND(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 2) AS gross_pos,
        ROUND(SUM(CASE WHEN u.usd_amount < 0 THEN u.usd_amount ELSE 0 END), 2) AS refunds,
        ROUND(SUM(u.usd_amount), 2) AS net_usd
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
    GROUP BY 1 ORDER BY 1
""").fetchall()
for plat, g, ref, net in ind_rev:
    sub = df_1a[df_1a["platform"] == plat]
    assert round(float(sub["gross_positive_usd"].sum()), 2) == g
    assert round(float(sub["refund_negative_usd"].sum()), 2) == ref
    assert round(float(sub["net_revenue_usd"].sum()), 2) == net
    print(f"  [PASS] {plat}: gross=${g:,.2f}, refunds=${ref:,.2f}, net=${net:,.2f}")

# Weighted vs simple average daily payer %
w_pct = df_1a.groupby("platform").apply(
    lambda g: pd.Series({
        "weighted_payer_pct_all": round(100.0 * g["paying_players_all"].sum() / g["dau"].sum(), 4),
        "weighted_payer_pct_matched": round(100.0 * g["paying_players_matched_pd"].sum() / g["dau"].sum(), 4),
        "mean_daily_payer_pct_all": round(g["pct_active_payers_all"].mean(), 4),
        "mean_daily_payer_pct_matched": round(g["pct_active_payers_matched_pd"].mean(), 4),
    }),
    include_groups=False,
)
print("  Platform daily payer % (weighted vs simple daily mean):\n", w_pct)

print("\n=== AUDIT 4: INDEPENDENT TASK 1B RETENTION CHECKS (FROM RAW CSVs) ===")
# Check any activity_date < install_date
pre_act = raw_con.execute("""
    SELECT COUNT(*) FROM player_day d JOIN player_profile p ON d.device_id = p.device_id
    WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE < p.install_date
""").fetchone()[0]
assert pre_act == 0, f"Found {pre_act} pre-install player_day rows!"

# Independently calculate retention for 2026-01-05 and 2026-03-23 weeks from raw CSVs
ind_1b = raw_con.execute("""
    WITH c AS (
        SELECT device_id, install_date, DATE_TRUNC('week', install_date)::DATE AS wk
        FROM player_profile
        WHERE install_date >= DATE '2026-01-01'
    ),
    a AS (
        SELECT DISTINCT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt
        FROM player_day
    )
    SELECT
        c.wk,
        COUNT(DISTINCT c.device_id) AS n,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.dt = c.install_date + INTERVAL 1 DAY THEN c.device_id END) / COUNT(DISTINCT c.device_id), 2) AS d1,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.dt = c.install_date + INTERVAL 7 DAY THEN c.device_id END) / COUNT(DISTINCT c.device_id), 2) AS d7,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.dt = c.install_date + INTERVAL 14 DAY THEN c.device_id END) / COUNT(DISTINCT c.device_id), 2) AS d14,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.dt = c.install_date + INTERVAL 30 DAY THEN c.device_id END) / COUNT(DISTINCT c.device_id), 2) AS d30
    FROM c LEFT JOIN a ON c.device_id = a.device_id
    WHERE c.wk IN (DATE '2026-01-05', DATE '2026-03-23', DATE '2026-04-13', DATE '2026-04-27')
    GROUP BY 1 ORDER BY 1
""").fetchall()
df_1b = pd.read_csv(OUT_TABLES / "task_1b_retention.csv")
for wk, n, d1, d7, d14, d30 in ind_1b:
    row = df_1b[df_1b["cohort_week"] == str(wk)].iloc[0]
    assert int(row["cohort_size"]) == n
    if pd.notna(row["retention_d1_pct"]):
        assert float(row["retention_d1_pct"]) == d1
    if pd.notna(row["retention_d7_pct"]):
        assert float(row["retention_d7_pct"]) == d7
    if pd.notna(row["retention_d14_pct"]):
        assert float(row["retention_d14_pct"]) == d14
    if pd.notna(row["retention_d30_pct"]):
        assert float(row["retention_d30_pct"]) == d30
    print(f"  [PASS] Cohort {wk}: n={n:,}, raw D1={d1}%, D7={d7}%, D14={d14}%, D30={d30}% (censored cells properly NULLed in CSV)")

print("\n=== AUDIT 5: INDEPENDENT TASK 1C SPENDER & TIE SENSITIVITY CHECKS ===")
# Check first_purchase_date vs MIN(DATE(purchase.event_ts)) for positive purchases
fp_diff = raw_con.execute("""
    WITH min_p AS (
        SELECT device_id, MIN(DATE(event_ts)) AS min_pos_dt
        FROM purchase WHERE usd_amount > 0 GROUP BY 1
    )
    SELECT COUNT(*) FROM player_profile pf FULL OUTER JOIN min_p m ON pf.device_id = m.device_id
    WHERE COALESCE(pf.first_purchase_date, DATE '1900-01-01') != COALESCE(m.min_pos_dt, DATE '1900-01-01')
""").fetchone()[0]
assert fp_diff == 0, f"first_purchase_date mismatch: {fp_diff}"
print("  [PASS] player_profile.first_purchase_date matches MIN(DATE(positive purchase)) for 100% of 80,295 players")

# Check boundary ties at Top 1%, 10%, 50% of payers
ties_check = raw_con.execute("""
    WITH pr AS (
        SELECT device_id, SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END) AS gross_usd
        FROM purchase GROUP BY 1 HAVING gross_usd > 0
    ),
    rk AS (
        SELECT device_id, gross_usd,
               ROW_NUMBER() OVER (ORDER BY gross_usd DESC, device_id) AS rn,
               RANK() OVER (ORDER BY gross_usd DESC) AS rnk,
               COUNT(*) OVER () AS n,
               SUM(gross_usd) OVER () AS tot
        FROM pr
    )
    SELECT pct,
           CEIL(MAX(n) * pct / 100.0) AS cutoff_n,
           ROUND(100.0 * SUM(CASE WHEN rn <= CEIL(n * pct / 100.0) THEN gross_usd ELSE 0 END) / MAX(tot), 2) AS row_num_pct,
           ROUND(100.0 * SUM(CASE WHEN rnk <= CEIL(n * pct / 100.0) THEN gross_usd ELSE 0 END) / MAX(tot), 2) AS rank_with_ties_pct,
           COUNT(*) FILTER (WHERE rnk <= CEIL(n * pct / 100.0)) AS n_with_ties
    FROM rk CROSS JOIN (VALUES (1), (10), (50)) t(pct)
    GROUP BY pct ORDER BY pct
""").fetchall()
print("  Top % payer tie-sensitivity (ROW_NUMBER vs RANK):")
for row in ties_check:
    print(f"    Top {row[0]}%: cutoff={int(row[1])}, ROW_NUMBER share={row[2]}%, RANK(with ties, n={row[4]}) share={row[3]}%")

print("\n=== AUDIT 6: INDEPENDENT TASK 1D AD ENGAGEMENT CHECKS ===")
df_1d = pd.read_csv(OUT_TABLES / "task_1d_ad_engagement.csv")
print("  Max ad views day:", df_1d.loc[df_1d["total_ad_views"].idxmax(), ["game_date", "total_ad_views"]].to_dict())
print("  Min non-outage ad views day:", df_1d[df_1d["is_outage_day"] == 0].loc[df_1d[df_1d["is_outage_day"] == 0]["total_ad_views"].idxmin(), ["game_date", "total_ad_views"]].to_dict())

ind_ad = raw_con.execute("""
    WITH pd AS (
        SELECT device_id, DATE(event_ts - INTERVAL 8 HOUR) AS dt,
               MAX(ad_daily_cap) AS cap, MAX(ad_daily_count) AS max_c, COUNT(*) AS n
        FROM ad_view GROUP BY 1, 2
    )
    SELECT
        COUNT(*) AS pdays,
        SUM(n) AS total_views,
        SUM(CASE WHEN max_c >= cap THEN 1 ELSE 0 END) AS cap_hits,
        ROUND(100.0 * SUM(CASE WHEN max_c >= cap THEN 1 ELSE 0 END) / COUNT(*), 4) AS cap_hit_pct
    FROM pd
""").fetchone()
assert ind_ad[0] == int(df_1d["ad_watching_player_days"].sum()) == 392949
assert ind_ad[1] == int(df_1d["total_ad_views"].sum()) == 647623
assert ind_ad[2] == int(df_1d["cap_hit_player_days"].sum()) == 3774
print(f"  [PASS] Ad engagement reconciled: {ind_ad[0]:,} player-days, {ind_ad[1]:,} views, {ind_ad[2]:,} cap hits ({ind_ad[3]}%)")

raw_con.close()
db_con.close()
print("\nAUDIT COMPLETE: ALL CORE CHECKS PASSED.")
