import sqlite3
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent / "archive"
OI_DB_PATH = BASE_DIR / "bingx_oi.sqlite"
SHADOW_DB_PATH = BASE_DIR / "s3_shadow_log.sqlite"

def get_table_columns(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def print_oi_stats():
    if not OI_DB_PATH.exists():
        print("bingx_oi.sqlite does not exist.")
        return
    with sqlite3.connect(OI_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*), min(receive_timestamp), max(receive_timestamp), (SELECT MAX(schema_version) FROM bingx_oi) FROM bingx_oi;")
        row = cursor.fetchone()
        print(f"--- bingx_oi.sqlite Stats ---")
        print(f"Row count: {row[0]}")
        print(f"Min TS: {row[1]}")
        print(f"Max TS: {row[2]}")
        print(f"Schema Ver: {row[3]}")

def migrate_shadow_db():
    if not SHADOW_DB_PATH.exists():
        print("s3_shadow_log.sqlite does not exist.")
        return
        
    with sqlite3.connect(SHADOW_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*), min(timestamp), max(timestamp) FROM shadow_opportunity;")
        row = cursor.fetchone()
        print(f"\n--- s3_shadow_log.sqlite Pre-Migration Stats ---")
        print(f"Row count: {row[0]}")
        print(f"Min TS: {row[1]}")
        print(f"Max TS: {row[2]}")
        
        columns = get_table_columns(conn, "shadow_opportunity")
        
        new_cols = {
            "bid": "REAL",
            "ask": "REAL",
            "mid": "REAL",
            "spread": "REAL",
            "decision_status": "TEXT",
            "reason_code": "TEXT"
        }
        
        for col, col_type in new_cols.items():
            if col not in columns:
                print(f"Adding column {col} {col_type}...")
                cursor.execute(f"ALTER TABLE shadow_opportunity ADD COLUMN {col} {col_type}")
            else:
                print(f"Column {col} already exists.")
                
        conn.commit()

        # Verify
        columns_after = get_table_columns(conn, "shadow_opportunity")
        missing = [col for col in new_cols.keys() if col not in columns_after]
        if missing:
            print("MIGRATION FAILED: missing columns", missing)
        else:
            print("MIGRATION SUCCESSFUL.")

if __name__ == "__main__":
    print_oi_stats()
    migrate_shadow_db()
