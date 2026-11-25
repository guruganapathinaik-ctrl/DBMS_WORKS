-- Task 1D: Rewarded Advertisement Engagement
-- Validates and applies the -8h game-day alignment on ad_view.event_ts (preserving raw timestamps),
-- evaluates daily cap hit rates by cap value (5 vs 8), daily ad volume, status breakdown,
-- and flags the March 5-6 telemetry outage.

WITH ad_aligned AS (
    SELECT
        device_id,
        event_ts AS raw_event_ts,
        event_ts - INTERVAL 8 HOUR AS aligned_ts,
        DATE(event_ts - INTERVAL 8 HOUR) AS game_date,
        status,
        placement,
        reward_type,
        reward_amount,
        ad_daily_count,
        ad_daily_cap
    FROM ad_view
),
player_day_ad AS (
    SELECT
        device_id,
        game_date,
        MAX(ad_daily_cap) AS ad_daily_cap,
        MAX(ad_daily_count) AS max_ad_daily_count,
        COUNT(*) AS total_ad_events,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_events,
        SUM(CASE WHEN status = 'abandoned' THEN 1 ELSE 0 END) AS abandoned_events,
        SUM(CASE WHEN status = 'started' THEN 1 ELSE 0 END) AS started_events,
        CASE WHEN MAX(ad_daily_count) >= MAX(ad_daily_cap) THEN 1 ELSE 0 END AS hit_cap_flag
    FROM ad_aligned
    GROUP BY 1, 2
),
calendar AS (
    SELECT UNNEST(GENERATE_SERIES(DATE '2026-01-01', DATE '2026-04-30', INTERVAL 1 DAY))::DATE AS game_date
),
daily_summary AS (
    SELECT
        c.game_date,
        CASE WHEN c.game_date IN (DATE '2026-03-05', DATE '2026-03-06') THEN 1 ELSE 0 END AS is_outage_day,
        COUNT(p.device_id) AS ad_watching_player_days,
        COALESCE(SUM(p.total_ad_events), 0) AS total_ad_views,
        COALESCE(SUM(p.completed_events), 0) AS completed_views,
        COALESCE(SUM(p.abandoned_events), 0) AS abandoned_views,
        COALESCE(SUM(p.started_events), 0) AS started_views,
        COALESCE(SUM(p.hit_cap_flag), 0) AS cap_hit_player_days,
        ROUND(100.0 * COALESCE(SUM(p.hit_cap_flag), 0) / NULLIF(COUNT(p.device_id), 0), 4) AS pct_player_days_hitting_cap,
        -- Cap = 5 breakdown
        SUM(CASE WHEN p.ad_daily_cap = 5 THEN 1 ELSE 0 END) AS cap5_player_days,
        SUM(CASE WHEN p.ad_daily_cap = 5 AND p.hit_cap_flag = 1 THEN 1 ELSE 0 END) AS cap5_hit_days,
        ROUND(100.0 * SUM(CASE WHEN p.ad_daily_cap = 5 AND p.hit_cap_flag = 1 THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN p.ad_daily_cap = 5 THEN 1 ELSE 0 END), 0), 4) AS cap5_hit_pct,
        -- Cap = 8 breakdown
        SUM(CASE WHEN p.ad_daily_cap = 8 THEN 1 ELSE 0 END) AS cap8_player_days,
        SUM(CASE WHEN p.ad_daily_cap = 8 AND p.hit_cap_flag = 1 THEN 1 ELSE 0 END) AS cap8_hit_days,
        ROUND(100.0 * SUM(CASE WHEN p.ad_daily_cap = 8 AND p.hit_cap_flag = 1 THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN p.ad_daily_cap = 8 THEN 1 ELSE 0 END), 0), 4) AS cap8_hit_pct,
        -- Completion / abandonment rates
        ROUND(100.0 * COALESCE(SUM(p.completed_events), 0) / NULLIF(SUM(p.total_ad_events), 0), 2) AS completion_rate_pct,
        ROUND(100.0 * COALESCE(SUM(p.abandoned_events), 0) / NULLIF(SUM(p.total_ad_events), 0), 2) AS abandonment_rate_pct
    FROM calendar c
    LEFT JOIN player_day_ad p
      ON c.game_date = p.game_date
    GROUP BY 1
)
SELECT * FROM daily_summary
ORDER BY game_date;
