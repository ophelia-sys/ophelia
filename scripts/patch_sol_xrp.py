import os
import zipfile
import pandas as pd
import urllib.request
import tempfile
import shutil

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
SYMBOLS = ["SOLUSDT", "XRPUSDT"]
MISSING = {
    "2022-02": ["2022-02-26", "2022-02-27", "2022-02-28"],
    "2022-04": ["2022-04-01", "2022-04-02"]
}

COLUMNS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count',
    'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
]

def load_zip_csv(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            df = pd.read_csv(f, names=COLUMNS, header=None)
            if str(df['open_time'].iloc[0]).startswith('open'):
                df = df.iloc[1:].copy()
            df['open_time'] = df['open_time'].astype('int64')
            return df

def download_daily(symbol, date_str, temp_dir):
    url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{date_str}.zip"
    dest_path = os.path.join(temp_dir, f"{symbol}-1m-{date_str}.zip")
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest_path)
    return load_zip_csv(dest_path)

def patch_datasets():
    with tempfile.TemporaryDirectory() as temp_dir:
        for symbol in SYMBOLS:
            for month_str, days in MISSING.items():
                year, month = month_str.split('-')
                monthly_filename = f"{symbol}-1m-{year}-{month}.zip"
                monthly_path = os.path.join(RAW_DIR, symbol, monthly_filename)
                
                print(f"Patching {monthly_path}...")
                monthly_df = load_zip_csv(monthly_path)
                
                daily_dfs = []
                for day in days:
                    df = download_daily(symbol, day, temp_dir)
                    daily_dfs.append(df)
                    
                combined = pd.concat([monthly_df] + daily_dfs, ignore_index=True)
                combined = combined.drop_duplicates(subset=['open_time'])
                combined = combined.sort_values('open_time').reset_index(drop=True)
                
                # Write back to zip
                csv_filename = monthly_filename.replace('.zip', '.csv')
                csv_path = os.path.join(temp_dir, csv_filename)
                combined.to_csv(csv_path, index=False, header=False)
                
                with zipfile.ZipFile(monthly_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    z.write(csv_path, arcname=csv_filename)
                    
                print(f"Successfully patched {monthly_filename} for {symbol}. Rows: {len(combined)}")

if __name__ == "__main__":
    patch_datasets()
