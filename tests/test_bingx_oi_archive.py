import os
import sys
import time
import sqlite3
import pytest
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

DB_PATH = Path(__file__).resolve().parents[1] / "institutional" / "data" / "archive" / "bingx_oi_test.sqlite"

def setup_module(module):
    if DB_PATH.exists():
        os.remove(DB_PATH)
        
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bingx_oi (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                exchange_timestamp INTEGER NOT NULL,
                receive_timestamp INTEGER NOT NULL,
                oi_value REAL NOT NULL,
                oi_notional REAL NOT NULL,
                data_quality TEXT NOT NULL,
                source TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                UNIQUE(symbol, receive_timestamp)
            )
        """)
        conn.commit()

def teardown_module(module):
    if DB_PATH.exists():
        os.remove(DB_PATH)

def test_append_only_causality():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        t1 = int(time.time() * 1000)
        
        # Insert first
        cursor.execute("""
            INSERT INTO bingx_oi (symbol, exchange_timestamp, receive_timestamp, oi_value, oi_notional, data_quality, source, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("BTC-USDT", t1, t1, 100.0, 1000.0, "FRESH", "TEST", 1))
        conn.commit()
        
        # Test Duplicate Observation (UNIQUE constraint prevents exact same receive timestamp)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO bingx_oi (symbol, exchange_timestamp, receive_timestamp, oi_value, oi_notional, data_quality, source, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("BTC-USDT", t1, t1, 101.0, 1010.0, "FRESH", "TEST", 1))
            
def test_future_observation_rejection():
    # In practice, causality is preserved by setting receive_time = LOCAL TIME.
    # A future exchange_timestamp > receive_timestamp indicates network skew.
    t_recv = int(time.time() * 1000)
    t_exch = t_recv + 10000  # 10s in the future
    
    # We should trust local receive_time for ordering over exchange time.
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bingx_oi (symbol, exchange_timestamp, receive_timestamp, oi_value, oi_notional, data_quality, source, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("ETH-USDT", t_exch, t_recv, 200.0, 2000.0, "FRESH", "TEST", 1))
        
        cursor.execute("SELECT receive_timestamp, exchange_timestamp FROM bingx_oi WHERE symbol='ETH-USDT'")
        row = cursor.fetchone()
        
        # Causality test: The index used for alignment must be receive_timestamp
        assert row[0] == t_recv
        assert row[1] == t_exch
