import numpy as np
import pandas as pd
from scipy.stats import norm

def calculate_rolling_percentile(series: pd.Series, window: int = 500) -> pd.Series:
    """
    Calculates the rolling percentile of a series over a given window.
    This safely handles regimes without lookahead bias.
    """
    if len(series) < window:
        return pd.Series(index=series.index, data=np.nan)
        
    def _percentile(x):
        # ECDF implementation
        current_val = x.iloc[-1]
        return (np.sum(x < current_val) / len(x)) * 100.0
        
    return series.rolling(window=window).apply(_percentile, raw=False)

def calculate_robust_z_score(series: pd.Series, window: int = 500) -> pd.Series:
    """
    Calculates a robust z-score using the rolling median and MAD (Median Absolute Deviation).
    Less sensitive to extreme outliers than standard rolling mean/std.
    """
    if len(series) < window:
        return pd.Series(index=series.index, data=np.nan)
        
    rolling_median = series.rolling(window=window).median()
    
    # Calculate rolling MAD
    def _mad(x):
        return np.median(np.abs(x - np.median(x)))
        
    rolling_mad = series.rolling(window=window).apply(_mad, raw=True)
    
    # MAD to standard deviation conversion factor is ~1.4826 for normal distribution
    robust_std = rolling_mad * 1.4826
    
    return (series - rolling_median) / robust_std.replace(0, np.nan)

def calculate_factor_rank_normalization(series: pd.Series) -> pd.Series:
    """
    For cross-sectional or time-series factors:
    Z_i = Phi^-1(Rank_i / (N + 1))
    """
    n = len(series.dropna())
    if n == 0:
        return pd.Series(index=series.index, data=np.nan)
        
    ranks = series.rank(method='average')
    # Rank_i / (N + 1)
    percentiles = ranks / (n + 1)
    
    # Phi^-1 (Inverse CDF of standard normal)
    # Using scipy.stats.norm.ppf
    return percentiles.apply(lambda p: norm.ppf(p) if pd.notnull(p) else np.nan)
