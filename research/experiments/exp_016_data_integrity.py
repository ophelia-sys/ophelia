import pandas as pd
import numpy as np
import os
import glob
from pathlib import Path

def run_integrity_audit():
    print("========================================")
    print("EXP 016: HISTORICAL DATA INTEGRITY AUDIT")
    print("========================================")
    
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT"
    
    # 1. Check bookTicker
    book_files = sorted(glob.glob(os.path.join(base_dir, 'bookTicker', '*.csv')))
    if not book_files:
        print("ERROR: No bookTicker files found.")
        return
        
    print(f"Found {len(book_files)} bookTicker files.")
    
    # Process the first few files to save memory
    book_dfs = []
    for f in book_files[:5]: 
        # Columns: update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty, transaction_time, event_time
        try:
            df = pd.read_csv(f, header=0)
            df.columns = ['update_id', 'bid_p', 'bid_q', 'ask_p', 'ask_q', 'transact_time', 'event_time']
            book_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if book_dfs:
        book_df = pd.concat(book_dfs, ignore_index=True)
        print("\n--- bookTicker Audit ---")
        total_rows = len(book_df)
        
        # Duplicates
        duplicates = book_df['update_id'].duplicated().sum()
        dup_rate = duplicates / total_rows * 100
        print(f"Total rows: {total_rows}")
        print(f"Duplicate update_ids: {duplicates} ({dup_rate:.4f}%)")
        
        # Sequence gaps
        # bookTicker updates in Binance are not strictly +1 sequence IDs like depth events, 
        # they are snapshot pushes. So update_id jumps are normal, but let's check ordering.
        out_of_order = (book_df['update_id'].diff() <= 0).sum() - duplicates # subtract dups
        print(f"Out of order update_ids: {out_of_order}")
        
        # Crossed book
        crossed = (book_df['bid_p'] > book_df['ask_p']).sum()
        print(f"Crossed book instances (bid > ask): {crossed}")
        
        # Invalid prices
        invalid_p = ((book_df['bid_p'] <= 0) | (book_df['ask_p'] <= 0)).sum()
        print(f"Invalid prices (<= 0): {invalid_p}")
        
        # Timestamp gaps
        book_df['dt'] = pd.to_datetime(book_df['transact_time'], unit='ms')
        max_gap = book_df['dt'].diff().dt.total_seconds().max()
        print(f"Maximum timestamp gap: {max_gap} seconds")

    # 2. Check aggTrades
    trade_files = sorted(glob.glob(os.path.join(base_dir, 'aggTrades', '*.csv')))
    if not trade_files:
        print("ERROR: No aggTrades files found.")
        return
        
    print(f"\nFound {len(trade_files)} aggTrades files.")
    trade_dfs = []
    for f in trade_files[:5]:
        # Columns: agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker
        try:
            df = pd.read_csv(f, header=0)
            df.columns = ['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id', 'transact_time', 'is_buyer_maker']
            trade_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if trade_dfs:
        trade_df = pd.concat(trade_dfs, ignore_index=True)
        print("\n--- aggTrades Audit ---")
        total_rows = len(trade_df)
        
        # Duplicates
        duplicates = trade_df['agg_trade_id'].duplicated().sum()
        dup_rate = duplicates / total_rows * 100
        print(f"Total rows: {total_rows}")
        print(f"Duplicate agg_trade_ids: {duplicates} ({dup_rate:.4f}%)")
        
        # Sequence missing
        min_id = trade_df['agg_trade_id'].min()
        max_id = trade_df['agg_trade_id'].max()
        expected = max_id - min_id + 1
        missing = expected - total_rows + duplicates
        print(f"Missing agg_trade_ids in sequence: {missing}")
        
        # Invalid prices/qty
        invalid_vals = ((trade_df['price'] <= 0) | (trade_df['quantity'] <= 0)).sum()
        print(f"Invalid price or qty (<= 0): {invalid_vals}")
        
        # Timestamp gaps
        trade_df['dt'] = pd.to_datetime(trade_df['transact_time'], unit='ms')
        max_gap = trade_df['dt'].diff().dt.total_seconds().max()
        print(f"Maximum timestamp gap: {max_gap} seconds")

if __name__ == '__main__':
    run_integrity_audit()
