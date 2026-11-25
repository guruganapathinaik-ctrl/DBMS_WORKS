"""Build a local read-optimized DuckDB database from the five raw CSV files.

This avoids repeatedly parsing the same CSV files while keeping the original
CSVs completely untouched.
"""
from pathlib import Path
import duckdb

DATA_DIR = Path("data")
DB_PATH = Path("outputs/telemetry.duckdb")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

FILES = {
    "player_profile": DATA_DIR / "player_profile - player_profile.csv",
    "player_day": DATA_DIR / "player_day - player_day.csv",
    "purchase": DATA_DIR / "purchase - purchase.csv",
    "currency_spend": DATA_DIR / "currency_spend - currency_spend.csv",
    "ad_view": DATA_DIR / "ad_view - ad_view.csv",
}

con = duckdb.connect(str(DB_PATH))
con.execute("SET memory_limit='1GB'")

for table_name, csv_path in FILES.items():
    p = csv_path.as_posix()
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{p}', sample_size=-1)")
    cnt = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"Loaded {table_name:16s}: {cnt:>9,} rows")

con.close()
print(f"Saved DuckDB database to {DB_PATH}")
