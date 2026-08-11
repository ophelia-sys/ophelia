import numpy as np
import pandas as pd
from typing import Optional
from institutional.types import DataQuality, FeatureResult, Direction

def analyze_volume(ohlcv: pd.DataFrame, window: int = 20) -> dict[str, FeatureResult]:
    """
    Volume Foundation Engine.
    Distinguishes OHLCV volume, quote volume, relative volume, robust z-score, etc.
    """
    if ohlcv is None or len(ohlcv) < window or window <= 0:
        return {
            "volume_z_score": FeatureResult(
                raw_value=None, normalized_value=None, direction=Direction.UNKNOWN,
                confidence=0.0, data_quality=DataQuality.INSUFFICIENT_DATA, provenance="volume.py: insufficient history"
            )
        }

    required_cols = {'volume', 'close'}
    if not required_cols.issubset(ohlcv.columns):
        return {
            "volume_z_score": FeatureResult(
                raw_value=None, normalized_value=None, direction=Direction.UNKNOWN,
                confidence=0.0, data_quality=DataQuality.INVALID, provenance="volume.py: missing columns"
            )
        }

    v_series = ohlcv['volume']
    recent_v = v_series.iloc[-1]
    
    # Optional quote volume (approx if exact quote_volume column is missing)
    quote_volume = ohlcv['quote_volume'].iloc[-1] if 'quote_volume' in ohlcv.columns else recent_v * ohlcv['close'].iloc[-1]
    
    # Rolling median for robust normalization
    rolling_median = v_series.rolling(window=window, min_periods=window).median()
    current_median = rolling_median.iloc[-1]
    
    # Median Absolute Deviation (MAD) over rolling window
    def _mad(x):
        return np.median(np.abs(x - np.median(x)))
        
    rolling_mad = v_series.rolling(window=window, min_periods=window).apply(_mad, raw=True)
    current_mad = rolling_mad.iloc[-1]
    
    # Relative volume
    rel_vol = recent_v / current_median if current_median and current_median > 0 else 1.0
    
    # Robust Z-Score
    z_score = 0.0
    if not pd.isna(current_mad) and current_mad > 0:
        z_score = (recent_v - current_median) / (current_mad * 1.4826)
        
    # Percentile
    window_data = v_series.iloc[-window:]
    percentile = (window_data < recent_v).mean() * 100.0

    return {
        "raw_volume": FeatureResult(
            raw_value=recent_v, normalized_value=rel_vol, direction=Direction.UNKNOWN,
            confidence=0.0, data_quality=DataQuality.VALID, provenance="volume.py: raw volume"
        ),
        "quote_volume": FeatureResult(
            raw_value=quote_volume, normalized_value=None, direction=Direction.UNKNOWN,
            confidence=0.0, data_quality=DataQuality.VALID, provenance="volume.py: quote volume"
        ),
        "volume_z_score": FeatureResult(
            raw_value=recent_v, normalized_value=float(z_score), direction=Direction.UNKNOWN,
            confidence=min(abs(float(z_score)) / 3.0, 1.0), data_quality=DataQuality.VALID, provenance=f"volume.py: robust z-score (pct={percentile:.1f})"
        )
    }

def calculate_aggressor_volume(buy_volume: float, sell_volume: float) -> dict[str, FeatureResult]:
    """
    Calculates order-flow imbalances from actual aggressor trades.
    DO NOT CALL THIS "OFI".
    """
    total_vol = buy_volume + sell_volume
    if total_vol <= 0:
        return {
            "cvd": FeatureResult(
                raw_value=None, normalized_value=None, direction=Direction.UNKNOWN,
                confidence=0.0, data_quality=DataQuality.INSUFFICIENT_DATA, provenance="volume.py: zero volume"
            )
        }
        
    cvd = buy_volume - sell_volume
    tvi = cvd / total_vol
    
    direction = Direction.BULLISH if cvd > 0 else Direction.BEARISH
    
    return {
        "cvd": FeatureResult(
            raw_value=cvd, normalized_value=None, direction=direction,
            confidence=abs(tvi), data_quality=DataQuality.VALID, provenance="volume.py: pure aggressor cvd"
        ),
        "tvi": FeatureResult(
            raw_value=tvi, normalized_value=tvi, direction=direction,
            confidence=abs(tvi), data_quality=DataQuality.VALID, provenance="volume.py: pure aggressor tvi"
        )
    }
