import numpy as np
import pandas as pd
from institutional.normalization import calculate_robust_z_score

def detect_anomaly(series: pd.Series, window: int = 500) -> pd.Series:
    """
    Generalized MAD Z-Score anomaly detection.
    Useful for Volume, Spread, CVD, Liquidations, etc.
    """
    z_scores = calculate_robust_z_score(series, window=window)
    # Threshold could be 3.0 or 5.0 for crypto outliers.
    # We return the continuous Z-Score so the Score Engine can determine the cutoff.
    return z_scores
