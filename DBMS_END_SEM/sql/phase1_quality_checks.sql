-- Phase 1 Data Quality & Analytical Decisions Verification SQL
-- Run against outputs/telemetry.duckdb (read-only)

-- 1. Purchase Revenue Reconciliation (Positive, Refunds/Negative, Net, Duplicate IDs, Pre-Install, Unmatched Player-Day)
WITH dup_ids AS (
    SELECT purchase_id
    FROM purchase
    GROUP BY purchase_id
    HAVING COUNT(*) > 1
),
ranked_purchases AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (PARTITION BY p.purchase_id ORDER BY p.event_ts ASC) AS rn_per_purchase_id,
        CASE WHEN d.purchase_id IS NOT NULL THEN 1 ELSE 0 END AS is_dup_purchase_id
    FROM purchase p
    LEFT JOIN dup_ids d ON p.purchase_id = d.purchase_id
),
pd_dates AS (
    SELECT
        device_id,
        TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_date
    FROM player_day
)
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT rp.purchase_id) AS distinct_purchase_ids,
    COUNT(DISTINCT rp.device_id) AS distinct_devices,
    SUM(CASE WHEN rp.usd_amount > 0 THEN 1 ELSE 0 END) AS positive_rows,
    ROUND(SUM(CASE WHEN rp.usd_amount > 0 THEN rp.usd_amount ELSE 0 END), 2) AS gross_positive_usd,
    SUM(CASE WHEN rp.usd_amount < 0 THEN 1 ELSE 0 END) AS negative_rows,
    ROUND(SUM(CASE WHEN rp.usd_amount < 0 THEN rp.usd_amount ELSE 0 END), 2) AS refund_negative_usd,
    ROUND(SUM(rp.usd_amount), 2) AS net_usd_raw,
    SUM(CASE WHEN rp.rn_per_purchase_id > 1 THEN 1 ELSE 0 END) AS excess_dup_rows,
    ROUND(SUM(CASE WHEN rp.rn_per_purchase_id > 1 THEN rp.usd_amount ELSE 0 END), 2) AS excess_dup_usd,
    ROUND(SUM(CASE WHEN rp.rn_per_purchase_id = 1 AND rp.usd_amount > 0 THEN rp.usd_amount ELSE 0 END), 2) AS gross_positive_dedup_usd,
    ROUND(SUM(CASE WHEN rp.rn_per_purchase_id = 1 THEN rp.usd_amount ELSE 0 END), 2) AS net_dedup_usd,
    SUM(CASE WHEN pd.device_id IS NULL THEN 1 ELSE 0 END) AS unmatched_player_day_rows,
    ROUND(SUM(CASE WHEN pd.device_id IS NULL THEN rp.usd_amount ELSE 0 END), 2) AS unmatched_player_day_net_usd,
    SUM(CASE WHEN DATE(rp.event_ts) < pf.install_date THEN 1 ELSE 0 END) AS before_install_rows,
    ROUND(SUM(CASE WHEN DATE(rp.event_ts) < pf.install_date THEN rp.usd_amount ELSE 0 END), 2) AS before_install_net_usd
FROM ranked_purchases rp
JOIN player_profile pf ON rp.device_id = pf.device_id
LEFT JOIN pd_dates pd ON rp.device_id = pd.device_id AND DATE(rp.event_ts) = pd.act_date;
