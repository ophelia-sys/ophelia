import numpy as np
import pandas as pd
from numba import njit

def calc_session_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Session VWAP resetting at 00:00 UTC.
    df must have 'timestamp' (datetime), 'high', 'low', 'close', 'volume'.
    """
    df = df.copy()
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    pv = tp * df['volume']
    
    # Create a session grouping key based on UTC date
    session_key = df['timestamp'].dt.date
    
    cum_pv = pv.groupby(session_key).cumsum()
    cum_v = df['volume'].groupby(session_key).cumsum()
    
    vwap = cum_pv / cum_v
    return vwap

@njit
def _calc_rma(tr: np.ndarray, length: int) -> np.ndarray:
    rma = np.full_like(tr, np.nan)
    alpha = 1.0 / length
    
    # Initialize the first RMA with SMA
    sma = np.mean(tr[:length])
    rma[length-1] = sma
    
    for i in range(length, len(tr)):
        rma[i] = alpha * tr[i] + (1 - alpha) * rma[i-1]
    return rma

@njit
def _calc_supertrend_core(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                          atr: np.ndarray, factor: float) -> tuple:
    n = len(close)
    hl2 = (high + low) / 2.0
    
    basic_upper = hl2 + factor * atr
    basic_lower = hl2 - factor * atr
    
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    direction = np.ones(n, dtype=np.int32)
    supertrend = np.full(n, np.nan)
    
    # Initialize first valid value
    for i in range(n):
        if not np.isnan(basic_upper[i]):
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            direction[i] = 1
            supertrend[i] = final_lower[i]
            start_idx = i + 1
            break
    else:
        return supertrend, direction
        
    for i in range(start_idx, n):
        # Final Upper
        if np.isnan(final_upper[i-1]):
            final_upper[i] = basic_upper[i]
        elif basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        # Final Lower
        if np.isnan(final_lower[i-1]):
            final_lower[i] = basic_lower[i]
        elif basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        # Direction
        if np.isnan(supertrend[i-1]):
            direction[i] = 1
        elif direction[i-1] == 1 and close[i] < final_lower[i]:
            direction[i] = -1
        elif direction[i-1] == -1 and close[i] > final_upper[i]:
            direction[i] = 1
        else:
            direction[i] = direction[i-1]
            
        # Supertrend
        if direction[i] == 1:
            supertrend[i] = final_lower[i]
        else:
            supertrend[i] = final_upper[i]
            
    return supertrend, direction

def calc_supertrend(df: pd.DataFrame, length: int = 10, factor: float = 3.0) -> pd.DataFrame:
    """
    TradingView-equivalent Supertrend based on documented Pine Script v5 canonical formulas.
    """
    df = df.copy()
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    prev_close = df['close'].shift(1).values
    
    # True Range
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    
    # Ignore NaN warnings for first row
    with np.errstate(invalid='ignore'):
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0] # Fallback for the first candle
    
    atr = _calc_rma(tr, length)
    
    supertrend, direction = _calc_supertrend_core(high, low, close, atr, factor)
    
    df['ATR'] = atr
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    
    return df
