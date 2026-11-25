-- Task 1A: Daily Health by Date and Platform
-- Aggregates player_day and purchase independently before joining on (activity_date, platform)
-- so unmatched purchases (17.26% of rows) are preserved and no row multiplication occurs.

WITH pd_daily AS (
    SELECT
        TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE AS metric_date,
        p.platform,
        COUNT(DISTINCT d.device_id) AS dau
    FROM player_day d
    JOIN player_profile p
      ON d.device_id = p.device_id
    GROUP BY 1, 2
),
pd_device_day AS (
    SELECT DISTINCT
        d.device_id,
        TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE AS activity_dt
    FROM player_day d
),
purchase_ranked AS (
    SELECT
        u.purchase_id,
        u.device_id,
        DATE(u.event_ts) AS purchase_date,
        p.platform,
        u.usd_amount,
        ROW_NUMBER() OVER (PARTITION BY u.purchase_id ORDER BY u.event_ts ASC) AS rn_pid,
        CASE WHEN pd.device_id IS NOT NULL THEN 1 ELSE 0 END AS is_active_in_player_day
    FROM purchase u
    JOIN player_profile p
      ON u.device_id = p.device_id
    LEFT JOIN pd_device_day pd
      ON u.device_id = pd.device_id
     AND DATE(u.event_ts) = pd.activity_dt
),
purch_daily AS (
    SELECT
        purchase_date AS metric_date,
        platform,
        COUNT(*) AS purchase_rows,
        SUM(CASE WHEN usd_amount > 0 THEN 1 ELSE 0 END) AS positive_tx_count,
        SUM(CASE WHEN usd_amount < 0 THEN 1 ELSE 0 END) AS refund_tx_count,
        ROUND(SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS gross_positive_usd,
        ROUND(SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END), 2) AS refund_negative_usd,
        ROUND(SUM(usd_amount), 2) AS net_revenue_usd,
        -- Sensitivity: deduplicated by earliest event_ts per purchase_id
        ROUND(SUM(CASE WHEN rn_pid = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS gross_positive_dedup_usd,
        ROUND(SUM(CASE WHEN rn_pid = 1 THEN usd_amount ELSE 0 END), 2) AS net_dedup_usd,
        -- Distinct positive buyers (all vs those also present in player_day on that exact day)
        COUNT(DISTINCT CASE WHEN usd_amount > 0 THEN device_id END) AS paying_players_all,
        COUNT(DISTINCT CASE WHEN usd_amount > 0 AND is_active_in_player_day = 1 THEN device_id END) AS paying_players_matched_pd,
        COUNT(DISTINCT CASE WHEN usd_amount > 0 AND is_active_in_player_day = 0 THEN device_id END) AS paying_players_unmatched_pd
    FROM purchase_ranked
    GROUP BY 1, 2
),
spine AS (
    SELECT metric_date, platform FROM pd_daily
    UNION
    SELECT metric_date, platform FROM purch_daily
)
SELECT
    s.metric_date,
    s.platform,
    COALESCE(d.dau, 0) AS dau,
    COALESCE(pu.positive_tx_count, 0) AS positive_tx_count,
    COALESCE(pu.refund_tx_count, 0) AS refund_tx_count,
    COALESCE(pu.gross_positive_usd, 0.0) AS gross_positive_usd,
    COALESCE(pu.refund_negative_usd, 0.0) AS refund_negative_usd,
    COALESCE(pu.net_revenue_usd, 0.0) AS net_revenue_usd,
    COALESCE(pu.gross_positive_dedup_usd, 0.0) AS gross_positive_dedup_usd,
    COALESCE(pu.net_dedup_usd, 0.0) AS net_dedup_usd,
    ROUND(COALESCE(pu.gross_positive_usd, 0.0) / NULLIF(d.dau, 0), 4) AS arpdau_gross_usd,
    ROUND(COALESCE(pu.net_revenue_usd, 0.0) / NULLIF(d.dau, 0), 4) AS arpdau_net_usd,
    COALESCE(pu.paying_players_all, 0) AS paying_players_all,
    COALESCE(pu.paying_players_matched_pd, 0) AS paying_players_matched_pd,
    COALESCE(pu.paying_players_unmatched_pd, 0) AS paying_players_unmatched_pd,
    ROUND(100.0 * COALESCE(pu.paying_players_all, 0) / NULLIF(d.dau, 0), 4) AS pct_active_payers_all,
    ROUND(100.0 * COALESCE(pu.paying_players_matched_pd, 0) / NULLIF(d.dau, 0), 4) AS pct_active_payers_matched_pd
FROM spine s
LEFT JOIN pd_daily d
  ON s.metric_date = d.metric_date AND s.platform = d.platform
LEFT JOIN purch_daily pu
  ON s.metric_date = pu.metric_date AND s.platform = pu.platform
ORDER BY s.metric_date, s.platform;
