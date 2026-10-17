import os
import sys
import glob
import pandas as pd
import numpy as np

# Ensure we can import from research and institutional
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.data.normalize_parquet import ParquetNormalizer
from institutional.normalization import calculate_robust_z_score

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw'))
PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'processed'))

def process_symbol(symbol: str, normalizer: ParquetNormalizer) -> pd.DataFrame:
    print(f"Processing {symbol}...")
    symbol_dir = os.path.join(RAW_DIR, symbol)
    
    # 1. Load Klines
    kline_files = glob.glob(os.path.join(symbol_dir, f"{symbol}-1m-*.zip"))
    kline_dfs = []
    for kf in kline_files:
        df = normalizer.parse_klines(kf, symbol)
        if not df.empty:
            kline_dfs.append(df)
            
    if not kline_dfs:
        print(f"No klines found for {symbol}.")
        return pd.DataFrame()
        
    klines = pd.concat(kline_dfs, ignore_index=True)
    klines = klines.sort_values('timestamp').reset_index(drop=True)
    
    # 2. Load Metrics (OI)
    metric_files = glob.glob(os.path.join(symbol_dir, f"{symbol}-metrics-*.zip"))
    metric_dfs = []
    for mf in metric_files:
        df = normalizer.normalize_metrics(mf)
        if not df.empty:
            metric_dfs.append(df)
            
    if not metric_dfs:
        print(f"No metrics found for {symbol}.")
        oi_df = pd.DataFrame()
    else:
        oi_df = pd.concat(metric_dfs, ignore_index=True)
        oi_df = oi_df.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate Delta OI and Robust Z-Scores natively on the 5m grid (Definition A)
        oi_df['delta_oi'] = oi_df['sum_open_interest'].diff()
        oi_df['Z_DeltaOI'] = calculate_robust_z_score(
            oi_df['delta_oi'], 
            window=100, 
            zero_dispersion_policy="unavailable"
        )
        
    # 3. Strict Causal As-of Join
    joined = normalizer.join_open_interest(klines, oi_df)
    
    # 4. Calculate return normalization on the 1m grid
    returns = np.log(joined['close'] / joined['close'].shift(1))
    joined['Z_R'] = calculate_robust_z_score(returns, window=500)
    
    return joined

def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    normalizer = ParquetNormalizer()
    
    all_symbols_df = []
    
    for symbol in SYMBOLS:
        sym_df = process_symbol(symbol, normalizer)
        if not sym_df.empty:
            all_symbols_df.append(sym_df)
            
    if all_symbols_df:
        final_df = pd.concat(all_symbols_df, ignore_index=True)
        # Sort primarily by symbol then timestamp
        final_df = final_df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        
        output_path = os.path.join(PROCESSED_DIR, "binance_um_universe_1m_v2.parquet")
        print(f"Writing final dataset to {output_path} with shape {final_df.shape}")
        final_df.to_parquet(output_path, engine='pyarrow', compression='snappy')
        print("Done.")
    else:
        print("No data processed.")

if __name__ == '__main__':
    main()
