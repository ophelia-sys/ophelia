import numpy as np
import pandas as pd

def engineer_positioning_features(df_ohlcv: pd.DataFrame, df_oi: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers Phase 6.2 P1 Open Interest features according to the frozen mathematical registry.
    Args:
        df_ohlcv: 5m OHLCV DataFrame with CVD features already merged.
        df_oi: 5m OI DataFrame (from research_oi_5m.parquet).
    Returns:
        DataFrame with new positioning features merged.
    """
    df_res = df_ohlcv.copy()
    df_oi = df_oi.copy()
    
    from pandas.api.types import is_datetime64_any_dtype as is_datetime
    if not is_datetime(df_res['timestamp']):
        df_res['timestamp'] = pd.to_datetime(df_res['timestamp'], unit='ms')
    if not is_datetime(df_oi['timestamp']):
        # Handle both ms and us timestamps
        ts_val = df_oi['timestamp'].iloc[0]
        if ts_val > 1e14:  # microseconds (16 digits)
            df_oi['timestamp'] = pd.to_datetime(df_oi['timestamp'], unit='us')
        else:              # milliseconds (13 digits)
            df_oi['timestamp'] = pd.to_datetime(df_oi['timestamp'], unit='ms')

    # 1. Exact Causal Alignment
    # OHLCV timestamp t represents [t, t+5m)
    # The decision is evaluated at t+5m.
    # Therefore, we want EXACTLY the OI snapshot at t+5m.
    df_res['decision_time'] = df_res['timestamp'] + pd.Timedelta(minutes=5)
    
    df_oi = df_oi.rename(columns={'timestamp': 'oi_timestamp'})
    # Drop duplicates on the snapshot timestamp just in case
    df_oi = df_oi.drop_duplicates(subset=['oi_timestamp'])
    
    # Left join exactly on decision_time == oi_timestamp
    df_res = pd.merge(
        df_res, 
        df_oi[['oi_timestamp', 'sum_open_interest']], 
        left_on='decision_time', 
        right_on='oi_timestamp', 
        how='left'
    )
    
    # If the OI snapshot at exactly decision_time is missing, aligned_oi becomes NaN.
    df_res['aligned_oi'] = df_res['sum_open_interest']
    
    # Drop intermediate merge columns
    df_res = df_res.drop(columns=['decision_time', 'oi_timestamp', 'sum_open_interest'])
    
    # 2. Compute Features on Continuous Grid
    oi_series = df_res['aligned_oi']
    
    # oi_change_1h (12 bars on 5m grid)
    df_res['oi_change_1h'] = (oi_series - oi_series.shift(12)) / oi_series.shift(12)
    
    # oi_change_4h (48 bars on 5m grid)
    df_res['oi_change_4h'] = (oi_series - oi_series.shift(48)) / oi_series.shift(48)
    
    # oi_zscore_1d (288 bars on 5m grid)
    oi_mean_1d = oi_series.rolling(288).mean()
    oi_std_1d = oi_series.rolling(288).std()
    
    df_res['oi_zscore_1d'] = (oi_series - oi_mean_1d) / oi_std_1d
    df_res['oi_zscore_1d'] = np.where(oi_std_1d == 0.0, 0.0, df_res['oi_zscore_1d'])
    
    # 3. price_oi_regime
    delta_p = df_res['close'] - df_res['close'].shift(12)
    delta_oi = df_res['aligned_oi'] - df_res['aligned_oi'].shift(12)
    
    regime = pd.Series(np.nan, index=df_res.index)
    
    mask_long_build = (delta_p > 0) & (delta_oi > 0)
    mask_short_cover = (delta_p > 0) & (delta_oi <= 0)
    mask_short_build = (delta_p <= 0) & (delta_oi > 0)
    mask_long_cover = (delta_p <= 0) & (delta_oi <= 0)
    
    regime[mask_long_build] = 1
    regime[mask_short_cover] = 2
    regime[mask_short_build] = -1
    regime[mask_long_cover] = -2
    
    regime = np.where(delta_p.isna() | delta_oi.isna(), np.nan, regime)
    df_res['price_oi_regime'] = regime
    
    # 4. cvd_oi_divergence & cvd_oi_interaction
    delta_oi_1h = delta_oi
    
    if 'cvd_delta_1h' in df_res.columns:
        cvd_1h = df_res['cvd_delta_1h']
    else:
        cvd_1h = pd.Series(np.nan, index=df_res.index)
        
    z_cvd_12 = (cvd_1h - cvd_1h.rolling(12).mean()) / cvd_1h.rolling(12).std()
    z_oi_12 = (delta_oi_1h - delta_oi_1h.rolling(12).mean()) / delta_oi_1h.rolling(12).std()
    
    z_cvd_12 = np.where(cvd_1h.rolling(12).std() == 0, 0, z_cvd_12)
    z_oi_12 = np.where(delta_oi_1h.rolling(12).std() == 0, 0, z_oi_12)
    
    df_res['cvd_oi_divergence'] = z_cvd_12 - z_oi_12
    df_res['cvd_oi_interaction'] = z_cvd_12 * z_oi_12
    
    # Final missingness check: ensure if aligned_oi is NaN, everything is NaN
    for col in ['oi_change_1h', 'oi_change_4h', 'oi_zscore_1d', 'price_oi_regime', 'cvd_oi_divergence', 'cvd_oi_interaction']:
        df_res[col] = np.where(df_res['aligned_oi'].isna(), np.nan, df_res[col])
        
    return df_res
