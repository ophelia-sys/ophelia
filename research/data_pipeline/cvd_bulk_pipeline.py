import pandas as pd
import numpy as np
import requests
import zipfile
import io
import os
import json
import time
import datetime
import traceback
import math

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
YEARS = [2022, 2023]
MONTHS = list(range(1, 13))
MANIFEST_PATH = 'research/data/normalized/cvd/manifest.json'
REPAIRS_PATH = 'research/data/manifests/aggtrades_repairs.json'

os.makedirs('research/data/normalized/cvd/1m', exist_ok=True)
os.makedirs('research/data/normalized/cvd/5m', exist_ok=True)
os.makedirs('research/data/normalized/cvd/15m', exist_ok=True)
os.makedirs('research/data/normalized/cvd/final', exist_ok=True)
os.makedirs('research/data/manifests', exist_ok=True)

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return {} if 'manifest' in path else []
    return {} if 'manifest' in path else []

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def repair_exact_duplicate_aggtrade_ids(df, symbol, year, month):
    dup_mask = df.duplicated(subset=['agg_trade_id'], keep=False)
    dup_count = dup_mask.sum()
    unique_ids = df['agg_trade_id'].nunique()
    
    if dup_count == 0:
        return df, False, 0, unique_ids
        
    exact_dup_mask = df.duplicated(keep=False)
    
    if not dup_mask.equals(exact_dup_mask):
        raise AssertionError("CONFLICTING_DUPLICATE: Duplicate agg_trade_id records contain conflicting fields.")
        
    df_clean = df.drop_duplicates(subset=['agg_trade_id'], keep='first').copy()
    rows_removed = len(df) - len(df_clean)
    
    repair_record = {
        "symbol": symbol,
        "month": f"{year}-{month:02d}",
        "source": "BINANCE_HISTORICAL",
        "repair_type": "EXACT_DUPLICATE_ID_REMOVAL",
        "rows_before": len(df),
        "rows_after": len(df_clean),
        "duplicate_rows_removed": rows_removed,
        "conflicting_duplicates": 0,
        "repair_verified": True
    }
    
    repairs = load_json(REPAIRS_PATH)
    if not isinstance(repairs, list):
        repairs = []
    repairs.append(repair_record)
    save_json(repairs, REPAIRS_PATH)
    
    print(f"[{symbol}-{year}-{month:02d}] REPAIRED: removed {rows_removed} exact duplicate rows.")
    return df_clean, True, rows_removed, unique_ids

def process_month(symbol, year, month, manifest):
    month_key = f"{symbol}-{year}-{month:02d}"
    
    # Check resumability
    if month_key in manifest:
        m = manifest[month_key]
        if m.get('final_status') in ['PASS', 'VALIDATED', 'REPAIRED_EXACT_DUPLICATES']:
            print(f"[{month_key}] Skipping, already completed successfully.")
            return m
            
    url = f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{year}-{month:02d}.zip"
    print(f"[{month_key}] Downloading {url}...")
    
    t0 = time.time()
    try:
        response = requests.get(url, stream=True, timeout=60)
        if response.status_code != 200:
            status = 'MISSING' if response.status_code == 404 else f'FAILED_{response.status_code}'
            print(f"[{month_key}] Download failed: {status}")
            manifest[month_key] = {'final_status': status, 'symbol': symbol, 'month': f"{year}-{month:02d}", 'source_url': url}
            save_json(manifest, MANIFEST_PATH)
            return manifest[month_key]
            
        zip_content = io.BytesIO()
        for chunk in response.iter_content(chunk_size=4*1024*1024):
            if chunk: zip_content.write(chunk)
                
        zip_content.seek(0)
        raw_size_mb = len(zip_content.getvalue()) / (1024*1024)
        
        with zipfile.ZipFile(zip_content) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                dtypes = {
                    'agg_trade_id': 'int64', 'price': 'float64', 'quantity': 'float64',
                    'first_trade_id': 'int64', 'last_trade_id': 'int64', 'transact_time': 'int64', 'is_buyer_maker': 'bool'
                }
                header_check = pd.read_csv(f, nrows=2, header=None)
                f.seek(0)
                if 'agg_trade_id' in str(header_check.iloc[0, 0]):
                    df = pd.read_csv(f, dtype=dtypes)
                else:
                    df = pd.read_csv(f, names=['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id', 'transact_time', 'is_buyer_maker'], dtype=dtypes)
        
        del zip_content
        raw_row_count = len(df)
        
        # Repair logic
        df, was_repaired, removed, unique_ids = repair_exact_duplicate_aggtrade_ids(df, symbol, year, month)
        
        # Post-repair validations
        assert df['agg_trade_id'].duplicated().sum() == 0, "Duplicate IDs still present after repair!"
        assert (df['quantity'] >= 0).all(), "Negative quantities found"
        assert (df['price'] > 0).all(), "Zero/negative prices found"
        assert not df['transact_time'].isnull().any(), "NaN timestamps found"
        assert df['is_buyer_maker'].isin([True, False]).all(), "Invalid is_buyer_maker values"
        assert df['agg_trade_id'].is_monotonic_increasing, "agg_trade_id not monotonic increasing"
        assert df['transact_time'].is_monotonic_increasing, "transact_time not monotonic increasing"
        
        df['datetime'] = pd.to_datetime(df['transact_time'], unit='ms')
        first_ts = df['datetime'].iloc[0]
        last_ts = df['datetime'].iloc[-1]
        
        assert first_ts.year == year and first_ts.month == month, f"First timestamp {first_ts} out of bounds"
        
        # Float64 volume
        df['signed_volume'] = np.where(df['is_buyer_maker'], -df['quantity'], df['quantity'])
        df['buy_volume'] = np.where(~df['is_buyer_maker'], df['quantity'], 0.0)
        df['sell_volume'] = np.where(df['is_buyer_maker'], df['quantity'], 0.0)
        
        df['minute'] = df['datetime'].dt.floor('1min')
        df_1m = df.groupby('minute').agg(
            delta_volume=('signed_volume', 'sum'),
            total_volume=('quantity', 'sum'),
            buy_volume=('buy_volume', 'sum'),
            sell_volume=('sell_volume', 'sum')
        ).reset_index()
        
        monthly_buy_volume = math.fsum(df['buy_volume'])
        monthly_sell_volume = math.fsum(df['sell_volume'])
        monthly_delta_volume = monthly_buy_volume - monthly_sell_volume
        monthly_direct_signed_delta = math.fsum(df['signed_volume'])
        
        del df
        
        scale = max(abs(monthly_buy_volume), abs(monthly_sell_volume), abs(monthly_delta_volume), 1.0)
        tolerance = max(1e-10, scale * 1e-15)
        absolute_error = abs(monthly_delta_volume - monthly_direct_signed_delta)
        relative_error = absolute_error / scale
        
        assert absolute_error <= tolerance, f"Conservation error exceeded scale-aware tolerance! Abs err: {absolute_error}, Tolerance: {tolerance}"
        
        sum_1m_delta = math.fsum(df_1m['delta_volume'])
        error_1m = abs(sum_1m_delta - monthly_direct_signed_delta)
        assert error_1m <= tolerance, f"1m aggregation conservation error exceeded tolerance! Err: {error_1m}, Tolerance: {tolerance}"
        
        df_1m_idx = df_1m.set_index('minute')
        df_5m = df_1m_idx.resample('5min').sum().reset_index()
        df_15m = df_1m_idx.resample('15min').sum().reset_index()
        
        sum_5m_delta = math.fsum(df_5m['delta_volume'])
        error_5m = abs(sum_1m_delta - sum_5m_delta)
        assert error_5m <= tolerance, f"5m aggregation conservation error exceeded tolerance! Err: {error_5m}, Tolerance: {tolerance}"

        sum_15m_delta = math.fsum(df_15m['delta_volume'])
        error_15m = abs(sum_1m_delta - sum_15m_delta)
        assert error_15m <= tolerance, f"15m aggregation conservation error exceeded tolerance! Err: {error_15m}, Tolerance: {tolerance}"
        
        out_1m = f"research/data/normalized/cvd/1m/{month_key}.parquet"
        out_5m = f"research/data/normalized/cvd/5m/{month_key}.parquet"
        out_15m = f"research/data/normalized/cvd/15m/{month_key}.parquet"
        
        df_1m.to_parquet(out_1m, index=False)
        df_5m.to_parquet(out_5m, index=False)
        df_15m.to_parquet(out_15m, index=False)
        
        res = {
            'symbol': symbol,
            'month': f"{year}-{month:02d}",
            'raw_row_count': int(raw_row_count),
            'duplicate_aggTrade_count': int(removed),
            '1m_row_count': len(df_1m),
            'buy_volume': float(monthly_buy_volume),
            'sell_volume': float(monthly_sell_volume),
            'delta_volume': float(monthly_delta_volume),
            'direct_signed_delta': float(monthly_direct_signed_delta),
            'absolute_error': float(absolute_error),
            'relative_error': float(relative_error),
            'allowed_tolerance': float(tolerance),
            'conservation_status': 'PASS',
            'final_status': 'REPAIRED_EXACT_DUPLICATES' if was_repaired else 'VALIDATED'
        }
        manifest[month_key] = res
        save_json(manifest, MANIFEST_PATH)
        print(f"[{month_key}] Completed. Abs Error: {absolute_error:.2e}, Rel Error: {relative_error:.2e}, Tolerance: {tolerance:.2e}")
        return res
        
    except Exception as e:
        print(f"[{month_key}] FAILED with exception: {e}")
        traceback.print_exc()
        manifest[month_key] = {'final_status': 'QUARANTINED', 'error': str(e), 'symbol': symbol, 'month': f"{year}-{month:02d}"}
        save_json(manifest, MANIFEST_PATH)
        return manifest[month_key]

def generate_report(manifest):
    lines = ["# PHASE 5.3 AGGTRADES DATA FINAL AUDIT\n"]
    lines.append("**Date:** " + datetime.datetime.now().strftime("%Y-%m-%d") + "\n")
    
    lines.append("## Summary Matrix\n")
    lines.append("| Symbol | Month | Status | Rows Processed | Duplicates |")
    lines.append("|--------|-------|--------|----------------|------------|")
    
    total_downloaded = 0
    total_processed = 0
    total_repaired = 0
    total_failed = 0
    total_missing = 0
    total_rows = 0
    
    for symbol in SYMBOLS:
        for year in YEARS:
            for month in MONTHS:
                mk = f"{symbol}-{year}-{month:02d}"
                m = manifest.get(mk, {})
                status = m.get('final_status', 'MISSING')
                rows = m.get('raw_row_count', 0)
                dups = m.get('duplicate_aggTrade_count', 0)
                
                if status in ['VALIDATED', 'PASS']: 
                    total_processed += 1
                    status = 'VALIDATED'
                elif status == 'REPAIRED_EXACT_DUPLICATES': total_repaired += 1
                elif status == 'QUARANTINED': total_failed += 1
                elif status == 'MISSING': total_missing += 1
                
                if status in ['VALIDATED', 'REPAIRED_EXACT_DUPLICATES']:
                    total_downloaded += 1
                    total_rows += rows
                
                lines.append(f"| {symbol} | {year}-{month:02d} | {status} | {rows:,} | {dups:,} |")
                
    lines.append("\n## Statistics")
    lines.append(f"- **Total Months Downloaded & Processed:** {total_downloaded}")
    lines.append(f"- **Validated directly (No Duplicates):** {total_processed}")
    lines.append(f"- **Repaired Exact Duplicates:** {total_repaired}")
    lines.append(f"- **Quarantined/Failed:** {total_failed}")
    lines.append(f"- **Missing at Source:** {total_missing}")
    lines.append(f"- **Total Rows Processed:** {total_rows:,}")
    
    # Needs to output to the brain directory
    # I'll save it locally here and let the tool sync it.
    with open('PHASE5_3_AGGTRADES_DATA_FINAL_AUDIT.md', 'w') as f:
        f.write("\n".join(lines))

def run_pipeline():
    manifest = load_json(MANIFEST_PATH)
    
    for symbol in SYMBOLS:
        print(f"=== Starting {symbol} ===")
        for year in YEARS:
            for month in MONTHS:
                process_month(symbol, year, month, manifest)
                
    # Refresh manifest and generate report
    manifest = load_json(MANIFEST_PATH)
    generate_report(manifest)

if __name__ == '__main__':
    run_pipeline()
    print("ALL DONE")
