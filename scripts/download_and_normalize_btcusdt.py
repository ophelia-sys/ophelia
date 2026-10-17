import os
import zipfile
import json
import pandas as pd
from datetime import datetime, timezone

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.data.download_vision import VisionDownloader
from research.data.normalize_parquet import ParquetNormalizer
from research.data.validate_gaps import GapValidator

def run_download_and_normalize():
    downloader = VisionDownloader()
    normalizer = ParquetNormalizer()
    validator = GapValidator()
    
    symbol = "BTCUSDT"
    interval = "1m"
    months = [1, 2, 3]
    year = 2023
    
    raw_dir = "data/raw/binance/futures/um"
    os.makedirs(raw_dir, exist_ok=True)
    
    csv_files = []
    
    for month in months:
        url = downloader.construct_klines_url(symbol, interval, year, month)
        zip_filename = url.split('/')[-1]
        dest_path = os.path.join(raw_dir, zip_filename)
        
        print(f"Downloading {url}...")
        success = downloader.download_file(url, dest_path)
        if not success:
            print(f"Failed to download {zip_filename}")
            return
        
        # Extract
        with zipfile.ZipFile(dest_path, 'r') as zip_ref:
            zip_ref.extractall(raw_dir)
            
        csv_filename = zip_filename.replace('.zip', '.csv')
        csv_path = os.path.join(raw_dir, csv_filename)
        if os.path.exists(csv_path):
            csv_files.append(csv_path)
        else:
            print(f"Expected CSV {csv_filename} not found after extraction.")
            return

    # Normalize and combine
    print(f"Normalizing {len(csv_files)} files...")
    all_dfs = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file, names=normalizer.raw_columns, header=None)
        if str(df['open_time'].iloc[0]).startswith('open'):
            df = df.iloc[1:].copy()
        
        # casting
        df['open_time'] = df['open_time'].astype('int64')
        df['close_time'] = df['close_time'].astype('int64')
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
            df[col] = df[col].astype('float64')
        df['number_of_trades'] = df['number_of_trades'].astype('int64')
        
        canonical = pd.DataFrame()
        canonical['timestamp'] = df['open_time']
        canonical['close_time'] = df['close_time']
        canonical['symbol'] = symbol
        canonical['open'] = df['open']
        canonical['high'] = df['high']
        canonical['low'] = df['low']
        canonical['close'] = df['close']
        canonical['volume'] = df['volume']
        canonical['quote_volume'] = df['quote_asset_volume']
        canonical['trades'] = df['number_of_trades']
        canonical['taker_buy_volume'] = df['taker_buy_base_asset_volume']
        canonical['taker_buy_quote_volume'] = df['taker_buy_quote_asset_volume']
        
        canonical['aggressive_buy_volume'] = canonical['taker_buy_volume']
        canonical['aggressive_sell_volume'] = canonical['volume'] - canonical['taker_buy_volume']
        canonical['delta_v'] = canonical['aggressive_buy_volume'] - canonical['aggressive_sell_volume']
        canonical['ofi'] = float('nan')
        canonical['microprice'] = float('nan')
        
        all_dfs.append(canonical)
        
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values('timestamp').reset_index(drop=True)
    
    dataset_id = "binance_um_btcusdt_1m_v1"
    parquet_path = os.path.join("data/normalized/v1", f"{dataset_id}.parquet")
    combined.to_parquet(parquet_path, engine='pyarrow', compression='snappy')
    print(f"Saved to {parquet_path}")
    
    # Gap Validation
    stats = validator.validate(combined)
    stats['dataset_id'] = dataset_id
    stats['symbol'] = symbol
    stats['start_timestamp'] = int(combined['timestamp'].min())
    stats['end_timestamp'] = int(combined['timestamp'].max())
    stats['source'] = 'Binance Vision'
    stats['schema_version'] = 'v1'
    
    manifest_path = os.path.join("data/manifests", f"{dataset_id}.json")
    with open(manifest_path, 'w') as f:
        json.dump(stats, f, indent=4)
        
    print("Gap Validation Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if stats['status'] == 'FAIL':
        print("DATA QUALITY FAILED. STOPPING.")
        return

if __name__ == "__main__":
    run_download_and_normalize()
