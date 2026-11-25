"""Phase 1: Comprehensive Dataset Exploration using Python and DuckDB.

Generates:
  - outputs/tables/row_counts.csv
  - outputs/tables/missing_values.csv
  - outputs/tables/duplicate_checks.csv
And prints detailed diagnostics for Phase 1 reports without modifying original CSVs.
"""

import csv
from pathlib import Path
import duckdb

DATA_DIR = Path("data")
OUT_TABLES = Path("outputs/tables")
OUT_TABLES.mkdir(parents=True, exist_ok=True)

FILES = {
    "player_profile": DATA_DIR / "player_profile - player_profile.csv",
    "player_day": DATA_DIR / "player_day - player_day.csv",
    "purchase": DATA_DIR / "purchase - purchase.csv",
    "currency_spend": DATA_DIR / "currency_spend - currency_spend.csv",
    "ad_view": DATA_DIR / "ad_view - ad_view.csv",
}

con = duckdb.connect()

# Register views for typed tables and raw varchar tables
for name, path in FILES.items():
    p = path.as_posix()
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_csv_auto('{p}', sample_size=-1)")
    con.execute(f"CREATE OR REPLACE VIEW {name}_raw AS SELECT * FROM read_csv('{p}', all_varchar=true, header=true)")


def section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


# ---------------------------------------------------------------------------
# 1. ROW COUNTS & UNIQUE PLAYER COUNTS -> outputs/tables/row_counts.csv
# ---------------------------------------------------------------------------
section("1. ROW COUNTS & UNIQUE PLAYERS")
row_counts_data = []
for name, path in FILES.items():
    res = con.execute(f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT device_id) AS unique_device_ids,
            COUNT(*) - COUNT(device_id) AS null_device_ids
        FROM {name}
    """).fetchone()
    total_rows, uniq_dev, null_dev = res
    row_counts_data.append({
        "table_name": name,
        "csv_filename": path.name,
        "file_size_bytes": path.stat().st_size,
        "total_rows": total_rows,
        "unique_device_ids": uniq_dev,
        "null_device_ids": null_dev,
        "avg_rows_per_device": round(total_rows / uniq_dev, 2) if uniq_dev else 0,
    })
    print(f"{name:16s} | rows={total_rows:>9,} | unique_device_id={uniq_dev:>7,} | null_device_id={null_dev}")

with open(OUT_TABLES / "row_counts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(row_counts_data[0].keys()))
    writer.writeheader()
    writer.writerows(row_counts_data)

# ---------------------------------------------------------------------------
# 2. MISSING VALUES -> outputs/tables/missing_values.csv
# ---------------------------------------------------------------------------
section("2. MISSING VALUES (ALL COLUMNS)")
missing_data = []
for name in FILES:
    desc = con.execute(f"DESCRIBE {name}").fetchall()
    total_rows = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    for col_name, col_type, *_ in desc:
        q = f"""
            SELECT
                COUNT(*) - COUNT(t."{col_name}") AS typed_nulls,
                SUM(CASE WHEN r."{col_name}" IS NULL THEN 1 ELSE 0 END) AS raw_nulls,
                SUM(CASE WHEN r."{col_name}" IS NOT NULL AND TRIM(r."{col_name}") = '' THEN 1 ELSE 0 END) AS blank_strings,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(r."{col_name}", ''))) IN ('null', 'none', 'nan', 'n/a', 'na') THEN 1 ELSE 0 END) AS string_null_tokens
            FROM {name} t
            JOIN (SELECT row_number() OVER () AS rn, * FROM {name}_raw) r ON FALSE
        """
        # Simpler: query typed nulls from typed view and string checks from raw view separately
        typed_nulls = con.execute(f'SELECT COUNT(*) - COUNT("{col_name}") FROM {name}').fetchone()[0]
        raw_stats = con.execute(f"""
            SELECT
                SUM(CASE WHEN "{col_name}" IS NULL THEN 1 ELSE 0 END),
                SUM(CASE WHEN "{col_name}" IS NOT NULL AND TRIM("{col_name}") = '' THEN 1 ELSE 0 END),
                SUM(CASE WHEN LOWER(TRIM(COALESCE("{col_name}", ''))) IN ('null', 'none', 'nan', 'n/a', 'na') THEN 1 ELSE 0 END)
            FROM {name}_raw
        """).fetchone()
        raw_nulls, blank_strings, string_null_tokens = [x or 0 for x in raw_stats]
        missing_pct = round(100.0 * typed_nulls / total_rows, 4) if total_rows else 0.0
        missing_data.append({
            "table_name": name,
            "column_name": col_name,
            "inferred_data_type": col_type,
            "total_rows": total_rows,
            "null_count": typed_nulls,
            "null_pct": missing_pct,
            "raw_null_count": raw_nulls,
            "blank_string_count": blank_strings,
            "string_null_token_count": string_null_tokens,
        })
        if typed_nulls > 0 or blank_strings > 0 or string_null_tokens > 0 or raw_nulls != typed_nulls:
            print(f"  {name}.{col_name} ({col_type}): nulls={typed_nulls:,} ({missing_pct}%), raw_nulls={raw_nulls:,}, blanks={blank_strings}, tokens={string_null_tokens}")

with open(OUT_TABLES / "missing_values.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(missing_data[0].keys()))
    writer.writeheader()
    writer.writerows(missing_data)

print("Non-missing columns omitted above; full details saved to outputs/tables/missing_values.csv.")

# ---------------------------------------------------------------------------
# 3. DUPLICATE CHECKS -> outputs/tables/duplicate_checks.csv
# ---------------------------------------------------------------------------
section("3. DUPLICATE CHECKS")
dup_specs = [
    ("player_profile", "exact_full_row", "*"),
    ("player_profile", "device_id", "device_id"),
    ("player_day", "exact_full_row", "*"),
    ("player_day", "device_id, activity_date", "device_id, activity_date"),
    ("purchase", "exact_full_row", "*"),
    ("purchase", "purchase_id", "purchase_id"),
    ("purchase", "device_id, event_ts", "device_id, event_ts"),
    ("purchase", "device_id, event_ts, pack_name, usd_amount", "device_id, event_ts, pack_name, usd_amount"),
    ("currency_spend", "exact_full_row", "*"),
    ("currency_spend", "device_id, event_ts", "device_id, event_ts"),
    ("currency_spend", "device_id, event_ts, currency_type, currency_value, spend_category", "device_id, event_ts, currency_type, currency_value, spend_category"),
    ("ad_view", "exact_full_row", "*"),
    ("ad_view", "device_id, event_ts", "device_id, event_ts"),
    ("ad_view", "device_id, event_ts, status, placement", "device_id, event_ts, status, placement"),
]

dup_results = []
for tbl, check_name, cols in dup_specs:
    total_rows = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    if cols == "*":
        distinct_groups = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {tbl})").fetchone()[0]
        extra_rows = total_rows - distinct_groups
        dup_groups = con.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT *, COUNT(*) AS _c FROM {tbl} GROUP BY ALL HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
    else:
        distinct_groups = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {cols} FROM {tbl})").fetchone()[0]
        extra_rows = total_rows - distinct_groups
        dup_groups = con.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM {tbl} GROUP BY {cols} HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
    dup_pct = round(100.0 * extra_rows / total_rows, 4) if total_rows else 0.0
    dup_results.append({
        "table_name": tbl,
        "check_scope": check_name,
        "total_rows": total_rows,
        "distinct_keys_or_rows": distinct_groups,
        "duplicate_groups": dup_groups,
        "excess_duplicate_rows": extra_rows,
        "excess_duplicate_pct": dup_pct,
    })
    print(f"  {tbl:15s} | {check_name:58s} | groups={dup_groups:>6,} | excess_rows={extra_rows:>6,} ({dup_pct}%)")

with open(OUT_TABLES / "duplicate_checks.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(dup_results[0].keys()))
    writer.writeheader()
    writer.writerows(dup_results)

# Print sample duplicates if any exist
for tbl, check_name, cols in dup_specs:
    row = next(r for r in dup_results if r["table_name"] == tbl and r["check_scope"] == check_name)
    if row["excess_duplicate_rows"] > 0:
        print(f"\nSample duplicate for {tbl} ({check_name}):")
        if cols == "*":
            q = f"SELECT *, COUNT(*) AS n FROM {tbl} GROUP BY ALL HAVING COUNT(*) > 1 LIMIT 3"
        else:
            q = f"SELECT {cols}, COUNT(*) AS n FROM {tbl} GROUP BY {cols} HAVING COUNT(*) > 1 LIMIT 3"
        for sample in con.execute(q).fetchall():
            print("   ", sample)

# ---------------------------------------------------------------------------
# 4. DATE RANGES & TEMPORAL DISTRIBUTIONS
# ---------------------------------------------------------------------------
section("4. DATE & TIMESTAMP RANGES")
print("player_profile.install_date:", con.execute("SELECT MIN(install_date), MAX(install_date) FROM player_profile").fetchone())
print("player_profile.first_purchase_date:", con.execute("SELECT MIN(first_purchase_date), MAX(first_purchase_date) FROM player_profile").fetchone())
print("player_day.activity_date (YYYYMMDD):", con.execute("SELECT MIN(activity_date), MAX(activity_date), COUNT(DISTINCT activity_date) FROM player_day").fetchone())
print("player_day invalid YYYYMMDD dates:", con.execute("SELECT COUNT(*) FROM player_day WHERE TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d') IS NULL").fetchone()[0])
print("purchase.event_ts:", con.execute("SELECT MIN(event_ts), MAX(event_ts), COUNT(DISTINCT DATE(event_ts)) FROM purchase").fetchone())
print("currency_spend.event_ts:", con.execute("SELECT MIN(event_ts), MAX(event_ts), COUNT(DISTINCT DATE(event_ts)) FROM currency_spend").fetchone())
print("ad_view.event_ts:", con.execute("SELECT MIN(event_ts), MAX(event_ts), COUNT(DISTINCT DATE(event_ts)) FROM ad_view").fetchone())

print("\nInstall volume by month:")
for r in con.execute("""
    SELECT STRFTIME(install_date, '%Y-%m') AS ym, COUNT(*) AS installs
    FROM player_profile GROUP BY 1 ORDER BY 1
""").fetchall():
    print(" ", r)

print("\nInstall volume by week inside 2026-01-01 to 2026-04-30:")
for r in con.execute("""
    SELECT DATE_TRUNC('week', install_date)::DATE AS wk, COUNT(*) AS installs
    FROM player_profile
    WHERE install_date >= DATE '2026-01-01'
    GROUP BY 1 ORDER BY 1
""").fetchall():
    print(" ", r)

# ---------------------------------------------------------------------------
# 5. RELATIONSHIPS & REFERENTIAL INTEGRITY
# ---------------------------------------------------------------------------
section("5. RELATIONSHIPS & REFERENTIAL INTEGRITY")
for child in ["player_day", "purchase", "currency_spend", "ad_view"]:
    res = con.execute(f"""
        SELECT
            COUNT(*) AS child_rows,
            COUNT(DISTINCT c.device_id) AS child_devices,
            SUM(CASE WHEN p.device_id IS NULL THEN 1 ELSE 0 END) AS orphan_rows,
            COUNT(DISTINCT CASE WHEN p.device_id IS NULL THEN c.device_id END) AS orphan_devices
        FROM {child} c
        LEFT JOIN player_profile p ON c.device_id = p.device_id
    """).fetchone()
    print(f"  {child:15s} -> player_profile | rows={res[0]:>7,} | devs={res[1]:>6,} | orphan_rows={res[2]} | orphan_devs={res[3]}")

# Check players in player_profile with 0 rows in player_day, etc.
print("\nProfile devices without activity in child tables:")
for child in ["player_day", "purchase", "currency_spend", "ad_view"]:
    cnt = con.execute(f"""
        SELECT COUNT(*)
        FROM player_profile p
        WHERE NOT EXISTS (SELECT 1 FROM {child} c WHERE c.device_id = p.device_id)
    """).fetchone()[0]
    print(f"  player_profile not in {child:15s}: {cnt:,}")

# Check events occurring on dates with no corresponding player_day row
for child in ["purchase", "currency_spend", "ad_view"]:
    res = con.execute(f"""
        SELECT
            COUNT(*) AS total_events,
            SUM(CASE WHEN d.device_id IS NULL THEN 1 ELSE 0 END) AS events_without_player_day
        FROM {child} c
        LEFT JOIN player_day d
          ON c.device_id = d.device_id
         AND CAST(STRFTIME(c.event_ts, '%Y%m%d') AS BIGINT) = d.activity_date
    """).fetchone()
    print(f"  {child:15s} events without matching (device_id, activity_date) in player_day: {res[1]:,} / {res[0]:,}")

# ---------------------------------------------------------------------------
# 6. ORIGINAL_DEVICE_ID & LINKED IDENTITIES
# ---------------------------------------------------------------------------
section("6. ORIGINAL_DEVICE_ID INVESTIGATION")
orig_stats = con.execute("""
    SELECT
        COUNT(*) AS total_profiles,
        COUNT(original_device_id) AS linked_profiles,
        COUNT(DISTINCT original_device_id) AS distinct_original_ids,
        SUM(CASE WHEN original_device_id = device_id THEN 1 ELSE 0 END) AS self_links
    FROM player_profile
""").fetchone()
print("Linked stats:", orig_stats)

orig_in_profile = con.execute("""
    SELECT
        COUNT(*) AS linked_rows,
        SUM(CASE WHEN orig.device_id IS NOT NULL THEN 1 ELSE 0 END) AS orig_exists_in_profile,
        SUM(CASE WHEN orig.device_id IS NULL THEN 1 ELSE 0 END) AS orig_missing_from_profile
    FROM player_profile p
    LEFT JOIN player_profile orig ON p.original_device_id = orig.device_id
    WHERE p.original_device_id IS NOT NULL
""").fetchone()
print("Original ID exists in player_profile:", orig_in_profile)

chains = con.execute("""
    SELECT COUNT(*)
    FROM player_profile a
    JOIN player_profile b ON a.original_device_id = b.device_id
    WHERE b.original_device_id IS NOT NULL
""").fetchone()[0]
print("Chained links (A -> B -> C):", chains)

multi_targets = con.execute("""
    SELECT COUNT(*), MAX(cnt)
    FROM (
        SELECT original_device_id, COUNT(*) AS cnt
        FROM player_profile
        WHERE original_device_id IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) > 1
    )
""").fetchone()
print("original_device_ids pointed to by >1 device (count, max):", multi_targets)

# Check activity overlap & attribute comparison for linked pairs
pair_comp = con.execute("""
    SELECT
        COUNT(*) AS pairs,
        SUM(CASE WHEN n.platform = o.platform THEN 1 ELSE 0 END) AS same_platform,
        SUM(CASE WHEN n.country = o.country THEN 1 ELSE 0 END) AS same_country,
        SUM(CASE WHEN n.acquisition_channel = o.acquisition_channel THEN 1 ELSE 0 END) AS same_channel,
        SUM(CASE WHEN n.install_date >= o.install_date THEN 1 ELSE 0 END) AS new_install_ge_old,
        SUM(CASE WHEN n.install_date < o.install_date THEN 1 ELSE 0 END) AS new_install_lt_old,
        SUM(CASE WHEN n.first_purchase_date = o.first_purchase_date THEN 1 ELSE 0 END) AS same_first_purch,
        SUM(CASE WHEN n.first_purchase_date IS NOT NULL AND o.first_purchase_date IS NULL THEN 1 ELSE 0 END) AS only_new_has_fp,
        SUM(CASE WHEN n.first_purchase_date IS NULL AND o.first_purchase_date IS NOT NULL THEN 1 ELSE 0 END) AS only_old_has_fp
    FROM player_profile n
    JOIN player_profile o ON n.original_device_id = o.device_id
""").fetchone()
print("Pair attribute comparison (pairs, same_plat, same_ctry, same_chan, new>=old_inst, new<old_inst, same_fp, only_new_fp, only_old_fp):", pair_comp)

overlap = con.execute("""
    WITH pairs AS (
        SELECT device_id AS new_id, original_device_id AS old_id
        FROM player_profile
        WHERE original_device_id IS NOT NULL
    ),
    act AS (
        SELECT
            p.new_id, p.old_id,
            (SELECT COUNT(*) FROM player_day d WHERE d.device_id = p.new_id) AS new_days,
            (SELECT COUNT(*) FROM player_day d WHERE d.device_id = p.old_id) AS old_days,
            (SELECT MIN(activity_date) FROM player_day d WHERE d.device_id = p.new_id) AS new_min_d,
            (SELECT MAX(activity_date) FROM player_day d WHERE d.device_id = p.old_id) AS old_max_d,
            (SELECT COUNT(*) FROM purchase u WHERE u.device_id = p.new_id) AS new_purch,
            (SELECT COUNT(*) FROM purchase u WHERE u.device_id = p.old_id) AS old_purch
        FROM pairs p
    )
    SELECT
        COUNT(*) AS pairs,
        SUM(CASE WHEN new_days > 0 AND old_days > 0 THEN 1 ELSE 0 END) AS both_active_in_window,
        SUM(CASE WHEN new_days > 0 AND old_days = 0 THEN 1 ELSE 0 END) AS only_new_active,
        SUM(CASE WHEN new_days = 0 AND old_days > 0 THEN 1 ELSE 0 END) AS only_old_active,
        SUM(CASE WHEN new_days = 0 AND old_days = 0 THEN 1 ELSE 0 END) AS neither_active,
        SUM(CASE WHEN new_min_d <= old_max_d THEN 1 ELSE 0 END) AS overlapping_dates,
        SUM(CASE WHEN new_purch > 0 AND old_purch > 0 THEN 1 ELSE 0 END) AS both_purchased
    FROM act
""").fetchone()
print("Linked activity overlap (pairs, both_active, only_new, only_old, neither, new_min<=old_max, both_purch):", overlap)

# ---------------------------------------------------------------------------
# 7. CATEGORICALS, NUMERIC RANGES, & SUSPICIOUS / INVALID VALUES
# ---------------------------------------------------------------------------
section("7. CATEGORICAL DISTRIBUTIONS & SUSPICIOUS VALUES")

print("\n-- player_profile categoricals --")
for col in ["platform", "country_tier", "acquisition_channel"]:
    print(f"  {col}:", con.execute(f"SELECT {col}, COUNT(*) FROM player_profile GROUP BY 1 ORDER BY 2 DESC").fetchall())

print("  country distinct count:", con.execute("SELECT COUNT(DISTINCT country) FROM player_profile").fetchone()[0])
print("  top 10 countries:", con.execute("SELECT country, country_tier, COUNT(*) FROM player_profile GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10").fetchall())
print("  countries with >1 tier:", con.execute("SELECT country, COUNT(DISTINCT country_tier) FROM player_profile GROUP BY 1 HAVING COUNT(DISTINCT country_tier) > 1").fetchall())

print("  first_purchase_date < install_date:", con.execute("SELECT COUNT(*) FROM player_profile WHERE first_purchase_date < install_date").fetchone()[0])
print("  first_purchase_date vs purchase table consistency:")
fp_check = con.execute("""
    WITH p_agg AS (
        SELECT device_id, MIN(DATE(event_ts)) AS min_purch_date, COUNT(*) AS purch_cnt
        FROM purchase
        GROUP BY 1
    )
    SELECT
        SUM(CASE WHEN pf.first_purchase_date IS NOT NULL AND pa.purch_cnt IS NULL AND pf.first_purchase_date >= DATE '2026-01-01' THEN 1 ELSE 0 END) AS fp_in_window_no_tx,
        SUM(CASE WHEN pf.first_purchase_date IS NOT NULL AND pa.purch_cnt IS NULL AND pf.first_purchase_date < DATE '2026-01-01' THEN 1 ELSE 0 END) AS fp_pre_window_no_tx,
        SUM(CASE WHEN pf.first_purchase_date IS NULL AND pa.purch_cnt IS NOT NULL THEN 1 ELSE 0 END) AS fp_null_but_has_tx,
        SUM(CASE WHEN pf.first_purchase_date IS NOT NULL AND pa.min_purch_date IS NOT NULL AND pf.first_purchase_date > pa.min_purch_date THEN 1 ELSE 0 END) AS fp_after_min_tx,
        SUM(CASE WHEN pf.first_purchase_date IS NOT NULL AND pa.min_purch_date IS NOT NULL AND pf.first_purchase_date < pa.min_purch_date AND pf.first_purchase_date >= DATE '2026-01-01' THEN 1 ELSE 0 END) AS fp_in_window_before_min_tx
    FROM player_profile pf
    LEFT JOIN p_agg pa ON pf.device_id = pa.device_id
""").fetchone()
print("  (fp_in_window_no_tx, fp_pre_window_no_tx, fp_null_but_has_tx, fp_after_min_tx, fp_in_window_before_min_tx):", fp_check)

print("\n-- player_day ranges & anomalies --")
print("  numeric min/max (level, sessions, playtime):", con.execute("""
    SELECT
        MIN(player_level), MAX(player_level),
        MIN(session_count), MAX(session_count),
        MIN(playtime_minutes), MAX(playtime_minutes)
    FROM player_day
""").fetchone())
print("  anomalies (lvl<=0, sess<=0, play<0, play=0, play>1440, play>720, sess>50):", con.execute("""
    SELECT
        SUM(CASE WHEN player_level <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN session_count <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN playtime_minutes < 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN playtime_minutes = 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN playtime_minutes > 1440 THEN 1 ELSE 0 END),
        SUM(CASE WHEN playtime_minutes > 720 THEN 1 ELSE 0 END),
        SUM(CASE WHEN session_count > 50 THEN 1 ELSE 0 END)
    FROM player_day
""").fetchone())
print("  activity_date < install_date:", con.execute("""
    SELECT COUNT(*)
    FROM player_day d
    JOIN player_profile p ON d.device_id = p.device_id
    WHERE TRY_STRPTIME(CAST(d.activity_date AS VARCHAR), '%Y%m%d')::DATE < p.install_date
""").fetchone()[0])
print("  app_version distribution:", con.execute("SELECT app_version, COUNT(*), MIN(activity_date), MAX(activity_date) FROM player_day GROUP BY 1 ORDER BY 3, 1").fetchall())
print("  level decreases within same device_id:", con.execute("""
    WITH lagged AS (
        SELECT device_id, activity_date, player_level,
               LAG(player_level) OVER (PARTITION BY device_id ORDER BY activity_date) AS prev_lvl
        FROM player_day
    )
    SELECT COUNT(*) FROM lagged WHERE player_level < prev_lvl
""").fetchone()[0])

print("\n-- purchase ranges & anomalies --")
print("  pack_name breakdown:", con.execute("""
    SELECT pack_name, COUNT(*), MIN(usd_amount), MAX(usd_amount), MIN(currency_granted), MAX(currency_granted), SUM(sale_flag)
    FROM purchase GROUP BY 1 ORDER BY 3
""").fetchall())
print("  sale_flag values:", con.execute("SELECT sale_flag, COUNT(*) FROM purchase GROUP BY 1 ORDER BY 1").fetchall())
print("  usd<=0, granted<=0, event_before_install:", con.execute("""
    SELECT
        SUM(CASE WHEN u.usd_amount <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN u.currency_granted <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN DATE(u.event_ts) < p.install_date THEN 1 ELSE 0 END)
    FROM purchase u
    JOIN player_profile p ON u.device_id = p.device_id
""").fetchone())

print("\n-- currency_spend ranges & anomalies --")
print("  spend_type:", con.execute("SELECT spend_type, COUNT(*) FROM currency_spend GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  currency_type:", con.execute("SELECT currency_type, COUNT(*) FROM currency_spend GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  spend_category:", con.execute("SELECT spend_category, COUNT(*) FROM currency_spend GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  numeric min/max (val, lvl, prem, soc, grind):", con.execute("""
    SELECT
        MIN(currency_value), MAX(currency_value),
        MIN(player_level), MAX(player_level),
        MIN(premium_balance), MAX(premium_balance),
        MIN(social_balance), MAX(social_balance),
        MIN(grind_balance), MAX(grind_balance)
    FROM currency_spend
""").fetchone())
print("  anomalies (val<=0, lvl<=0, prem<0, soc<0, grind<0, before_install):", con.execute("""
    SELECT
        SUM(CASE WHEN s.currency_value <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN s.player_level <= 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN s.premium_balance < 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN s.social_balance < 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN s.grind_balance < 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN DATE(s.event_ts) < p.install_date THEN 1 ELSE 0 END)
    FROM currency_spend s
    JOIN player_profile p ON s.device_id = p.device_id
""").fetchone())

print("\n-- ad_view ranges & anomalies --")
print("  status:", con.execute("SELECT status, COUNT(*) FROM ad_view GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  placement:", con.execute("SELECT placement, COUNT(*) FROM ad_view GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  reward_type:", con.execute("SELECT reward_type, COUNT(*) FROM ad_view GROUP BY 1 ORDER BY 2 DESC").fetchall())
print("  reward_amount by status:", con.execute("""
    SELECT status, COUNT(*), MIN(reward_amount), MAX(reward_amount),
           SUM(CASE WHEN reward_amount > 0 THEN 1 ELSE 0 END) AS pos_reward,
           SUM(CASE WHEN reward_amount <= 0 THEN 1 ELSE 0 END) AS nonpos_reward
    FROM ad_view GROUP BY 1
""").fetchall())
print("  ad_daily_count & cap min/max & anomalies:", con.execute("""
    SELECT
        MIN(ad_daily_count), MAX(ad_daily_count),
        MIN(ad_daily_cap), MAX(ad_daily_cap),
        SUM(CASE WHEN ad_daily_count <= 0 THEN 1 ELSE 0 END) AS count_le_0,
        SUM(CASE WHEN ad_daily_cap <= 0 THEN 1 ELSE 0 END) AS cap_le_0,
        SUM(CASE WHEN ad_daily_count > ad_daily_cap THEN 1 ELSE 0 END) AS count_gt_cap
    FROM ad_view
""").fetchone())
print("  ad_daily_cap values:", con.execute("SELECT ad_daily_cap, COUNT(*) FROM ad_view GROUP BY 1 ORDER BY 1").fetchall())
print("  ad_view before_install:", con.execute("""
    SELECT COUNT(*)
    FROM ad_view a JOIN player_profile p ON a.device_id = p.device_id
    WHERE DATE(a.event_ts) < p.install_date
""").fetchone()[0])

# Check daily volume anomalies across all 4 event/day tables
section("8. DAILY VOLUME CHECKS (GAPS & OUTLIERS)")
for tbl, date_expr in [
    ("player_day", "TRY_STRPTIME(CAST(activity_date AS VARCHAR), '%Y%m%d')::DATE"),
    ("purchase", "DATE(event_ts)"),
    ("currency_spend", "DATE(event_ts)"),
    ("ad_view", "DATE(event_ts)"),
]:
    stats = con.execute(f"""
        WITH d AS (
            SELECT {date_expr} AS dt, COUNT(*) AS n
            FROM {tbl}
            GROUP BY 1
        )
        SELECT COUNT(*) AS num_days, MIN(n), PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n), MAX(n)
        FROM d
    """).fetchone()
    print(f"  {tbl:15s} daily counts (days, min, median, max):", stats)
    low_high = con.execute(f"""
        WITH d AS (
            SELECT {date_expr} AS dt, COUNT(*) AS n
            FROM {tbl}
            GROUP BY 1
        ),
        med AS (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) AS m FROM d)
        SELECT d.dt, d.n
        FROM d, med
        WHERE d.n < med.m * 0.6 OR d.n > med.m * 1.8
        ORDER BY 1
    """).fetchall()
    if low_high:
        print(f"    Outlier days (<0.6x or >1.8x median): {low_high}")
