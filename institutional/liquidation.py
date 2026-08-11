import numpy as np
import pandas as pd
from institutional.types import DataQuality, FeatureStatus, FeatureResult, Direction

def analyze_liquidation_state(long_liq: pd.Series = None, short_liq: pd.Series = None) -> FeatureResult:
    """
    Liquidation Imbalance analysis.
    LI = (L_long - L_short) / V_total
    Also computes robust MAD Z-scores of liquidation intensity.
    """
    # Currently UNAVAILABLE because BingXClient doesn't provide real-time liquidations.
    return FeatureResult(
        raw_value=None,
        normalized_value=None,
        direction=Direction.UNKNOWN,
        confidence=0.0,
        data_quality=DataQuality.UNAVAILABLE,
        provenance=None
    )
