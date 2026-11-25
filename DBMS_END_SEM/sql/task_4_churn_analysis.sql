-- Deliverable 4: Churn Prediction Dataset Construction (Leak-Free Snapshots)
-- Builds player-level features strictly <= snapshot_date (T) and labels over [T+1, T+14].
-- Population: Players installed <= T who were active at least once in [T-6, T] ("currently active").
-- Snapshots:
--   train: 2026-03-02 (future window Mar 03 - Mar 16)
--   val:   2026-03-23 (future window Mar 24 - Apr 06)
--   test:  2026-04-16 (future window Apr 17 - Apr 30)

WITH snapshots AS (
    SELECT 'train' AS split_name, DATE '2026-03-02' AS snap_date
    UNION ALL SELECT 'val', DATE '2026-03-23'
    UNION ALL SELECT 'test', DATE '2026-04-16'
),
pd_clean AS (
    SELECT
        device_id,
        TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_date,
        player_level,
        session_count,
        playtime_minutes
    FROM player_day
),
ad_aligned AS (
    SELECT
        device_id,
        DATE(event_ts - INTERVAL 8 HOUR) AS game_date,
        status
    FROM ad_view
),
eligible_players AS (
    -- Currently active: installed <= snap_date AND >= 1 active day in [snap_date - 6, snap_date]
    SELECT
        s.split_name,
        s.snap_date,
        pf.device_id,
        pf.install_date,
        pf.platform,
        pf.country_tier,
        pf.acquisition_channel,
        DATEDIFF('day', pf.install_date, s.snap_date) AS install_age_days,
        -- Activity & engagement features strictly <= snap_date
        COUNT(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 6 DAY AND s.snap_date THEN 1 END) AS act_7d,
        COUNT(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 13 DAY AND s.snap_date - INTERVAL 7 DAY THEN 1 END) AS act_prev_7d,
        COUNT(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 13 DAY AND s.snap_date THEN 1 END) AS act_14d,
        COUNT(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 29 DAY AND s.snap_date THEN 1 END) AS act_30d,
        COUNT(CASE WHEN pd.act_date <= s.snap_date THEN 1 END) AS act_lifetime,
        DATEDIFF('day', MAX(CASE WHEN pd.act_date <= s.snap_date THEN pd.act_date END), s.snap_date) AS days_since_last_activity,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 6 DAY AND s.snap_date THEN pd.session_count ELSE 0 END), 0) AS sess_7d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 13 DAY AND s.snap_date THEN pd.session_count ELSE 0 END), 0) AS sess_14d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 29 DAY AND s.snap_date THEN pd.session_count ELSE 0 END), 0) AS sess_30d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 6 DAY AND s.snap_date THEN pd.playtime_minutes ELSE 0.0 END), 0.0) AS play_7d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 13 DAY AND s.snap_date - INTERVAL 7 DAY THEN pd.playtime_minutes ELSE 0.0 END), 0.0) AS play_prev_7d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 13 DAY AND s.snap_date THEN pd.playtime_minutes ELSE 0.0 END), 0.0) AS play_14d,
        COALESCE(SUM(CASE WHEN pd.act_date BETWEEN s.snap_date - INTERVAL 29 DAY AND s.snap_date THEN pd.playtime_minutes ELSE 0.0 END), 0.0) AS play_30d,
        MAX(CASE WHEN pd.act_date <= s.snap_date THEN pd.player_level END) AS level_as_of,
        COALESCE(MAX(CASE WHEN pd.act_date <= s.snap_date - INTERVAL 14 DAY THEN pd.player_level END),
                 MIN(CASE WHEN pd.act_date <= s.snap_date THEN pd.player_level END)) AS level_14d_ago_or_start,
        -- Target label strictly in [snap_date + 1, snap_date + 14]
        CASE WHEN MAX(CASE WHEN pd.act_date BETWEEN s.snap_date + INTERVAL 1 DAY AND s.snap_date + INTERVAL 14 DAY THEN 1 ELSE 0 END) = 0
             THEN 1 ELSE 0 END AS churn_14d
    FROM snapshots s
    JOIN player_profile pf
      ON pf.install_date <= s.snap_date
    JOIN pd_clean pd
      ON pf.device_id = pd.device_id
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
    HAVING act_7d >= 1
),
purch_agg AS (
    SELECT
        e.split_name,
        e.device_id,
        COALESCE(SUM(CASE WHEN DATE(u.event_ts) <= e.snap_date AND u.usd_amount > 0 THEN u.usd_amount ELSE 0.0 END), 0.0) AS gross_spend_lifetime_usd,
        COALESCE(SUM(CASE WHEN DATE(u.event_ts) <= e.snap_date THEN u.usd_amount ELSE 0.0 END), 0.0) AS net_spend_lifetime_usd,
        COALESCE(SUM(CASE WHEN DATE(u.event_ts) BETWEEN e.snap_date - INTERVAL 29 DAY AND e.snap_date AND u.usd_amount > 0 THEN u.usd_amount ELSE 0.0 END), 0.0) AS gross_spend_30d_usd,
        COUNT(CASE WHEN DATE(u.event_ts) <= e.snap_date AND u.usd_amount > 0 THEN 1 END) AS purchase_count_lifetime,
        MAX(CASE WHEN DATE(u.event_ts) <= e.snap_date AND u.usd_amount > 0 THEN DATE(u.event_ts) END) AS last_purchase_date
    FROM eligible_players e
    LEFT JOIN purchase u
      ON e.device_id = u.device_id
     AND DATE(u.event_ts) <= e.snap_date
    GROUP BY 1, 2
),
spend_agg AS (
    SELECT
        e.split_name,
        e.device_id,
        COUNT(CASE WHEN DATE(c.event_ts) BETWEEN e.snap_date - INTERVAL 13 DAY AND e.snap_date THEN 1 END) AS spend_events_14d,
        -- Respect Phase 1 rule: do not sum extreme >10,000 corrupted currency_value outliers into feature totals
        COALESCE(SUM(CASE WHEN DATE(c.event_ts) BETWEEN e.snap_date - INTERVAL 13 DAY AND e.snap_date AND c.currency_value <= 10000 THEN c.currency_value ELSE 0 END), 0) AS clean_currency_spent_14d
    FROM eligible_players e
    LEFT JOIN currency_spend c
      ON e.device_id = c.device_id
     AND DATE(c.event_ts) <= e.snap_date
    GROUP BY 1, 2
),
ad_agg AS (
    SELECT
        e.split_name,
        e.device_id,
        COUNT(CASE WHEN a.game_date BETWEEN e.snap_date - INTERVAL 13 DAY AND e.snap_date THEN 1 END) AS ad_views_14d,
        COUNT(CASE WHEN a.game_date BETWEEN e.snap_date - INTERVAL 13 DAY AND e.snap_date AND a.status = 'completed' THEN 1 END) AS ad_completed_14d
    FROM eligible_players e
    LEFT JOIN ad_aligned a
      ON e.device_id = a.device_id
     AND a.game_date <= e.snap_date
    GROUP BY 1, 2
)
SELECT
    e.split_name,
    e.snap_date,
    e.device_id,
    e.platform,
    e.country_tier,
    e.acquisition_channel,
    e.install_age_days,
    e.act_7d,
    e.act_prev_7d,
    e.act_7d - e.act_prev_7d AS act_trend_7d,
    e.act_14d,
    e.act_30d,
    e.act_lifetime,
    e.days_since_last_activity,
    e.sess_7d,
    e.sess_14d,
    e.sess_30d,
    e.play_7d,
    e.play_prev_7d,
    e.play_7d - e.play_prev_7d AS play_trend_7d,
    e.play_14d,
    e.play_30d,
    ROUND(e.play_30d / NULLIF(e.sess_30d, 0), 4) AS avg_session_duration_30d,
    ROUND(CAST(e.sess_30d AS DOUBLE) / NULLIF(e.act_30d, 0), 4) AS sessions_per_active_day_30d,
    ROUND(e.play_30d / NULLIF(e.act_30d, 0), 4) AS playtime_per_active_day_30d,
    e.level_as_of,
    GREATEST(0, e.level_as_of - e.level_14d_ago_or_start) AS level_gain_14d,
    CASE WHEN p.gross_spend_lifetime_usd > 0 THEN 1 ELSE 0 END AS is_payer_lifetime,
    p.gross_spend_lifetime_usd,
    p.net_spend_lifetime_usd,
    p.gross_spend_30d_usd,
    p.purchase_count_lifetime,
    COALESCE(DATEDIFF('day', p.last_purchase_date, e.snap_date), e.install_age_days + 1) AS days_since_last_purchase_filled,
    s.spend_events_14d,
    s.clean_currency_spent_14d,
    a.ad_views_14d,
    a.ad_completed_14d,
    e.churn_14d
FROM eligible_players e
JOIN purch_agg p ON e.split_name = p.split_name AND e.device_id = p.device_id
JOIN spend_agg s ON e.split_name = s.split_name AND e.device_id = s.device_id
JOIN ad_agg a ON e.split_name = a.split_name AND e.device_id = a.device_id
ORDER BY e.split_name, e.device_id;
