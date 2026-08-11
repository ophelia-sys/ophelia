import numpy as np
import pandas as pd
from institutional.volatility import calculate_close_to_close_volatility

def estimate_slippage_proxy(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Estimates a proxy for slippage/execution cost.
    When true order book depth is unavailable, short-term realized volatility 
    often correlates with wider spreads and thinner liquidity, causing higher slippage.
    """
    vol = calculate_close_to_close_volatility(df, window=window)
    # A simple proportional proxy: higher vol implies higher expected slippage.
    # Scaled arbitrarily to represent basis points of impact.
    return vol * 100.0  # scaling factor for proxy
