import pandas as pd
import numpy as np
import requests
import zipfile
import io
import time

def audit_symbol_month(symbol, year, month):
    url = f"https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{year}-{month:02d}.zip"
    print(f"\n{'='*60}\nAuditing {symbol} {year}-{month:02d}\n{'='*60}")
    
    response = requests.get(url, stream=True)
    zip_content = io.BytesIO()
    for chunk in response.iter_content(chunk_size=4*1024*1024):
        if chunk:
            zip_content.write(chunk)
            
    zip_content.seek(0)
    
    with zipfile.ZipFile(zip_content) as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            dtypes = {
                'agg_trade_id': 'int64',
                'price': 'float64',
                'quantity': 'float64',
                'first_trade_id': 'int64',
                'last_trade_id': 'int64',
                'transact_time': 'int64',
                'is_buyer_maker': 'bool'
            }
            header_check = pd.read_csv(f, nrows=2, header=None)
            f.seek(0)
            if 'agg_trade_id' in str(header_check.iloc[0, 0]):
                df = pd.read_csv(f, dtype=dtypes)
            else:
                df = pd.read_csv(f, names=['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id', 'transact_time', 'is_buyer_maker'], dtype=dtypes)
                
    raw_row_count = len(df)
    unique_ids = df['agg_trade_id'].nunique()
    dup_count = raw_row_count - unique_ids
    
    print(f"Total Rows: {raw_row_count:,}")
    print(f"Unique IDs: {unique_ids:,}")
    print(f"Duplicate IDs (surplus rows): {dup_count:,}")
    print(f"Duplicate %: {dup_count / raw_row_count * 100:.2f}%")
    
    if dup_count == 0:
        print("No duplicates found.")
        return
        
    # Check Ordering
    is_id_monotonic = df['agg_trade_id'].is_monotonic_increasing
    is_ts_monotonic = df['transact_time'].is_monotonic_increasing
    print(f"ID monotonic increasing: {is_id_monotonic}")
    print(f"Time monotonic increasing: {is_ts_monotonic}")
    
    # Analyze Duplicates
    dup_mask = df.duplicated(subset=['agg_trade_id'], keep=False)
    df_dups = df[dup_mask]
    
    num_exact = df.duplicated(keep=False).sum()
    print(f"Total rows in duplicate groups: {len(df_dups):,}")
    print(f"Total exact duplicate rows (all columns match): {num_exact:,}")
    
    if len(df_dups) == num_exact:
        print("CLASSIFICATION: EXACT_DUPLICATE (All duplicated rows are identical)")
        classification = "EXACT_DUPLICATE"
    else:
        print("CLASSIFICATION: CONFLICTING_DUPLICATE (Some fields differ)")
        classification = "CONFLICTING_DUPLICATE"
        
    # Duplication structure
    first_dup_ts = pd.to_datetime(df_dups['transact_time'].min(), unit='ms')
    last_dup_ts = pd.to_datetime(df_dups['transact_time'].max(), unit='ms')
    print(f"First duplicated timestamp: {first_dup_ts}")
    print(f"Last duplicated timestamp: {last_dup_ts}")
    
    df['is_dup_row'] = df.duplicated(keep='first')
    dup_indices = df.index[df['is_dup_row']]
    
    if len(dup_indices) > 0:
        blocks = np.split(dup_indices, np.where(np.diff(dup_indices) != 1)[0]+1)
        print(f"Found {len(blocks)} contiguous blocks of duplicated rows.")
        largest_block = max(blocks, key=len)
        print(f"Largest contiguous block: {len(largest_block):,} rows")
        
        for i, b in enumerate(blocks[:3]):
            print(f"  Block {i+1}: length {len(b):,}, from idx {b[0]} to {b[-1]}, time {pd.to_datetime(df.at[b[0], 'transact_time'], unit='ms')} to {pd.to_datetime(df.at[b[-1], 'transact_time'], unit='ms')}")
        if len(blocks) > 3: print("  ...")
    
    if classification == "EXACT_DUPLICATE":
        print("\n--- SIMULATING REPAIR ---")
        df_clean = df.drop_duplicates(subset=['agg_trade_id'], keep='first').copy()
        print(f"Rows removed: {raw_row_count - len(df_clean):,}")
        
        # Calculate Volume Before
        buy_vol_before = np.where(~df['is_buyer_maker'], df['quantity'], 0.0).sum()
        sell_vol_before = np.where(df['is_buyer_maker'], df['quantity'], 0.0).sum()
        delta_before = buy_vol_before - sell_vol_before
        
        # Calculate Volume After
        buy_vol_after = np.where(~df_clean['is_buyer_maker'], df_clean['quantity'], 0.0).sum()
        sell_vol_after = np.where(df_clean['is_buyer_maker'], df_clean['quantity'], 0.0).sum()
        delta_after = buy_vol_after - sell_vol_after
        
        print(f"Buy Vol Before: {buy_vol_before:,.2f} | After: {buy_vol_after:,.2f} | Diff: {buy_vol_after - buy_vol_before:,.2f}")
        print(f"Sell Vol Before: {sell_vol_before:,.2f} | After: {sell_vol_after:,.2f} | Diff: {sell_vol_after - sell_vol_before:,.2f}")
        print(f"Delta Before: {delta_before:,.2f} | After: {delta_after:,.2f} | Diff: {delta_after - delta_before:,.2f}")
        
        # CVD Conservation test
        df_clean['signed_volume'] = np.where(df_clean['is_buyer_maker'], -df_clean['quantity'], df_clean['quantity'])
        df_clean['buy_volume'] = np.where(~df_clean['is_buyer_maker'], df_clean['quantity'], 0.0)
        df_clean['sell_volume'] = np.where(df_clean['is_buyer_maker'], df_clean['quantity'], 0.0)
        
        df_clean['minute'] = pd.to_datetime(df_clean['transact_time'], unit='ms').dt.floor('1min')
        df_1m = df_clean.groupby('minute').agg(
            delta_volume=('signed_volume', 'sum'),
            total_volume=('quantity', 'sum'),
            buy_volume=('buy_volume', 'sum'),
            sell_volume=('sell_volume', 'sum')
        ).reset_index()
        
        calc_delta = df_1m['buy_volume'] - df_1m['sell_volume']
        max_err = np.abs(df_1m['delta_volume'] - calc_delta).max()
        print(f"Max Absolute Conservation Error (1m): {max_err:.2e}")
        
        if df_clean['agg_trade_id'].is_monotonic_increasing and df_clean['transact_time'].is_monotonic_increasing:
            print("FINAL STATUS: CASE A (REPAIR APPROVED) - Monotonicity restored and conservation error is tiny.")
        else:
            print("FINAL STATUS: CASE A (REPAIR APPROVED) - But note monotonicity is not strict!")
            
if __name__ == '__main__':
    audit_symbol_month('BTCUSDT', 2022, 9)
    audit_symbol_month('ETHUSDT', 2022, 9)
