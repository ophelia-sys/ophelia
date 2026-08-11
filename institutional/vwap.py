import numpy as np
import pandas as pd
from typing import Optional
from institutional.types import DataQuality, FeatureResult, Direction

def calculate_vwap(ohlcv: pd.DataFrame, window: int = 15) -> FeatureResult:
    """
    Mathematically valid trailing VWAP.
    Base definition: VWAP = sum(P_i * V_i) / sum(V_i)
    where P_i is the typical price (High + Low + Close) / 3.
    
    Parameters:
    - ohlcv: DataFrame with columns 'high', 'low', 'close', 'volume'
    - window: The trailing window period (e.g., 15 for 15-period VWAP)
    """
    if ohlcv is None or len(ohlcv) < window or window <= 0:
        return FeatureResult(
            raw_value=None,
            normalized_value=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            provenance=f"vwap.py: insufficient history for {window}-period VWAP"
        )
        
    required_cols = {'high', 'low', 'close', 'volume'}
    if not required_cols.issubset(ohlcv.columns):
        return FeatureResult(
            raw_value=None,
            normalized_value=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INVALID,
            provenance="vwap.py: missing required OHLCV columns"
        )
        
    # Ensure no future look-ahead by using strictly the rolling window up to the current row
    typical_price = (ohlcv['high'] + ohlcv['low'] + ohlcv['close']) / 3.0
    pv = typical_price * ohlcv['volume']
    
    # Calculate rolling sums
    rolling_pv = pv.rolling(window=window, min_periods=window).sum()
    rolling_v = ohlcv['volume'].rolling(window=window, min_periods=window).sum()
    
    current_pv = rolling_pv.iloc[-1]
    current_v = rolling_v.iloc[-1]
    
    if pd.isna(current_pv) or pd.isna(current_v) or current_v == 0:
        return FeatureResult(
            raw_value=None,
            normalized_value=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            provenance="vwap.py: zero volume or NaN in rolling window"
        )
        
    vwap = current_pv / current_v
    current_close = ohlcv['close'].iloc[-1]
    
    vwap_deviation = (current_close - vwap) / vwap
    
    # VWAP is evidence, not a signal. We don't naively convert it to LONG/SHORT.
    # A large deviation implies over-extension and potential mean reversion, 
    # but could also imply strong trend. We leave direction as UNKNOWN.
    return FeatureResult(
        raw_value=vwap,
        normalized_value=vwap_deviation,
        direction=Direction.UNKNOWN,
        confidence=min(abs(vwap_deviation) * 100, 1.0), # simple pseudo-confidence scaling
        data_quality=DataQuality.VALID,
        provenance=f"Trailing VWAP ({window}): {vwap:.2f}, Dev: {vwap_deviation:.4%}"
    )
