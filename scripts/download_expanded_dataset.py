import os
import sys
import datetime
import concurrent.futures
import time

# Ensure we can import from research
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.data.download_vision import VisionDownloader

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
START_DATE = datetime.date(2022, 1, 1)
END_DATE = datetime.date(2023, 12, 31)

def main():
    downloader = VisionDownloader()
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw'))
    os.makedirs(base_dir, exist_ok=True)
    
    download_tasks = []
    
    for symbol in SYMBOLS:
        symbol_dir = os.path.join(base_dir, symbol)
        os.makedirs(symbol_dir, exist_ok=True)
        
        # Monthly klines
        curr = START_DATE.replace(day=1)
        while curr <= END_DATE:
            url = downloader.construct_klines_url(symbol, '1m', curr.year, curr.month, is_daily=False)
            filename = url.split('/')[-1]
            dest_path = os.path.join(symbol_dir, filename)
            download_tasks.append((url, dest_path))
            
            if curr.month == 12:
                curr = curr.replace(year=curr.year+1, month=1)
            else:
                curr = curr.replace(month=curr.month+1)
                
        # Daily metrics
        curr = START_DATE
        while curr <= END_DATE:
            url = downloader.construct_metrics_url(symbol, curr.year, curr.month, curr.day)
            filename = url.split('/')[-1]
            dest_path = os.path.join(symbol_dir, filename)
            download_tasks.append((url, dest_path))
            curr += datetime.timedelta(days=1)
            
    print(f"Total files to download: {len(download_tasks)}")
    
    def worker(task):
        url, dest_path = task
        success = downloader.download_file(url, dest_path)
        return success
    
    success_count = 0
    fail_count = 0
    
    # Use max_workers=10 to avoid hammering Binance too aggressively, but enough to saturate bandwidth
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(worker, task): task for task in download_tasks}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            success = future.result()
            if success:
                success_count += 1
            else:
                fail_count += 1
            
            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{len(download_tasks)} (Success: {success_count}, Fail: {fail_count})")
                
    print(f"Download complete. Success: {success_count}, Failed: {fail_count}")
    
if __name__ == '__main__':
    main()
