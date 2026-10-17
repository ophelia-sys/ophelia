import pandas as pd
import numpy as np

def compute_p3_spot_perp_features(df_futures: pd.DataFrame, df_spot: pd.DataFrame) -> pd.DataFrame:
    """
    Computes P3 Spot/Perpetual Divergence & Basis features.
    Strictly aligns by exact timestamp.
    df_futures and df_spot must both be indexed by T_decision (or equivalently open_time).
    """
    # Align by index explicitly
    common_idx = df_futures.index.intersection(df_spot.index)
    
    fut = df_futures.loc[common_idx]
    spot = df_spot.loc[common_idx]
    
    out = pd.DataFrame(index=common_idx)
    
    # Pre-checks for strict missingness rules: 
    # if Spot is missing (NaN), features become NaN natively through pandas math.
    spot_close = spot['close']
    fut_close = fut['close']
    
    # 2.1 basis_bps
    # basis_bps = ((FuturesClose / SpotClose) - 1) * 10000
    # Rule: If SpotClose == 0, basis_bps = NaN
    spot_close_safe = spot_close.replace(0, np.nan)
    out['basis_bps'] = ((fut_close / spot_close_safe) - 1.0) * 10000.0
    
    # 2.2 basis_zscore_1d
    # Window = 288 periods (24h of 5m bars)
    # basis_zscore_1d_t = (basis_bps_t - rolling_mean_288(basis_bps)) / rolling_std_288(basis_bps)
    # Rule: Minimum 288 valid non-NaN observations. If std == 0, NaN.
    roll_mean = out['basis_bps'].rolling(window=288, min_periods=288).mean()
    roll_std = out['basis_bps'].rolling(window=288, min_periods=288).std()
    
    roll_std_safe = roll_std.replace(0, np.nan)
    out['basis_zscore_1d'] = (out['basis_bps'] - roll_mean) / roll_std_safe
    
    # 2.3 basis_change_1h
    # basis_change_1h_t = basis_bps_t - basis_bps_{t-12}
    out['basis_change_1h'] = out['basis_bps'] - out['basis_bps'].shift(12)
    
    # 2.4 spot_perp_return_spread_5m
    # spot_return_5m = (SpotClose_t / SpotClose_{t-1}) - 1
    # perp_return_5m = (FuturesClose_t / FuturesClose_{t-1}) - 1
    spot_ret_5m = spot_close.pct_change(periods=1)
    fut_ret_5m = fut_close.pct_change(periods=1)
    out['spot_perp_return_spread_5m'] = spot_ret_5m - fut_ret_5m
    
    # 2.5 spot_perp_return_spread_15m
    # spot_return_15m = (SpotClose_t / SpotClose_{t-3}) - 1
    # perp_return_15m = (FuturesClose_t / FuturesClose_{t-3}) - 1
    spot_ret_15m = spot_close.pct_change(periods=3)
    fut_ret_15m = fut_close.pct_change(periods=3)
    out['spot_perp_return_spread_15m'] = spot_ret_15m - fut_ret_15m
    
    # Finally, ensure any missing spot close induces NaN in all features
    missing_spot = spot_close.isna()
    out.loc[missing_spot, :] = np.nan
    
    return out
