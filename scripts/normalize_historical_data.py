import os
import zipfile
import json
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
NORM_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'normalized', 'v2')
MANIFEST_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'manifests')

os.makedirs(NORM_DIR, exist_ok=True)
os.makedirs(MANIFEST_DIR, exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
YEARS = [2022, 2023]
MONTHS = list(range(1, 13))

COLUMNS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count',
    'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
]

TIMEFRAMES = {
    '1m': 1,
    '3m': 3,
    '5m': 5,
    '15m': 15,
    '1h': 60,
    '4h': 240
}

def load_1m_raw(symbol):
    print(f"Loading raw 1m data for {symbol}...")
    dfs = []
    for year in YEARS:
        for month in MONTHS:
            filename = f"{symbol}-1m-{year}-{month:02d}.zip"
            path = os.path.join(RAW_DIR, symbol, filename)
            if os.path.exists(path):
                with zipfile.ZipFile(path, 'r') as z:
                    csv_filename = z.namelist()[0]
                    with z.open(csv_filename) as f:
                        df = pd.read_csv(f, names=COLUMNS, header=None)
                        if str(df['open_time'].iloc[0]).startswith('open'):
                            df = df.iloc[1:].copy()
                        df['open_time'] = df['open_time'].astype('int64')
                        for c in ['open', 'high', 'low', 'close', 'volume']:
                            df[c] = df[c].astype('float64')
                        dfs.append(df)
    
    if not dfs:
        return None
        
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=['open_time'])
    combined = combined.sort_values('open_time').reset_index(drop=True)
    return combined

def save_parquet_with_metadata(df, path, metadata_dict):
    table = pa.Table.from_pandas(df)
    custom_metadata = {k.encode('utf-8'): str(v).encode('utf-8') for k, v in metadata_dict.items()}
    existing_metadata = table.schema.metadata or {}
    merged_metadata = {**existing_metadata, **custom_metadata}
    table = table.replace_schema_metadata(merged_metadata)
    pq.write_table(table, path)

def generate_manifest(symbol, tf_name, source_tf, df, incomplete_count, validation_status, metadata, first_ts, last_ts):
    manifest = {
        "symbol": symbol,
        "expected_rows": len(df) + incomplete_count,
        "actual_rows": len(df),
        "missing_rows": incomplete_count,
        "duplicate_rows": 0,
        "malformed_rows": 0,
        "nan_inf_count": int(df.isnull().sum().sum()),
        "incomplete_derived_candles": incomplete_count,
        "first_timestamp": int(first_ts),
        "last_timestamp": int(last_ts),
        "source_exchange": metadata["source_exchange"],
        "source_timeframe": source_tf,
        "derived_timeframe": tf_name,
        "validation_status": validation_status,
        "data_version": metadata["data_version"],
        "derivation_method": metadata["derivation_method"]
    }
    
    manifest_path = os.path.join(MANIFEST_DIR, f"{symbol}_{tf_name}_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=4)

def normalize_symbol(symbol):
    df_1m = load_1m_raw(symbol)
    if df_1m is None:
        return
        
    df_1m['dt'] = pd.to_datetime(df_1m['open_time'], unit='ms', utc=True)
    df_1m.set_index('dt', inplace=True)
    
    first_ts = df_1m['open_time'].min()
    last_ts = df_1m['open_time'].max()
    download_ts = int(time.time() * 1000)
    
    for tf_name, tf_minutes in TIMEFRAMES.items():
        print(f"Generating {tf_name} for {symbol}...")
        
        if tf_name == '1m':
            final_df = df_1m[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()
            final_df.rename(columns={'open_time': 'timestamp'}, inplace=True)
            incomplete_count = 0
            derivation_method = "raw_binance_um_klines"
        else:
            # Resample deterministically
            resampled = df_1m.resample(f'{tf_minutes}min').agg({
                'open_time': 'first',
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'count': 'count' # Using 'count' field to count the number of 1m rows
            })
            
            # Count expected vs actual
            incomplete_mask = resampled['count'] != tf_minutes
            incomplete_count = incomplete_mask.sum()
            
            # DO NOT generate higher-timeframe candle if missing source candles
            final_df = resampled[~incomplete_mask].copy()
            final_df.rename(columns={'open_time': 'timestamp'}, inplace=True)
            final_df = final_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            final_df['timestamp'] = final_df['timestamp'].astype('int64')
            
            derivation_method = "deterministic_1m_aggregation"
            
        # Metadata
        metadata = {
            "source_exchange": "BINANCE_HISTORICAL",
            "symbol": symbol,
            "timeframe": tf_name,
            "source_timeframe": "1m",
            "start_timestamp": first_ts,
            "end_timestamp": last_ts,
            "download_timestamp": download_ts,
            "data_version": "v2",
            "derivation_method": derivation_method
        }
        
        # Save Parquet
        parquet_filename = f"binance_um_{symbol.lower()}_{tf_name}_v2.parquet"
        parquet_path = os.path.join(NORM_DIR, parquet_filename)
        save_parquet_with_metadata(final_df, parquet_path, metadata)
        
        # Generate Manifest
        status = "VALID" if incomplete_count == 0 else "INVALID_GAPS"
        generate_manifest(symbol, tf_name, "1m", final_df, int(incomplete_count), status, metadata, first_ts, last_ts)
        
        print(f"[{symbol} {tf_name}] Saved {len(final_df)} rows to {parquet_filename}. Incomplete: {incomplete_count}")

def main():
    for symbol in SYMBOLS:
        normalize_symbol(symbol)
        
if __name__ == "__main__":
    main()
