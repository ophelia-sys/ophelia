import numpy as np
import pandas as pd
from indicators.ema import EMA
from institutional.volatility import calculate_atr

def calculate_efficiency_ratio(df: pd.DataFrame, window: int = 10) -> pd.Series:
    """
    Calculate Kaufman Efficiency Ratio (ER).
    ER = abs(Close[t] - Close[t-N]) / sum(abs(Close[i] - Close[i-1]))
    """
    close = df["close"].astype(float)
    
    direction = (close - close.shift(window)).abs()
    volatility = close.diff().abs().rolling(window=window).sum()
    
    er = direction / volatility.replace(0, np.nan)
    return er.fillna(0.0)

def calculate_directional_persistence(df: pd.DataFrame, window: int = 10) -> pd.Series:
    """
    Calculate the ratio of positive returns to total returns in the window.
    Ranges from 0 (all down) to 1.0 (all up).
    """
    returns = df["close"].astype(float).diff()
    up_moves = (returns > 0).astype(int)
    
    persistence = up_moves.rolling(window=window).sum() / window
    return persistence

def calculate_atr_scaled_trend(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Measures the distance of the current close from the N-period SMA, scaled by ATR.
    This normalizes trend strength against recent volatility.
    """
    close = df["close"].astype(float)
    sma = close.rolling(window=window).mean()
    atr = calculate_atr(df, window=window)
    
    return (close - sma) / atr.replace(0, np.nan)

def get_ema_structure(df: pd.DataFrame, fast: int = 9, slow: int = 21, baseline: int = 200) -> dict:
    """
    Evaluate EMA structural alignment.
    Returns the alignment state and spread magnitudes.
    This is purely descriptive, not prescriptive.
    """
    ema_fast = EMA.calculate(df, fast).iloc[-1]
    ema_slow = EMA.calculate(df, slow).iloc[-1]
    ema_base = EMA.calculate(df, baseline).iloc[-1]
    close = float(df["close"].iloc[-1])
    
    aligned_bullish = (close > ema_fast > ema_slow > ema_base)
    aligned_bearish = (close < ema_fast < ema_slow < ema_base)
    
    state = "CONFLICTED"
    if aligned_bullish:
        state = "ALIGNED_BULLISH"
    elif aligned_bearish:
        state = "ALIGNED_BEARISH"
    elif ema_fast > ema_slow:
        state = "PARTIAL_BULLISH"
    elif ema_fast < ema_slow:
        state = "PARTIAL_BEARISH"
        
    return {
        "state": state,
        "fast_slow_spread": (ema_fast - ema_slow) / ema_slow if ema_slow else 0.0,
        "price_base_spread": (close - ema_base) / ema_base if ema_base else 0.0
    }
