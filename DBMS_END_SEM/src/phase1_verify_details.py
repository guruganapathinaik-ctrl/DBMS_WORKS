"""Phase 1 Verification: Fast set-based DuckDB queries on materialized tables."""
import duckdb

con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

print("=== A. PURCHASE vs PLAYER_DAY DATE DIFFERENCES ===")
print(con.execute("""
    WITH pd AS (
        SELECT device_id,
               TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_dt
        FROM player_day
    ),
    pd_devs AS (
        SELECT DISTINCT device_id FROM player_day
    ),
    unmatched AS (
        SELECT u.purchase_id, u.device_id, DATE(u.event_ts) AS p_dt
        FROM purchase u
        LEFT JOIN pd ON u.device_id = pd.device_id AND DATE(u.event_ts) = pd.act_dt
        WHERE pd.device_id IS NULL
    )
    SELECT
        COUNT(*) AS unmatched_total,
        COUNT(DISTINCT p_prev.device_id || '_' || u.purchase_id) FILTER (WHERE p_prev.device_id IS NOT NULL) AS active_prev_1d,
        COUNT(DISTINCT p_next.device_id || '_' || u.purchase_id) FILTER (WHERE p_next.device_id IS NOT NULL) AS active_next_1d,
        COUNT(*) FILTER (WHERE pd_devs.device_id IS NOT NULL) AS device_has_any_player_day
    FROM unmatched u
    LEFT JOIN pd p_prev ON u.device_id = p_prev.device_id AND p_prev.act_dt = u.p_dt - INTERVAL 1 DAY
    LEFT JOIN pd p_next ON u.device_id = p_next.device_id AND p_next.act_dt = u.p_dt + INTERVAL 1 DAY
    LEFT JOIN pd_devs ON u.device_id = pd_devs.device_id
""").fetchone())

print("\n=== B. PURCHASE_ID DUPLICATE DETAILS (non-positive groups & sample positive groups) ===")
for r in con.execute("""
    WITH d AS (SELECT purchase_id FROM purchase GROUP BY 1 HAVING COUNT(*) > 1 AND MIN(usd_amount) <= 0)
    SELECT p.* FROM purchase p JOIN d ON p.purchase_id = d.purchase_id ORDER BY p.purchase_id, p.event_ts
""").fetchall():
    print(" ", r)

print("\n=== C. AD_VIEW DAILY COUNTS AROUND 2026-03-01 TO 2026-03-10 & LOW DAYS ===")
for r in con.execute("""
    WITH cal AS (SELECT UNNEST(GENERATE_SERIES(DATE '2026-01-01', DATE '2026-04-30', INTERVAL 1 DAY))::DATE AS dt),
         raw_d AS (SELECT DATE(event_ts) AS dt, COUNT(*) AS raw_cnt FROM ad_view GROUP BY 1),
         sh_d AS (SELECT DATE(event_ts - INTERVAL 8 HOUR) AS dt, COUNT(*) AS sh_cnt FROM ad_view GROUP BY 1)
    SELECT c.dt, COALESCE(r.raw_cnt, 0) AS raw_cnt, COALESCE(s.sh_cnt, 0) AS sh_cnt
    FROM cal c
    LEFT JOIN raw_d r ON c.dt = r.dt
    LEFT JOIN sh_d s ON c.dt = s.dt
    WHERE COALESCE(s.sh_cnt, 0) < 1500
       OR c.dt BETWEEN DATE '2026-03-03' AND DATE '2026-03-10'
    ORDER BY 1
""").fetchall():
    print(" ", r)

print("Raw boundary around 2026-03-05..2026-03-07:")
print("  Max ts < 2026-03-06 16:00:", con.execute("SELECT MAX(event_ts) FROM ad_view WHERE event_ts < TIMESTAMP '2026-03-06 16:00:00'").fetchone())
print("  Min ts >= 2026-03-06 00:00:", con.execute("SELECT MIN(event_ts) FROM ad_view WHERE event_ts >= TIMESTAMP '2026-03-06 00:00:00'").fetchone())
print("  Count on shifted 2026-03-06:", con.execute("SELECT COUNT(*) FROM ad_view WHERE DATE(event_ts - INTERVAL 8 HOUR) = DATE '2026-03-06'").fetchone())

print("\n=== D. CURRENCY_SPEND EXTREME & ZERO VALUE BREAKDOWN ===")
print("currency_value > 10000 by currency_type, spend_type:")
print(con.execute("SELECT currency_type, spend_type, COUNT(*), MIN(currency_value), MAX(currency_value) FROM currency_spend WHERE currency_value > 10000 GROUP BY 1, 2").fetchall())
print("currency_value = 0 by currency_type, spend_type:")
print(con.execute("SELECT currency_type, spend_type, COUNT(*) FROM currency_spend WHERE currency_value = 0 GROUP BY 1, 2").fetchall())
print("Normal range (1..10000) max by currency_type:")
print(con.execute("SELECT currency_type, COUNT(*), MIN(currency_value), PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY currency_value), MAX(currency_value) FROM currency_spend WHERE currency_value BETWEEN 1 AND 10000 GROUP BY 1").fetchall())
print("Gap check (5865..37000):", con.execute("SELECT COUNT(*) FROM currency_spend WHERE currency_value BETWEEN 5865 AND 37000").fetchone()[0])

print("\n=== E. ORIGINAL_DEVICE_ID SAME-DAY OVERLAP (SET-BASED) ===")
print(con.execute("""
    WITH pairs AS (
        SELECT device_id AS new_id, original_device_id AS old_id
        FROM player_profile
        WHERE original_device_id IS NOT NULL AND device_id != original_device_id
    ),
    same_day AS (
        SELECT DISTINCT p.new_id, p.old_id
        FROM pairs p
        JOIN player_day dn ON dn.device_id = p.new_id
        JOIN player_day do_tbl ON do_tbl.device_id = p.old_id AND dn.activity_date = do_tbl.activity_date
    )
    SELECT (SELECT COUNT(*) FROM pairs) AS total_non_self_pairs,
           (SELECT COUNT(*) FROM same_day) AS pairs_active_same_day
""").fetchone())

print("\n=== F. COUNTRY TIER & PLATFORM CHECKS ===")
for r in con.execute("SELECT country_tier, country, COUNT(*) FROM player_profile GROUP BY 1, 2 ORDER BY 1, 3 DESC").fetchall():
    print(" ", r)

print("\n=== G. MISSING CALENDAR DAYS IN ALL TABLES ===")
for tbl, expr in [("player_day", "TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE"),
                  ("purchase", "DATE(event_ts)"),
                  ("currency_spend", "DATE(event_ts)"),
                  ("ad_view", "DATE(event_ts - INTERVAL 8 HOUR)")]:
    miss = con.execute(f"""
        WITH cal AS (SELECT UNNEST(GENERATE_SERIES(DATE '2026-01-01', DATE '2026-04-30', INTERVAL 1 DAY))::DATE AS dt),
             present AS (SELECT DISTINCT {expr} AS dt FROM {tbl})
        SELECT cal.dt FROM cal LEFT JOIN present ON cal.dt = present.dt WHERE present.dt IS NULL ORDER BY 1
    """).fetchall()
    print(f"  {tbl}: missing days = {miss}")

print("\n=== H. AD_DAILY_CAP & CARDINALITY STATS ===")
print("ad_daily_cap by platform / country_tier (sample):")
print(con.execute("""
    SELECT p.country_tier, p.platform, a.ad_daily_cap, COUNT(*)
    FROM ad_view a JOIN player_profile p ON a.device_id = p.device_id
    GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
""").fetchall())

print("Rows per device_id (min, p50, p95, max) across child tables:")
for tbl in ["player_day", "purchase", "currency_spend", "ad_view"]:
    print(" ", tbl, con.execute(f"""
        WITH c AS (SELECT device_id, COUNT(*) AS n FROM {tbl} GROUP BY 1)
        SELECT MIN(n), PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n), PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY n), MAX(n) FROM c
    """).fetchone())

print("23:59:56 / 07:59:56 timestamp clamp check (distribution by date):")
print("  currency_spend 23:59:56 distinct dates:", con.execute("SELECT COUNT(DISTINCT DATE(event_ts)) FROM currency_spend WHERE STRFTIME(event_ts, '%H:%M:%S') = '23:59:56'").fetchone()[0])
print("  ad_view 07:59:56 distinct dates:", con.execute("SELECT COUNT(DISTINCT DATE(event_ts)) FROM ad_view WHERE STRFTIME(event_ts, '%H:%M:%S') = '07:59:56'").fetchone()[0])

con.close()
