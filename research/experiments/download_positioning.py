import os
import sys
import zipfile
import urllib.request
from datetime import datetime, timedelta
import pandas as pd
import json

class PositioningDownloader:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, 'raw', 'positioning')
        self.norm_dir = os.path.join(data_dir, 'normalized', 'positioning')
        self.status_file = os.path.join(self.raw_dir, 'download_status.log')
        for sub in ['metrics', 'premium_index', 'funding']:
            os.makedirs(os.path.join(self.raw_dir, sub), exist_ok=True)
        os.makedirs(self.norm_dir, exist_ok=True)
            
    def _log(self, msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line)
        with open(self.status_file, "a") as f:
            f.write(line + "\n")
            
    def _download_and_verify(self, url, dest_path):
        if os.path.exists(dest_path):
            try:
                with zipfile.ZipFile(dest_path, 'r') as z:
                    if z.testzip() is None:
                        return True
            except:
                pass
            os.remove(dest_path)
            
        try:
            urllib.request.urlretrieve(url, dest_path)
            with zipfile.ZipFile(dest_path, 'r') as z:
                if z.testzip() is None:
                    return True
            os.remove(dest_path)
            return False
        except Exception as e:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

    def download_all(self, symbols, years, months):
        import concurrent.futures
        tasks = []
        for sym in symbols:
            for y in years:
                for m in months:
                    sym_upper = sym.upper()
                    y_str = str(y)
                    m_str = f"{m:02d}"
                    
                    # 1. Premium Index
                    pi_url = f"https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/{sym_upper}/5m/{sym_upper}-5m-{y_str}-{m_str}.zip"
                    pi_path = os.path.join(self.raw_dir, 'premium_index', f"{sym_upper}-5m-{y_str}-{m_str}.zip")
                    tasks.append((pi_url, pi_path))
                        
                    # 2. Funding Rate
                    fr_url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym_upper}/{sym_upper}-fundingRate-{y_str}-{m_str}.zip"
                    fr_path = os.path.join(self.raw_dir, 'funding', f"{sym_upper}-fundingRate-{y_str}-{m_str}.zip")
                    tasks.append((fr_url, fr_path))
                        
                    # 3. Metrics (Daily)
                    start_date = datetime(y, m, 1)
                    if m == 12:
                        end_date = datetime(y + 1, 1, 1) - timedelta(days=1)
                    else:
                        end_date = datetime(y, m + 1, 1) - timedelta(days=1)
                        
                    curr_date = start_date
                    while curr_date <= end_date:
                        d_str = curr_date.strftime("%Y-%m-%d")
                        met_url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym_upper}/{sym_upper}-metrics-{d_str}.zip"
                        met_path = os.path.join(self.raw_dir, 'metrics', f"{sym_upper}-metrics-{d_str}.zip")
                        tasks.append((met_url, met_path))
                        curr_date += timedelta(days=1)

        self._log(f"Queued {len(tasks)} files for download.")
        import time
        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # We don't need the results necessarily, just wait for them to finish
            list(executor.map(lambda args: self._download_and_verify(*args), tasks))
        t1 = time.time()
        self._log(f"Finished bulk download in {t1 - t0:.1f} seconds")

    def normalize_and_validate(self, symbols):
        md = []
        md.append("# PHASE 5.2 POSITIONING DATA VALIDATION")
        md.append("This document audits the historical Open Interest, Funding Rate, and Premium Index datasets for 2022-2023 across 6 benchmark symbols.")
        md.append("\n## 1. Causal Availability Assumptions & Provenance")
        md.append("- **Provenance**: `data.binance.vision`. Stored independently in `research/data/normalized/positioning/`.")
        md.append("- **Metrics (OI/Long-Short Ratio)**: Native 5m snapshots representing exactly the state at `create_time`. Causal alignment means appending to the 5m OHLCV bar closing at `create_time`.")
        md.append("- **Funding Rate**: Sparse 8-hour events. Retains its exact `calc_time` (e.g., 00:00, 08:00, 16:00). A `funding_age` feature will be calculated at runtime rather than assuming instantaneous forward-fill predictability.")
        md.append("- **Premium Index**: Native 5m klines representing premium fluctuations perfectly synchronized with OHLCV.")
        
        md.append("\n## 2. Dataset Inventory & Missing Data Analysis")
        
        for sym in symbols:
            sym_u = sym.upper()
            self._log(f"Normalizing {sym_u}...")
            
            # --- METRICS ---
            met_files = sorted([os.path.join(self.raw_dir, 'metrics', f) for f in os.listdir(os.path.join(self.raw_dir, 'metrics')) if f.startswith(f"{sym_u}-metrics")])
            dfs_met = []
            for f in met_files:
                try:
                    df = pd.read_csv(f)
                    dfs_met.append(df)
                except:
                    pass
            if dfs_met:
                df_met = pd.concat(dfs_met, ignore_index=True)
                # Drop duplicate headers that might appear
                df_met = df_met[df_met['create_time'] != 'create_time'].copy()
                df_met['create_time'] = pd.to_datetime(df_met['create_time'])
                df_met.sort_values('create_time', inplace=True)
                df_met.drop_duplicates(subset=['create_time'], inplace=True)
                for col in ['sum_open_interest', 'sum_open_interest_value', 'count_long_short_ratio']:
                    df_met[col] = pd.to_numeric(df_met[col], errors='coerce')
                
                df_met.to_parquet(os.path.join(self.norm_dir, f"{sym_u}_metrics.parquet"), index=False)
                met_rows = len(df_met)
                met_nans = df_met.isna().sum().sum()
            else:
                met_rows = 0
                met_nans = 0

            # --- FUNDING ---
            fr_files = sorted([os.path.join(self.raw_dir, 'funding', f) for f in os.listdir(os.path.join(self.raw_dir, 'funding')) if f.startswith(f"{sym_u}-fundingRate")])
            dfs_fr = []
            for f in fr_files:
                try:
                    df = pd.read_csv(f)
                    dfs_fr.append(df)
                except:
                    pass
            if dfs_fr:
                df_fr = pd.concat(dfs_fr, ignore_index=True)
                df_fr = df_fr[df_fr['calc_time'] != 'calc_time'].copy()
                df_fr['calc_time'] = pd.to_numeric(df_fr['calc_time'])
                df_fr['datetime'] = pd.to_datetime(df_fr['calc_time'], unit='ms')
                df_fr.sort_values('calc_time', inplace=True)
                df_fr.drop_duplicates(subset=['calc_time'], inplace=True)
                df_fr['last_funding_rate'] = pd.to_numeric(df_fr['last_funding_rate'], errors='coerce')
                
                df_fr.to_parquet(os.path.join(self.norm_dir, f"{sym_u}_fundingRate.parquet"), index=False)
                fr_rows = len(df_fr)
                fr_nans = df_fr.isna().sum().sum()
            else:
                fr_rows = 0
                fr_nans = 0
                
            # --- PREMIUM INDEX ---
            pi_files = sorted([os.path.join(self.raw_dir, 'premium_index', f) for f in os.listdir(os.path.join(self.raw_dir, 'premium_index')) if f.startswith(f"{sym_u}-5m")])
            dfs_pi = []
            for f in pi_files:
                try:
                    df = pd.read_csv(f, header=None, names=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'count', 'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'])
                    dfs_pi.append(df)
                except:
                    pass
            if dfs_pi:
                df_pi = pd.concat(dfs_pi, ignore_index=True)
                df_pi = df_pi[df_pi['open_time'] != 'open_time'].copy()
                for col in ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'count', 'taker_buy_volume', 'taker_buy_quote_volume', 'ignore']:
                    df_pi[col] = pd.to_numeric(df_pi[col], errors='coerce')
                df_pi.dropna(subset=['open_time'], inplace=True)
                df_pi['datetime'] = pd.to_datetime(df_pi['open_time'], unit='ms')
                df_pi.sort_values('open_time', inplace=True)
                df_pi.drop_duplicates(subset=['open_time'], inplace=True)
                df_pi.to_parquet(os.path.join(self.norm_dir, f"{sym_u}_premiumIndex.parquet"), index=False)
                pi_rows = len(df_pi)
                pi_nans = df_pi.isna().sum().sum()
            else:
                pi_rows = 0
                pi_nans = 0
                
            md.append(f"\n### {sym_u}")
            md.append(f"- **Metrics (OI/LSR)**: {met_rows} rows (Expected ~210,240). Missing/NaNs: {met_nans}.")
            md.append(f"- **Funding Rate**: {fr_rows} rows (Expected ~2,190). Missing/NaNs: {fr_nans}.")
            md.append(f"- **Premium Index**: {pi_rows} rows (Expected ~210,240). Missing/NaNs: {pi_nans}.")
            
            # Basic sanity check reporting
            if met_rows > 0:
                first = df_met['create_time'].iloc[0]
                last = df_met['create_time'].iloc[-1]
                md.append(f"  - Metric Coverage: {first} to {last}")
                
        # Write report
        report_path = r"c:\Users\dopa.mine\.gemini\antigravity-ide\brain\320b7087-6818-4ae4-9442-87b81c2ec8e0\PHASE5_2_POSITIONING_DATA_VALIDATION.md"
        with open(report_path, "w") as f:
            f.write("\n".join(md))
        print(f"Validation report saved to {report_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bulk', action='store_true')
    args = parser.parse_args()
    
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
    downloader = PositioningDownloader(data_dir)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    years = [2022, 2023]
    months = list(range(1, 13))
    
    if args.bulk:
        print("Starting bulk download of positioning data...")
        downloader.download_all(symbols, years, months)
        print("Normalizing and validating datasets...")
        downloader.normalize_and_validate(symbols)
