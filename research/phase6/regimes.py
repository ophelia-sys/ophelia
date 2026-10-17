import pandas as pd
import numpy as np
from typing import Dict

class RegimeAnalyzer:
    """
    Causal regime classification based strictly on historical data.
    """
    def __init__(self, vol_window: int = 100):
        self.vol_window = vol_window
        
    def classify_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds regime labels to the dataframe.
        """
        result = df.copy()
        
        if 'high' in result.columns and 'low' in result.columns and 'close' in result.columns:
            # Simple ATR approx
            tr1 = result['high'] - result['low']
            tr2 = (result['high'] - result['close'].shift(1)).abs()
            tr3 = (result['low'] - result['close'].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(window=14).mean()
            
            # Causal historical median of ATR (up to t-1)
            hist_median_atr = atr.shift(1).rolling(window=self.vol_window, min_periods=10).median()
            
            # Volatility regime
            result['vol_regime'] = np.where(atr.shift(1) > hist_median_atr, 'HIGH_VOL', 'LOW_VOL')
        else:
            result['vol_regime'] = 'UNKNOWN'
            
        return result
