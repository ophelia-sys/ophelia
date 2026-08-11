import numpy as np
import pandas as pd
from institutional.volatility import calculate_log_returns
from institutional.normalization import calculate_robust_z_score

def calculate_standardized_momentum(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Calculate the robust Z-score of log returns over a rolling window.
    Uses Median Absolute Deviation to prevent outliers from squashing the momentum reading.
    """
    returns = calculate_log_returns(df, horizon=1)
    return calculate_robust_z_score(returns, window=window)

def calculate_momentum_acceleration(df: pd.DataFrame, momentum_window: int = 20, roc_window: int = 5) -> pd.Series:
    """
    Calculate the Rate of Change (ROC) of standardized momentum.
    Provides evidence of momentum accelerating or decelerating.
    """
    momentum = calculate_standardized_momentum(df, window=momentum_window)
    return momentum.diff(roc_window)

def calculate_volume_imbalance(df: pd.DataFrame, window: int = 10) -> pd.Series:
    """
    Calculates the ratio of up-volume to down-volume based on return direction.
    A proxy for buying vs selling pressure over the window.
    NOTE: This is NOT true Order Flow Imbalance (OFI). OFI requires L1/L2 data.
    """
    returns = calculate_log_returns(df, horizon=1)
    volume = df["volume"].astype(float)
    
    up_vol = volume.where(returns > 0, 0.0)
    down_vol = volume.where(returns < 0, 0.0)
    
    sum_up = up_vol.rolling(window=window).sum()
    sum_down = down_vol.rolling(window=window).sum()
    
    # Range (-1 to 1) where 1 is pure up volume, -1 is pure down volume
    return (sum_up - sum_down) / (sum_up + sum_down).replace(0, np.nan)
