-- Deliverable 3: Acquisition Channel Quality Analysis
-- Compares organic, paid_social, and paid_video across profile mix, engagement,
-- real-money revenue, and stratified (country_tier x platform) cohorts.

-- === QUERY 1: CHANNEL PROFILE & CONFOUNDING MIX (ALL 80,295 PLAYERS) ===
WITH pd_devs AS (
    SELECT DISTINCT device_id FROM player_day
),
pu_all AS (
    SELECT device_id,
           SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END) AS gross_usd,
           SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END) AS refund_usd,
           SUM(usd_amount) AS net_usd
    FROM purchase
    GROUP BY 1
)
SELECT
    pf.acquisition_channel,
    COUNT(*) AS total_players,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_of_players_pct,
    SUM(CASE WHEN pf.install_date < DATE '2026-01-01' THEN 1 ELSE 0 END) AS pre_2026_players,
    SUM(CASE WHEN pf.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31' THEN 1 ELSE 0 END) AS elig_30d_players,
    SUM(CASE WHEN pf.install_date BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 1 ELSE 0 END) AS apr_censored_players,
    SUM(CASE WHEN pd.device_id IS NULL THEN 1 ELSE 0 END) AS zero_activity_players,
    SUM(CASE WHEN pf.original_device_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_orig_id_players,
    ROUND(100.0 * SUM(CASE WHEN pf.platform = 'Android' THEN 1 ELSE 0 END) / COUNT(*), 2) AS android_pct,
    ROUND(100.0 * SUM(CASE WHEN pf.platform = 'iOS' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ios_pct,
    ROUND(100.0 * SUM(CASE WHEN pf.country_tier = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier1_pct,
    ROUND(100.0 * SUM(CASE WHEN pf.country_tier = 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier2_pct,
    ROUND(100.0 * SUM(CASE WHEN pf.country_tier = 3 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier3_pct,
    ROUND(100.0 * SUM(CASE WHEN pf.country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier4_pct,
    ROUND(COALESCE(SUM(pu.gross_usd), 0), 2) AS all_window_gross_usd,
    ROUND(COALESCE(SUM(pu.refund_usd), 0), 2) AS all_window_refund_usd,
    ROUND(COALESCE(SUM(pu.net_usd), 0), 2) AS all_window_net_usd
FROM player_profile pf
LEFT JOIN pd_devs pd ON pf.device_id = pd.device_id
LEFT JOIN pu_all pu ON pf.device_id = pu.device_id
GROUP BY 1
ORDER BY total_players DESC;

-- === QUERY 2: INSTALL MONTH x CHANNEL BREAKDOWN ===
SELECT
    CASE WHEN install_date < DATE '2026-01-01' THEN '2025-pre'
         ELSE STRFTIME(install_date, '%Y-%m') END AS install_month,
    acquisition_channel,
    COUNT(*) AS installs,
    ROUND(100.0 * SUM(CASE WHEN country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 2) AS tier4_pct,
    ROUND(100.0 * SUM(CASE WHEN platform = 'Android' THEN 1 ELSE 0 END) / COUNT(*), 2) AS android_pct
FROM player_profile
GROUP BY 1, 2
ORDER BY 1, 2;

-- === QUERY 3: ENGAGEMENT COMPARISON (CLEAN 30D COHORT vs NAIVE ALL PLAYERS) ===
WITH base_all AS (
    SELECT device_id, acquisition_channel, install_date,
           CASE WHEN install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31' THEN 'clean_30d_cohort'
                ELSE 'other_window' END AS cohort_flag
    FROM player_profile
),
pd_metrics AS (
    SELECT
        b.device_id,
        COUNT(*) FILTER (WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY) AS active_days_30d,
        MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
        MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30,
        COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.playtime_minutes ELSE 0 END), 0.0) AS play_30d,
        COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.session_count ELSE 0 END), 0) AS sess_30d,
        COUNT(d.activity_date) AS active_days_any
    FROM base_all b
    LEFT JOIN player_day d ON b.device_id = d.device_id
    GROUP BY 1
)
SELECT
    'clean_30d_cohort_jan_mar' AS population,
    b.acquisition_channel,
    COUNT(*) AS acquired_players,
    SUM(CASE WHEN pm.active_days_30d > 0 THEN 1 ELSE 0 END) AS active_players_30d,
    ROUND(100.0 * AVG(pm.ret_d7), 2) AS retention_d7_pct,
    ROUND(100.0 * AVG(pm.ret_d30), 2) AS retention_d30_pct,
    ROUND(AVG(pm.active_days_30d), 3) AS avg_active_days_per_acquired,
    ROUND(AVG(CASE WHEN pm.active_days_30d > 0 THEN pm.active_days_30d END), 3) AS avg_active_days_per_active,
    ROUND(AVG(pm.play_30d), 2) AS avg_playtime_mins_per_acquired,
    ROUND(AVG(CASE WHEN pm.active_days_30d > 0 THEN pm.play_30d END), 2) AS avg_playtime_mins_per_active,
    ROUND(AVG(pm.sess_30d), 2) AS avg_sessions_per_acquired
FROM base_all b
JOIN pd_metrics pm ON b.device_id = pm.device_id
WHERE b.cohort_flag = 'clean_30d_cohort'
GROUP BY 1, 2

UNION ALL

SELECT
    'naive_all_80295_unadjusted' AS population,
    b.acquisition_channel,
    COUNT(*) AS acquired_players,
    SUM(CASE WHEN pm.active_days_any > 0 THEN 1 ELSE 0 END) AS active_players_30d,
    ROUND(100.0 * AVG(pm.ret_d7), 2) AS retention_d7_pct,
    ROUND(100.0 * AVG(pm.ret_d30), 2) AS retention_d30_pct,
    ROUND(AVG(pm.active_days_30d), 3) AS avg_active_days_per_acquired,
    ROUND(AVG(CASE WHEN pm.active_days_30d > 0 THEN pm.active_days_30d END), 3) AS avg_active_days_per_active,
    ROUND(AVG(pm.play_30d), 2) AS avg_playtime_mins_per_acquired,
    ROUND(AVG(CASE WHEN pm.active_days_30d > 0 THEN pm.play_30d END), 2) AS avg_playtime_mins_per_active,
    ROUND(AVG(pm.sess_30d), 2) AS avg_sessions_per_acquired
FROM base_all b
JOIN pd_metrics pm ON b.device_id = pm.device_id
GROUP BY 1, 2
ORDER BY population, acquisition_channel;

-- === QUERY 4: REVENUE COMPARISON (CLEAN 30D COHORT + ALL-WINDOW RECONCILIATION + DEDUP SENSITIVITY) ===
WITH purchase_dedup AS (
    SELECT * EXCLUDE (rn)
    FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts ASC) AS rn FROM purchase)
    WHERE rn = 1
),
player_rev_30d AS (
    SELECT
        pf.device_id,
        pf.acquisition_channel,
        pf.install_date,
        COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN pf.install_date AND pf.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS gross_30d,
        COALESCE(SUM(CASE WHEN u.usd_amount < 0 AND DATE(u.event_ts) BETWEEN pf.install_date AND pf.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS refund_30d,
        COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN pf.install_date AND pf.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS net_30d,
        COALESCE(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 0.0) AS gross_all,
        COALESCE(SUM(CASE WHEN u.usd_amount < 0 THEN u.usd_amount ELSE 0 END), 0.0) AS refund_all,
        COALESCE(SUM(u.usd_amount), 0.0) AS net_all
    FROM player_profile pf
    LEFT JOIN purchase u ON pf.device_id = u.device_id
    GROUP BY 1, 2, 3
),
player_rev_30d_dedup AS (
    SELECT
        pf.device_id,
        COALESCE(SUM(CASE WHEN u.usd_amount > 0 AND DATE(u.event_ts) BETWEEN pf.install_date AND pf.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS gross_30d_dedup,
        COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN pf.install_date AND pf.install_date + INTERVAL 29 DAY THEN u.usd_amount ELSE 0 END), 0.0) AS net_30d_dedup
    FROM player_profile pf
    LEFT JOIN purchase_dedup u ON pf.device_id = u.device_id
    GROUP BY 1
),
clean_ranked AS (
    SELECT r.*, d.gross_30d_dedup, d.net_30d_dedup,
           ROW_NUMBER() OVER (PARTITION BY r.acquisition_channel ORDER BY r.gross_30d DESC, r.device_id) AS rk,
           COUNT(*) OVER (PARTITION BY r.acquisition_channel) AS ch_n
    FROM player_rev_30d r
    JOIN player_rev_30d_dedup d ON r.device_id = d.device_id
    WHERE r.install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
)
SELECT
    'clean_30d_cohort_jan_mar' AS population,
    acquisition_channel,
    COUNT(*) AS acquired_players,
    SUM(CASE WHEN gross_30d > 0 THEN 1 ELSE 0 END) AS paying_players,
    ROUND(100.0 * AVG(CASE WHEN gross_30d > 0 THEN 1.0 ELSE 0.0 END), 2) AS payer_conversion_pct,
    ROUND(SUM(gross_30d), 2) AS total_gross_usd,
    ROUND(SUM(refund_30d), 2) AS total_refund_usd,
    ROUND(SUM(net_30d), 2) AS total_net_usd,
    ROUND(SUM(gross_30d_dedup), 2) AS total_gross_dedup_usd,
    ROUND(SUM(net_30d_dedup), 2) AS total_net_dedup_usd,
    ROUND(AVG(gross_30d), 4) AS arpu_gross_usd,
    ROUND(AVG(net_30d), 4) AS arpu_net_usd,
    ROUND(AVG(gross_30d_dedup), 4) AS arpu_gross_dedup_usd,
    ROUND(AVG(CASE WHEN gross_30d > 0 THEN gross_30d END), 2) AS arppu_gross_payers_only,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gross_30d), 2) AS p50_all_usd,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY gross_30d), 2) AS p90_all_usd,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY gross_30d), 2) AS p99_all_usd,
    ROUND(MAX(gross_30d), 2) AS max_player_gross_usd,
    ROUND(100.0 * SUM(CASE WHEN rk <= CEIL(0.10 * ch_n) THEN gross_30d ELSE 0 END) / NULLIF(SUM(gross_30d), 0), 2) AS top_10pct_player_rev_share
FROM clean_ranked
GROUP BY 1, 2

UNION ALL

SELECT
    'all_80295_full_window' AS population,
    acquisition_channel,
    COUNT(*) AS acquired_players,
    SUM(CASE WHEN gross_all > 0 THEN 1 ELSE 0 END) AS paying_players,
    ROUND(100.0 * AVG(CASE WHEN gross_all > 0 THEN 1.0 ELSE 0.0 END), 2) AS payer_conversion_pct,
    ROUND(SUM(gross_all), 2) AS total_gross_usd,
    ROUND(SUM(refund_all), 2) AS total_refund_usd,
    ROUND(SUM(net_all), 2) AS total_net_usd,
    NULL::DOUBLE AS total_gross_dedup_usd,
    NULL::DOUBLE AS total_net_dedup_usd,
    ROUND(AVG(gross_all), 4) AS arpu_gross_usd,
    ROUND(AVG(net_all), 4) AS arpu_net_usd,
    NULL::DOUBLE AS arpu_gross_dedup_usd,
    ROUND(AVG(CASE WHEN gross_all > 0 THEN gross_all END), 2) AS arppu_gross_payers_only,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gross_all), 2) AS p50_all_usd,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY gross_all), 2) AS p90_all_usd,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY gross_all), 2) AS p99_all_usd,
    ROUND(MAX(gross_all), 2) AS max_player_gross_usd,
    NULL::DOUBLE AS top_10pct_player_rev_share
FROM player_rev_30d
GROUP BY 1, 2
ORDER BY population, acquisition_channel;

-- === QUERY 5: STRATIFIED BREAKDOWN (COUNTRY_TIER x PLATFORM x CHANNEL, 30D COHORT) ===
WITH base AS (
    SELECT device_id, acquisition_channel, install_date, country_tier, platform
    FROM player_profile
    WHERE install_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
),
pd30 AS (
    SELECT b.device_id,
           COUNT(*) FILTER (WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY) AS active_days_30d,
           MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
           MAX(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE = b.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30,
           COALESCE(SUM(CASE WHEN TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE BETWEEN b.install_date AND b.install_date + INTERVAL 29 DAY THEN d.playtime_minutes ELSE 0 END), 0.0) AS play_30d
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
SELECT
    b.country_tier,
    b.platform,
    b.acquisition_channel,
    COUNT(*) AS n_players,
    ROUND(100.0 * AVG(pd30.ret_d7), 2) AS ret_d7_pct,
    ROUND(100.0 * AVG(pd30.ret_d30), 2) AS ret_d30_pct,
    ROUND(AVG(pd30.active_days_30d), 3) AS avg_active_days_30d,
    ROUND(AVG(pd30.play_30d), 2) AS avg_playtime_30d,
    ROUND(100.0 * AVG(CASE WHEN pu30.gross_30d > 0 THEN 1.0 ELSE 0.0 END), 2) AS payer_30d_pct,
    ROUND(AVG(pu30.gross_30d), 4) AS arpu_gross_30d,
    ROUND(AVG(pu30.net_30d), 4) AS arpu_net_30d
FROM base b
JOIN pd30 ON b.device_id = pd30.device_id
JOIN pu30 ON b.device_id = pu30.device_id
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;

-- === QUERY 6: CLEAN 30D PLAYER-LEVEL EXTRACT FOR STATISTICAL BOOTSTRAP & TESTS ===
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
JOIN pu30 ON b.device_id = pu30.device_id;
