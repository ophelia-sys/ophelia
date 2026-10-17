import os
import sys
import zipfile
import urllib.request
import hashlib
from datetime import datetime

class AggTradesDownloader:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, 'raw', 'aggTrades')
        self.status_file = os.path.join(self.raw_dir, 'download_status.log')
        os.makedirs(self.raw_dir, exist_ok=True)
        
    def _log_status(self, msg):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self.status_file, "a") as f:
            f.write(line + "\n")
            
    def _verify_zip(self, filepath):
        if not os.path.exists(filepath):
            return False
        try:
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                if zip_ref.testzip() is not None:
                    return False
                # Optionally check if CSV exists inside
                names = zip_ref.namelist()
                if not any(n.endswith('.csv') for n in names):
                    return False
            return True
        except Exception:
            return False
            
    def download_month(self, symbol, year, month):
        base_url = "https://data.binance.vision/data/futures/um/monthly/aggTrades"
        month_str = f"{month:02d}"
        filename = f"{symbol.upper()}-aggTrades-{year}-{month_str}.zip"
        checksum_filename = f"{filename}.CHECKSUM"
        
        url = f"{base_url}/{symbol.upper()}/{year}-{month_str}/{filename}"
        checksum_url = f"{base_url}/{symbol.upper()}/{year}-{month_str}/{checksum_filename}"
        
        dest_path = os.path.join(self.raw_dir, filename)
        checksum_path = os.path.join(self.raw_dir, checksum_filename)
        
        # 1. Skip if valid zip already exists
        if self._verify_zip(dest_path):
            self._log_status(f"SKIPPED {filename} - Valid ZIP already exists.")
            return True
            
        # 2. Download Checksum
        try:
            urllib.request.urlretrieve(checksum_url, checksum_path)
        except Exception as e:
            self._log_status(f"ERROR {checksum_filename} - Failed to download checksum: {e}")
            return False
            
        with open(checksum_path, 'r') as f:
            expected_checksum = f.read().split()[0].strip()
            
        # 3. Download ZIP
        self._log_status(f"DOWNLOADING {filename}...")
        try:
            urllib.request.urlretrieve(url, dest_path)
        except Exception as e:
            self._log_status(f"ERROR {filename} - Failed to download ZIP: {e}")
            return False
            
        # 4. Verify Checksum
        sha256_hash = hashlib.sha256()
        with open(dest_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        actual_checksum = sha256_hash.hexdigest()
        
        if actual_checksum != expected_checksum:
            self._log_status(f"ERROR {filename} - Checksum mismatch. Expected: {expected_checksum}, Actual: {actual_checksum}")
            os.remove(dest_path)
            return False
            
        # 5. Verify ZIP integrity
        if not self._verify_zip(dest_path):
            self._log_status(f"ERROR {filename} - ZIP integrity check failed.")
            os.remove(dest_path)
            return False
            
        self._log_status(f"SUCCESS {filename} - Downloaded and verified.")
        return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot', action='store_true', help='Run 1-month BTCUSDT pilot')
    args = parser.parse_args()
    
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
    downloader = AggTradesDownloader(data_dir)
    
    if args.pilot:
        print("Starting 1-month BTCUSDT pilot download (Jan 2023)...")
        success = downloader.download_month('BTCUSDT', 2023, 1)
        if success:
            print("Pilot download verified successfully. Ready for full extraction pilot.")
        else:
            print("Pilot download failed.")
