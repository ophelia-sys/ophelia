import os
import zipfile
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import sys
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
YEARS = [2022, 2023]
MONTHS = list(range(1, 13))
EXPECTED_CANDLES = 1051200 # 2 years

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
            for c in ['open', 'high', 'low', 'close', 'volume']:
                df[c] = df[c].astype('float64')
            return df

def validate_1m():
    results = []
    
    for symbol in SYMBOLS:
        print(f"Validating {symbol} 1m...")
        dfs = []
        for year in YEARS:
            for month in MONTHS:
                filename = f"{symbol}-1m-{year}-{month:02d}.zip"
                path = os.path.join(RAW_DIR, symbol, filename)
                if os.path.exists(path):
                    df = load_zip_csv(path)
                    dfs.append(df)
        
        if not dfs:
            results.append({
                'symbol': symbol, 'expected': EXPECTED_CANDLES, 'actual': 0, 'missing': EXPECTED_CANDLES,
                'duplicates': 0, 'first': None, 'last': None, 'status': 'MISSING'
            })
            continue
            
        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.sort_values('open_time').reset_index(drop=True)
        
        actual_count = len(combined)
        first_ts = combined['open_time'].min()
        last_ts = combined['open_time'].max()
        
        # Calculate gaps
        time_diffs = combined['open_time'].diff().dropna()
        missing_candles = int((time_diffs > 60000).sum() + ((time_diffs[time_diffs > 60000] - 60000) / 60000).sum())
        
        # Calculate expected based on start and end
        expected_span = int((last_ts - first_ts) / 60000) + 1
        missing_intervals = expected_span - actual_count if expected_span > actual_count else 0
        
        duplicates = combined['open_time'].duplicated().sum()
        
        malformed = ((combined['high'] < combined['open']) | 
                     (combined['high'] < combined['close']) |
                     (combined['low'] > combined['open']) | 
                     (combined['low'] > combined['close'])).sum()
        
        nan_inf = combined.isnull().sum().sum() + np.isinf(combined[['open','high','low','close','volume']]).sum().sum()
        
        status = 'COMPLETE' if missing_intervals == 0 and duplicates == 0 and malformed == 0 and nan_inf == 0 and actual_count == EXPECTED_CANDLES else 'PARTIAL/ERRORS'
        
        results.append({
            'symbol': symbol,
            'expected': int(EXPECTED_CANDLES),
            'actual': int(actual_count),
            'missing': int(missing_intervals),
            'duplicates': int(duplicates),
            'first': int(first_ts) if first_ts is not pd.NaT else None,
            'last': int(last_ts) if last_ts is not pd.NaT else None,
            'malformed': int(malformed),
            'nan_inf': int(nan_inf),
            'status': status
        })
        
    return results

def compare_native_vs_resampled():
    print("Comparing native 5m vs resampled 1m for BTCUSDT 2022-01...")
    # 1. Load 1m
    path_1m = os.path.join(RAW_DIR, "BTCUSDT", "BTCUSDT-1m-2022-01.zip")
    df_1m = load_zip_csv(path_1m)
    df_1m['dt'] = pd.to_datetime(df_1m['open_time'], unit='ms')
    df_1m.set_index('dt', inplace=True)
    
    # Resample
    resampled = df_1m.resample('5min').agg({
        'open_time': 'first',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # 2. Download native 5m if not exists
    path_5m = os.path.join(RAW_DIR, "BTCUSDT", "BTCUSDT-5m-2022-01.zip")
    if not os.path.exists(path_5m):
        url = "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2022-01.zip"
        urllib.request.urlretrieve(url, path_5m)
        
    df_5m = load_zip_csv(path_5m)
    
    # Merge and compare
    comp = resampled.merge(df_5m, on='open_time', suffixes=('_res', '_nat'))
    
    diff_open = (comp['open_res'] - comp['open_nat']).abs().max()
    diff_high = (comp['high_res'] - comp['high_nat']).abs().max()
    diff_low = (comp['low_res'] - comp['low_nat']).abs().max()
    diff_close = (comp['close_res'] - comp['close_nat']).abs().max()
    diff_vol = (comp['volume_res'] - comp['volume_nat']).abs().max()
    
    match_count = len(comp)
    expected_count = len(df_5m)
    
    return {
        'diff_open': float(diff_open),
        'diff_high': float(diff_high),
        'diff_low': float(diff_low),
        'diff_close': float(diff_close),
        'diff_vol': float(diff_vol),
        'match_count': int(match_count),
        'expected_count': int(expected_count)
    }

if __name__ == "__main__":
    res_1m = validate_1m()
    res_cmp = compare_native_vs_resampled()
    
    output = {
        '1m_completeness': res_1m,
        'native_vs_resampled': res_cmp
    }
    
    with open('audit_results.json', 'w') as f:
        json.dump(output, f, indent=4)
    print("Validation complete. Results saved to audit_results.json")
