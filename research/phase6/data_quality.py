import pandas as pd
from typing import Dict, Any

class DataQualityAuditor:
    """
    Audits historical data for gaps, missing timestamps, zero-volume candles, etc.
    Invalidates active states on large gaps.
    """
    def __init__(self, max_data_gap_seconds: int = 300):
        self.max_data_gap_seconds = max_data_gap_seconds

    def audit_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Returns an audit report on the dataset.
        """
        if df.empty or 'timestamp' not in df.columns:
            return {"status": "INVALID", "reason": "Empty or missing timestamp"}
            
        # Check monotonicity
        is_monotonic = df['timestamp'].is_monotonic_increasing
        
        # Check gaps
        time_diffs = df['timestamp'].diff()
        max_gap = time_diffs.max() if len(df) > 1 else 0
        
        # Check zero volume
        zero_vol = (df['volume'] == 0).sum() if 'volume' in df.columns else 0
        
        # Check OHLC consistency (H >= max(O,C) and L <= min(O,C))
        ohlc_valid = True
        if all(c in df.columns for c in ['open', 'high', 'low', 'close']):
            high_valid = (df['high'] >= df[['open', 'close']].max(axis=1)).all()
            low_valid = (df['low'] <= df[['open', 'close']].min(axis=1)).all()
            ohlc_valid = bool(high_valid and low_valid)
            
        return {
            "status": "PASS" if is_monotonic and ohlc_valid else "FAIL",
            "is_monotonic": bool(is_monotonic),
            "max_data_gap": float(max_gap),
            "zero_volume_candles": int(zero_vol),
            "ohlc_consistent": ohlc_valid
        }
        
    def get_gap_indices(self, df: pd.DataFrame) -> list:
        """
        Returns indices where a gap exceeds max_data_gap_seconds.
        Used to force cold starts in event generation.
        """
        if len(df) < 2: return []
        time_diffs = df['timestamp'].diff()
        gaps = time_diffs > self.max_data_gap_seconds
        return df[gaps].index.tolist()
