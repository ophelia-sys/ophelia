import pandas as pd
import numpy as np
import requests
import zipfile
import io
import os
import time

def process_monthly_cvd(symbol, year, month):
    url = f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{year}-{month:02d}.zip"
    print(f"Downloading {url}...")
    
    t0 = time.time()
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        raise ValueError(f"Failed to download: {response.status_code}")
    
    zip_content = io.BytesIO()
    for chunk in response.iter_content(chunk_size=1024*1024):
        if chunk:
            zip_content.write(chunk)
            
    zip_content.seek(0)
    raw_size_mb = len(zip_content.getvalue()) / (1024*1024)
    print(f"Downloaded {raw_size_mb:.2f} MB in {time.time()-t0:.2f}s")
    
    with zipfile.ZipFile(zip_content) as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            # We don't read the whole thing at once if we want to save memory, 
            # but for 1 month (1.5GB) pandas can usually handle it if we specify dtypes.
            dtypes = {
                'agg_trade_id': 'int64',
                'price': 'float32',
                'quantity': 'float32',
                'first_trade_id': 'int64',
                'last_trade_id': 'int64',
                'transact_time': 'int64',
                'is_buyer_maker': 'bool'
            }
            # The CSV from binance vision usually doesn't have a header row by default sometimes,
            # or it does. Let's read first 2 rows to check.
            header_check = pd.read_csv(f, nrows=2, header=None)
            f.seek(0)
            
            if 'agg_trade_id' in str(header_check.iloc[0, 0]):
                df = pd.read_csv(f, dtype=dtypes)
            else:
                df = pd.read_csv(f, names=['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id', 'transact_time', 'is_buyer_maker'], dtype=dtypes)
    
    raw_row_count = len(df)
    print(f"Parsed {raw_row_count} rows.")
    
    # 1. Validation
    assert (df['quantity'] > 0).all(), "Zero or negative quantities found"
    assert (df['price'] > 0).all(), "Zero or negative prices found"
    assert not df['transact_time'].isnull().any(), "NaN timestamps found"
    
    # 2. Signed Aggressor Volume
    df['signed_volume'] = np.where(df['is_buyer_maker'], -df['quantity'], df['quantity'])
    df['buy_volume'] = np.where(~df['is_buyer_maker'], df['quantity'], 0.0)
    df['sell_volume'] = np.where(df['is_buyer_maker'], df['quantity'], 0.0)
    
    first_ts = pd.to_datetime(df['transact_time'].iloc[0], unit='ms')
    last_ts = pd.to_datetime(df['transact_time'].iloc[-1], unit='ms')
    
    # 3. Aggregate to 1m
    df['minute'] = pd.to_datetime(df['transact_time'], unit='ms').dt.floor('1min')
    
    df_1m = df.groupby('minute').agg(
        delta_volume=('signed_volume', 'sum'),
        total_volume=('quantity', 'sum'),
        buy_volume=('buy_volume', 'sum'),
        sell_volume=('sell_volume', 'sum')
    ).reset_index()
    
    # Validate conservation
    assert np.isclose(df_1m['delta_volume'].sum(), df['signed_volume'].sum()), "Delta Volume Leak!"
    assert np.isclose(df_1m['buy_volume'].sum() + df_1m['sell_volume'].sum(), df_1m['total_volume'].sum()), "Total Volume Leak!"
    
    # 4. Derive 5m and 15m
    df_1m_idx = df_1m.set_index('minute')
    df_5m = df_1m_idx.resample('5min').sum().reset_index()
    df_15m = df_1m_idx.resample('15min').sum().reset_index()
    
    # 5. Save output
    out_dir = os.path.join("research", "data", "normalized", "cvd")
    os.makedirs(os.path.join(out_dir, "1m"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "5m"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "15m"), exist_ok=True)
    
    out_1m = os.path.join(out_dir, "1m", f"{symbol}-{year}-{month:02d}.parquet")
    df_1m.to_parquet(out_1m, index=False)
    
    df_5m.to_parquet(os.path.join(out_dir, "5m", f"{symbol}-{year}-{month:02d}.parquet"), index=False)
    df_15m.to_parquet(os.path.join(out_dir, "15m", f"{symbol}-{year}-{month:02d}.parquet"), index=False)
    
    # Output stats
    print("\n" + "="*50)
    print("PHASE 5.3 FIRST MONTH VALIDATION REPORT")
    print("="*50)
    print(f"Symbol: {symbol}")
    print(f"Month: {year}-{month:02d}")
    print(f"Raw File Size: {raw_size_mb:.2f} MB (zipped)")
    print(f"Raw Row Count: {raw_row_count:,}")
    print(f"First Timestamp: {first_ts}")
    print(f"Last Timestamp: {last_ts}")
    print(f"Validation Status: PASS")
    print(f"Generated 1m row count: {len(df_1m):,}")
    print(f"Generated 5m row count: {len(df_5m):,}")
    print(f"Generated 15m row count: {len(df_15m):,}")
    print(f"Total Buy Volume: {df_1m['buy_volume'].sum():,.2f}")
    print(f"Total Sell Volume: {df_1m['sell_volume'].sum():,.2f}")
    print(f"Total Delta Volume: {df_1m['delta_volume'].sum():,.2f}")
    print(f"Output 1m file size: {os.path.getsize(out_1m) / 1024:.2f} KB")
    print(f"Disk space saved: ~99% (No raw files retained on disk)")
    
if __name__ == "__main__":
    process_monthly_cvd("BTCUSDT", 2022, 1)
