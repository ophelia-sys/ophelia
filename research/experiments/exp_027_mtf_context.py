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

def build_missing_microstructure(oos_dates):
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT"
    
    all_book_files = sorted(glob.glob(os.path.join(base_dir, 'bookTicker', '*.csv')))
    book_files = [f for f in all_book_files if any(d in f for d in oos_dates)]
    
    book_dfs = [process_book_file(f) for f in book_files]
    book_minute = pd.concat([df for df in book_dfs if df is not None], ignore_index=True)
    
    trade_files = sorted(glob.glob(os.path.join(base_dir, 'aggTrades', '*.csv')))
    trade_files_oos = [f for f in trade_files if any(d in f for d in oos_dates)]
    
    trade_dfs = [process_trade_file(f) for f in trade_files_oos]
    trade_minute = pd.concat([df for df in trade_dfs if df is not None], ignore_index=True)
    
    micro_df = pd.merge(book_minute, trade_minute, on='minute_ts', how='inner')
    
    pq_df = pd.read_parquet(r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\v2_fixed_timestamp\BTCUSDT.parquet")
    pq_df['timestamp'] = pq_df['timestamp'].astype(np.int64)
    micro_df['minute_ts'] = micro_df['minute_ts'].astype(np.int64)
    
    joined_df = pd.merge(pq_df, micro_df, left_on='timestamp', right_on='minute_ts', how='inner')
    return joined_df

def compute_causal_mtf(df):
    """
    Computes higher-timeframe features (5m, 15m, 1h) and merges them back CAUSALLY.
    Decision happens at 1m close.
    Example: 10:10 decision happens at 10:10:59.
    It can ONLY see 15m candles that closed at or before 10:10:59.
    A 15m candle spanning 10:00 to 10:14:59 closes at 10:14:59, so it is NOT visible at 10:10.
    The visible 15m candle at 10:10 is the one covering 09:45-09:59:59.
    """
    df = df.copy()
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('dt').reset_index(drop=True)
    
    # Pre-calculate simple 1m features for base signal
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_15'] = df['close'].pct_change(15)
    df['vol_15'] = df['ret_1'].rolling(15).std()
    df['mom_5'] = df['close'] / df['close'].shift(5) - 1
    df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
    df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
    df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
    
    # We will resample. 
    # For a 1-minute row with dt (open time), the candle closes at dt + 1 min.
    # A 15m candle starting at 10:00 closes at 10:15.
    # For causal join, we map the 1m row's close time to the latest completed HTF close time.
    # 1m close time = df['dt'] + pd.Timedelta(minutes=1)
    df['close_dt'] = df['dt'] + pd.Timedelta(minutes=1)
    
    # HTF calculation function
    def get_htf_features(df, freq, prefix):
        df_htf = df.set_index('dt').resample(freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # A candle with index 10:00 and freq 15T means it covers 10:00 to 10:15.
        # Its close time is index + 15T.
        df_htf['htf_close_dt'] = df_htf.index + pd.Timedelta(freq)
        
        # Features on HTF
        df_htf['ret'] = df_htf['close'].pct_change()
        df_htf['tr'] = np.maximum(
            df_htf['high'] - df_htf['low'],
            np.maximum(
                (df_htf['high'] - df_htf['close'].shift()).abs(),
                (df_htf['low'] - df_htf['close'].shift()).abs()
            )
        )
        df_htf['atr'] = df_htf['tr'].rolling(window=14).mean()
        
        # Volatility (Realized Vol over 24 periods)
        df_htf['volatility'] = df_htf['ret'].rolling(24).std()
        
        # Trend (Close - Shift(14)) / ATR
        df_htf['trend'] = (df_htf['close'] - df_htf['close'].shift(14)) / (df_htf['atr'] + 1e-8)
        
        # Momentum (Z-score of returns over 24 periods)
        mean_ret = df_htf['ret'].rolling(24).mean()
        df_htf['momentum'] = (df_htf['ret'] - mean_ret) / (df_htf['volatility'] + 1e-8)
        
        df_htf = df_htf[['htf_close_dt', 'volatility', 'trend', 'momentum']].dropna().reset_index(drop=True)
        df_htf = df_htf.rename(columns={
            'volatility': f'{prefix}_volatility',
            'trend': f'{prefix}_trend',
            'momentum': f'{prefix}_momentum'
        })
        return df_htf

    htf_15m = get_htf_features(df, '15min', '15m')
    htf_1h = get_htf_features(df, '1h', '1h')
    
    # To merge causally:
    # merge_asof matches each 1m `close_dt` to the latest `htf_close_dt` that is <= `close_dt`
    # This guarantees we only see HTF features from candles that CLOSED at or before our 1m candle closed.
    df = pd.merge_asof(df.sort_values('close_dt'), htf_15m.sort_values('htf_close_dt'), 
                       left_on='close_dt', right_on='htf_close_dt', direction='backward')
    df = pd.merge_asof(df.sort_values('close_dt'), htf_1h.sort_values('htf_close_dt'), 
                       left_on='close_dt', right_on='htf_close_dt', direction='backward')
    
    # Calculate causal regimes based on rolling quantiles to avoid future leakage
    # We use 1000 minutes rolling window for quantiles (approx 16 hours)
    df['1h_volatility_q75'] = df['1h_volatility'].rolling(1000, min_periods=100).quantile(0.75)
    df['1h_volatility_q95'] = df['1h_volatility'].rolling(1000, min_periods=100).quantile(0.95)
    df['1h_volatility_q25'] = df['1h_volatility'].rolling(1000, min_periods=100).quantile(0.25)
    
    df['regime_vol'] = 'Normal'
    df.loc[df['1h_volatility'] > df['1h_volatility_q95'], 'regime_vol'] = 'Extreme'
    df.loc[(df['1h_volatility'] > df['1h_volatility_q75']) & (df['1h_volatility'] <= df['1h_volatility_q95']), 'regime_vol'] = 'High'
    df.loc[df['1h_volatility'] < df['1h_volatility_q25'], 'regime_vol'] = 'Low'
    
    # Trend state (1h trend)
    df['regime_trend'] = 'Neutral'
    df.loc[df['1h_trend'] > 1.0, 'regime_trend'] = 'Up'
    df.loc[df['1h_trend'] < -1.0, 'regime_trend'] = 'Down'
    
    # Momentum state (15m momentum)
    df['regime_mom'] = 'Neutral'
    df.loc[df['15m_momentum'] > 0.5, 'regime_mom'] = 'Positive'
    df.loc[df['15m_momentum'] < -0.5, 'regime_mom'] = 'Negative'
    
    # Clean up auxiliary columns
    df = df.drop(columns=['close_dt', 'htf_close_dt_x', 'htf_close_dt_y', '1h_volatility_q75', '1h_volatility_q95', '1h_volatility_q25'])
    return df

def run_exp_027():
    print("========================================")
    print("EXP 027: MTF CONTEXT GENERATION")
    print("========================================")
    
    # 1. Load Dev (Nov 1-5)
    dev_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    dev_df = pd.read_parquet(dev_path)
    
    # 2. Load Val (Nov 6-10)
    val_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4_1\BTCUSDT_microstructure_oos.parquet"
    val_df = pd.read_parquet(val_path)
    
    # 3. Build New OOS (Nov 11-15)
    print("Building missing microstructure for OOS (Nov 11-15)...")
    oos_dates = ['2023-11-11', '2023-11-12', '2023-11-13', '2023-11-14', '2023-11-15']
    oos_df = build_missing_microstructure(oos_dates)
    
    print(f"Dev rows: {len(dev_df)}")
    print(f"Val rows: {len(val_df)}")
    print(f"OOS rows: {len(oos_df)}")
    
    full_df = pd.concat([dev_df, val_df, oos_df], ignore_index=True)
    full_df = full_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
    
    print("\nComputing Multi-Timeframe Context and Regimes...")
    context_df = compute_causal_mtf(full_df)
    
    # Split back out and save
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_5"
    os.makedirs(out_dir, exist_ok=True)
    
    dev_end = pd.to_datetime('2023-11-05 23:59:59')
    val_end = pd.to_datetime('2023-11-10 23:59:59')
    
    final_dev = context_df[context_df['dt'] <= dev_end].copy()
    final_val = context_df[(context_df['dt'] > dev_end) & (context_df['dt'] <= val_end)].copy()
    final_oos = context_df[context_df['dt'] > val_end].copy()
    
    print("\n--- Final Datasets ---")
    print(f"Dev Context: {len(final_dev)} rows")
    print(f"Val Context: {len(final_val)} rows")
    print(f"OOS Context: {len(final_oos)} rows")
    
    final_dev.to_parquet(os.path.join(out_dir, "BTCUSDT_context_dev.parquet"))
    final_val.to_parquet(os.path.join(out_dir, "BTCUSDT_context_val.parquet"))
    final_oos.to_parquet(os.path.join(out_dir, "BTCUSDT_context_oos.parquet"))
    print("\nSaved context datasets successfully.")

if __name__ == '__main__':
    run_exp_027()
