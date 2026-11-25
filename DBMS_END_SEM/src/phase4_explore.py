"""Phase 4 Exploratory Investigation: Activity gaps, return rates, and churn definition."""
import duckdb

con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

print("=== 1. GAP DISTRIBUTION BETWEEN CONSECUTIVE ACTIVE DAYS (PLAYER_DAY) ===")
# For players active on day t, how many days until their next active day (among observed gaps)?
# Also check: if a player has 0 activity in [T+1, T+14], what % come back in [T+15, T+42]?
print(con.execute("""
    WITH pd AS (
        SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt
        FROM player_day
    ),
    gaps AS (
        SELECT device_id, dt,
               LEAD(dt) OVER (PARTITION BY device_id ORDER BY dt) AS next_dt,
               DATEDIFF('day', dt, LEAD(dt) OVER (PARTITION BY device_id ORDER BY dt)) AS gap_days
        FROM pd
        WHERE dt <= DATE '2026-03-15'  -- ensure >=45 days of follow-up to see late returns
    )
    SELECT
        COUNT(*) AS total_active_events_before_mar15,
        SUM(CASE WHEN next_dt IS NULL THEN 1 ELSE 0 END) AS never_returned_by_apr30,
        SUM(CASE WHEN gap_days <= 7 THEN 1 ELSE 0 END) AS returned_within_7d,
        SUM(CASE WHEN gap_days BETWEEN 8 AND 14 THEN 1 ELSE 0 END) AS returned_8_to_14d,
        SUM(CASE WHEN gap_days BETWEEN 15 AND 28 THEN 1 ELSE 0 END) AS returned_15_to_28d,
        SUM(CASE WHEN gap_days > 28 THEN 1 ELSE 0 END) AS returned_after_28d
    FROM gaps
""").fetchone())

print("\n=== 2. RETURN RATE IN NEXT 14D BY DAYS SINCE LAST ACTIVITY (AS OF 2026-03-15) ===")
for r in con.execute("""
    WITH pd AS (
        SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt
        FROM player_day
    ),
    as_of AS (
        SELECT pf.device_id, pf.install_date,
               MAX(CASE WHEN pd.dt <= DATE '2026-03-15' THEN pd.dt END) AS last_act_dt,
               MAX(CASE WHEN pd.dt BETWEEN DATE '2026-03-16' AND DATE '2026-03-29' THEN 1 ELSE 0 END) AS active_next_14d,
               MAX(CASE WHEN pd.dt BETWEEN DATE '2026-03-30' AND DATE '2026-04-30' THEN 1 ELSE 0 END) AS active_after_14d
        FROM player_profile pf
        LEFT JOIN pd ON pf.device_id = pd.device_id
        WHERE pf.install_date <= DATE '2026-03-15'
        GROUP BY 1, 2
    ),
    binned AS (
        SELECT *,
               DATEDIFF('day', last_act_dt, DATE '2026-03-15') AS recency_days,
               CASE
                   WHEN last_act_dt IS NULL THEN 'Never active'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') = 0 THEN '0d (today)'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 1 AND 3 THEN '1-3d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 4 AND 7 THEN '4-7d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 8 AND 14 THEN '8-14d'
                   WHEN DATEDIFF('day', last_act_dt, DATE '2026-03-15') BETWEEN 15 AND 30 THEN '15-30d'
                   ELSE '31+d'
               END AS recency_bin
        FROM as_of
    )
    SELECT recency_bin, COUNT(*) AS players,
           ROUND(100.0 * AVG(active_next_14d), 2) AS pct_active_next_14d,
           ROUND(100.0 * AVG(CASE WHEN active_next_14d = 0 THEN 1.0 ELSE 0.0 END), 2) AS churn_next_14d_pct,
           ROUND(100.0 * AVG(CASE WHEN active_next_14d = 0 AND active_after_14d = 1 THEN 1.0 ELSE 0.0 END), 2) AS late_return_after_14d_pct
    FROM binned GROUP BY 1 ORDER BY 1
""").fetchall():
    print(" ", r)

print("\n=== 3. SNAPSHOT SIZES FOR CANDIDATE AS-OF DATES (ACTIVE IN LAST 7D vs LAST 14D) ===")
for snap in ["2026-02-16", "2026-03-02", "2026-03-23", "2026-04-16"]:
    res = con.execute(f"""
        WITH pd AS (
            SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt
            FROM player_day
        ),
        s AS (
            SELECT pf.device_id,
                   MAX(CASE WHEN pd.dt BETWEEN DATE '{snap}' - INTERVAL 6 DAY AND DATE '{snap}' THEN 1 ELSE 0 END) AS act_7d,
                   MAX(CASE WHEN pd.dt BETWEEN DATE '{snap}' - INTERVAL 13 DAY AND DATE '{snap}' THEN 1 ELSE 0 END) AS act_14d,
                   MAX(CASE WHEN pd.dt BETWEEN DATE '{snap}' + INTERVAL 1 DAY AND DATE '{snap}' + INTERVAL 14 DAY THEN 1 ELSE 0 END) AS fut_14d
            FROM player_profile pf
            LEFT JOIN pd ON pf.device_id = pd.device_id
            WHERE pf.install_date <= DATE '{snap}'
            GROUP BY 1
        )
        SELECT '{snap}' AS snap_date,
               SUM(act_7d) AS active_7d_n,
               ROUND(100.0 * AVG(CASE WHEN act_7d = 1 THEN 1 - fut_14d END), 2) AS churn_rate_act7d,
               SUM(act_14d) AS active_14d_n,
               ROUND(100.0 * AVG(CASE WHEN act_14d = 1 THEN 1 - fut_14d END), 2) AS churn_rate_act14d
        FROM s
    """).fetchone()
    print(" ", res)

con.close()
