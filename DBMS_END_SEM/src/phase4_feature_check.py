"""Quick feature signal & cohort overlap check for Deliverable 4."""
import duckdb

con = duckdb.connect("outputs/telemetry.duckdb", read_only=True)

# Check how many players overlap between Mar 02, Mar 23, Apr 16 active-7d cohorts
print("Cohort sizes & disjointness across T_train=2026-03-02, T_val=2026-03-23, T_test=2026-04-16:")
print(con.execute("""
    WITH pd AS (SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE dt FROM player_day),
         tr AS (SELECT DISTINCT device_id FROM pd WHERE dt BETWEEN DATE '2026-03-02' - 6 AND DATE '2026-03-02'),
         va AS (SELECT DISTINCT device_id FROM pd WHERE dt BETWEEN DATE '2026-03-23' - 6 AND DATE '2026-03-23'),
         te AS (SELECT DISTINCT device_id FROM pd WHERE dt BETWEEN DATE '2026-04-16' - 6 AND DATE '2026-04-16')
    SELECT (SELECT COUNT(*) FROM tr) AS n_train,
           (SELECT COUNT(*) FROM va) AS n_val,
           (SELECT COUNT(*) FROM te) AS n_test,
           (SELECT COUNT(*) FROM te WHERE device_id NOT IN (SELECT device_id FROM tr) AND device_id NOT IN (SELECT device_id FROM va)) AS n_test_unseen_players
""").fetchone())

# Check feature signal at T=2026-03-23 (active in last 7d) comparing churned vs retained
print("\nFeature means by churn_14d at T=2026-03-23:")
for r in con.execute("""
    WITH pd AS (
        SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE dt,
               player_level, session_count, playtime_minutes
        FROM player_day
    ),
    base AS (
        SELECT pf.device_id, pf.install_date, pf.platform, pf.country_tier, pf.acquisition_channel,
               COUNT(*) FILTER (WHERE pd.dt BETWEEN DATE '2026-03-23' - 6 AND DATE '2026-03-23') AS act_7d,
               COUNT(*) FILTER (WHERE pd.dt BETWEEN DATE '2026-03-23' - 13 AND DATE '2026-03-23') AS act_14d,
               COUNT(*) FILTER (WHERE pd.dt BETWEEN DATE '2026-03-23' - 29 AND DATE '2026-03-23') AS act_30d,
               DATE '2026-03-23' - MAX(CASE WHEN pd.dt <= DATE '2026-03-23' THEN pd.dt END) AS recency_days,
               COALESCE(SUM(CASE WHEN pd.dt BETWEEN DATE '2026-03-23' - 6 AND DATE '2026-03-23' THEN pd.playtime_minutes ELSE 0 END), 0) AS play_7d,
               COALESCE(SUM(CASE WHEN pd.dt BETWEEN DATE '2026-03-23' - 6 AND DATE '2026-03-23' THEN pd.session_count ELSE 0 END), 0) AS sess_7d,
               MAX(CASE WHEN pd.dt <= DATE '2026-03-23' THEN pd.player_level END) AS lvl_as_of,
               MAX(CASE WHEN pd.dt BETWEEN DATE '2026-03-24' AND DATE '2026-04-06' THEN 1 ELSE 0 END) AS fut_14d
        FROM player_profile pf
        JOIN pd ON pf.device_id = pd.device_id
        WHERE pf.install_date <= DATE '2026-03-23'
        GROUP BY 1, 2, 3, 4, 5
        HAVING act_7d >= 1
    )
    SELECT 1 - fut_14d AS churn_14d,
           COUNT(*) AS n,
           ROUND(AVG(recency_days), 2) AS avg_recency,
           ROUND(AVG(act_7d), 2) AS avg_act_7d,
           ROUND(AVG(act_14d), 2) AS avg_act_14d,
           ROUND(AVG(act_30d), 2) AS avg_act_30d,
           ROUND(AVG(play_7d), 2) AS avg_play_7d,
           ROUND(AVG(sess_7d), 2) AS avg_sess_7d,
           ROUND(AVG(lvl_as_of), 2) AS avg_level,
           ROUND(AVG(DATE '2026-03-23' - install_date), 1) AS avg_install_age
    FROM base
    GROUP BY 1 ORDER BY 1
""").fetchall():
    print(" ", r)

con.close()
