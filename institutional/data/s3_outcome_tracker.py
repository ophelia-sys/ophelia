import os
import sys
import time
import signal
import logging
import sqlite3
import traceback
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from exchange.bingx_client import BingXClient

SHADOW_DB_PATH = Path(__file__).resolve().parent / "archive" / "s3_shadow_log.sqlite"
TRACK_INTERVAL = 300  # 5 minutes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("s3_outcome_tracker")

_running = True

def handle_shutdown(signum, frame):
    global _running
    logger.info("Shutdown signal received. Initiating graceful shutdown...")
    _running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

def track_outcomes(client: BingXClient):
    current_ts = int(time.time() * 1000)
    
    with sqlite3.connect(SHADOW_DB_PATH, timeout=10) as conn:
        cursor = conn.cursor()
        
        # Select opportunities that need tracking (where 4 hours have passed since generation, or parts thereof)
        # We process them once they are fully aged to 4 hours to write the complete outcome record at once.
        four_hours_ms = 4 * 60 * 60 * 1000
        
        cursor.execute("""
            SELECT o.opportunity_id, o.symbol, o.timestamp, o.price, o.signal_direction
            FROM shadow_opportunity o
            LEFT JOIN shadow_outcome out ON o.opportunity_id = out.opportunity_id
            WHERE out.opportunity_id IS NULL
            AND (? - o.timestamp) > ?
        """, (current_ts, four_hours_ms))
        
        pending = cursor.fetchall()
        
        for row in pending:
            opp_id, symbol, sig_ts, entry_price, sig_dir = row
            
            try:
                # Fetch Klines post-signal. (4 hours = 240 minutes = 240 1m klines)
                resp = client.get_klines(symbol, "1m", limit=240, start_time=sig_ts)
                if not resp or len(resp) == 0:
                    continue
                
                df = pd.DataFrame(resp)
                df['time'] = pd.to_numeric(df['time'])
                df['close'] = pd.to_numeric(df['close'])
                df['high'] = pd.to_numeric(df['high'])
                df['low'] = pd.to_numeric(df['low'])
                df.sort_values('time', inplace=True)
                
                # We need to compute returns based on sig_dir
                def calc_ret(idx):
                    if idx >= len(df): return 0.0
                    exit_price = df['close'].iloc[idx]
                    return sig_dir * (exit_price - entry_price) / entry_price
                
                ret_15m = calc_ret(min(15, len(df)-1))
                ret_30m = calc_ret(min(30, len(df)-1))
                ret_1h = calc_ret(min(60, len(df)-1))
                ret_4h = calc_ret(min(239, len(df)-1))
                
                # MFE / MAE
                if sig_dir > 0: # LONG
                    mfe_px = df['high'].max()
                    mae_px = df['low'].min()
                    time_to_mfe = int((df.loc[df['high'].idxmax(), 'time'] - sig_ts) / 60000)
                    time_to_mae = int((df.loc[df['low'].idxmin(), 'time'] - sig_ts) / 60000)
                else: # SHORT
                    mfe_px = df['low'].min()
                    mae_px = df['high'].max()
                    time_to_mfe = int((df.loc[df['low'].idxmin(), 'time'] - sig_ts) / 60000)
                    time_to_mae = int((df.loc[df['high'].idxmax(), 'time'] - sig_ts) / 60000)
                    
                mfe = sig_dir * (mfe_px - entry_price) / entry_price
                mae = sig_dir * (mae_px - entry_price) / entry_price
                
                cursor.execute("""
                    INSERT INTO shadow_outcome 
                    (opportunity_id, realized_return_15m, realized_return_30m, realized_return_1h, realized_return_4h, 
                    MAE, MFE, time_to_MAE, time_to_MFE)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (opp_id, ret_15m, ret_30m, ret_1h, ret_4h, mae, mfe, time_to_mae, time_to_mfe))
                
                logger.info(f"Logged outcome for Opp {opp_id} ({symbol}): 4h={ret_4h*10000:.1f}bps")
            
            except Exception as e:
                logger.error(f"Error computing outcome for Opp {opp_id}: {e}")
                
        conn.commit()

def run_tracker():
    logger.info("Starting S3 Outcome Tracker...")
    
    try:
        client = BingXClient()
    except Exception as e:
        logger.critical(f"Failed to initialize BingXClient: {e}")
        sys.exit(1)
        
    while _running:
        start_time = time.time()
        
        try:
            track_outcomes(client)
        except Exception as e:
            logger.error(f"Unexpected error in tracking cycle: {e}")
            logger.error(traceback.format_exc())
            
        elapsed = time.time() - start_time
        sleep_time = max(0.1, TRACK_INTERVAL - elapsed)
        
        wake_time = time.time() + sleep_time
        while time.time() < wake_time and _running:
            time.sleep(1)

    logger.info("S3 Outcome Tracker shutdown complete.")

if __name__ == "__main__":
    run_tracker()
