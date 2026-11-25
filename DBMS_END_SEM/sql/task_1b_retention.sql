-- Task 1B: Weekly Install Cohort Retention (Day 1, Day 7, Day 14, Day 30)
-- Denominator rule:
--   Only players installed within the observation window (2026-01-01 to 2026-04-30) are included,
--   because pre-2026 installs had their Day 1..30 milestones before telemetry began.
--   For each milestone N in {1, 7, 14, 30}, a cohort cell is populated ONLY when the entire
--   weekly cohort has completed day N (max_install_date + N <= 2026-04-30), preventing partial-week
--   censoring bias. Eligible player counts are also reported for full transparency.

WITH cohorts AS (
    SELECT
        device_id,
        install_date,
        DATE_TRUNC('week', install_date)::DATE AS cohort_week
    FROM player_profile
    WHERE install_date >= DATE '2026-01-01'
),
activity AS (
    SELECT DISTINCT
        device_id,
        TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_date
    FROM player_day
),
player_milestones AS (
    SELECT
        c.device_id,
        c.cohort_week,
        c.install_date,
        CASE WHEN c.install_date + INTERVAL 1 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END AS obs_d1,
        CASE WHEN c.install_date + INTERVAL 7 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END AS obs_d7,
        CASE WHEN c.install_date + INTERVAL 14 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END AS obs_d14,
        CASE WHEN c.install_date + INTERVAL 30 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END AS obs_d30,
        MAX(CASE WHEN a.act_date = c.install_date + INTERVAL 1 DAY THEN 1 ELSE 0 END) AS ret_d1,
        MAX(CASE WHEN a.act_date = c.install_date + INTERVAL 7 DAY THEN 1 ELSE 0 END) AS ret_d7,
        MAX(CASE WHEN a.act_date = c.install_date + INTERVAL 14 DAY THEN 1 ELSE 0 END) AS ret_d14,
        MAX(CASE WHEN a.act_date = c.install_date + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS ret_d30
    FROM cohorts c
    LEFT JOIN activity a
      ON c.device_id = a.device_id
    GROUP BY 1, 2, 3
)
SELECT
    cohort_week,
    MIN(install_date) AS cohort_start_date,
    MAX(install_date) AS cohort_end_date,
    COUNT(*) AS cohort_size,
    SUM(obs_d1) AS eligible_d1,
    SUM(obs_d7) AS eligible_d7,
    SUM(obs_d14) AS eligible_d14,
    SUM(obs_d30) AS eligible_d30,
    CASE WHEN MAX(install_date) + INTERVAL 1 DAY <= DATE '2026-04-30' THEN SUM(ret_d1) ELSE NULL END AS retained_d1,
    CASE WHEN MAX(install_date) + INTERVAL 7 DAY <= DATE '2026-04-30' THEN SUM(ret_d7) ELSE NULL END AS retained_d7,
    CASE WHEN MAX(install_date) + INTERVAL 14 DAY <= DATE '2026-04-30' THEN SUM(ret_d14) ELSE NULL END AS retained_d14,
    CASE WHEN MAX(install_date) + INTERVAL 30 DAY <= DATE '2026-04-30' THEN SUM(ret_d30) ELSE NULL END AS retained_d30,
    CASE WHEN MAX(install_date) + INTERVAL 1 DAY <= DATE '2026-04-30'
         THEN ROUND(100.0 * SUM(ret_d1) / COUNT(*), 2) ELSE NULL END AS retention_d1_pct,
    CASE WHEN MAX(install_date) + INTERVAL 7 DAY <= DATE '2026-04-30'
         THEN ROUND(100.0 * SUM(ret_d7) / COUNT(*), 2) ELSE NULL END AS retention_d7_pct,
    CASE WHEN MAX(install_date) + INTERVAL 14 DAY <= DATE '2026-04-30'
         THEN ROUND(100.0 * SUM(ret_d14) / COUNT(*), 2) ELSE NULL END AS retention_d14_pct,
    CASE WHEN MAX(install_date) + INTERVAL 30 DAY <= DATE '2026-04-30'
         THEN ROUND(100.0 * SUM(ret_d30) / COUNT(*), 2) ELSE NULL END AS retention_d30_pct,
    -- Also provide eligible-only retention % for partially observed latest weeks (for audit)
    CASE WHEN SUM(obs_d1) > 0 THEN ROUND(100.0 * SUM(CASE WHEN obs_d1 = 1 THEN ret_d1 ELSE 0 END) / SUM(obs_d1), 2) ELSE NULL END AS eligible_only_d1_pct,
    CASE WHEN SUM(obs_d7) > 0 THEN ROUND(100.0 * SUM(CASE WHEN obs_d7 = 1 THEN ret_d7 ELSE 0 END) / SUM(obs_d7), 2) ELSE NULL END AS eligible_only_d7_pct,
    CASE WHEN SUM(obs_d14) > 0 THEN ROUND(100.0 * SUM(CASE WHEN obs_d14 = 1 THEN ret_d14 ELSE 0 END) / SUM(obs_d14), 2) ELSE NULL END AS eligible_only_d14_pct,
    CASE WHEN SUM(obs_d30) > 0 THEN ROUND(100.0 * SUM(CASE WHEN obs_d30 = 1 THEN ret_d30 ELSE 0 END) / SUM(obs_d30), 2) ELSE NULL END AS eligible_only_d30_pct
FROM player_milestones
GROUP BY cohort_week
ORDER BY cohort_week;
