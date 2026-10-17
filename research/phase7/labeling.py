import pandas as pd
import numpy as np

def calculate_forward_return(df: pd.DataFrame, horizon: int = 15, price_col: str = 'close') -> pd.Series:
    """
    Calculates the forward return over the specified horizon (in bars).
    F_t = (P_{t+h} - P_t) / P_t
    """
    future_price = df[price_col].shift(-horizon)
    current_price = df[price_col]
    return (future_price - current_price) / current_price

def calculate_volatility_adjusted_forward_return(
    df: pd.DataFrame, 
    horizon: int = 15, 
    volatility_window: int = 60,
    price_col: str = 'close'
) -> pd.Series:
    """
    Calculates the forward return normalized by trailing volatility.
    vol_t = std(returns_{t-w:t}) * sqrt(horizon)
    target = F_t / vol_t
    """
    returns = df[price_col].pct_change()
    # Trailing volatility over the window, scaled to the horizon
    volatility = returns.rolling(window=volatility_window, min_periods=max(2, volatility_window//2)).std() * np.sqrt(horizon)
    
    # Forward return
    fwd_ret = calculate_forward_return(df, horizon, price_col)
    
    # Avoid division by zero
    adjusted = fwd_ret / volatility.replace(0, np.nan)
    return adjusted

def calculate_mfe_mae(df: pd.DataFrame, horizon: int = 15, side: str = 'LONG') -> pd.DataFrame:
    """
    Calculates Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)
    over a future horizon.
    """
    high_roll = df['high'].shift(-horizon).rolling(window=horizon, min_periods=1).max()
    # To properly get the forward rolling max/min, we actually need to look ahead.
    # Pandas rolling looks backward. So we reverse, roll, and reverse.
    
    fwd_max_high = df['high'][::-1].rolling(window=horizon, min_periods=1).max()[::-1].shift(-1)
    fwd_min_low = df['low'][::-1].rolling(window=horizon, min_periods=1).min()[::-1].shift(-1)
    
    current_close = df['close']
    
    if side == 'LONG':
        mfe = (fwd_max_high - current_close) / current_close
        mae = (current_close - fwd_min_low) / current_close
    elif side == 'SELL' or side == 'SHORT':
        mfe = (current_close - fwd_min_low) / current_close
        mae = (fwd_max_high - current_close) / current_close
    else:
        raise ValueError("side must be LONG or SHORT")
        
    return pd.DataFrame({'mfe': mfe, 'mae': mae})
