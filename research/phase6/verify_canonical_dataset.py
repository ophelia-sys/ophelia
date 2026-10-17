import os
import sys
import pandas as pd
import numpy as np

def verify_canonical_dataset():
    PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed'))
    dataset_path = os.path.join(PROCESSED_DIR, "binance_um_universe_1m_v2.parquet")
    
    print(f"Loading {dataset_path}...")
    df = pd.read_parquet(dataset_path)
    print(f"Shape: {df.shape}")
    
    symbols = df['symbol'].unique()
    print(f"Symbols found: {symbols}")
    
    for symbol in symbols:
        print(f"\n======================================")
        print(f"AUDITING: {symbol}")
        print(f"======================================")
        
        sym_df = df[df['symbol'] == symbol]
        
        # 1. Row Counts
        total_rows = len(sym_df)
        print(f"Total Rows: {total_rows}")
        
        # 2. Timestamp Integrity
        # Monotonicity
        is_monotonic = sym_df['timestamp'].is_monotonic_increasing
        print(f"Timestamp Monotonic Increasing: {is_monotonic}")
        
        # Duplicate timestamps
        duplicates = sym_df['timestamp'].duplicated().sum()
        print(f"Duplicate Timestamps: {duplicates}")
        
        # 3. OHLCV Integrity
        negative_price = (sym_df[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        print(f"Negative/Zero Prices: {negative_price}")
        negative_vol = (sym_df['volume'] < 0).sum()
        print(f"Negative Volume: {negative_vol}")
        
        # 4. OI Coverage & Causality
        oi_notna = sym_df['oi_timestamp'].notna()
        print(f"OI Observation Coverage: {oi_notna.mean()*100:.2f}%")
        
        # Causal Check
        valid_oi = sym_df[oi_notna]
        future_leaks = (valid_oi['oi_timestamp'] > valid_oi['timestamp']).sum()
        print(f"Future Leaks (OI Timestamp > Candle Timestamp): {future_leaks}")
        
        # Calculate lag
        lag_ms = valid_oi['timestamp'] - valid_oi['oi_timestamp']
        lag_min = lag_ms / 60000.0
        print(f"OI Lag (min) -> min: {lag_min.min():.2f}, median: {lag_min.median():.2f}, mean: {lag_min.mean():.2f}, max: {lag_min.max():.2f}")
        
        # 5. DeltaOI and Z_DeltaOI distributions
        delta_zeros = (valid_oi['delta_oi'] == 0).sum()
        print(f"DeltaOI == 0 (zero-dispersion raw events): {delta_zeros} ({(delta_zeros/len(valid_oi))*100:.2f}%)")
        
        z = sym_df['Z_DeltaOI']
        z_nan_rate = z.isna().mean()
        print(f"Z_DeltaOI NaN / Unavailable Rate: {z_nan_rate*100:.2f}%")
        
        z_valid = z.dropna()
        if not z_valid.empty:
            print(f"Z_DeltaOI Stats -> min: {z_valid.min():.4f}, median: {z_valid.median():.4f}, mean: {z_valid.mean():.4f}, max: {z_valid.max():.4f}, std: {z_valid.std():.4f}")
            print(f"Z_DeltaOI P01: {z_valid.quantile(0.01):.4f}, P05: {z_valid.quantile(0.05):.4f}, P95: {z_valid.quantile(0.95):.4f}, P99: {z_valid.quantile(0.99):.4f}")
            extreme_rate = (z_valid.abs() > 10).mean()
            print(f"Z_DeltaOI Exteme Rate (|Z| > 10): {extreme_rate*100:.2f}%")
        
        # 6. Verify Symbol Isolation
        # If any lag is 53 years, it means 1970 was joined, indicating corruption
        if lag_min.max() > 60:
            print(f"WARNING: Max lag is {lag_min.max():.2f} minutes (>1 hour) - Verify missing data gaps.")
            
    print("\nVerification Complete.")

if __name__ == '__main__':
    verify_canonical_dataset()
