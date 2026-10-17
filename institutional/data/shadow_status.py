import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parents[2]))

OI_DB = Path(__file__).resolve().parent / "archive" / "bingx_oi.sqlite"
SHADOW_DB = Path(__file__).resolve().parent / "archive" / "s3_shadow_log.sqlite"
TARGET_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"]

def compute_health_score(oi_age, fund_age, bid, ask, status):
    score = 100
    if oi_age is None or oi_age > 900:
        score -= 25
    if fund_age is None or fund_age > 900:
        score -= 25
    if bid is None or ask is None:
        score -= 25
    if status == 'UNAVAILABLE':
        score -= 25
    return max(0, score)

def report_status():
    print("========================================")
    print(" BINGX S3 SHADOW MODE STATUS REPORT")
    print("========================================")
    
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    print(f"Current UTC Time: {datetime.utcfromtimestamp(current_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print("----------------------------------------")
    
    # Check OI archive
    if OI_DB.exists():
        with sqlite3.connect(OI_DB) as conn:
            cursor = conn.cursor()
            for sym in TARGET_SYMBOLS:
                cursor.execute("SELECT MAX(receive_timestamp), COUNT(*) FROM bingx_oi WHERE symbol=?", (sym,))
                row = cursor.fetchone()
                if row and row[0]:
                    last_ts, count = row
                    age = (current_time - last_ts) / 1000.0
                    warmup_pct = min(100.0, (count / 4080.0) * 100)
                    print(f"{sym:<10} | OI Age: {age:8.1f}s | Polled: {count:<5} | Warmup: {warmup_pct:5.1f}%")
                else:
                    print(f"{sym:<10} | NO DATA")
    else:
        print("OI Archive Database not found.")
        
    print("----------------------------------------")
    
    # Check Shadow log and Data Health
    if SHADOW_DB.exists():
        with sqlite3.connect(SHADOW_DB) as conn:
            cursor = conn.cursor()
            
            # Health Score
            print("SHADOW DATA HEALTH (Non-Trading Metric):")
            for sym in TARGET_SYMBOLS:
                cursor.execute("""
                    SELECT oi_age_seconds, funding_age_seconds, bid, ask, decision_status, reason_code 
                    FROM shadow_opportunity 
                    WHERE symbol=? ORDER BY timestamp DESC LIMIT 1
                """, (sym,))
                row = cursor.fetchone()
                if row:
                    oi_age, fund_age, bid, ask, status, reason = row
                    score = compute_health_score(oi_age, fund_age, bid, ask, status)
                    health_str = "EXCELLENT" if score == 100 else ("DEGRADED" if score >= 50 else "POOR")
                    
                    bbo_status = "PASS" if (bid and ask) else "FAIL"
                    oi_status = "PASS" if (oi_age is not None and oi_age <= 900) else "FAIL"
                    fund_status = "PASS" if (fund_age is not None and fund_age <= 900) else "FAIL"
                    
                    print(f"{sym:<10} | HEALTH: {score:3}/100 [{health_str}] | OI: {oi_status} | FUNDING: {fund_status} | BBO: {bbo_status} | REASON: {reason}")
                else:
                    print(f"{sym:<10} | NO SHADOW DATA")
                    
            print("----------------------------------------")
            
            # Overall Stats
            cursor.execute("SELECT COUNT(*), MAX(timestamp) FROM shadow_opportunity")
            opp_row = cursor.fetchone()
            opp_count = opp_row[0] if opp_row else 0
            last_opp = opp_row[1] if (opp_row and opp_row[1]) else 0
            last_opp_dt = datetime.utcfromtimestamp(last_opp/1000).strftime('%Y-%m-%d %H:%M:%S') if last_opp else "Never"
            
            cursor.execute("SELECT COUNT(*) FROM shadow_outcome")
            out_row = cursor.fetchone()
            out_count = out_row[0] if out_row else 0
            
            print(f"Shadow Opportunities Generated : {opp_count}")
            print(f"Shadow Outcomes Tracked        : {out_count}")
            print(f"Last Opportunity Eval          : {last_opp_dt}")
            
            print("\nRecent Opportunities (Last 5):")
            cursor.execute("""
                SELECT symbol, decision_status, reason_code, signal_direction 
                FROM shadow_opportunity ORDER BY timestamp DESC LIMIT 5
            """)
            for row in cursor.fetchall():
                print(f" -> {row[0]:<10} | {row[1]:<13} | {row[2]:<25} | DIR: {row[3]}")
                
            # Reason Code Distribution
            print("\nReason Code Distribution (All Time):")
            cursor.execute("SELECT reason_code, COUNT(*) FROM shadow_opportunity GROUP BY reason_code ORDER BY COUNT(*) DESC")
            for row in cursor.fetchall():
                print(f" - {row[0]:<25}: {row[1]}")
                
    else:
        print("Shadow Database not found.")
        
    print("========================================")
    print("EXECUTION STATUS = DISABLED (SHADOW ONLY)")
    print("========================================")

if __name__ == "__main__":
    report_status()
