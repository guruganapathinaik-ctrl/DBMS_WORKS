"""Phase 1 Deep Dive: Investigate discovered anomalies, timezone shifts, duplicates, and linkage."""
from pathlib import Path
import duckdb

DATA_DIR = Path("data")
FILES = {
    "player_profile": DATA_DIR / "player_profile - player_profile.csv",
    "player_day": DATA_DIR / "player_day - player_day.csv",
    "purchase": DATA_DIR / "purchase - purchase.csv",
    "currency_spend": DATA_DIR / "currency_spend - currency_spend.csv",
    "ad_view": DATA_DIR / "ad_view - ad_view.csv",
}

con = duckdb.connect()
for name, path in FILES.items():
    p = path.as_posix()
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_csv_auto('{p}', sample_size=-1)")

print("=== 1. PURCHASE DUPLICATE purchase_id & NEGATIVE AMOUNTS ===")
print("Total rows with usd_amount < 0:", con.execute("SELECT COUNT(*), MIN(usd_amount), MAX(usd_amount) FROM purchase WHERE usd_amount < 0").fetchone())
print("Total rows with usd_amount = 0:", con.execute("SELECT COUNT(*) FROM purchase WHERE usd_amount = 0").fetchone()[0])
print("Sample duplicate purchase_id rows:")
for r in con.execute("""
    WITH d AS (SELECT purchase_id FROM purchase GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 5)
    SELECT p.* FROM purchase p JOIN d ON p.purchase_id = d.purchase_id ORDER BY p.purchase_id, p.event_ts
""").fetchall():
    print(" ", r)

print("\nCompare duplicate purchase_ids vs negative usd_amount:")
print(con.execute("""
    WITH d AS (SELECT purchase_id, COUNT(*) AS cnt, MIN(usd_amount) AS min_u, MAX(usd_amount) AS max_u, COUNT(DISTINCT device_id) AS devs FROM purchase GROUP BY 1 HAVING COUNT(*) > 1)
    SELECT
        COUNT(*) AS dup_id_groups,
        SUM(CASE WHEN min_u < 0 AND max_u > 0 THEN 1 ELSE 0 END) AS pos_and_neg_pair,
        SUM(CASE WHEN min_u > 0 THEN 1 ELSE 0 END) AS both_pos,
        SUM(CASE WHEN devs > 1 THEN 1 ELSE 0 END) AS diff_devices
    FROM d
""").fetchone())

print("Negative usd_amount rows that do NOT share a purchase_id with a positive row:")
print(con.execute("""
    WITH neg AS (SELECT * FROM purchase WHERE usd_amount <= 0),
         pos AS (SELECT DISTINCT purchase_id FROM purchase WHERE usd_amount > 0)
    SELECT COUNT(*) AS neg_total,
           SUM(CASE WHEN pos.purchase_id IS NOT NULL THEN 1 ELSE 0 END) AS matched_pos_id,
           SUM(CASE WHEN pos.purchase_id IS NULL THEN 1 ELSE 0 END) AS unmatched_neg
    FROM neg LEFT JOIN pos ON neg.purchase_id = pos.purchase_id
""").fetchone())

print("\n=== 2. PURCHASE BEFORE INSTALL_DATE & FIRST_PURCHASE_DATE < INSTALL_DATE ===")
for r in con.execute("""
    SELECT p.device_id, p.original_device_id, p.install_date, p.first_purchase_date, u.purchase_id, u.event_ts, u.usd_amount
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
    WHERE DATE(u.event_ts) < p.install_date
    LIMIT 10
""").fetchall():
    print(" ", r)

print("How many of the 114 purchases before install_date have original_device_id IS NOT NULL?",
      con.execute("""
          SELECT COUNT(*), COUNT(p.original_device_id)
          FROM purchase u JOIN player_profile p ON u.device_id = p.device_id
          WHERE DATE(u.event_ts) < p.install_date
      """).fetchone())

print("\n=== 3. AD_VIEW TIMEZONE SHIFT (+8 HOURS?) & DAILY ANOMALIES ===")
print("ad_view events matching player_day if shifted -8 hours:")
print(con.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN d_raw.device_id IS NOT NULL THEN 1 ELSE 0 END) AS match_raw_date,
        SUM(CASE WHEN d_m8.device_id IS NOT NULL THEN 1 ELSE 0 END) AS match_minus_8h
    FROM ad_view a
    LEFT JOIN player_day d_raw
      ON a.device_id = d_raw.device_id AND CAST(STRFTIME(a.event_ts, '%Y%m%d') AS BIGINT) = d_raw.activity_date
    LEFT JOIN player_day d_m8
      ON a.device_id = d_m8.device_id AND CAST(STRFTIME(a.event_ts - INTERVAL 8 HOUR, '%Y%m%d') AS BIGINT) = d_m8.activity_date
""").fetchone())

print("purchase events matching player_day (raw vs -8h vs +8h vs UTC hour breakdown):")
print(con.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN d_raw.device_id IS NOT NULL THEN 1 ELSE 0 END) AS match_raw_date,
        SUM(CASE WHEN d_m6.device_id IS NOT NULL THEN 1 ELSE 0 END) AS match_minus_6h,
        SUM(CASE WHEN d_p5.device_id IS NOT NULL THEN 1 ELSE 0 END) AS match_plus_5h
    FROM purchase u
    LEFT JOIN player_day d_raw ON u.device_id = d_raw.device_id AND CAST(STRFTIME(u.event_ts, '%Y%m%d') AS BIGINT) = d_raw.activity_date
    LEFT JOIN player_day d_m6 ON u.device_id = d_m6.device_id AND CAST(STRFTIME(u.event_ts - INTERVAL 6 HOUR, '%Y%m%d') AS BIGINT) = d_m6.activity_date
    LEFT JOIN player_day d_p5 ON u.device_id = d_p5.device_id AND CAST(STRFTIME(u.event_ts + INTERVAL 5 HOUR, '%Y%m%d') AS BIGINT) = d_p5.activity_date
""").fetchone())

print("Hour distribution across tables (hour 0..23):")
for tbl in ["purchase", "currency_spend", "ad_view"]:
    hrs = con.execute(f"SELECT EXTRACT(HOUR FROM event_ts) AS hr, COUNT(*) FROM {tbl} GROUP BY 1 ORDER BY 1").fetchall()
    print(f"  {tbl}: min_hr={hrs[0]}, max_hr={hrs[-1]}, top3={sorted(hrs, key=lambda x: -x[1])[:3]}")

print("Purchase rows without player_day on same date - sample 10:")
for r in con.execute("""
    SELECT u.purchase_id, u.device_id, u.event_ts, u.usd_amount,
           (SELECT MIN(activity_date) FROM player_day d WHERE d.device_id = u.device_id) AS min_d,
           (SELECT MAX(activity_date) FROM player_day d WHERE d.device_id = u.device_id) AS max_d,
           (SELECT COUNT(*) FROM player_day d WHERE d.device_id = u.device_id) AS tot_days
    FROM purchase u
    LEFT JOIN player_day d ON u.device_id = d.device_id AND CAST(STRFTIME(u.event_ts, '%Y%m%d') AS BIGINT) = d.activity_date
    WHERE d.device_id IS NULL
    LIMIT 10
""").fetchall():
    print(" ", r)

print("\n=== 4. CLUSTERED TIMESTAMPS (e.g. 23:59:56 & 07:59:56) ===")
for tbl in ["purchase", "currency_spend", "ad_view"]:
    top_times = con.execute(f"""
        SELECT STRFTIME(event_ts, '%H:%M:%S') AS tm, COUNT(*) AS n
        FROM {tbl}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 5
    """).fetchall()
    print(f"  {tbl} top exact HH:MM:SS:", top_times)

print("\n=== 5. AD_VIEW DAILY ANOMALIES (especially March 7 and Jan 1 etc.) ===")
for r in con.execute("""
    SELECT DATE(event_ts - INTERVAL 8 HOUR) AS dt_shifted, COUNT(*) AS cnt,
           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS comp
    FROM ad_view
    GROUP BY 1
    HAVING cnt < 2000 OR (dt_shifted BETWEEN DATE '2026-03-01' AND DATE '2026-03-15')
    ORDER BY 1
""").fetchall():
    print(" ", r)

print("\n=== 6. CURRENCY_SPEND EXTREME VALUES & ZERO VALUES ===")
print("currency_value percentiles & extreme counts:")
print(con.execute("""
    SELECT
        SUM(CASE WHEN currency_value = 0 THEN 1 ELSE 0 END) AS eq_0,
        SUM(CASE WHEN currency_value < 0 THEN 1 ELSE 0 END) AS lt_0,
        SUM(CASE WHEN currency_value > 10000 THEN 1 ELSE 0 END) AS gt_10k,
        SUM(CASE WHEN currency_value > 100000 THEN 1 ELSE 0 END) AS gt_100k,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY currency_value) AS p50,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY currency_value) AS p99,
        PERCENTILE_CONT(0.999) WITHIN GROUP (ORDER BY currency_value) AS p999
    FROM currency_spend
""").fetchone())
print("Top 15 largest currency_value rows:")
for r in con.execute("SELECT * FROM currency_spend ORDER BY currency_value DESC LIMIT 15").fetchall():
    print(" ", r)
print("Sample currency_value = 0 rows:")
for r in con.execute("SELECT * FROM currency_spend WHERE currency_value = 0 LIMIT 5").fetchall():
    print(" ", r)

print("\n=== 7. PLAYERS IN PLAYER_PROFILE WITH 0 ROWS IN PLAYER_DAY ===")
print(con.execute("""
    WITH no_pd AS (
        SELECT p.* FROM player_profile p
        WHERE NOT EXISTS (SELECT 1 FROM player_day d WHERE d.device_id = p.device_id)
    )
    SELECT
        COUNT(*) AS total_no_pd,
        COUNT(original_device_id) AS has_orig_id,
        COUNT(first_purchase_date) AS has_fp,
        SUM(CASE WHEN EXISTS (SELECT 1 FROM purchase u WHERE u.device_id = no_pd.device_id) THEN 1 ELSE 0 END) AS in_purchase,
        SUM(CASE WHEN EXISTS (SELECT 1 FROM currency_spend s WHERE s.device_id = no_pd.device_id) THEN 1 ELSE 0 END) AS in_spend,
        SUM(CASE WHEN EXISTS (SELECT 1 FROM ad_view a WHERE a.device_id = no_pd.device_id) THEN 1 ELSE 0 END) AS in_ad,
        MIN(install_date), MAX(install_date)
    FROM no_pd
""").fetchone())

print("\n=== 8. ORIGINAL_DEVICE_ID SAMPLE PAIRS & SELF-LINK ===")
print("Self-link row:", con.execute("SELECT * FROM player_profile WHERE original_device_id = device_id").fetchall())
print("Sample 10 linked pairs (new vs old):")
for r in con.execute("""
    SELECT n.device_id AS new_id, n.install_date AS new_inst, n.platform AS new_plat, n.country AS new_ctry, n.acquisition_channel AS new_chan,
           o.device_id AS old_id, o.install_date AS old_inst, o.platform AS old_plat, o.country AS old_ctry, o.acquisition_channel AS old_chan
    FROM player_profile n
    JOIN player_profile o ON n.original_device_id = o.device_id
    WHERE n.device_id != o.device_id
    LIMIT 10
""").fetchall():
    print(" ", r)
