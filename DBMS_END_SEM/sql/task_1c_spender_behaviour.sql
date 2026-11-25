-- Task 1C: Spender Behaviour Analysis
-- Covers:
--   1. Revenue concentration (Top 1%, 10%, 50% of payers AND of all 80,295 players; gross vs net; raw vs dedup)
--   2. Time-to-first-purchase distribution + % never purchasing (split all vs 2026-only installs)
--   3. Repeat purchase gap (consecutive positive purchases via LAG window function; raw vs dedup)

WITH player_rev_raw AS (
    SELECT
        pf.device_id,
        pf.install_date,
        pf.first_purchase_date,
        COALESCE(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 0.0) AS gross_pos_usd,
        COALESCE(SUM(CASE WHEN u.usd_amount < 0 THEN u.usd_amount ELSE 0 END), 0.0) AS refund_usd,
        COALESCE(SUM(u.usd_amount), 0.0) AS net_usd
    FROM player_profile pf
    LEFT JOIN purchase u ON pf.device_id = u.device_id
    GROUP BY 1, 2, 3
),
purchase_dedup AS (
    SELECT * EXCLUDE (rn)
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts ASC) AS rn
        FROM purchase
    )
    WHERE rn = 1
),
player_rev_dedup AS (
    SELECT
        pf.device_id,
        COALESCE(SUM(CASE WHEN u.usd_amount > 0 THEN u.usd_amount ELSE 0 END), 0.0) AS gross_pos_dedup_usd,
        COALESCE(SUM(u.usd_amount), 0.0) AS net_dedup_usd
    FROM player_profile pf
    LEFT JOIN purchase_dedup u ON pf.device_id = u.device_id
    GROUP BY 1
),
payers_ranked AS (
    SELECT
        device_id,
        gross_pos_usd,
        net_usd,
        ROW_NUMBER() OVER (ORDER BY gross_pos_usd DESC, device_id) AS rk_gross,
        COUNT(*) OVER () AS total_payers,
        SUM(gross_pos_usd) OVER () AS tot_gross_usd,
        ROW_NUMBER() OVER (ORDER BY net_usd DESC, device_id) AS rk_net,
        SUM(net_usd) OVER () AS tot_net_usd
    FROM player_rev_raw
    WHERE gross_pos_usd > 0
),
all_players_ranked AS (
    SELECT
        device_id,
        gross_pos_usd,
        net_usd,
        ROW_NUMBER() OVER (ORDER BY gross_pos_usd DESC, device_id) AS rk_gross,
        COUNT(*) OVER () AS total_players,
        SUM(gross_pos_usd) OVER () AS tot_gross_usd,
        ROW_NUMBER() OVER (ORDER BY net_usd DESC, device_id) AS rk_net,
        SUM(net_usd) OVER () AS tot_net_usd
    FROM player_rev_raw
),
payers_dedup_ranked AS (
    SELECT
        device_id,
        gross_pos_dedup_usd,
        net_dedup_usd,
        ROW_NUMBER() OVER (ORDER BY gross_pos_dedup_usd DESC, device_id) AS rk_gross,
        COUNT(*) OVER () AS total_payers,
        SUM(gross_pos_dedup_usd) OVER () AS tot_gross_usd,
        ROW_NUMBER() OVER (ORDER BY net_dedup_usd DESC, device_id) AS rk_net,
        SUM(net_dedup_usd) OVER () AS tot_net_usd
    FROM player_rev_dedup
    WHERE gross_pos_dedup_usd > 0
),
ttfp AS (
    SELECT
        device_id,
        install_date,
        first_purchase_date,
        DATEDIFF('day', install_date, first_purchase_date) AS days_to_first_purchase,
        CASE
            WHEN first_purchase_date IS NULL THEN 'Never purchased'
            WHEN DATEDIFF('day', install_date, first_purchase_date) < 0 THEN 'Pre-install anomaly (<0d)'
            WHEN DATEDIFF('day', install_date, first_purchase_date) = 0 THEN 'Day 0 (install day)'
            WHEN DATEDIFF('day', install_date, first_purchase_date) BETWEEN 1 AND 3 THEN 'Days 1-3'
            WHEN DATEDIFF('day', install_date, first_purchase_date) BETWEEN 4 AND 7 THEN 'Days 4-7'
            WHEN DATEDIFF('day', install_date, first_purchase_date) BETWEEN 8 AND 14 THEN 'Days 8-14'
            WHEN DATEDIFF('day', install_date, first_purchase_date) BETWEEN 15 AND 30 THEN 'Days 15-30'
            WHEN DATEDIFF('day', install_date, first_purchase_date) BETWEEN 31 AND 60 THEN 'Days 31-60'
            ELSE '61+ days'
        END AS ttfp_bucket
    FROM player_profile
),
repeat_gaps_raw AS (
    SELECT
        device_id,
        event_ts,
        LAG(event_ts) OVER (PARTITION BY device_id ORDER BY event_ts ASC) AS prev_ts,
        EXTRACT(EPOCH FROM (event_ts - LAG(event_ts) OVER (PARTITION BY device_id ORDER BY event_ts ASC))) / 86400.0 AS gap_days
    FROM purchase
    WHERE usd_amount > 0
),
repeat_gaps_dedup AS (
    SELECT
        device_id,
        event_ts,
        LAG(event_ts) OVER (PARTITION BY device_id ORDER BY event_ts ASC) AS prev_ts,
        EXTRACT(EPOCH FROM (event_ts - LAG(event_ts) OVER (PARTITION BY device_id ORDER BY event_ts ASC))) / 86400.0 AS gap_days
    FROM purchase_dedup
    WHERE usd_amount > 0
)
-- Combine standardized summary rows into one unified output table with unambiguous columns
SELECT '1_concentration_payers_only_raw' AS section,
       'Top ' || pct || '% of paying players (n=' || CAST(CEIL(MAX(total_payers) * pct / 100.0) AS INT) || ' / ' || MAX(total_payers) || ')' AS metric,
       CAST(CEIL(MAX(total_payers) * pct / 100.0) AS BIGINT) AS count_val,
       ROUND(SUM(CASE WHEN rk_gross <= CEIL(total_payers * pct / 100.0) THEN gross_pos_usd ELSE 0 END), 2) AS gross_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_gross <= CEIL(total_payers * pct / 100.0) THEN gross_pos_usd ELSE 0 END) / MAX(tot_gross_usd), 2) AS gross_share_pct,
       ROUND(SUM(CASE WHEN rk_net <= CEIL(total_payers * pct / 100.0) THEN net_usd ELSE 0 END), 2) AS net_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_net <= CEIL(total_payers * pct / 100.0) THEN net_usd ELSE 0 END) / MAX(tot_net_usd), 2) AS net_share_pct,
       NULL::DOUBLE AS mean_days,
       NULL::DOUBLE AS p25_days,
       NULL::DOUBLE AS median_days,
       NULL::DOUBLE AS p75_days
FROM payers_ranked CROSS JOIN (VALUES (1), (10), (50)) AS t(pct)
GROUP BY pct

UNION ALL

SELECT '2_concentration_all_players_raw' AS section,
       'Top ' || pct || '% of all players (n=' || CAST(CEIL(MAX(total_players) * pct / 100.0) AS INT) || ' / ' || MAX(total_players) || ')' AS metric,
       CAST(CEIL(MAX(total_players) * pct / 100.0) AS BIGINT) AS count_val,
       ROUND(SUM(CASE WHEN rk_gross <= CEIL(total_players * pct / 100.0) THEN gross_pos_usd ELSE 0 END), 2) AS gross_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_gross <= CEIL(total_players * pct / 100.0) THEN gross_pos_usd ELSE 0 END) / MAX(tot_gross_usd), 2) AS gross_share_pct,
       ROUND(SUM(CASE WHEN rk_net <= CEIL(total_players * pct / 100.0) THEN net_usd ELSE 0 END), 2) AS net_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_net <= CEIL(total_players * pct / 100.0) THEN net_usd ELSE 0 END) / MAX(tot_net_usd), 2) AS net_share_pct,
       NULL::DOUBLE AS mean_days,
       NULL::DOUBLE AS p25_days,
       NULL::DOUBLE AS median_days,
       NULL::DOUBLE AS p75_days
FROM all_players_ranked CROSS JOIN (VALUES (1), (10), (50)) AS t(pct)
GROUP BY pct

UNION ALL

SELECT '3_concentration_payers_only_dedup' AS section,
       'Top ' || pct || '% of payers dedup (n=' || CAST(CEIL(MAX(total_payers) * pct / 100.0) AS INT) || ' / ' || MAX(total_payers) || ')' AS metric,
       CAST(CEIL(MAX(total_payers) * pct / 100.0) AS BIGINT) AS count_val,
       ROUND(SUM(CASE WHEN rk_gross <= CEIL(total_payers * pct / 100.0) THEN gross_pos_dedup_usd ELSE 0 END), 2) AS gross_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_gross <= CEIL(total_payers * pct / 100.0) THEN gross_pos_dedup_usd ELSE 0 END) / MAX(tot_gross_usd), 2) AS gross_share_pct,
       ROUND(SUM(CASE WHEN rk_net <= CEIL(total_payers * pct / 100.0) THEN net_dedup_usd ELSE 0 END), 2) AS net_usd,
       ROUND(100.0 * SUM(CASE WHEN rk_net <= CEIL(total_payers * pct / 100.0) THEN net_dedup_usd ELSE 0 END) / MAX(tot_net_usd), 2) AS net_share_pct,
       NULL::DOUBLE AS mean_days,
       NULL::DOUBLE AS p25_days,
       NULL::DOUBLE AS median_days,
       NULL::DOUBLE AS p75_days
FROM payers_dedup_ranked CROSS JOIN (VALUES (1), (10), (50)) AS t(pct)
GROUP BY pct

UNION ALL

SELECT '4_time_to_first_purchase_all' AS section,
       ttfp_bucket AS metric,
       COUNT(*) AS count_val,
       NULL::DOUBLE AS gross_usd,
       ROUND(100.0 * COUNT(*) / 80295.0, 2) AS gross_share_pct,
       NULL::DOUBLE AS net_usd,
       CASE WHEN ttfp_bucket = 'Never purchased' THEN NULL
            ELSE ROUND(100.0 * COUNT(*) / 11054.0, 2) END AS net_share_pct,
       ROUND(AVG(days_to_first_purchase), 2) AS mean_days,
       ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS p25_days,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS median_days,
       ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS p75_days
FROM ttfp
GROUP BY ttfp_bucket

UNION ALL

SELECT '5_time_to_first_purchase_2026_installs' AS section,
       ttfp_bucket AS metric,
       COUNT(*) AS count_val,
       NULL::DOUBLE AS gross_usd,
       ROUND(100.0 * COUNT(*) / 64295.0, 2) AS gross_share_pct,
       NULL::DOUBLE AS net_usd,
       CASE WHEN ttfp_bucket = 'Never purchased' THEN NULL
            ELSE ROUND(100.0 * COUNT(*) / 8379.0, 2) END AS net_share_pct,
       ROUND(AVG(days_to_first_purchase), 2) AS mean_days,
       ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS p25_days,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS median_days,
       ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_first_purchase), 2) AS p75_days
FROM ttfp
WHERE install_date >= DATE '2026-01-01'
GROUP BY ttfp_bucket

UNION ALL

SELECT '6_repeat_purchase_gap_raw' AS section,
       'Consecutive positive purchases (raw, repeat_buyers=' || COUNT(DISTINCT device_id) || ')' AS metric,
       COUNT(*) AS count_val,
       NULL::DOUBLE AS gross_usd,
       NULL::DOUBLE AS gross_share_pct,
       NULL::DOUBLE AS net_usd,
       NULL::DOUBLE AS net_share_pct,
       ROUND(AVG(gap_days), 2) AS mean_days,
       ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gap_days), 2) AS p25_days,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gap_days), 2) AS median_days,
       ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gap_days), 2) AS p75_days
FROM repeat_gaps_raw
WHERE prev_ts IS NOT NULL

UNION ALL

SELECT '7_repeat_purchase_gap_dedup' AS section,
       'Consecutive positive purchases (dedup, repeat_buyers=' || COUNT(DISTINCT device_id) || ')' AS metric,
       COUNT(*) AS count_val,
       NULL::DOUBLE AS gross_usd,
       NULL::DOUBLE AS gross_share_pct,
       NULL::DOUBLE AS net_usd,
       NULL::DOUBLE AS net_share_pct,
       ROUND(AVG(gap_days), 2) AS mean_days,
       ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gap_days), 2) AS p25_days,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gap_days), 2) AS median_days,
       ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gap_days), 2) AS p75_days
FROM repeat_gaps_dedup
WHERE prev_ts IS NOT NULL

ORDER BY section, metric;
