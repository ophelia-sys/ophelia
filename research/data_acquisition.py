import urllib.request
import zipfile
import io
import os
import ssl
from datetime import datetime, timedelta

ssl._create_default_https_context = ssl._create_unverified_context

def download_binance_vision_daily(market_type, data_type, symbol, date_str, base_dir):
    url = f"https://data.binance.vision/data/futures/{market_type}/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date_str}.zip"
    target_dir = os.path.join(base_dir, 'raw', 'binance', 'futures', market_type, symbol, data_type)
    os.makedirs(target_dir, exist_ok=True)
    
    # Check if already exists (check for csv inside)
    csv_path = os.path.join(target_dir, f"{symbol}-{data_type}-{date_str}.csv")
    if os.path.exists(csv_path):
        print(f"Already exists: {csv_path}")
        return

    print(f"Downloading {url} ...")
    try:
        response = urllib.request.urlopen(url, timeout=30)
        with zipfile.ZipFile(io.BytesIO(response.read())) as z:
            z.extractall(target_dir)
            print(f"Success! Extracted to {target_dir}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

if __name__ == "__main__":
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data"
    
    start_date = datetime(2023, 11, 1)
    for i in range(15): # 15 days
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        download_binance_vision_daily('um', 'bookTicker', 'BTCUSDT', date_str, base_dir)
        download_binance_vision_daily('um', 'aggTrades', 'BTCUSDT', date_str, base_dir)

