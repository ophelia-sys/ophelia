import pandas as pd
import numpy as np
import os

def analyze_asset_volatility(file_path, symbol, start_date="2023-11-01", end_date="2023-11-15"):
    df = pd.read_parquet(file_path)
    
    # Filter to Nov 1 - 15, 2023 for consistency with Phase 5.6
    # Assuming timestamp is in ms
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[(df['dt'] >= pd.Timestamp(start_date)) & (df['dt'] <= pd.Timestamp(end_date))].copy()
    
    if len(df) == 0:
        return None
        
    df.set_index('dt', inplace=True)
    
    # Execution Friction on BingX (Taker round trip)
    bingx_taker_bps = 12.0
    
    timeframes = ['15min', '1h', '4h']
    
    res = {'symbol': symbol}
    
    for tf in timeframes:
        resampled = df['close'].resample(tf, label='left', closed='left').ohlc()
        resampled.dropna(inplace=True)
        
        # Absolute forward return of the NEXT candle
        fwd_return = (resampled['close'].shift(-1) - resampled['close']) / resampled['close']
        abs_move_bps = fwd_return.abs() * 10000
        
        mean_abs_move_bps = abs_move_bps.mean()
        
        # Volatility-to-Cost Ratio
        vol_to_cost = mean_abs_move_bps / bingx_taker_bps
        
        res[f'mean_move_{tf}'] = mean_abs_move_bps
        res[f'vol_to_cost_{tf}'] = vol_to_cost
        
    return res

def run_branch_c():
    print("========================================")
    print("EXP 033: BRANCH C - ASSET / VENUE ECONOMICS")
    print("========================================")
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']
    data_dir = "data/processed/v2_fixed_timestamp"
    
    results = []
    
    for sym in symbols:
        fp = os.path.join(data_dir, f"{sym}.parquet")
        if os.path.exists(fp):
            r = analyze_asset_volatility(fp, sym)
            if r is not None:
                results.append(r)
        else:
            print(f"File not found: {fp}")
            
    res_df = pd.DataFrame(results)
    
    out_dir = "research/results/phase5_6"
    os.makedirs(out_dir, exist_ok=True)
    res_df.to_csv(os.path.join(out_dir, "branch_c_asset_venue_economics.csv"), index=False)
    
    print(res_df.to_string(index=False))

if __name__ == "__main__":
    run_branch_c()
