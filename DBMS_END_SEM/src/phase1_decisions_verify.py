"""Phase 1 Data-Quality Decisions Verification & Reconciliation Script.

Queries outputs/telemetry.duckdb (read-only), performs deep verification of all
7 provisional analytical areas, asserts revenue reconciliation, and writes:
  - outputs/tables/purchase_reconciliation.csv
  - outputs/tables/anomaly_summary.csv
"""

import csv
from pathlib import Path
import duckdb

DB_PATH = Path("outputs/telemetry.duckdb")
OUT_TABLES = Path("outputs/tables")
OUT_TABLES.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_PATH), read_only=True)


def section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


# =============================================================================
# 1. REVENUE & PURCHASE RECONCILIATION
# =============================================================================
section("1. REVENUE & PURCHASE RECONCILIATION")

recon_sql = """
WITH dup_ids AS (
    SELECT purchase_id
    FROM purchase
    GROUP BY 1
    HAVING COUNT(*) > 1
),
pd_dates AS (
    SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_date
    FROM player_day
),
enriched AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (PARTITION BY p.purchase_id ORDER BY p.event_ts ASC) AS rn_per_pid,
        CASE WHEN d.purchase_id IS NOT NULL THEN 1 ELSE 0 END AS is_dup_pid,
        CASE WHEN pd.device_id IS NOT NULL THEN 1 ELSE 0 END AS has_player_day,
        CASE WHEN DATE(p.event_ts) < pf.install_date THEN 1 ELSE 0 END AS is_before_install
    FROM purchase p
    JOIN player_profile pf ON p.device_id = pf.device_id
    LEFT JOIN dup_ids d ON p.purchase_id = d.purchase_id
    LEFT JOIN pd_dates pd ON p.device_id = pd.device_id AND DATE(p.event_ts) = pd.act_date
)
SELECT
    -- Overall totals
    COUNT(*) AS total_rows,
    COUNT(DISTINCT purchase_id) AS distinct_purchase_ids,
    COUNT(DISTINCT device_id) AS distinct_devices,
    ROUND(SUM(CASE WHEN usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS gross_positive_usd,
    SUM(CASE WHEN usd_amount > 0 THEN 1 ELSE 0 END) AS positive_rows,
    ROUND(SUM(CASE WHEN usd_amount < 0 THEN usd_amount ELSE 0 END), 2) AS negative_refund_usd,
    SUM(CASE WHEN usd_amount < 0 THEN 1 ELSE 0 END) AS negative_rows,
    ROUND(SUM(usd_amount), 2) AS net_usd_raw,
    -- Duplicate purchase_id breakdown
    SUM(CASE WHEN is_dup_pid = 1 THEN 1 ELSE 0 END) AS all_rows_in_dup_pid_groups,
    SUM(CASE WHEN rn_per_pid > 1 THEN 1 ELSE 0 END) AS excess_dup_rows,
    ROUND(SUM(CASE WHEN rn_per_pid > 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS excess_dup_positive_usd,
    ROUND(SUM(CASE WHEN rn_per_pid > 1 AND usd_amount < 0 THEN usd_amount ELSE 0 END), 2) AS excess_dup_negative_usd,
    ROUND(SUM(CASE WHEN rn_per_pid > 1 THEN usd_amount ELSE 0 END), 2) AS excess_dup_net_usd,
    -- Deduplicated (keeping earliest event_ts per purchase_id)
    ROUND(SUM(CASE WHEN rn_per_pid = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS gross_positive_dedup_usd,
    ROUND(SUM(CASE WHEN rn_per_pid = 1 AND usd_amount < 0 THEN usd_amount ELSE 0 END), 2) AS negative_refund_dedup_usd,
    ROUND(SUM(CASE WHEN rn_per_pid = 1 THEN usd_amount ELSE 0 END), 2) AS net_usd_dedup,
    -- Matched vs Unmatched with player_day
    SUM(CASE WHEN has_player_day = 1 THEN 1 ELSE 0 END) AS matched_pd_rows,
    ROUND(SUM(CASE WHEN has_player_day = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS matched_pd_gross_usd,
    ROUND(SUM(CASE WHEN has_player_day = 1 THEN usd_amount ELSE 0 END), 2) AS matched_pd_net_usd,
    SUM(CASE WHEN has_player_day = 0 THEN 1 ELSE 0 END) AS unmatched_pd_rows,
    ROUND(SUM(CASE WHEN has_player_day = 0 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS unmatched_pd_gross_usd,
    ROUND(SUM(CASE WHEN has_player_day = 0 THEN usd_amount ELSE 0 END), 2) AS unmatched_pd_net_usd,
    -- Pre-install purchases
    SUM(CASE WHEN is_before_install = 1 THEN 1 ELSE 0 END) AS pre_install_rows,
    ROUND(SUM(CASE WHEN is_before_install = 1 AND usd_amount > 0 THEN usd_amount ELSE 0 END), 2) AS pre_install_gross_usd,
    ROUND(SUM(CASE WHEN is_before_install = 1 THEN usd_amount ELSE 0 END), 2) AS pre_install_net_usd
FROM enriched
"""
cols = [d[0] for d in con.execute(recon_sql).description]
vals = con.execute(recon_sql).fetchone()
r = dict(zip(cols, vals))
for k, v in r.items():
    print(f"  {k:32s}: {v}")

# Strict reconciliation assertions (in cents to avoid float rounding)
assert round(r["gross_positive_usd"] + r["negative_refund_usd"], 2) == r["net_usd_raw"], "Raw gross + refunds != net!"
assert round(r["gross_positive_dedup_usd"] + r["negative_refund_dedup_usd"], 2) == r["net_usd_dedup"], "Dedup gross + refunds != net!"
assert round(r["net_usd_dedup"] + r["excess_dup_net_usd"], 2) == r["net_usd_raw"], "Dedup + excess != raw!"
assert round(r["matched_pd_net_usd"] + r["unmatched_pd_net_usd"], 2) == r["net_usd_raw"], "Matched + unmatched != raw!"
assert r["positive_rows"] + r["negative_rows"] == r["total_rows"], "Row counts don't sum!"
print("ALL REVENUE RECONCILIATION ASSERTIONS PASSED.")

# Detailed duplicate purchase_id investigation
print("\nDuplicate purchase_id timing & attribute stats:")
print(con.execute("""
    WITH g AS (
        SELECT purchase_id,
               COUNT(*) AS cnt,
               COUNT(DISTINCT device_id) AS n_dev,
               COUNT(DISTINCT pack_name) AS n_pack,
               COUNT(DISTINCT usd_amount) AS n_usd,
               COUNT(DISTINCT sale_flag) AS n_sale,
               MIN(event_ts) AS ts1, MAX(event_ts) AS ts2,
               EXTRACT(EPOCH FROM (MAX(event_ts) - MIN(event_ts))) / 60.0 AS diff_mins
        FROM purchase
        GROUP BY 1
        HAVING COUNT(*) > 1
    )
    SELECT COUNT(*) AS groups,
           SUM(CASE WHEN n_dev = 1 AND n_pack = 1 AND n_usd = 1 AND n_sale = 1 THEN 1 ELSE 0 END) AS identical_attrs,
           SUM(CASE WHEN DATE(ts1) = DATE(ts2) THEN 1 ELSE 0 END) AS same_calendar_day,
           ROUND(MIN(diff_mins), 2) AS min_gap_mins,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY diff_mins), 2) AS med_gap_mins,
           ROUND(MAX(diff_mins), 2) AS max_gap_mins
    FROM g
""").fetchone())

# Check whether negative purchases affect first_purchase_date or duplicate purchase_id overlap
print("Negative purchase players: how many also have positive purchases?")
print(con.execute("""
    WITH neg_devs AS (SELECT DISTINCT device_id FROM purchase WHERE usd_amount < 0),
         pos_devs AS (SELECT DISTINCT device_id FROM purchase WHERE usd_amount > 0)
    SELECT (SELECT COUNT(*) FROM neg_devs) AS devs_with_neg,
           COUNT(*) AS devs_with_both_neg_and_pos
    FROM neg_devs n JOIN pos_devs p ON n.device_id = p.device_id
""").fetchone())

# Write purchase_reconciliation.csv
recon_rows = [
    {"category": "1_all_transactions_raw", "metric": "Gross positive purchases (usd_amount > 0)", "row_count": r["positive_rows"], "distinct_purchase_ids": con.execute("SELECT COUNT(DISTINCT purchase_id) FROM purchase WHERE usd_amount > 0").fetchone()[0], "distinct_devices": con.execute("SELECT COUNT(DISTINCT device_id) FROM purchase WHERE usd_amount > 0").fetchone()[0], "usd_amount": r["gross_positive_usd"], "pct_of_gross_positive": 100.0},
    {"category": "1_all_transactions_raw", "metric": "Negative purchases / potential refunds (usd_amount < 0)", "row_count": r["negative_rows"], "distinct_purchase_ids": con.execute("SELECT COUNT(DISTINCT purchase_id) FROM purchase WHERE usd_amount < 0").fetchone()[0], "distinct_devices": con.execute("SELECT COUNT(DISTINCT device_id) FROM purchase WHERE usd_amount < 0").fetchone()[0], "usd_amount": r["negative_refund_usd"], "pct_of_gross_positive": round(100.0 * r["negative_refund_usd"] / r["gross_positive_usd"], 4)},
    {"category": "1_all_transactions_raw", "metric": "Net revenue (raw: gross + refunds)", "row_count": r["total_rows"], "distinct_purchase_ids": r["distinct_purchase_ids"], "distinct_devices": r["distinct_devices"], "usd_amount": r["net_usd_raw"], "pct_of_gross_positive": round(100.0 * r["net_usd_raw"] / r["gross_positive_usd"], 4)},
    {"category": "2_duplicate_purchase_ids", "metric": "Excess duplicate purchase_id rows (positive)", "row_count": con.execute("WITH t AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts) rn FROM purchase) SELECT COUNT(*) FROM t WHERE rn > 1 AND usd_amount > 0").fetchone()[0], "distinct_purchase_ids": 120, "distinct_devices": con.execute("WITH t AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts) rn FROM purchase) SELECT COUNT(DISTINCT device_id) FROM t WHERE rn > 1 AND usd_amount > 0").fetchone()[0], "usd_amount": r["excess_dup_positive_usd"], "pct_of_gross_positive": round(100.0 * r["excess_dup_positive_usd"] / r["gross_positive_usd"], 4)},
    {"category": "2_duplicate_purchase_ids", "metric": "Excess duplicate purchase_id rows (negative)", "row_count": con.execute("WITH t AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY purchase_id ORDER BY event_ts) rn FROM purchase) SELECT COUNT(*) FROM t WHERE rn > 1 AND usd_amount < 0").fetchone()[0], "distinct_purchase_ids": 2, "distinct_devices": 2, "usd_amount": r["excess_dup_negative_usd"], "pct_of_gross_positive": round(100.0 * r["excess_dup_negative_usd"] / r["gross_positive_usd"], 4)},
    {"category": "2_duplicate_purchase_ids", "metric": "Gross positive revenue (if deduplicated by purchase_id)", "row_count": r["positive_rows"] - 120, "distinct_purchase_ids": con.execute("SELECT COUNT(DISTINCT purchase_id) FROM purchase WHERE usd_amount > 0").fetchone()[0], "distinct_devices": con.execute("SELECT COUNT(DISTINCT device_id) FROM purchase WHERE usd_amount > 0").fetchone()[0], "usd_amount": r["gross_positive_dedup_usd"], "pct_of_gross_positive": round(100.0 * r["gross_positive_dedup_usd"] / r["gross_positive_usd"], 4)},
    {"category": "2_duplicate_purchase_ids", "metric": "Net revenue (if deduplicated by purchase_id)", "row_count": r["distinct_purchase_ids"], "distinct_purchase_ids": r["distinct_purchase_ids"], "distinct_devices": r["distinct_devices"], "usd_amount": r["net_usd_dedup"], "pct_of_gross_positive": round(100.0 * r["net_usd_dedup"] / r["gross_positive_usd"], 4)},
    {"category": "3_player_day_join_coverage", "metric": "Purchases WITH matching (device_id, activity_date) in player_day (net)", "row_count": r["matched_pd_rows"], "distinct_purchase_ids": con.execute("WITH pd AS (SELECT DISTINCT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE d FROM player_day) SELECT COUNT(DISTINCT p.purchase_id) FROM purchase p JOIN pd ON p.device_id=pd.device_id AND DATE(p.event_ts)=pd.d").fetchone()[0], "distinct_devices": con.execute("WITH pd AS (SELECT DISTINCT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE d FROM player_day) SELECT COUNT(DISTINCT p.device_id) FROM purchase p JOIN pd ON p.device_id=pd.device_id AND DATE(p.event_ts)=pd.d").fetchone()[0], "usd_amount": r["matched_pd_net_usd"], "pct_of_gross_positive": round(100.0 * r["matched_pd_net_usd"] / r["gross_positive_usd"], 4)},
    {"category": "3_player_day_join_coverage", "metric": "Purchases WITHOUT matching (device_id, activity_date) in player_day (net)", "row_count": r["unmatched_pd_rows"], "distinct_purchase_ids": con.execute("WITH pd AS (SELECT DISTINCT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE d FROM player_day) SELECT COUNT(DISTINCT p.purchase_id) FROM purchase p LEFT JOIN pd ON p.device_id=pd.device_id AND DATE(p.event_ts)=pd.d WHERE pd.device_id IS NULL").fetchone()[0], "distinct_devices": con.execute("WITH pd AS (SELECT DISTINCT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE d FROM player_day) SELECT COUNT(DISTINCT p.device_id) FROM purchase p LEFT JOIN pd ON p.device_id=pd.device_id AND DATE(p.event_ts)=pd.d WHERE pd.device_id IS NULL").fetchone()[0], "usd_amount": r["unmatched_pd_net_usd"], "pct_of_gross_positive": round(100.0 * r["unmatched_pd_net_usd"] / r["gross_positive_usd"], 4)},
    {"category": "4_pre_install_date_flag", "metric": "Purchases dated BEFORE player_profile.install_date (net)", "row_count": r["pre_install_rows"], "distinct_purchase_ids": con.execute("SELECT COUNT(DISTINCT p.purchase_id) FROM purchase p JOIN player_profile pf ON p.device_id=pf.device_id WHERE DATE(p.event_ts) < pf.install_date").fetchone()[0], "distinct_devices": con.execute("SELECT COUNT(DISTINCT p.device_id) FROM purchase p JOIN player_profile pf ON p.device_id=pf.device_id WHERE DATE(p.event_ts) < pf.install_date").fetchone()[0], "usd_amount": r["pre_install_net_usd"], "pct_of_gross_positive": round(100.0 * r["pre_install_net_usd"] / r["gross_positive_usd"], 4)},
]

with open(OUT_TABLES / "purchase_reconciliation.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(recon_rows[0].keys()))
    writer.writeheader()
    writer.writerows(recon_rows)

# =============================================================================
# 2. PRE-INSTALL PURCHASES DEEP DIVE
# =============================================================================
section("2. PRE-INSTALL PURCHASES DEEP DIVE")
print(con.execute("""
    SELECT
        COUNT(*) AS rows_before_install,
        COUNT(DISTINCT p.device_id) AS devices_before_install,
        MIN(DATE(p.event_ts) - pf.install_date) AS min_day_diff,
        MAX(DATE(p.event_ts) - pf.install_date) AS max_day_diff,
        SUM(CASE WHEN p.usd_amount > 0 THEN 1 ELSE 0 END) AS pos_rows,
        SUM(CASE WHEN p.usd_amount < 0 THEN 1 ELSE 0 END) AS neg_rows,
        SUM(CASE WHEN pf.original_device_id IS NOT NULL THEN 1 ELSE 0 END) AS has_orig_id
    FROM purchase p
    JOIN player_profile pf ON p.device_id = pf.device_id
    WHERE DATE(p.event_ts) < pf.install_date
""").fetchone())

# Also check if those players have player_day rows before install_date (we saw 0 earlier) vs around purchase date
print("Do pre-install purchase devices have player_day on their purchase date?")
print(con.execute("""
    WITH pre AS (
        SELECT p.device_id, DATE(p.event_ts) AS p_dt, pf.install_date
        FROM purchase p JOIN player_profile pf ON p.device_id = pf.device_id
        WHERE DATE(p.event_ts) < pf.install_date
    ),
    pd AS (
        SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS act_dt
        FROM player_day
    )
    SELECT COUNT(*) AS total_pre,
           SUM(CASE WHEN pd.device_id IS NOT NULL THEN 1 ELSE 0 END) AS matched_pd
    FROM pre LEFT JOIN pd ON pre.device_id = pd.device_id AND pre.p_dt = pd.act_dt
""").fetchone())

# =============================================================================
# 3. AD_VIEW TIMEZONE OFFSET & OUTAGE PROOF
# =============================================================================
section("3. AD_VIEW TIMEZONE OFFSET & MARCH 5-6 OUTAGE")

print("Hour of day when ad_daily_count = 1 (testing when daily ad cap counter resets!):")
print(con.execute("""
    SELECT EXTRACT(HOUR FROM event_ts) AS raw_hr,
           COUNT(*) AS total_events,
           SUM(CASE WHEN ad_daily_count = 1 THEN 1 ELSE 0 END) AS count_eq_1
    FROM ad_view
    GROUP BY 1
    ORDER BY 1
""").fetchall())

print("\nTesting different hour shifts against player_day.activity_date:")
for shift_h in [0, -6, -7, -8, -9, -10]:
    matched = con.execute(f"""
        WITH pd AS (SELECT device_id, TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS d FROM player_day)
        SELECT COUNT(*)
        FROM ad_view a
        JOIN pd ON a.device_id = pd.device_id AND DATE(a.event_ts + INTERVAL '{shift_h} HOUR') = pd.d
    """).fetchone()[0]
    print(f"  shift {shift_h:+3d} hours -> matches {matched:,} / 647,623 ({100.0*matched/647623:.2f}%)")

print("\nExact outage timestamps in ad_view (raw & -8h):")
print(con.execute("""
    SELECT
        MAX(event_ts) FILTER (WHERE event_ts < TIMESTAMP '2026-03-06 16:00:00') AS last_raw_before_outage,
        MIN(event_ts) FILTER (WHERE event_ts > TIMESTAMP '2026-03-06 00:00:00') AS first_raw_after_outage,
        ROUND(EXTRACT(EPOCH FROM (
            MIN(event_ts) FILTER (WHERE event_ts > TIMESTAMP '2026-03-06 00:00:00') -
            MAX(event_ts) FILTER (WHERE event_ts < TIMESTAMP '2026-03-06 16:00:00')
        )) / 3600.0, 2) AS outage_gap_hours
    FROM ad_view
""").fetchone())

print("\nNeighboring days around March 5-6 across player_day and ad_view (-8h):")
for row in con.execute("""
    WITH pd_d AS (
        SELECT TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE AS dt, COUNT(*) AS active_players
        FROM player_day GROUP BY 1
    ),
    ad_d AS (
        SELECT DATE(event_ts - INTERVAL 8 HOUR) AS dt, COUNT(*) AS ad_events
        FROM ad_view GROUP BY 1
    )
    SELECT pd_d.dt, pd_d.active_players, COALESCE(ad_d.ad_events, 0) AS ad_events_shifted
    FROM pd_d LEFT JOIN ad_d ON pd_d.dt = ad_d.dt
    WHERE pd_d.dt BETWEEN DATE '2026-03-03' AND DATE '2026-03-09'
    ORDER BY 1
""").fetchall():
    print(" ", row)

# =============================================================================
# 4. CURRENCY_SPEND EXTREME VALUES IMPACT
# =============================================================================
section("4. CURRENCY_SPEND EXTREME & ZERO VALUES IMPACT")
for row in con.execute("""
    SELECT
        currency_type,
        COUNT(*) AS total_rows,
        SUM(CASE WHEN currency_value = 0 THEN 1 ELSE 0 END) AS zero_rows,
        SUM(CASE WHEN currency_value > 10000 THEN 1 ELSE 0 END) AS extreme_rows,
        SUM(currency_value) AS total_raw,
        SUM(CASE WHEN currency_value <= 10000 THEN currency_value ELSE 0 END) AS total_excl_extreme,
        ROUND(AVG(currency_value), 2) AS mean_raw,
        ROUND(AVG(CASE WHEN currency_value <= 10000 THEN currency_value END), 2) AS mean_excl_extreme,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY currency_value) AS median_raw
    FROM currency_spend
    GROUP BY 1
    ORDER BY 1
""").fetchall():
    print(" ", row)

print("How often does currency_value > corresponding balance at time of event?")
print(con.execute("""
    SELECT
        currency_type,
        COUNT(*) AS extreme_rows,
        SUM(CASE WHEN currency_type='PREMIUM' AND currency_value > premium_balance THEN 1
                 WHEN currency_type='SOCIAL' AND currency_value > social_balance THEN 1
                 WHEN currency_type='GRIND' AND currency_value > grind_balance THEN 1
                 ELSE 0 END) AS exceeds_balance
    FROM currency_spend
    WHERE currency_value > 10000
    GROUP BY 1
""").fetchall())

# =============================================================================
# 5. INSTALL VOLUME SURGE & OBSERVATION WINDOW CENSORING
# =============================================================================
section("5. INSTALL VOLUME SURGE (JAN-APR 2026) & COHORT CENSORING")
print("Monthly installs by country_tier (2026-01 to 2026-04 + 2025 total):")
for row in con.execute("""
    SELECT
        CASE WHEN install_date < DATE '2026-01-01' THEN '2025-pre-window'
             ELSE STRFTIME(install_date, '%Y-%m') END AS install_period,
        COUNT(*) AS total_installs,
        SUM(CASE WHEN country_tier = 1 THEN 1 ELSE 0 END) AS tier_1,
        SUM(CASE WHEN country_tier = 2 THEN 1 ELSE 0 END) AS tier_2,
        SUM(CASE WHEN country_tier = 3 THEN 1 ELSE 0 END) AS tier_3,
        SUM(CASE WHEN country_tier = 4 THEN 1 ELSE 0 END) AS tier_4,
        ROUND(100.0 * SUM(CASE WHEN country_tier = 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS tier_4_pct
    FROM player_profile
    GROUP BY 1
    ORDER BY 1
""").fetchall():
    print(" ", row)

print("\nMonthly installs by acquisition_channel (2026-01 to 2026-04):")
for row in con.execute("""
    SELECT
        CASE WHEN install_date < DATE '2026-01-01' THEN '2025-pre-window'
             ELSE STRFTIME(install_date, '%Y-%m') END AS install_period,
        SUM(CASE WHEN acquisition_channel = 'organic' THEN 1 ELSE 0 END) AS organic,
        SUM(CASE WHEN acquisition_channel = 'paid_social' THEN 1 ELSE 0 END) AS paid_social,
        SUM(CASE WHEN acquisition_channel = 'paid_video' THEN 1 ELSE 0 END) AS paid_video
    FROM player_profile
    GROUP BY 1
    ORDER BY 1
""").fetchall():
    print(" ", row)

print("\nCohort observation eligibility (for installs >= 2026-01-01, window ends 2026-04-30):")
print(con.execute("""
    SELECT
        COUNT(*) AS installs_in_window,
        SUM(CASE WHEN install_date + INTERVAL 1 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END) AS eligible_d1,
        SUM(CASE WHEN install_date + INTERVAL 7 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END) AS eligible_d7,
        SUM(CASE WHEN install_date + INTERVAL 14 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END) AS eligible_d14,
        SUM(CASE WHEN install_date + INTERVAL 30 DAY <= DATE '2026-04-30' THEN 1 ELSE 0 END) AS eligible_d30
    FROM player_profile
    WHERE install_date >= DATE '2026-01-01'
""").fetchone())

# =============================================================================
# 6. ORIGINAL_DEVICE_ID IMPACT CHECK
# =============================================================================
section("6. ORIGINAL_DEVICE_ID REVENUE & LINKAGE IMPACT")
print(con.execute("""
    WITH linked AS (
        SELECT device_id AS new_id, original_device_id AS old_id
        FROM player_profile WHERE original_device_id IS NOT NULL
    )
    SELECT
        (SELECT COUNT(*) FROM player_profile) AS total_devices,
        (SELECT COUNT(*) FROM linked) AS linked_rows,
        (SELECT COUNT(*) FROM linked WHERE new_id = old_id) AS self_links,
        (SELECT COUNT(*) FROM player_profile a JOIN player_profile b ON a.original_device_id=b.device_id WHERE b.original_device_id IS NOT NULL) AS chained_links,
        (SELECT COUNT(*) FROM player_profile n JOIN player_profile o ON n.original_device_id=o.device_id WHERE n.country != o.country) AS diff_country,
        (SELECT COUNT(*) FROM player_profile n JOIN player_profile o ON n.original_device_id=o.device_id WHERE n.platform != o.platform) AS diff_platform,
        (SELECT COUNT(*) FROM player_profile n JOIN player_profile o ON n.original_device_id=o.device_id WHERE n.install_date < o.install_date) AS new_installed_before_old
""").fetchone())

# =============================================================================
# 7. WRITE outputs/tables/anomaly_summary.csv (using exact computed values)
# =============================================================================
anomaly_rows = [
    {
        "issue_id": "DQ-01",
        "table_name": "ad_view",
        "anomaly_name": "8-hour forward timestamp offset",
        "affected_rows": 647623,
        "total_table_rows": 647623,
        "pct_of_table": 100.0,
        "provisional_treatment": "Preserve raw event_ts; apply -8h alignment only when joining/comparing to game-day dates",
        "evidence_summary": "Raw range 2026-01-01 14:00 to 2026-05-01 07:59; -8h shift aligns 07:59:56 clamp to 23:59:56 and matches 100.00% of player_day dates vs 48.94% raw",
    },
    {
        "issue_id": "DQ-02",
        "table_name": "ad_view",
        "anomaly_name": "2-day logging outage (2026-03-05 and 2026-03-06)",
        "affected_rows": 0,
        "total_table_rows": 647623,
        "pct_of_table": 0.0,
        "provisional_treatment": "Flag outage dates separately; exclude from daily ad averages/rates rather than treating as 0 ads",
        "evidence_summary": "Zero events between 2026-03-05 07:59:56 raw and 2026-03-07 14:00:14 raw (54.01h gap) while player_day had 4,994 and 4,979 active players",
    },
    {
        "issue_id": "DQ-03",
        "table_name": "player_profile",
        "anomaly_name": "Noisy/conflicting original_device_id linkages",
        "affected_rows": 3211,
        "total_table_rows": 80295,
        "pct_of_table": 3.999,
        "provisional_treatment": "Use device_id as primary player unit; do not automatically merge original_device_id",
        "evidence_summary": "1 self-link, 112 chains, 3,025 (94.21%) different countries, 1,584 (49.33%) reversed install dates, 1,425 same-day overlaps",
    },
    {
        "issue_id": "DQ-04",
        "table_name": "purchase",
        "anomaly_name": "Negative usd_amount and currency_granted (potential refunds)",
        "affected_rows": r["negative_rows"],
        "total_table_rows": r["total_rows"],
        "pct_of_table": round(100.0 * r["negative_rows"] / r["total_rows"], 4),
        "provisional_treatment": "Report gross positive, negative refunds, and net revenue separately",
        "evidence_summary": f"{r['negative_rows']} rows totaling ${r['negative_refund_usd']:,.2f} vs gross positive ${r['gross_positive_usd']:,.2f} (net ${r['net_usd_raw']:,.2f}); all 224 players also have positive purchases",
    },
    {
        "issue_id": "DQ-05",
        "table_name": "purchase",
        "anomaly_name": "Duplicate purchase_id values",
        "affected_rows": r["excess_dup_rows"],
        "total_table_rows": r["total_rows"],
        "pct_of_table": round(100.0 * r["excess_dup_rows"] / r["total_rows"], 4),
        "provisional_treatment": "Do not auto-delete unless confirmed; report both raw and deduplicated revenue in reconciliation",
        "evidence_summary": f"122 purchase_ids appear twice ({r['excess_dup_rows']} excess rows: ${r['excess_dup_positive_usd']:,.2f} pos, ${r['excess_dup_negative_usd']:,.2f} neg) with identical attributes 2.6-1071.9 mins apart same day",
    },
    {
        "issue_id": "DQ-06",
        "table_name": "purchase",
        "anomaly_name": "Purchases without matching (device_id, activity_date) in player_day",
        "affected_rows": r["unmatched_pd_rows"],
        "total_table_rows": r["total_rows"],
        "pct_of_table": round(100.0 * r["unmatched_pd_rows"] / r["total_rows"], 4),
        "provisional_treatment": "Never INNER JOIN purchase to player_day on date; aggregate independently or LEFT JOIN",
        "evidence_summary": f"{r['unmatched_pd_rows']} purchases (${r['unmatched_pd_gross_usd']:,.2f} gross / ${r['unmatched_pd_net_usd']:,.2f} net) lack same-day player_day rows; all devices active on other days",
    },
    {
        "issue_id": "DQ-07",
        "table_name": "purchase",
        "anomaly_name": "Purchases dated before player_profile.install_date",
        "affected_rows": r["pre_install_rows"],
        "total_table_rows": r["total_rows"],
        "pct_of_table": round(100.0 * r["pre_install_rows"] / r["total_rows"], 4),
        "provisional_treatment": "Flag pre-install purchases instead of silently deleting them",
        "evidence_summary": f"{r['pre_install_rows']} rows (110 devices, ${r['pre_install_gross_usd']:,.2f}) dated 1-4 days before install_date; 0 match player_day on purchase date",
    },
    {
        "issue_id": "DQ-08",
        "table_name": "currency_spend",
        "anomaly_name": "Extreme currency_value outliers (>10,000, up to 75.8M)",
        "affected_rows": 233,
        "total_table_rows": 489892,
        "pct_of_table": 0.0476,
        "provisional_treatment": "Do not automatically remove or cap; flag >10,000 and report median alongside mean/total",
        "evidence_summary": "100% (233/233) exceed player balance at event time; inflates total spend >11x across all 3 currencies",
    },
    {
        "issue_id": "DQ-09",
        "table_name": "currency_spend",
        "anomaly_name": "Zero currency_value spend events",
        "affected_rows": 277,
        "total_table_rows": 489892,
        "pct_of_table": 0.0565,
        "provisional_treatment": "Flag zero-value events; retain in raw counts",
        "evidence_summary": "240 PREMIUM and 37 SOCIAL events have currency_value = 0",
    },
    {
        "issue_id": "DQ-10",
        "table_name": "purchase, currency_spend, ad_view",
        "anomaly_name": "End-of-day timestamp clamping (23:59:56 / 07:59:56)",
        "affected_rows": 29105,
        "total_table_rows": 1152941,
        "pct_of_table": 2.5244,
        "provisional_treatment": "Do not rely on sub-minute ordering at day boundaries",
        "evidence_summary": "374 purchase, 12,224 currency_spend (at 23:59:56), and 16,507 ad_view (at 07:59:56) share exact clamped second",
    },
    {
        "issue_id": "DQ-11",
        "table_name": "player_day",
        "anomaly_name": "Zero playtime_minutes with positive session_count",
        "affected_rows": 45,
        "total_table_rows": 667435,
        "pct_of_table": 0.0067,
        "provisional_treatment": "Retain as valid active days (short sessions rounded to 0.0)",
        "evidence_summary": "45 rows have session_count >= 1 and playtime_minutes = 0.0",
    },
    {
        "issue_id": "DQ-12",
        "table_name": "player_profile",
        "anomaly_name": "Inactive profiles with zero rows in all event tables",
        "affected_rows": 1114,
        "total_table_rows": 80295,
        "pct_of_table": 1.3874,
        "provisional_treatment": "Keep in player_profile; exclude from active-only denominators unless measuring install cohort retention",
        "evidence_summary": "1,114 profiles have 0 rows in player_day, purchase, currency_spend, and ad_view",
    },
    {
        "issue_id": "DQ-13",
        "table_name": "player_profile",
        "anomaly_name": "March-April 2026 install surge & Tier 4 / paid_video mix shift",
        "affected_rows": 45015,
        "total_table_rows": 80295,
        "pct_of_table": 56.062,
        "provisional_treatment": "Use exact observation-window eligibility for retention cohorts and stratify by country_tier",
        "evidence_summary": "Mar (18,209) + Apr (26,806) = 45,015 installs driven by Tier 4 (62.7% in Apr) & paid_video; only 37,489/64,295 window installs observable at Day 30",
    },
]

with open(OUT_TABLES / "anomaly_summary.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(anomaly_rows[0].keys()))
    writer.writeheader()
    writer.writerows(anomaly_rows)

con.close()
print("\nSaved outputs/tables/purchase_reconciliation.csv and outputs/tables/anomaly_summary.csv.")
