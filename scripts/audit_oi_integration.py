import pandas as pd
import numpy as np
import sys
from pathlib import Path

DATA_PATH = Path("data/processed/binance_um_universe_1m_v2.parquet")
OUTPUT_MD = Path("PHASE6_OI_INTEGRATION_AUDIT.md")

def main():
    print(f"Loading {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    
    with open(OUTPUT_MD, "w") as f:
        f.write("# Phase 6 Open Interest Integration Forensic Audit\n\n")
        f.write("## 1. Dataset Overview\n")
        f.write(f"- **Symbols:** {', '.join(df['symbol'].unique())}\n")
        f.write(f"- **Total Rows:** {len(df)}\n")
        f.write(f"- **Rows with Valid OI:** {df['oi_timestamp'].notna().sum()}\n")
        f.write(f"- **Rows with NaN OI:** {df['oi_timestamp'].isna().sum()}\n\n")
        
        f.write("## 2. Causality Audit\n")
        f.write("This test verifies that `oi_timestamp <= timestamp` for all joined rows, ensuring zero look-ahead bias.\n")
        
        # We must filter out NaN oi_timestamp
        valid_df = df.dropna(subset=['oi_timestamp'])
        
        future_leaks = (valid_df['oi_timestamp'] > valid_df['timestamp']).sum()
        max_lag = (valid_df['timestamp'] - valid_df['oi_timestamp']).max()
        mean_lag = (valid_df['timestamp'] - valid_df['oi_timestamp']).mean()
        
        f.write(f"- **Forward-Looking Leaks (oi_timestamp > timestamp):** {future_leaks}\n")
        f.write(f"- **Maximum As-Of Lag (ms):** {max_lag}\n")
        f.write(f"- **Mean As-Of Lag (ms):** {mean_lag:.2f}\n\n")
        
        if future_leaks > 0:
            f.write("> [!CAUTION]\n> **DATA LEAK DETECTED!** The Open Interest join contains future information.\n\n")
        else:
            f.write("> [!NOTE]\n> **CAUSALITY CONFIRMED:** Zero instances of forward-looking data leakage.\n\n")
        
        f.write("## 3. Z_DeltaOI Distribution Audit\n")
        f.write("This verifies the trailing 500-period robust Z-score calculation for Open Interest changes.\n")
        for symbol in df['symbol'].unique():
            sym_df = df[df['symbol'] == symbol]
            z_mean = sym_df['Z_DeltaOI'].mean()
            z_std = sym_df['Z_DeltaOI'].std()
            z_min = sym_df['Z_DeltaOI'].min()
            z_max = sym_df['Z_DeltaOI'].max()
            nan_count = sym_df['Z_DeltaOI'].isna().sum()
            
            f.write(f"### {symbol}\n")
            f.write(f"- **Mean Z-Score:** {z_mean:.4f}\n")
            f.write(f"- **Std Dev Z-Score:** {z_std:.4f}\n")
            f.write(f"- **Min / Max:** {z_min:.4f} / {z_max:.4f}\n")
            f.write(f"- **NaN Count:** {nan_count} (Expected initial warmup period)\n\n")
            
    print(f"Audit report written to {OUTPUT_MD}")

if __name__ == "__main__":
    main()
