"""Phase 3.1-3.3 Exploratory Investigation for Deliverable 3."""
import duckdb

con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

print("=== 1. CHANNEL COUNTS, PERIODS, TIER4%, ANDROID% ===")
for r in con.execute("""
    SELECT acquisition_channel,
           COUNT(*) AS total_players,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct,
           SUM(CASE WHEN install_date < DATE '2026-01-01' THEN 1 ELSE 0 END) AS pre_2026,
           SUM(CASE WHEN install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31' THEN 1 ELSE 0 END) AS jan_mar_30d_elig,
           SUM(CASE WHEN install_date BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 1 ELSE 0 END) AS apr_censored,
           ROUND(100.0 * SUM(CASE WHEN country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier4_pct,
           ROUND(100.0 * SUM(CASE WHEN platform = 'Android' THEN 1 ELSE 0 END) / COUNT(*), 2) AS android_pct
    FROM player_profile GROUP BY 1 ORDER BY 2 DESC
""").fetchall():
    print(" ", r)

print("\n=== 2. CHANNEL x INSTALL MONTH ===")
for r in con.execute("""
    SELECT CASE WHEN install_date < DATE '2026-01-01' THEN '2025-pre' ELSE STRFTIME(install_date, '%Y-%m') END AS ym,
           acquisition_channel,
           COUNT(*) AS n,
           ROUND(100.0 * SUM(CASE WHEN country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS t4_pct,
           ROUND(100.0 * SUM(CASE WHEN platform = 'Android' THEN 1 ELSE 0 END) / COUNT(*), 1) AS and_pct
    FROM player_profile GROUP BY 1, 2 ORDER BY 1, 2
""").fetchall():
    print(" ", r)

print("\n=== 3. NAIVE vs 30D-ELIGIBLE vs STRATIFIED (TIER, PLATFORM, MONTH) ===")
for label, where_clause in [
    ("ALL_80295_NAIVE", "1=1"),
    ("ELIG_30D_JAN_MAR", "pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'"),
    ("ELIG_30D_JAN_FEB_PRE_SURGE", "pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-02-28'"),
]:
    print(f"\n-- {label} --")
    q = f"""
    WITH base AS (
        SELECT pf.device_id, pf.acquisition_channel, pf.install_date, pf.country_tier, pf.platform
        FROM player_profile pf WHERE {where_clause}
    ),
    pd30 AS (
        SELECT b.device_id,
               COUNT(*) FILTER (WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY) AS active_days_30d,
               MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
               MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30,
               COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.playtime_minutes ELSE 0 END), 0) AS play_30d,
               COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.session_count ELSE 0 END), 0) AS sess_30d
        FROM base b LEFT JOIN player_day d ON b.device_id = d.device_id
        GROUP BY 1
    ),
    pu30 AS (
        SELECT b.device_id,
               COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0) AS gross_30d,
               COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0) AS net_30d,
               COALESCE(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 0) AS gross_all,
               COALESCE(SUM(u.usd_amount), 0) AS net_all
        FROM base b LEFT JOIN purchase u ON b.device_id = u.device_id
        GROUP BY 1
    )
    SELECT b.acquisition_channel,
           COUNT(*) AS n,
           ROUND(100.0 * AVG(pd30.ret_d7), 2) AS d7_pct,
           ROUND(100.0 * AVG(pd30.ret_d30), 2) AS d30_pct,
           ROUND(AVG(pd30.active_days_30d), 3) AS avg_act_days_30d,
           ROUND(AVG(pd30.play_30d), 2) AS avg_play_30d,
           ROUND(100.0 * AVG(CASE WHEN pu30.gross_30d > 0 THEN 1.0 ELSE 0.0 END), 2) AS payer_30d_pct,
           ROUND(AVG(pu30.gross_30d), 4) AS arpu_gross_30d,
           ROUND(AVG(pu30.net_30d), 4) AS arpu_net_30d,
           ROUND(AVG(pu30.gross_all), 4) AS arpu_gross_all
    FROM base b
    JOIN pd30 ON b.device_id = pd30.device_id
    JOIN pu30 ON b.device_id = pu30.device_id
    GROUP BY 1 ORDER BY 1
    """
    for r in con.execute(q).fetchall():
        print(" ", r)

print("\n=== 4. STRATIFIED BY COUNTRY_TIER (JAN 1 - MAR 31 30D-ELIGIBLE) ===")
q_tier = """
WITH base AS (
    SELECT pf.device_id, pf.acquisition_channel, pf.install_date, pf.country_tier, pf.platform
    FROM player_profile pf
    WHERE pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
),
pd30 AS (
    SELECT b.device_id,
           COUNT(*) FILTER (WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY) AS active_days_30d,
           MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
           MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30
    FROM base b LEFT JOIN player_day d ON b.device_id = d.device_id
    GROUP BY 1
),
pu30 AS (
    SELECT b.device_id,
           COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0) AS gross_30d
    FROM base b LEFT JOIN purchase u ON b.device_id = u.device_id
    GROUP BY 1
)
SELECT b.country_tier, b.acquisition_channel, COUNT(*) AS n,
       ROUND(100.0 * AVG(pd30.ret_d7), 2) AS d7_pct,
       ROUND(100.0 * AVG(pd30.ret_d30), 2) AS d30_pct,
       ROUND(AVG(pd30.active_days_30d), 3) AS act_days_30d,
       ROUND(100.0 * AVG(CASE WHEN pu30.gross_30d > 0 THEN 1.0 ELSE 0.0 END), 2) AS payer_30d_pct,
       ROUND(AVG(pu30.gross_30d), 4) AS arpu_gross_30d
FROM base b JOIN pd30 ON b.device_id = pd30.device_id JOIN pu30 ON b.device_id = pu30.device_id
GROUP BY 1, 2 ORDER BY 1, 2
"""
for r in con.execute(q_tier).fetchall():
    print(" ", r)

con.close()
