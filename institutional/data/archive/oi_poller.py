import os
import sys
import time
import signal
import logging
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parents[3]))

from exchange.bingx_client import BingXClient

# Configuration
DB_PATH = Path(__file__).resolve().parent / "bingx_oi.sqlite"
TARGET_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"]
POLL_INTERVAL = 300  # 5 minutes
SCHEMA_VERSION = 1

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("oi_poller")

# Daemon Control
_running = True

def handle_shutdown(signum, frame):
    global _running
    logger.info("Shutdown signal received. Initiating graceful shutdown...")
    _running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

def init_db():
    """Initializes the SQLite database with append-only semantics."""
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

def fetch_and_store_oi(client: BingXClient):
    """Fetches OI for target symbols and persists immutably."""
    receive_timestamp = int(time.time() * 1000)
    
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cursor = conn.cursor()
        
        for symbol in TARGET_SYMBOLS:
            try:
                # Polling
                resp = client.get_open_interest(symbol)
                exchange_timestamp = int(resp.get("time", receive_timestamp))
                oi_value = float(resp.get("openInterest", 0))
                price_resp = client.get_latest_price(symbol)
                oi_notional = oi_value * price_resp
                
                # Append-only insert (causal timestamp preservation)
                cursor.execute("""
                    INSERT OR IGNORE INTO bingx_oi 
                    (symbol, exchange_timestamp, receive_timestamp, oi_value, oi_notional, data_quality, source, schema_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    exchange_timestamp,
                    receive_timestamp,
                    oi_value,
                    oi_notional,
                    "FRESH",
                    "REST_POLLER_V1",
                    SCHEMA_VERSION
                ))
                logger.debug(f"Persisted OI for {symbol}: {oi_value} @ {receive_timestamp}")
            
            except Exception as e:
                logger.error(f"Error fetching OI for {symbol}: {e}")
                # We do NOT manufacture missing rows. We skip.
                
        conn.commit()

def run_poller():
    logger.info("Starting BingX Institutional OI Poller...")
    init_db()
    
    try:
        client = BingXClient()
    except Exception as e:
        logger.critical(f"Failed to initialize BingXClient: {e}")
        sys.exit(1)
        
    logger.info(f"Targeting symbols: {TARGET_SYMBOLS}")
    logger.info(f"Polling interval: {POLL_INTERVAL} seconds")
    
    while _running:
        start_time = time.time()
        
        try:
            fetch_and_store_oi(client)
        except Exception as e:
            logger.error(f"Unexpected error in polling cycle: {e}")
            logger.error(traceback.format_exc())
            
        elapsed = time.time() - start_time
        sleep_time = max(0.1, POLL_INTERVAL - elapsed)
        
        # Sleep in small chunks to remain responsive to SIGINT
        wake_time = time.time() + sleep_time
        while time.time() < wake_time and _running:
            time.sleep(1)

    logger.info("BingX Institutional OI Poller shutdown complete.")

if __name__ == "__main__":
    run_poller()
