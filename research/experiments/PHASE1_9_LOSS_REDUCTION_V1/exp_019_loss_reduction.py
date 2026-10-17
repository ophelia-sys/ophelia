import pandas as pd
import numpy as np
import datetime

def get_period(timestamp):
    # Timestamp is in unix time.
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    if dt < datetime.datetime(2026, 7, 11): return "P1"
    elif dt < datetime.datetime(2026, 7, 19): return "P2"
    elif dt < datetime.datetime(2026, 7, 27): return "P3"
    elif dt < datetime.datetime(2026, 8, 4): return "P4"
    elif dt < datetime.datetime(2026, 8, 12): return "P5"
    else: return "P6"

def run_phase1_9_feature_extraction(csv_path):
    df = pd.read_csv(csv_path)
    
    # Precalculate TR and ATR for Volatility
    df['prev_close'] = df['close'].shift(1)
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = (df['high'] - df['prev_close']).abs()
    df['tr3'] = (df['low'] - df['prev_close']).abs()
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr14'] = df['tr'].rolling(window=14).mean()
    df['atr_pct'] = (df['atr14'] / df['close']) * 100
    
    # Precalculate logic
    df['prev_VWAP'] = df['VWAP'].shift(1)
    df['prev_Up Trend'] = df['Up Trend'].shift(1)
    df['prev_Down Trend'] = df['Down Trend'].shift(1)
    
    # LONG cross logic
    df['long_cross'] = (
        (df['prev_Up Trend'] < df['prev_VWAP']) & 
        (df['Up Trend'] >= df['VWAP']) & 
        (df['close'] > df['VWAP'])
    )
    
    # SHORT cross logic
    df['short_cross'] = (
        (df['prev_Down Trend'] > df['prev_VWAP']) & 
        (df['Down Trend'] <= df['VWAP']) & 
        (df['close'] < df['VWAP'])
    )

    trades = []
    
    print("Evaluating signals and forward trajectories...")
    for idx in range(15, len(df)-1):
        row = df.iloc[idx]
        is_long = row['long_cross']
        is_short = row['short_cross']
        
        if is_long or is_short:
            ts = row['time']
            next_row = df.iloc[idx + 1]
            entry_price = float(next_row['open'])
            period = get_period(int(ts))
            
            direction = 'LONG' if is_long else 'SHORT'
            
            if direction == 'LONG':
                active_st = next_row['Up Trend']
                if pd.isna(active_st): active_st = row['Up Trend']
                stop = active_st * 0.9999
                risk = abs(entry_price - stop)
                st_slope_1 = (active_st - df['Up Trend'].iloc[idx-1]) / entry_price * 100
                st_slope_3 = (active_st - df['Up Trend'].iloc[idx-3]) / entry_price * 100
                sep = active_st - row['VWAP']
            else:
                active_st = next_row['Down Trend']
                if pd.isna(active_st): active_st = row['Down Trend']
                stop = active_st * 1.0001
                risk = abs(entry_price - stop)
                st_slope_1 = (active_st - df['Down Trend'].iloc[idx-1]) / entry_price * 100
                st_slope_3 = (active_st - df['Down Trend'].iloc[idx-3]) / entry_price * 100
                sep = row['VWAP'] - active_st
                
            if risk == 0: continue
            risk_pct = (risk / entry_price) * 100
            
            t15 = entry_price + (1.5 * risk) if direction == 'LONG' else entry_price - (1.5 * risk)
            t20 = entry_price + (2.0 * risk) if direction == 'LONG' else entry_price - (2.0 * risk)
            t30 = entry_price + (3.0 * risk) if direction == 'LONG' else entry_price - (3.0 * risk)
            
            res_15, res_20, res_30 = None, None, None
            mfe_price = entry_price
            mae_price = entry_price
            hold_15, hold_20, hold_30 = 0, 0, 0
            final_hold = 0
            
            for j in range(idx + 1, len(df)):
                sim_row = df.iloc[j]
                c_close = sim_row['close']
                c_high = sim_row['high']
                c_low = sim_row['low']
                bars = j - idx
                
                if direction == 'LONG':
                    if c_high > mfe_price: mfe_price = c_high
                    if c_low < mae_price: mae_price = c_low
                    
                    if res_15 is None and c_close >= t15: res_15 = 'WIN'; hold_15 = bars
                    if res_20 is None and c_close >= t20: res_20 = 'WIN'; hold_20 = bars
                    if res_30 is None and c_close >= t30: res_30 = 'WIN'; hold_30 = bars
                    
                    if c_close <= stop:
                        if res_15 is None: res_15 = 'LOSS'; hold_15 = bars
                        if res_20 is None: res_20 = 'LOSS'; hold_20 = bars
                        if res_30 is None: res_30 = 'LOSS'; hold_30 = bars
                        final_hold = bars
                        break
                else:
                    if c_low < mfe_price: mfe_price = c_low
                    if c_high > mae_price: mae_price = c_high
                    
                    if res_15 is None and c_close <= t15: res_15 = 'WIN'; hold_15 = bars
                    if res_20 is None and c_close <= t20: res_20 = 'WIN'; hold_20 = bars
                    if res_30 is None and c_close <= t30: res_30 = 'WIN'; hold_30 = bars
                    
                    if c_close >= stop:
                        if res_15 is None: res_15 = 'LOSS'; hold_15 = bars
                        if res_20 is None: res_20 = 'LOSS'; hold_20 = bars
                        if res_30 is None: res_30 = 'LOSS'; hold_30 = bars
                        final_hold = bars
                        break
                        
                if res_15 == 'WIN' and res_20 == 'WIN' and res_30 == 'WIN':
                    final_hold = bars
                    break
                    
            if final_hold == 0:
                final_hold = len(df) - idx - 1 
                
            mfe_pct = abs(mfe_price - entry_price) / entry_price * 100
            mae_pct = abs(mae_price - entry_price) / entry_price * 100
            
            # Additional features
            norm_sep = abs(sep) / entry_price * 100
            vwap_slope_1 = (row['VWAP'] - df['VWAP'].iloc[idx-1]) / entry_price * 100
            vwap_slope_3 = (row['VWAP'] - df['VWAP'].iloc[idx-3]) / entry_price * 100
            
            close_t = row['close']
            ret_3 = (close_t - df['close'].iloc[idx-3]) / df['close'].iloc[idx-3] * 100
            ret_6 = (close_t - df['close'].iloc[idx-6]) / df['close'].iloc[idx-6] * 100
            ret_12 = (close_t - df['close'].iloc[idx-12]) / df['close'].iloc[idx-12] * 100
            atr_pct = df['atr_pct'].iloc[idx]
            
            trades.append({
                'period': period,
                'timestamp': next_row['time'],
                'direction': direction,
                '1.5R': res_15,
                '2R': res_20,
                '3R': res_30,
                'crossover_separation': norm_sep,
                'vwap_slope_1': vwap_slope_1,
                'vwap_slope_3': vwap_slope_3,
                'st_slope_1': st_slope_1,
                'st_slope_3': st_slope_3,
                'risk_pct': risk_pct,
                'ret_3': ret_3,
                'ret_6': ret_6,
                'ret_12': ret_12,
                'atr_pct': atr_pct,
                'MFE_pct': mfe_pct,
                'MAE_pct': mae_pct,
                'holding_time': final_hold
            })

    trades_df = pd.DataFrame(trades)
    trades_df.to_csv("OPHELIA_PHASE19_LOSS_FORENSICS.csv", index=False)
    print(f"Exported {len(trades_df)} trades to OPHELIA_PHASE19_LOSS_FORENSICS.csv")
    
if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    csv_path = r"C:\Users\dopa.mine\Pictures\BINGX_SOLUSDT.P, 5.csv"
    run_phase1_9_feature_extraction(csv_path)
