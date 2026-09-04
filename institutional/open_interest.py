import numpy as np
import pandas as pd
from institutional.types import DataQuality, FeatureStatus, FeatureResult, Direction

def analyze_open_interest_state(price_series: pd.Series = None, oi_series: pd.Series = None) -> FeatureResult:
    """
    Open Interest Hypothesis engine.
    
    Inferences/Hypotheses used for classification:
    - Price UP (DeltaP > 0) + OI UP (DeltaOI > 0) -> LONG_INITIATION (New money pushing price up)
    - Price DOWN (DeltaP < 0) + OI DOWN (DeltaOI < 0) -> LONG_LIQUIDATION (Existing longs exiting, price falling)
    - Price DOWN (DeltaP < 0) + OI UP (DeltaOI > 0) -> SHORT_INITIATION (New money pushing price down)
    - Price UP (DeltaP > 0) + OI DOWN (DeltaOI < 0) -> SHORT_COVERING (Existing shorts exiting, price rising)
    
    IMPORTANT: These states are HYPOTHESES/INFERENCES and not raw exchange truths.
    """
    if price_series is None or oi_series is None or len(price_series) < 2 or len(oi_series) < 2:
        return FeatureResult(
            raw_value=None,
            normalized_value=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            provenance="open_interest.py: insufficient data"
        )
        
    delta_p = price_series.iloc[-1] - price_series.iloc[0]
    delta_oi = oi_series.iloc[-1] - oi_series.iloc[0]
    
    # Calculate percentage changes
    pct_p = delta_p / price_series.iloc[0] if price_series.iloc[0] != 0 else 0
    pct_oi = delta_oi / oi_series.iloc[0] if oi_series.iloc[0] != 0 else 0
    
    state_str = "UNKNOWN"
    direction = Direction.UNKNOWN
    confidence = 0.0
    
    if pct_p > 0 and pct_oi > 0:
        state_str = "LONG_INITIATION"
        direction = Direction.BULLISH
        confidence = min(abs(pct_p * 100) + abs(pct_oi * 100), 10.0) / 10.0
    elif pct_p < 0 and pct_oi < 0:
        state_str = "LONG_LIQUIDATION"
        direction = Direction.BEARISH
        confidence = min(abs(pct_p * 100) + abs(pct_oi * 100), 10.0) / 10.0
    elif pct_p < 0 and pct_oi > 0:
        state_str = "SHORT_INITIATION"
        direction = Direction.BEARISH
        confidence = min(abs(pct_p * 100) + abs(pct_oi * 100), 10.0) / 10.0
    elif pct_p > 0 and pct_oi < 0:
        state_str = "SHORT_COVERING"
        direction = Direction.BULLISH
        confidence = min(abs(pct_p * 100) + abs(pct_oi * 100), 10.0) / 10.0

    return FeatureResult(
        raw_value=pct_oi,
        normalized_value=None,
        direction=direction,
        confidence=float(np.clip(confidence, 0.0, 1.0)),
        data_quality=DataQuality.VALID,
        provenance=f"OI Hypothesis: {state_str} (dP={pct_p:.4f}, dOI={pct_oi:.4f})"
    )

def calculate_oi_state_vector(price_series: pd.Series, oi_series: pd.Series, window: int = 500) -> list:
    """
    Phase 6: OI State Vector
    Returns [Z_DeltaOI, Z_R] using causal robust Z-score.
    Does not collapse into a single scalar or create liquidation classifications.
    """
    if len(price_series) < window + 1 or len(oi_series) < window + 1:
        return [np.nan, np.nan]
        
    from institutional.normalization import calculate_robust_z_score
    from institutional.volatility import calculate_log_returns
    
    # We need a dataframe for calculate_log_returns, or we can just compute it directly
    returns = np.log(price_series / price_series.shift(1))
    delta_oi = oi_series.diff(1)
    
    z_r_series = calculate_robust_z_score(returns, window=window)
    z_delta_oi_series = calculate_robust_z_score(delta_oi, window=window)
    
    z_r = z_r_series.iloc[-1]
    z_delta_oi = z_delta_oi_series.iloc[-1]
    
    return [float(z_delta_oi), float(z_r)]
