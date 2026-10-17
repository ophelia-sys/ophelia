import pandas as pd
import numpy as np
import os
import glob
import json

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
        
        # Floor transact_time to nearest minute
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

def run_oos_dataset_prep():
    print("========================================")
    print("EXP 024: OOS DATASET PREPARATION")
    print("========================================")
    
    with open(r"c:\Users\dopa.mine\Desktop\ophelia\research\configs\phase5_4_1_locked_config.json", 'r') as f:
        config = json.load(f)
        
    start_dt = config['locked_oos_period']['start']
    end_dt = config['locked_oos_period']['end']
    print(f"Preparing OOS period: {start_dt} to {end_dt}")
    
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT"
    
    # 1. Process bookTicker files
    print("\nProcessing bookTicker files...", flush=True)
    all_book_files = sorted(glob.glob(os.path.join(base_dir, 'bookTicker', '*.csv')))
    
    oos_dates = ['2023-11-06', '2023-11-07', '2023-11-08', '2023-11-09', '2023-11-10']
    
    book_files = [f for f in all_book_files if any(d in f for d in oos_dates)]
    print(f"Found {len(book_files)} OOS book files.")
    
    book_dfs = [process_book_file(f) for f in book_files]
    book_minute = pd.concat([df for df in book_dfs if df is not None], ignore_index=True)
    
    # 2. Process aggTrades files
    print("Processing aggTrades files...", flush=True)
    trade_files = sorted(glob.glob(os.path.join(base_dir, 'aggTrades', '*.csv')))
    trade_files_oos = [f for f in trade_files if any(d in f for d in oos_dates)]
    
    trade_dfs = [process_trade_file(f) for f in trade_files_oos]
    trade_minute = pd.concat([df for df in trade_dfs if df is not None], ignore_index=True)
    
    # 3. Merge micro features
    micro_df = pd.merge(book_minute, trade_minute, on='minute_ts', how='inner')
    
    # 4. Load Parquet Baseline
    pq_df = pd.read_parquet(r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\v2_fixed_timestamp\BTCUSDT.parquet")
    pq_df['timestamp'] = pq_df['timestamp'].astype(np.int64)
    micro_df['minute_ts'] = micro_df['minute_ts'].astype(np.int64)
    
    # Causal Join
    joined_df = pd.merge(pq_df, micro_df, left_on='timestamp', right_on='minute_ts', how='inner')
    
    # Convert 'timestamp' back to datetime for filtering
    joined_df['dt'] = pd.to_datetime(joined_df['timestamp'], unit='ms')
    
    # Strict boundary checks
    train_end = pd.to_datetime(config['training_period']['end'])
    oos_start = pd.to_datetime(config['locked_oos_period']['start'])
    oos_end = pd.to_datetime(config['locked_oos_period']['end'])
    
    # Filter exact OOS
    oos_df = joined_df[(joined_df['dt'] >= oos_start) & (joined_df['dt'] <= oos_end)].copy()
    
    print(f"\n--- OOS Dataset Generation ---")
    print(f"Total rows in OOS period: {len(oos_df)}")
    
    # Check contamination
    if oos_df['dt'].min() <= train_end:
        raise ValueError(f"OOS PURITY VIOLATION: Found timestamp {oos_df['dt'].min()} <= train_end {train_end}")
    
    # Purity Assertions
    # 1. No overlap with Phase 5.4 train (11-01 to 11-05)
    train_df = joined_df[(joined_df['dt'] >= pd.to_datetime(config['training_period']['start'])) & 
                         (joined_df['dt'] <= train_end)]
                         
    overlap = set(oos_df['timestamp']).intersection(set(train_df['timestamp']))
    if overlap:
        raise ValueError(f"OOS PURITY VIOLATION: {len(overlap)} overlapping timestamps with training set.")
    
    # The actual train data used for phase5_4_1 is train_df
    # We should save both out
    oos_df.drop(columns=['dt'], inplace=True)
    train_df.drop(columns=['dt'], inplace=True)
    
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4_1"
    os.makedirs(out_dir, exist_ok=True)
    
    out_path_oos = os.path.join(out_dir, "BTCUSDT_microstructure_oos.parquet")
    oos_df.to_parquet(out_path_oos)
    print(f"Saved OOS data to {out_path_oos}")
    
    out_path_train = os.path.join(out_dir, "BTCUSDT_microstructure_train.parquet")
    train_df.to_parquet(out_path_train)
    print(f"Saved TRAIN data to {out_path_train}")

if __name__ == '__main__':
    run_oos_dataset_prep()
