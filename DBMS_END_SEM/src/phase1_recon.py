"""Phase 1 Step 1: Reconnaissance of all five CSV schemas, types, row counts, and raw string samples."""
import duckdb
from pathlib import Path

DATA_DIR = Path("data")
FILES = {
    "player_profile": DATA_DIR / "player_profile - player_profile.csv",
    "player_day": DATA_DIR / "player_day - player_day.csv",
    "purchase": DATA_DIR / "purchase - purchase.csv",
    "currency_spend": DATA_DIR / "currency_spend - currency_spend.csv",
    "ad_view": DATA_DIR / "ad_view - ad_view.csv",
}

con = duckdb.connect()

for name, path in FILES.items():
    p = path.as_posix()
    print(f"\n==================== {name} ({path.name}) ====================")
    cnt = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{p}', sample_size=-1)").fetchone()[0]
    print(f"Total rows: {cnt:,}")

    print("Schema (read_csv_auto, full sample):")
    desc = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{p}', sample_size=-1)").fetchall()
    for col_name, col_type, null_flag, key, default, extra in desc:
        print(f"  - {col_name}: {col_type}")

    print("First 3 raw rows (all_varchar=true):")
    raw_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_csv('{p}', all_varchar=true, header=true)").fetchall()]
    print("  Columns:", raw_cols)
    rows = con.execute(f"SELECT * FROM read_csv('{p}', all_varchar=true, header=true) LIMIT 3").fetchall()
    for r in rows:
        print(" ", dict(zip(raw_cols, r)))
