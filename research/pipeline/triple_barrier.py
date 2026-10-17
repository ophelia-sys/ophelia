import pandas as pd
import numpy as np

def label_triple_barrier(df: pd.DataFrame, horizons: list, atr_multiplier_sl: float, atr_multiplier_tp: float, cost_usdt: float = 0.0) -> pd.DataFrame:
    """
    Labels a 1m OHLCV DataFrame using the Triple Barrier Method.
    df must contain: 'close', 'high', 'low', 'atr' (or similar volatility measure).
    
    Implements strict intrabar ambiguity rules:
    - CASE A: Hits Upper Barrier only -> +1.0
    - CASE B: Hits Lower Barrier only -> -1.0
    - CASE C: Hits neither -> 0.0
    - CASE D: Hits both in the same 1m candle -> np.nan (AMBIGUOUS / EXCLUDE)
    
    Returns df with added label columns (e.g. label_long_15min, label_short_15min).
    """
    df_out = df.copy()
    n = len(df)
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    atrs = df['atr'].values
    
    for h in horizons:
        horizon_periods = int(pd.Timedelta(h).total_seconds() / 60)
        labels_l = np.full(n, np.nan, dtype=float)
        labels_s = np.full(n, np.nan, dtype=float)
        
        for i in range(n):
            if i + 1 >= n or pd.isna(atrs[i]):
                continue
                
            entry_price = closes[i]
            
            # Long Barriers
            l_upper = entry_price + (atrs[i] * atr_multiplier_tp) + cost_usdt
            l_lower = entry_price - (atrs[i] * atr_multiplier_sl) - cost_usdt
            
            # Short Barriers
            s_upper = entry_price - (atrs[i] * atr_multiplier_tp) - cost_usdt
            s_lower = entry_price + (atrs[i] * atr_multiplier_sl) + cost_usdt
            
            forward_window_end = min(i + 1 + horizon_periods, n)
            
            label_l = 0.0
            label_s = 0.0
            touched_l = False
            touched_s = False
            
            for j in range(i + 1, forward_window_end):
                h_val = highs[j]
                l_val = lows[j]
                
                # Evaluate Long
                if not touched_l:
                    hit_upper = h_val >= l_upper
                    hit_lower = l_val <= l_lower
                    if hit_upper and hit_lower:
                        label_l = np.nan
                        touched_l = True
                    elif hit_upper:
                        label_l = 1.0
                        touched_l = True
                    elif hit_lower:
                        label_l = -1.0
                        touched_l = True
                        
                # Evaluate Short
                if not touched_s:
                    hit_upper = l_val <= s_upper
                    hit_lower = h_val >= s_lower
                    if hit_upper and hit_lower:
                        label_s = np.nan
                        touched_s = True
                    elif hit_upper:
                        label_s = 1.0
                        touched_s = True
                    elif hit_lower:
                        label_s = -1.0
                        touched_s = True
                        
                if touched_l and touched_s:
                    break
                    
            labels_l[i] = label_l
            labels_s[i] = label_s
            
        df_out[f'label_long_{h}'] = labels_l
        df_out[f'label_short_{h}'] = labels_s
        
    return df_out
