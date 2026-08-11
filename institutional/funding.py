import numpy as np
import pandas as pd
from institutional.types import DataQuality, FeatureStatus, FeatureResult, Direction

def analyze_funding_state(funding_series: pd.Series = None) -> FeatureResult:
    """
    Funding Rate Analysis engine.
    Calculates the robust rolling Z-score of funding.
    
    If funding_series has insufficient history, the robust z-score defaults to 0.0.
    """
    if funding_series is None or len(funding_series) == 0:
        return FeatureResult(
            raw_value=None,
            normalized_value=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            provenance="funding.py: missing data"
        )
        
    latest_funding = funding_series.iloc[-1]
    
    if len(funding_series) < 10:
        return FeatureResult(
            raw_value=latest_funding,
            normalized_value=0.0,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            provenance="funding.py: insufficient history for normalization"
        )
        
    # Robust normalization using Median Absolute Deviation (MAD)
    rolling_median = funding_series.median()
    mad = np.median(np.abs(funding_series - rolling_median))
    
    if mad == 0:
        std = funding_series.std()
        if std == 0:
            z_score = 0.0
        else:
            z_score = (latest_funding - rolling_median) / std
    else:
        # Scale factor 1.4826 for normal distribution consistency
        z_score = (latest_funding - rolling_median) / (mad * 1.4826)
        
    # Example heuristic: extremely high funding > 2 implies long over-crowding (bearish)
    # extremely negative funding < -2 implies short over-crowding (bullish)
    # But it is observational.
    direction = Direction.UNKNOWN
    confidence = min(abs(z_score) / 4.0, 1.0)
    
    if z_score > 2.0:
        direction = Direction.BEARISH # overcrowded longs -> mean reversion
    elif z_score < -2.0:
        direction = Direction.BULLISH # overcrowded shorts -> mean reversion

    return FeatureResult(
        raw_value=latest_funding,
        normalized_value=float(z_score),
        direction=direction,
        confidence=float(confidence),
        data_quality=DataQuality.VALID,
        provenance=f"Funding Z-Score: {z_score:.2f} (Median: {rolling_median:.5f})"
    )
