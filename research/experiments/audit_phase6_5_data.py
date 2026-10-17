import os
import pandas as pd
import numpy as np

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
V2_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/normalized/v2'))
P4_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/normalized/p4'))
CVD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/normalized/cvd/5m'))

def run_audit():
    lines = ["# PHASE 6.5 DATA AVAILABILITY AUDIT\n"]
    lines.append("**Date:** 2026-08-15")
    lines.append("**Objective:** Verify integrity of 2024 blind confirmation datasets.\n")
    
    for symbol in SYMBOLS:
        lines.append(f"## {symbol}")
        
        # 1. Base Data
        v2_path = os.path.join(V2_DIR, f"binance_um_{symbol.lower()}_5m_2024.parquet")
        if not os.path.exists(v2_path):
            lines.append(f"- **[ERROR] Base Data Missing:** {v2_path}")
            continue
            
        df = pd.read_parquet(v2_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filter strictly for the 2024+ window if the file contains old data
        df = df[df['timestamp'] >= '2024-01-01 00:00:00'].copy()
        
        start_date = df['timestamp'].min()
        end_date = df['timestamp'].max()
        duplicates = df.duplicated(subset=['timestamp']).sum()
        
        expected_index = pd.date_range(start=start_date, end=end_date, freq='5min')
        actual_index = pd.DatetimeIndex(df['timestamp'])
        missing_bars = expected_index.difference(actual_index)
        
        lines.append("### Base OHLCV (2024 + 2025 Label Support)")
        lines.append(f"- **Start Date:** {start_date}")
        lines.append(f"- **End Date:** {end_date}")
        lines.append(f"- **Total Bars:** {len(df):,}")
        lines.append(f"- **Duplicate Timestamps:** {duplicates}")
        lines.append(f"- **Missing 5m Gaps:** {len(missing_bars)}")
        
        if len(missing_bars) > 0:
            lines.append(f"  - *Sample missing:* {missing_bars[:5].tolist()}")
            
        # 2. 2025 Label Support
        # Check if we have data past 2024-12-31 23:55:00
        label_support_bars = df[df['timestamp'] >= '2025-01-01 00:00:00']
        lines.append(f"- **2025 Label Support Bars:** {len(label_support_bars)} (Need at least 60)")
        
        # 3. P4 Data
        p4_path = os.path.join(P4_DIR, f"{symbol}_p4_features.parquet")
        if os.path.exists(p4_path):
            df_p4 = pd.read_parquet(p4_path)
            # Ensure it is parsed to datetime if it's not already
            if not pd.api.types.is_datetime64_any_dtype(df_p4['timestamp']):
                df_p4['timestamp'] = pd.to_datetime(df_p4['timestamp'], unit='ms')
            df_p4 = df_p4[df_p4['timestamp'] >= '2024-01-01 00:00:00'].copy()
            
            p4_start = df_p4['timestamp'].min()
            p4_end = df_p4['timestamp'].max()
            lines.append("### P4 Features")
            lines.append(f"- **Start Date:** {p4_start}")
            lines.append(f"- **End Date:** {p4_end}")
            lines.append(f"- **Total 2024 Bars:** {len(df_p4):,}")
            
            # Check NaN padded fields (if first day is padded correctly)
            first_day = df_p4[df_p4['timestamp'] < '2024-01-02']
            if len(first_day) > 0:
                nan_count = first_day['trade_size_zscore'].isna().sum()
                lines.append(f"- **First Day NaNs (Causal Padding Check):** {nan_count}")
        else:
            lines.append(f"### P4 Features\n- **[PENDING/MISSING]**")
            
        # 4. CVD Data
        cvd_dfs = []
        for m in range(1, 13):
            cp = os.path.join(CVD_DIR, f"{symbol}-2024-{m:02d}.parquet")
            if os.path.exists(cp):
                cvd_dfs.append(pd.read_parquet(cp))
                
        if cvd_dfs:
            df_cvd = pd.concat(cvd_dfs, ignore_index=True)
            cvd_start = df_cvd['minute'].min()
            cvd_end = df_cvd['minute'].max()
            lines.append("### CVD Features")
            lines.append(f"- **Start Date:** {cvd_start}")
            lines.append(f"- **End Date:** {cvd_end}")
            lines.append(f"- **Total 2024 Bars:** {len(df_cvd):,}")
        else:
            lines.append(f"### CVD Features\n- **[PENDING/MISSING]**")
            
        lines.append("\n---\n")

    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../PHASE6_5_DATA_AVAILABILITY_AUDIT.md'))
    with open(out_file, 'w') as f:
        f.write("\n".join(lines))
    print(f"Audit written to {out_file}")

if __name__ == '__main__':
    run_audit()
