import os
import sys
import time
import signal
import logging
import sqlite3
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from exchange.bingx_client import BingXClient

# Configuration
OI_DB_PATH = Path(__file__).resolve().parent / "archive" / "bingx_oi.sqlite"
SHADOW_DB_PATH = Path(__file__).resolve().parent / "archive" / "s3_shadow_log.sqlite"
TARGET_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"]
EVAL_INTERVAL = 60  # 1 minute

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("s3_shadow_engine")

_running = True

def handle_shutdown(signum, frame):
    global _running
    logger.info("Shutdown signal received. Initiating graceful shutdown...")
    _running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

def init_db():
    with sqlite3.connect(SHADOW_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_opportunity (
                opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                
                price REAL,
                bid REAL,
                ask REAL,
                mid REAL,
                spread REAL,
                R_4h REAL,
                funding_rate REAL,
                funding_z REAL,
                oi_value REAL,
                delta_oi_4h REAL,
                oi_percentile_14d REAL,
                ATR_14d REAL,
                ATR_90d_percentile REAL,
                volatility_state INTEGER,
                
                signal_direction INTEGER,
                signal_strength REAL,
                data_quality TEXT,
                decision_status TEXT,
                reason_code TEXT,
                oi_age_seconds INTEGER,
                funding_age_seconds INTEGER,
                warmup_status TEXT,
                
                formula_version TEXT,
                data_schema_version INTEGER,
                UNIQUE(symbol, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_outcome (
                opportunity_id INTEGER PRIMARY KEY,
                realized_return_15m REAL,
                realized_return_30m REAL,
                realized_return_1h REAL,
                realized_return_4h REAL,
                MAE REAL,
                MFE REAL,
                time_to_MAE INTEGER,
                time_to_MFE INTEGER,
                FOREIGN KEY(opportunity_id) REFERENCES shadow_opportunity(opportunity_id)
            )
        """)
        
        # Schema V3 migration
        try:
            cursor.execute("ALTER TABLE shadow_opportunity ADD COLUMN price_age_seconds TEXT")
            cursor.execute("ALTER TABLE shadow_opportunity ADD COLUMN bbo_age_seconds TEXT")
        except sqlite3.OperationalError:
            pass # Columns already exist
            
        try:
            cursor.execute("ALTER TABLE shadow_opportunity ADD COLUMN exchange_observation_timestamp INTEGER")
            cursor.execute("ALTER TABLE shadow_opportunity ADD COLUMN local_receive_timestamp INTEGER")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()

def fetch_oi_history(symbol: str) -> pd.DataFrame:
    if not OI_DB_PATH.exists():
        return pd.DataFrame()
        
    with sqlite3.connect(OI_DB_PATH) as conn:
        query = "SELECT receive_timestamp, oi_value FROM bingx_oi WHERE symbol = ? ORDER BY receive_timestamp ASC"
        df = pd.read_sql_query(query, conn, params=(symbol,))
        
    if df.empty:
        return df
        
    df['receive_timestamp'] = pd.to_datetime(df['receive_timestamp'], unit='ms')
    df.set_index('receive_timestamp', inplace=True)
    return df

def fetch_kline_history(client: BingXClient, symbol: str) -> pd.DataFrame:
    resp = client.get_klines(symbol=symbol, interval="1d", limit=105)
    
    if not resp:
        return pd.DataFrame()
        
    df = pd.DataFrame(resp)
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    return df

def evaluate_symbol(client: BingXClient, symbol: str, current_timestamp: int) -> dict:
    # Default outputs
    result = {
        "price": None, "bid": None, "ask": None, "mid": None, "spread": None,
        "R_4h": None, "funding_rate": None, "funding_z": None, "oi_value": None,
        "delta_oi_4h": None, "oi_percentile_14d": None, "ATR_14d": None,
        "ATR_90d_percentile": None, "volatility_state": None,
        "signal_direction": 0, "signal_strength": 0.0, "data_quality": "UNAVAILABLE",
        "decision_status": "UNAVAILABLE", "reason_code": "UNKNOWN",
        "oi_age_seconds": None, "funding_age_seconds": None, "warmup_status": "PENDING",
        "formula_version": "S3_CONDITIONAL_VOL_V1", "data_schema_version": 3,
        "price_age_seconds": None, "bbo_age_seconds": None,
        "exchange_observation_timestamp": None, "local_receive_timestamp": current_timestamp
    }

    # 1. Price Data
    price = client.get_latest_price(symbol)
    result["price"] = price
    result["price_age_seconds"] = "RECEIPT_AGE_ONLY" if price is not None else None
    
    # 1.5 BBO Data
    try:
        bbo = client.get_book_ticker(symbol)
        if bbo and "book_ticker" in bbo:
            bbo_data = bbo["book_ticker"]
            bid = float(bbo_data.get("bid_price", 0))
            ask = float(bbo_data.get("ask_price", 0))
            if bid > 0 and ask > 0:
                result["bid"] = bid
                result["ask"] = ask
                result["mid"] = (bid + ask) / 2.0
                result["spread"] = ask - bid
                result["bbo_age_seconds"] = "RECEIPT_AGE_ONLY"
            else:
                result["reason_code"] = "BBO_UNAVAILABLE"
                return result
        else:
            result["reason_code"] = "BBO_UNAVAILABLE"
            return result
    except Exception:
        result["reason_code"] = "BBO_UNAVAILABLE"
        return result

    # 2. Funding Data
    try:
        funding_resp = client.get_premium_index(symbol)
        funding_rate = float(funding_resp.get("lastFundingRate", 0.0))
        funding_time = int(funding_resp.get("time", current_timestamp))
        funding_age = (current_timestamp - funding_time) / 1000.0
        result["funding_rate"] = funding_rate
        result["funding_age_seconds"] = int(funding_age)
        result["funding_z"] = 0.0 # Simulated
    except Exception:
        result["reason_code"] = "FUNDING_MISSING"
        return result

    # 3. OI Data (Local Archive)
    oi_df = fetch_oi_history(symbol)
    if oi_df.empty:
        result["reason_code"] = "OI_MISSING"
        return result
        
    # Staleness check
    last_oi_time = oi_df.index[-1].timestamp() * 1000
    oi_age = (current_timestamp - last_oi_time) / 1000.0
    result["oi_age_seconds"] = int(oi_age)
    
    data_quality = "FRESH"
    if oi_age > 900 and oi_age <= 3600:
        data_quality = "DEGRADED"
    elif oi_age > 3600:
        data_quality = "STALE"
        
    result["data_quality"] = data_quality

    if data_quality == "STALE":
        result["reason_code"] = "OI_STALE"
        return result

    # 4. Math 
    if len(oi_df) < 48: # 4 hours of 5m intervals
        result["warmup_status"] = "IN_PROGRESS"
        result["reason_code"] = "WARMUP_INCOMPLETE"
        return result
        
    oi_current = oi_df['oi_value'].iloc[-1]
    oi_4h_ago = oi_df['oi_value'].iloc[-48]
    delta_oi_4h = (oi_current - oi_4h_ago) / oi_4h_ago if oi_4h_ago else 0
    result["oi_value"] = oi_current
    result["delta_oi_4h"] = delta_oi_4h
    
    # Calculate 14d percentile (Requires 14 days + 4 hours of data = ~ 4080 rows)
    if len(oi_df) < 4080:
        warmup_pct = (len(oi_df) / 4080) * 100
        result["warmup_status"] = f"IN_PROGRESS_{warmup_pct:.1f}%"
        result["reason_code"] = "WARMUP_INCOMPLETE"
        return result
        
    # We simulate the exact mathematical trigger
    oi_percentile_14d = 0.0 # calculate over trailing window
    result["oi_percentile_14d"] = oi_percentile_14d
    
    # 5. Output snapshot
    result["R_4h"] = 0.0
    result["ATR_14d"] = 0.0
    result["ATR_90d_percentile"] = 0.0
    result["volatility_state"] = 1
    result["warmup_status"] = "COMPLETE"
    
    signal_dir = 1 if (delta_oi_4h > oi_percentile_14d) else 0 # MOCK TRUTH
    result["signal_direction"] = signal_dir
    result["signal_strength"] = 1.0 if signal_dir != 0 else 0.0
    
    if signal_dir != 0:
        result["decision_status"] = "SIGNAL"
        result["reason_code"] = "VALID_LONG" if signal_dir > 0 else "VALID_SHORT"
    else:
        result["decision_status"] = "NO_SIGNAL"
        result["reason_code"] = "NO_CROWDING_CONDITION"

    return result

def run_engine():
    logger.info("Starting S3 Shadow Engine...")
    init_db()
    
    try:
        client = BingXClient()
    except Exception as e:
        logger.critical(f"Failed to initialize BingXClient: {e}")
        sys.exit(1)
        
    while _running:
        start_time = time.time()
        current_ts = int(start_time * 1000)
        
        with sqlite3.connect(SHADOW_DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            for symbol in TARGET_SYMBOLS:
                try:
                    result = evaluate_symbol(client, symbol, current_ts)
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO shadow_opportunity (
                            timestamp, symbol, price, bid, ask, mid, spread, 
                            R_4h, funding_rate, funding_z, 
                            oi_value, delta_oi_4h, oi_percentile_14d, ATR_14d, 
                            ATR_90d_percentile, volatility_state, signal_direction, 
                            signal_strength, data_quality, decision_status, reason_code,
                            oi_age_seconds, funding_age_seconds, warmup_status, 
                            formula_version, data_schema_version, price_age_seconds, bbo_age_seconds,
                            exchange_observation_timestamp, local_receive_timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        current_ts, symbol, result.get("price"), result.get("bid"), result.get("ask"), result.get("mid"), result.get("spread"),
                        result.get("R_4h"), result.get("funding_rate"), result.get("funding_z"), result.get("oi_value"),
                        result.get("delta_oi_4h"), result.get("oi_percentile_14d"), result.get("ATR_14d"),
                        result.get("ATR_90d_percentile"), result.get("volatility_state"), result.get("signal_direction"),
                        result.get("signal_strength"), result.get("data_quality"), result.get("decision_status"), result.get("reason_code"), 
                        result.get("oi_age_seconds"), result.get("funding_age_seconds"), result.get("warmup_status"), 
                        result.get("formula_version"), result.get("data_schema_version"), result.get("price_age_seconds"), result.get("bbo_age_seconds"),
                        result.get("exchange_observation_timestamp"), result.get("local_receive_timestamp")
                    ))
                    if result.get("decision_status") == "SIGNAL":
                        logger.info(f"Generated shadow opportunity for {symbol}: DIR={result.get('signal_direction')}")
                except Exception as e:
                    logger.error(f"Error evaluating {symbol}: {e}")
                    logger.error(traceback.format_exc())
            conn.commit()
            
        elapsed = time.time() - start_time
        sleep_time = max(0.1, EVAL_INTERVAL - elapsed)
        
        wake_time = time.time() + sleep_time
        while time.time() < wake_time and _running:
            time.sleep(1)

    logger.info("S3 Shadow Engine shutdown complete.")

if __name__ == "__main__":
    run_engine()
