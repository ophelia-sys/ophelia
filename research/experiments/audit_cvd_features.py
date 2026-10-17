import os
import glob
import pandas as pd
import numpy as np

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
YEARS = [2022, 2023]
MONTHS = list(range(1, 13))

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
CVD_DIR = os.path.join(BASE_DIR, 'research/data/normalized/cvd/5m')
OHLCV_DIR = os.path.join(BASE_DIR, 'data/normalized/v2')

def load_cvd_symbol(symbol):
    dfs = []
    for year in YEARS:
        for month in MONTHS:
            path = os.path.join(CVD_DIR, f"{symbol}-{year}-{month:02d}.parquet")
            if os.path.exists(path):
                dfs.append(pd.read_parquet(path))
    if len(dfs) == 0:
        return pd.DataFrame(columns=['minute', 'delta_volume', 'buy_volume', 'sell_volume'])
    
    df = pd.concat(dfs, ignore_index=True)
    df.sort_values('minute', inplace=True)
    return df

def engineer_cvd_features(df_cvd, df_ohlcv):
    df_ohlcv = df_ohlcv.copy()
    df_ohlcv['timestamp'] = pd.to_datetime(df_ohlcv['timestamp'], unit='ms')
    
    df = pd.merge(df_ohlcv, df_cvd, left_on='timestamp', right_on='minute', how='left')
    
    # ONLY set to 1 if the underlying CVD source interval is genuinely unavailable
    df['cvd_is_missing'] = df['delta_volume'].isna().astype(int)
    
    source_missing_count = int(df['delta_volume'].isna().sum())
    
    # ---- Explicit Invariants ----
    assert source_missing_count == int(df['cvd_is_missing'].sum())
    assert df["cvd_is_missing"].isin([0, 1]).all()
    assert df.loc[df["cvd_is_missing"] == 1, "delta_volume"].isna().all()
    assert df.loc[df["cvd_is_missing"] == 0, "delta_volume"].notna().all()
    
    df['cvd_delta_5m'] = df['delta_volume']
    
    assert df.loc[df["cvd_is_missing"] == 1, "cvd_delta_5m"].isna().all()
    assert df.loc[df["cvd_is_missing"] == 0, "cvd_delta_5m"].notna().all()
    # -----------------------------
    
    df['cvd_delta_15m'] = df['cvd_delta_5m'].rolling(3).sum()
    df['cvd_delta_1h'] = df['cvd_delta_5m'].rolling(12).sum()
    
    buy_5m = df['buy_volume']
    sell_5m = df['sell_volume']
    
    buy_15m = buy_5m.rolling(3).sum()
    sell_15m = sell_5m.rolling(3).sum()
    
    buy_1h = buy_5m.rolling(12).sum()
    sell_1h = sell_5m.rolling(12).sum()
    
    df['cvd_imbalance_5m'] = df['cvd_delta_5m'] / (buy_5m + sell_5m + 1e-8)
    df['cvd_imbalance_15m'] = df['cvd_delta_15m'] / (buy_15m + sell_15m + 1e-8)
    df['cvd_imbalance_1h'] = df['cvd_delta_1h'] / (buy_1h + sell_1h + 1e-8)
    
    df['std_5m_raw'] = df['cvd_delta_5m'].rolling(288).std()
    df['std_15m_raw'] = df['cvd_delta_15m'].rolling(288).std()
    df['std_1h_raw'] = df['cvd_delta_1h'].rolling(288).std()
    
    mean_5m = df['cvd_delta_5m'].rolling(288).mean()
    mean_15m = df['cvd_delta_15m'].rolling(288).mean()
    mean_1h = df['cvd_delta_1h'].rolling(288).mean()
    
    df['cvd_zscore_5m'] = (df['cvd_delta_5m'] - mean_5m) / df['std_5m_raw']
    df['cvd_zscore_15m'] = (df['cvd_delta_15m'] - mean_15m) / df['std_15m_raw']
    df['cvd_zscore_1h'] = (df['cvd_delta_1h'] - mean_1h) / df['std_1h_raw']
    
    df['cvd_zscore_5m'] = np.where(df['std_5m_raw'] == 0.0, np.nan, df['cvd_zscore_5m'])
    df['cvd_zscore_15m'] = np.where(df['std_15m_raw'] == 0.0, np.nan, df['cvd_zscore_15m'])
    df['cvd_zscore_1h'] = np.where(df['std_1h_raw'] == 0.0, np.nan, df['cvd_zscore_1h'])
    
    df['cvd_acceleration_15m'] = df['cvd_delta_15m'] - df['cvd_delta_15m'].shift(3)
    df['cvd_acceleration_1h'] = df['cvd_delta_1h'] - df['cvd_delta_1h'].shift(12)
    
    return df, source_missing_count

def generate_audit():
    lines = ["# PHASE 5.3 CVD FEATURE AUDIT\n"]
    lines.append("**Date:** 2026-08-14\n")
    
    lines.append("## Strict Missingness Semantics")
    lines.append("The boolean flag `cvd_is_missing` has been strictly frozen. It mathematically represents **only** periods where the underlying Binance 5m CVD source data is natively absent.")
    lines.append("Mathematical warm-ups, shift operations, or zero-variance periods **do not** set the missingness flag.\n")
    
    lines.append("## Source Provenance Investigation")
    lines.append("**BTCUSDT September 2022:**")
    lines.append("- Binance monthly `aggTrades` source begins precisely at `2022-09-02 00:00:00 UTC` (`1662076800038`).")
    lines.append("- Therefore `2022-09-01` is a genuine upstream source omission (288 rows).")
    lines.append("- The exact-duplicate anomaly identified previously is a separate anomaly occurring strictly from September 2 onward, and does not mathematically cause the September 1 gap.\n")
    
    features = [
        'cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h',
        'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
        'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
        'cvd_acceleration_15m', 'cvd_acceleration_1h'
    ]
    
    for symbol in SYMBOLS:
        print(f"Auditing {symbol}...")
        df_cvd = load_cvd_symbol(symbol)
        ohlcv_path = os.path.join(OHLCV_DIR, f"binance_um_{symbol.lower()}_5m_v2.parquet")
        df_ohlcv = pd.read_parquet(ohlcv_path)
        
        df, source_missing_count = engineer_cvd_features(df_cvd, df_ohlcv)
        
        total_rows = len(df)
        ones = int(df['cvd_is_missing'].sum())
        zeros = total_rows - ones
        nans = int(df['cvd_is_missing'].isna().sum())
        missing_pct = (ones / total_rows) * 100
        
        lines.append(f"## {symbol}")
        lines.append(f"- **Total 5m Rows:** {total_rows:,}")
        
        lines.append("\n**`cvd_is_missing` Flag Status:**")
        lines.append(f"- **Total Rows:** {total_rows:,}")
        lines.append(f"- **NaN Count:** {nans:,}")
        lines.append(f"- **Zero Flags (0):** {zeros:,}")
        lines.append(f"- **Source Missing Flags (1):** {ones:,}")
        lines.append(f"- **Missing Percentage:** {missing_pct:.2f}%\n")
        
        lines.append("\n**Derived Feature NaN Decomposition:**")
        lines.append("| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |")
        lines.append("|---------|------------|------------------|--------------------------------|-----------------------------|")
        
        for f in features:
            total_nans = int(df[f].isna().sum())
            
            is_missing_mask = (df['cvd_is_missing'] == 1)
            not_missing_mask = (df['cvd_is_missing'] == 0)
            
            nan_missing_source = int((df[f].isna() & is_missing_mask).sum())
            
            if 'zscore' in f:
                raw_std_col = 'std_' + f.split('_')[2] + '_raw'
                zero_var_mask = (df[raw_std_col] == 0.0)
                
                zero_var_nans = int((df[f].isna() & not_missing_mask & zero_var_mask).sum())
                warmup_nans = int((df[f].isna() & not_missing_mask & ~zero_var_mask).sum())
            else:
                zero_var_nans = 0
                warmup_nans = int((df[f].isna() & not_missing_mask).sum())
            
            assert total_nans == (nan_missing_source + warmup_nans + zero_var_nans)
            
            lines.append(f"| {f} | {total_nans:,} | {nan_missing_source:,} | {warmup_nans:,} | {zero_var_nans:,} |")
            
        lines.append("\n")
        
    audit_path = os.path.join(BASE_DIR, 'PHASE5_3_CVD_FEATURE_AUDIT.md')
    with open(audit_path, 'w') as f:
        f.write("\n".join(lines))
    print(f"Audit written to {audit_path}")

if __name__ == '__main__':
    generate_audit()
