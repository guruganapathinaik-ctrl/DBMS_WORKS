-- Deliverable 2 (Option A): "ARPDAU is falling. Fix it."
-- Simpson's Paradox & Country-Tier Composition Deep Dive
-- First 30 days: 2026-01-01 to 2026-01-30
-- Last 30 days:  2026-04-01 to 2026-04-30
-- Note: player_day and purchase are aggregated separately before joining to prevent row multiplication.

-- === QUERY 1: PERIOD COMPARISON ===
WITH pd_daily AS (
    SELECT
        TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt,
        CASE
            WHEN activity_date BETWEEN 20260101 AND 20260130 THEN 'first_30d'
            WHEN activity_date BETWEEN 20260401 AND 20260430 THEN 'last_30d'
        END AS period,
        COUNT(*) AS dau
    FROM player_day
    WHERE activity_date BETWEEN 20260101 AND 20260130
       OR activity_date BETWEEN 20260401 AND 20260430
    GROUP BY 1, 2
),
purch_ranked AS (
    SELECT
        purchase_id,
        device_id,
        DATE(event_ts) AS dt,
        CASE
            WHEN DATE(event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30' THEN 'first_30d'
            WHEN DATE(event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 'last_30d'
        END AS period,
        usd_amount,
        ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts ASC) AS rn_pid
    FROM purchase
    WHERE DATE(event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
       OR DATE(event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
),
purch_daily AS (
    SELECT
        dt,
        period,
        SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END) AS gross_pos_usd,
        SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END) AS refund_usd,
        SUM(usd_amount) AS net_usd,
        SUM(CASE WHEN rn_pid = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END) AS gross_dedup_usd,
        SUM(CASE WHEN rn_pid = 1 THEN usd_amount ELSE 0 END) AS net_dedup_usd
    FROM purch_ranked
    GROUP BY 1, 2
),
daily_joined AS (
    SELECT
        d.period,
        d.dt,
        d.dau,
        COALESCE(u.gross_pos_usd, 0.0) AS gross_pos_usd,
        COALESCE(u.refund_usd, 0.0) AS refund_usd,
        COALESCE(u.net_usd, 0.0) AS net_usd,
        COALESCE(u.gross_pos_usd, 0.0) / d.dau AS daily_gross_arpdau,
        COALESCE(u.net_usd, 0.0) / d.dau AS daily_net_arpdau
    FROM pd_daily d
    LEFT JOIN purch_daily u ON d.dt = u.dt AND d.period = u.period
),
period_unique_players AS (
    SELECT
        CASE
            WHEN activity_date BETWEEN 20260101 AND 20260130 THEN 'first_30d'
            WHEN activity_date BETWEEN 20260401 AND 20260430 THEN 'last_30d'
        END AS period,
        COUNT(DISTINCT device_id) AS unique_active_players
    FROM player_day
    WHERE activity_date BETWEEN 20260101 AND 20260130
       OR activity_date BETWEEN 20260401 AND 20260430
    GROUP BY 1
),
period_dedup AS (
    SELECT
        period,
        ROUND(SUM(gross_dedup_usd), 2) AS gross_dedup_usd,
        ROUND(SUM(net_dedup_usd), 2) AS net_dedup_usd
    FROM purch_daily
    GROUP BY 1
)
SELECT
    dj.period,
    MIN(dj.dt) AS start_date,
    MAX(dj.dt) AS end_date,
    COUNT(*) AS num_days,
    SUM(dj.dau) AS total_active_player_days,
    pup.unique_active_players,
    ROUND(SUM(dj.gross_pos_usd), 2) AS total_gross_revenue_usd,
    ROUND(SUM(dj.refund_usd), 2) AS total_refund_usd,
    ROUND(SUM(dj.net_usd), 2) AS total_net_revenue_usd,
    pdd.gross_dedup_usd,
    pdd.net_dedup_usd,
    ROUND(SUM(dj.gross_pos_usd) / SUM(dj.dau), 6) AS weighted_gross_arpdau_usd,
    ROUND(SUM(dj.net_usd) / SUM(dj.dau), 6) AS weighted_net_arpdau_usd,
    ROUND(pdd.gross_dedup_usd / SUM(dj.dau), 6) AS weighted_gross_dedup_arpdau_usd,
    ROUND(AVG(dj.daily_gross_arpdau), 6) AS daily_avg_gross_arpdau_usd,
    ROUND(AVG(dj.daily_net_arpdau), 6) AS daily_avg_net_arpdau_usd
FROM daily_joined dj
JOIN period_unique_players pup ON dj.period = pup.period
JOIN period_dedup pdd ON dj.period = pdd.period
GROUP BY dj.period, pup.unique_active_players, pdd.gross_dedup_usd, pdd.net_dedup_usd
ORDER BY dj.period;

-- === QUERY 2: COUNTRY TIER COMPARISON ===
WITH pd_tier AS (
    SELECT
        CASE
            WHEN d.activity_date BETWEEN 20260101 AND 20260130 THEN 'first_30d'
            WHEN d.activity_date BETWEEN 20260401 AND 20260430 THEN 'last_30d'
        END AS period,
        p.country_tier,
        COUNT(*) AS active_player_days,
        COUNT(DISTINCT d.device_id) AS unique_active_players
    FROM player_day d
    JOIN player_profile p ON d.device_id = p.device_id
    WHERE d.activity_date BETWEEN 20260101 AND 20260130
       OR d.activity_date BETWEEN 20260401 AND 20260430
    GROUP BY 1, 2
),
purch_tier AS (
    SELECT
        CASE
            WHEN DATE(u.event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30' THEN 'first_30d'
            WHEN DATE(u.event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 'last_30d'
        END AS period,
        p.country_tier,
        ROUND(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 2) AS gross_revenue_usd,
        ROUND(SUM(CASE WHEN u.usd_amount < 0 THEN u.usd_amount ELSE 0 END), 2) AS refund_usd,
        ROUND(SUM(u.usd_amount), 2) AS net_revenue_usd
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
    WHERE DATE(u.event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
       OR DATE(u.event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
    GROUP BY 1, 2
),
combined AS (
    SELECT
        pd.country_tier,
        pd.period,
        pd.active_player_days,
        pd.unique_active_players,
        COALESCE(pu.gross_revenue_usd, 0.0) AS gross_revenue_usd,
        COALESCE(pu.refund_usd, 0.0) AS refund_usd,
        COALESCE(pu.net_revenue_usd, 0.0) AS net_revenue_usd,
        COALESCE(pu.gross_revenue_usd, 0.0) / pd.active_player_days AS weighted_gross_arpdau,
        COALESCE(pu.net_revenue_usd, 0.0) / pd.active_player_days AS weighted_net_arpdau
    FROM pd_tier pd
    LEFT JOIN purch_tier pu ON pd.country_tier = pu.country_tier AND pd.period = pu.period
),
pivoted AS (
    SELECT
        country_tier,
        MAX(CASE WHEN period = 'first_30d' THEN active_player_days END) AS p1_player_days,
        MAX(CASE WHEN period = 'last_30d' THEN active_player_days END) AS p2_player_days,
        MAX(CASE WHEN period = 'first_30d' THEN unique_active_players END) AS p1_unique_players,
        MAX(CASE WHEN period = 'last_30d' THEN unique_active_players END) AS p2_unique_players,
        MAX(CASE WHEN period = 'first_30d' THEN gross_revenue_usd END) AS p1_gross_usd,
        MAX(CASE WHEN period = 'last_30d' THEN gross_revenue_usd END) AS p2_gross_usd,
        MAX(CASE WHEN period = 'first_30d' THEN refund_usd END) AS p1_refund_usd,
        MAX(CASE WHEN period = 'last_30d' THEN refund_usd END) AS p2_refund_usd,
        MAX(CASE WHEN period = 'first_30d' THEN net_revenue_usd END) AS p1_net_usd,
        MAX(CASE WHEN period = 'last_30d' THEN net_revenue_usd END) AS p2_net_usd,
        ROUND(MAX(CASE WHEN period = 'first_30d' THEN weighted_gross_arpdau END), 6) AS p1_gross_arpdau,
        ROUND(MAX(CASE WHEN period = 'last_30d' THEN weighted_gross_arpdau END), 6) AS p2_gross_arpdau,
        ROUND(MAX(CASE WHEN period = 'first_30d' THEN weighted_net_arpdau END), 6) AS p1_net_arpdau,
        ROUND(MAX(CASE WHEN period = 'last_30d' THEN weighted_net_arpdau END), 6) AS p2_net_arpdau
    FROM combined
    GROUP BY country_tier
)
SELECT
    CAST(country_tier AS VARCHAR) AS country_tier,
    p1_player_days,
    p2_player_days,
    p1_unique_players,
    p2_unique_players,
    p1_gross_usd,
    p2_gross_usd,
    p1_refund_usd,
    p2_refund_usd,
    p1_net_usd,
    p2_net_usd,
    p1_gross_arpdau,
    p2_gross_arpdau,
    ROUND(p2_gross_arpdau - p1_gross_arpdau, 6) AS gross_arpdau_diff_usd,
    ROUND(100.0 * (p2_gross_arpdau - p1_gross_arpdau) / p1_gross_arpdau, 2) AS gross_arpdau_pct_change,
    p1_net_arpdau,
    p2_net_arpdau,
    ROUND(100.0 * (p2_net_arpdau - p1_net_arpdau) / p1_net_arpdau, 2) AS net_arpdau_pct_change,
    CASE
        WHEN (p2_gross_arpdau - p1_gross_arpdau) / p1_gross_arpdau > 0.01 THEN 'Improved'
        WHEN (p2_gross_arpdau - p1_gross_arpdau) / p1_gross_arpdau < -0.01 THEN 'Declined'
        ELSE 'Flat'
    END AS tier_direction
FROM pivoted
ORDER BY country_tier;

-- === QUERY 3: PLAYER COMPOSITION & CHANNEL MIX ===
WITH pd_mix AS (
    SELECT
        CASE
            WHEN d.activity_date BETWEEN 20260101 AND 20260130 THEN 'first_30d'
            WHEN d.activity_date BETWEEN 20260401 AND 20260430 THEN 'last_30d'
        END AS period,
        p.country_tier,
        COUNT(*) AS active_player_days,
        COUNT(DISTINCT d.device_id) AS unique_active_players,
        SUM(CASE WHEN p.acquisition_channel = 'paid_video' THEN 1 ELSE 0 END) AS paid_video_player_days,
        SUM(CASE WHEN p.acquisition_channel = 'paid_social' THEN 1 ELSE 0 END) AS paid_social_player_days,
        SUM(CASE WHEN p.acquisition_channel = 'organic' THEN 1 ELSE 0 END) AS organic_player_days
    FROM player_day d
    JOIN player_profile p ON d.device_id = p.device_id
    WHERE d.activity_date BETWEEN 20260101 AND 20260130
       OR d.activity_date BETWEEN 20260401 AND 20260430
    GROUP BY 1, 2
),
purch_mix AS (
    SELECT
        CASE
            WHEN DATE(u.event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30' THEN 'first_30d'
            WHEN DATE(u.event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30' THEN 'last_30d'
        END AS period,
        p.country_tier,
        ROUND(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 2) AS gross_revenue_usd
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
    WHERE DATE(u.event_ts) BETWEEN DATE '2026-01-01' AND DATE '2026-01-30'
       OR DATE(u.event_ts) BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
    GROUP BY 1, 2
)
SELECT
    m.period,
    m.country_tier,
    m.active_player_days,
    ROUND(100.0 * m.active_player_days / SUM(m.active_player_days) OVER (PARTITION BY m.period), 4) AS player_day_share_pct,
    m.unique_active_players,
    ROUND(100.0 * m.unique_active_players / SUM(m.unique_active_players) OVER (PARTITION BY m.period), 4) AS unique_player_share_pct,
    pu.gross_revenue_usd,
    ROUND(100.0 * pu.gross_revenue_usd / SUM(pu.gross_revenue_usd) OVER (PARTITION BY m.period), 4) AS gross_revenue_share_pct,
    m.paid_video_player_days,
    ROUND(100.0 * m.paid_video_player_days / m.active_player_days, 2) AS paid_video_share_pct,
    m.paid_social_player_days,
    m.organic_player_days
FROM pd_mix m
JOIN purch_mix pu ON m.period = pu.period AND m.country_tier = pu.country_tier
ORDER BY m.period, m.country_tier;

-- === QUERY 4: DAILY TIER TRENDS (ALL 120 DAYS FOR CHARTING) ===
WITH pd_d AS (
    SELECT
        TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt,
        p.country_tier,
        COUNT(*) AS dau
    FROM player_day d
    JOIN player_profile p ON d.device_id = p.device_id
    GROUP BY 1, 2
),
pu_d AS (
    SELECT
        DATE(u.event_ts) AS dt,
        p.country_tier,
        SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END) AS gross_usd
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
    GROUP BY 1, 2
)
SELECT
    pd_d.dt,
    pd_d.country_tier,
    pd_d.dau,
    COALESCE(pu_d.gross_usd, 0.0) AS gross_usd,
    COALESCE(pu_d.gross_usd, 0.0) / pd_d.dau AS gross_arpdau
FROM pd_d
LEFT JOIN pu_d ON pd_d.dt = pu_d.dt AND pd_d.country_tier = pu_d.country_tier
ORDER BY pd_d.dt, pd_d.country_tier;
