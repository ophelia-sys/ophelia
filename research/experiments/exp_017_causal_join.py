import pandas as pd
import numpy as np
import os
import glob

def process_book_file(f):
    try:
        df = pd.read_csv(f, header=0)
        df.columns = ['update_id', 'bid_p', 'bid_q', 'ask_p', 'ask_q', 'transact_time', 'event_time']
        
        df = df.sort_values('transact_time')
        
        prev_bid_p = df['bid_p'].shift(1)
        prev_bid_q = df['bid_q'].shift(1)
        bid_flow = np.where(df['bid_p'] > prev_bid_p, df['bid_q'],
                    np.where(df['bid_p'] == prev_bid_p, df['bid_q'] - prev_bid_q, -prev_bid_q))
        
        prev_ask_p = df['ask_p'].shift(1)
        prev_ask_q = df['ask_q'].shift(1)
        ask_flow = np.where(df['ask_p'] < prev_ask_p, df['ask_q'],
                    np.where(df['ask_p'] == prev_ask_p, df['ask_q'] - prev_ask_q, -prev_ask_q))
                    
        df['snapshot_ofi_proxy'] = bid_flow - ask_flow
        df['queue_imbalance'] = (df['bid_q'] - df['ask_q']) / (df['bid_q'] + df['ask_q'])
        
        df['minute_ts'] = (df['transact_time'] // 60000) * 60000
        
        minute_df = df.groupby('minute_ts').agg(
            snapshot_ofi_proxy=('snapshot_ofi_proxy', 'sum'),
            mean_queue_imbalance=('queue_imbalance', 'mean'),
            end_spread=('ask_p', lambda x: x.iloc[-1] - df.loc[x.index[-1], 'bid_p']),
            mean_relative_spread=('ask_p', lambda x: np.mean((x - df.loc[x.index, 'bid_p']) / ((x + df.loc[x.index, 'bid_p']) / 2)))
        ).reset_index()
        
        return minute_df
    except Exception as e:
        print(f"Error on {f}: {e}")
        return None

def process_trade_file(f):
    try:
        df = pd.read_csv(f, header=0)
        df.columns = ['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id', 'transact_time', 'is_buyer_maker']
        
        df['signed_volume'] = np.where(df['is_buyer_maker'], -df['quantity'], df['quantity'])
        df['minute_ts'] = (df['transact_time'] // 60000) * 60000
        
        minute_df = df.groupby('minute_ts').agg(
            cvd=('signed_volume', 'sum'),
            trade_count=('agg_trade_id', 'count')
        ).reset_index()
        return minute_df
    except Exception as e:
        print(f"Error on {f}: {e}")
        return None

def run_causal_join():
    print("========================================")
    print("EXP 017: CAUSAL JOIN AND CANONICAL OFI GATE")
    print("========================================")
    
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT"
    
    # 1. Process bookTicker files
    print("\nProcessing bookTicker files...", flush=True)
    book_files = sorted(glob.glob(os.path.join(base_dir, 'bookTicker', '*.csv')))[:5]
    book_dfs = [process_book_file(f) for f in book_files]
    book_minute = pd.concat([df for df in book_dfs if df is not None], ignore_index=True)
    
    # 2. Process aggTrades files
    print("Processing aggTrades files...", flush=True)
    trade_files = sorted(glob.glob(os.path.join(base_dir, 'aggTrades', '*.csv')))
    # Filter to only the dates we have in bookTicker to avoid huge outer joins
    valid_dates = [os.path.basename(f).split('-')[2:5] for f in book_files]
    valid_date_strs = ['-'.join(d).replace('.csv', '') for d in valid_dates]
    
    trade_dfs = []
    for f in trade_files:
        if any(d in f for d in valid_date_strs):
            trade_dfs.append(process_trade_file(f))
            
    trade_minute = pd.concat([df for df in trade_dfs if df is not None], ignore_index=True)
    
    # Merge micro features
    micro_df = pd.merge(book_minute, trade_minute, on='minute_ts', how='inner')
    
    # 4. Load Parquet Baseline
    pq_df = pd.read_parquet(r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\v2_fixed_timestamp\BTCUSDT.parquet")
    pq_df['timestamp'] = pq_df['timestamp'].astype(np.int64)
    micro_df['minute_ts'] = micro_df['minute_ts'].astype(np.int64)
    
    # Causal Join
    joined_df = pd.merge(pq_df, micro_df, left_on='timestamp', right_on='minute_ts', how='inner')
    
    print(f"\n--- Causal Join Audit ---")
    print(f"Microstructure valid minutes: {len(micro_df)}")
    print(f"Joined rows: {len(joined_df)}")
    
    # Save the Phase 5.4 subset
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "BTCUSDT_microstructure.parquet")
    joined_df.to_parquet(out_path)
    print(f"Saved to {out_path}")

if __name__ == '__main__':
    run_causal_join()
