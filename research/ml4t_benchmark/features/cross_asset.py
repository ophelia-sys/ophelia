import pandas as pd
import numpy as np

# Frozen mapping: BTC uses ETH as leader, all others use BTC
PRIMARY_LEADER_MAP = {
    "BTCUSDT": "ETHUSDT",
    "ETHUSDT": "BTCUSDT",
    "SOLUSDT": "BTCUSDT",
    "XRPUSDT": "BTCUSDT",
    "BNBUSDT": "BTCUSDT",
    "ADAUSDT": "BTCUSDT",
}

ALL_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def generate_p5_features(target_symbol: str, universe_dfs: dict) -> pd.DataFrame:
    """
    Generate P5 Cross-Asset Leadership features for a target symbol.
    
    Args:
        target_symbol: The symbol being predicted (e.g. 'BTCUSDT')
        universe_dfs: Dict mapping symbol -> DataFrame of OHLCV data. 
                      Each DF must have 'timestamp' and 'close'.
                      Timestamps must be identical 5m grids across all dict entries.
    
    Returns:
        DataFrame with index aligned to the target symbol's OHLCV and P5 columns.
    """
    if target_symbol not in universe_dfs:
        raise ValueError(f"Target symbol {target_symbol} missing from universe_dfs")
        
    df_target = universe_dfs[target_symbol]
    timestamps = df_target['timestamp'].values
    
    # Pre-allocate output
    out = pd.DataFrame({'timestamp': timestamps})
    n_rows = len(timestamps)
    
    # 1. Self-reference check
    primary_leader = PRIMARY_LEADER_MAP[target_symbol]
    if primary_leader == target_symbol:
        raise ValueError(f"Self-reference detected: {target_symbol} cannot lead itself.")
        
    if primary_leader not in universe_dfs:
        raise ValueError(f"Required primary leader {primary_leader} missing from universe_dfs")
        
    # 2. Extract closes as numpy arrays aligned by timestamp index implicitly
    # (Assuming the caller aligned timestamps perfectly as required by the dataset)
    # We will verify timestamp alignment in the tests.
    closes = {sym: universe_dfs[sym]['close'].values for sym in universe_dfs}
    
    # 3. Compute returns
    # R(t, k) = C_t / C_{t-k} - 1
    def get_return(sym, k):
        C = closes[sym]
        ret = np.full(n_rows, np.nan)
        if len(C) > k:
            ret[k:] = C[k:] / C[:-k] - 1.0
        return ret
        
    # Primary Leader returns
    r_lead_5m = get_return(primary_leader, 1)
    r_lead_15m = get_return(primary_leader, 3)
    r_lead_30m = get_return(primary_leader, 6)
    
    out['primary_lead_return_5m'] = r_lead_5m
    out['primary_lead_return_15m'] = r_lead_15m
    out['primary_lead_return_30m'] = r_lead_30m
    
    # Target relative strength
    r_target_15m = get_return(target_symbol, 3)
    out['target_relative_strength_to_primary_15m'] = r_target_15m - r_lead_15m
    
    # Cross-asset metrics (excluding target symbol)
    other_symbols = [s for s in universe_dfs if s != target_symbol]
    
    # Need at least one other symbol to compute median/dispersion
    if not other_symbols:
        out['cross_asset_median_return_5m'] = np.nan
        out['cross_asset_median_return_15m'] = np.nan
        out['cross_asset_dispersion_15m'] = np.nan
    else:
        # Collect returns for others
        other_ret_5m = np.column_stack([get_return(s, 1) for s in other_symbols])
        other_ret_15m = np.column_stack([get_return(s, 3) for s in other_symbols])
        
        # Calculate cross-sectional stats
        # Using nanmedian / nanstd to handle missing data in individual assets,
        # but if the prompt implies strict missingness, we could enforce it.
        # "If any required cross-asset OHLCV bar is missing... evaluate to NaN"
        # We will use strict numpy functions without nan-handling to enforce this.
        
        # But pandas OHLCV forward-fills? 
        # For our universe, we know the 5m data is perfectly aligned with no missing bars.
        # If there are NaNs, they propagate.
        
        # Enforce strict missingness: if any OTHER asset is NaN, the result is NaN.
        out['cross_asset_median_return_5m'] = np.median(other_ret_5m, axis=1)
        out['cross_asset_median_return_15m'] = np.median(other_ret_15m, axis=1)
        out['cross_asset_dispersion_15m'] = np.std(other_ret_15m, axis=1, ddof=1) # Sample std
        
    return out
