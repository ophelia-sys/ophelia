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

def calculate_robust_z_score(series: pd.Series, window: int = 500, zero_dispersion_policy: str = "legacy") -> pd.Series:
    """
    Calculates a causal robust z-score using the rolling median and MAD (Median Absolute Deviation).
    The normalization window is strictly shifted by 1 to prevent lookahead leakage.
    Z_t = (X_t - Median(X_{t-W:t-1})) / max(MAD(X_{t-W:t-1}) * 1.4826, 1e-6)
    
    zero_dispersion_policy:
    - "legacy": Uses max(MAD * 1.4826, 1e-6) to avoid division by zero.
    - "unavailable": Explicitly returns 0.0 if X_t == Median when MAD == 0, and NaN otherwise.
    """
    if zero_dispersion_policy not in ["legacy", "unavailable"]:
        raise ValueError("Invalid zero_dispersion_policy")
        
    if len(series) < window + 1:
        return pd.Series(index=series.index, data=np.nan)
        
    past_series = series.shift(1)
    
    rolling_median = past_series.rolling(window=window).median()
    
    def _mad(x):
        valid_x = x[~np.isnan(x)]
        if len(valid_x) == 0: 
            return np.nan
        med = np.median(valid_x)
        return np.median(np.abs(valid_x - med))
        
    rolling_mad = past_series.rolling(window=window).apply(_mad, raw=True)
    
    if zero_dispersion_policy == "legacy":
        # max(MAD * 1.4826, 1e-6) handles zero variance safely without fabricating zero
        safe_mad = np.maximum(rolling_mad * 1.4826, 1e-6)
        z_score = (series - rolling_median) / safe_mad
    else:
        # "unavailable" policy
        mad_scaled = rolling_mad * 1.4826
        # Avoid division by zero warnings by temporarily replacing 0 with 1
        safe_mad = np.where(mad_scaled == 0, 1.0, mad_scaled)
        z_score = (series - rolling_median) / safe_mad
        
        # Explicit override for zero MAD
        zero_mad_mask = (mad_scaled == 0)
        match_median = (series == rolling_median)
        
        z_score = np.where(zero_mad_mask & match_median, 0.0, z_score)
        z_score = np.where(zero_mad_mask & ~match_median, np.nan, z_score)
        z_score = pd.Series(z_score, index=series.index)
        
    return z_score

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
