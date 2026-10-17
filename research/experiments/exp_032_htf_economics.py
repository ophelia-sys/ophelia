import pandas as pd
import numpy as np
import os
import json

def calculate_htf_opportunities(df):
    """
    Evaluate the distribution of forward returns on higher timeframes.
    We resample the 1m data to 5m, 15m, 1h, 4h, and calculate the 
    forward return for the next period.
    Then we measure what percentage of these forward returns 
    are large enough to overcome the execution friction (12 bps).
    """
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    
    timeframes = ['5min', '15min', '1h', '4h', '1d']
    results_list = []
    
    # 12 bps round-trip friction, plus 5 bps margin = 17 bps minimum necessary move
    threshold_bps = 17.0
    
    for tf in timeframes:
        # Resample OHLC
        resampled = df['close'].resample(tf, label='left', closed='left').ohlc()
        resampled.dropna(inplace=True)
        
        # Forward return is the return of the NEXT candle.
        # This is purely causal. At the end of candle T, we can capture the return of candle T+1.
        resampled['fwd_return'] = (resampled['close'].shift(-1) - resampled['close']) / resampled['close']
        resampled['fwd_return_bps'] = resampled['fwd_return'] * 10000
        
        resampled.dropna(inplace=True)
        
        # Absolute magnitude of the move
        resampled['abs_fwd_return_bps'] = resampled['fwd_return_bps'].abs()
        
        total_samples = len(resampled)
        if total_samples == 0:
            continue
            
        # Opportunities that exceed the hurdle
        num_opportunities = (resampled['abs_fwd_return_bps'] >= threshold_bps).sum()
        pct_opportunities = (num_opportunities / total_samples) * 100
        
        mean_abs_move = resampled['abs_fwd_return_bps'].mean()
        median_abs_move = resampled['abs_fwd_return_bps'].median()
        
        results_list.append({
            'timeframe': tf,
            'total_candles': total_samples,
            'mean_abs_move_bps': mean_abs_move,
            'median_abs_move_bps': median_abs_move,
            'num_opportunities': num_opportunities,
            'pct_opportunities_gt_17bps': pct_opportunities
        })
        
    return pd.DataFrame(results_list)

def run_branch_b():
    print("========================================")
    print("EXP 032: BRANCH B - HTF ECONOMICS")
    print("========================================")
    
    dev = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_dev.parquet")
    val = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_val.parquet")
    oos = pd.read_parquet("data/processed/phase5_5/BTCUSDT_context_oos.parquet")
    
    df = pd.concat([dev, val, oos], ignore_index=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"Loaded {len(df)} 1-minute rows (Nov 1 - Nov 15).")
    
    res_df = calculate_htf_opportunities(df.copy())
    
    out_dir = "research/results/phase5_6"
    os.makedirs(out_dir, exist_ok=True)
    res_df.to_csv(os.path.join(out_dir, "branch_b_htf_economics.csv"), index=False)
    
    print(res_df.to_string(index=False))

if __name__ == "__main__":
    run_branch_b()
