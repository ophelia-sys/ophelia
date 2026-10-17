import numpy as np
import pandas as pd

def engineer_p7_volume_acceptance_features(df_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers Phase 6.4 P7 OHLCV-Derived Volume / Price Acceptance Proxies.
    Calculated completely deterministically from the 5m OHLCV grid.
    """
    df_res = df_ohlcv.copy()
    
    close = df_res['close']
    vol = df_res['volume']
    
    # 8-hour VWAP = 96 periods
    vol_price_8h = (close * vol).rolling(96).sum()
    vol_sum_8h = vol.rolling(96).sum()
    vwap_8h = vol_price_8h / vol_sum_8h
    df_res['price_to_vwap_8h'] = np.where(vol_sum_8h == 0, 0.0, (close / vwap_8h) - 1.0)
    
    # 24-hour VWAP = 288 periods
    vol_price_1d = (close * vol).rolling(288).sum()
    vol_sum_1d = vol.rolling(288).sum()
    vwap_1d = vol_price_1d / vol_sum_1d
    df_res['price_to_vwap_1d'] = np.where(vol_sum_1d == 0, 0.0, (close / vwap_1d) - 1.0)
    
    # Volume concentration 1d
    vol_mean_1d = vol.rolling(288).mean()
    df_res['volume_concentration_1d'] = np.where(vol_mean_1d == 0, 1.0, vol / vol_mean_1d)
    
    # Value area proxy
    # VWSD = sqrt( sum(vol * (close - VWAP_1d)^2) / sum(vol) )
    diff_sq = (close - vwap_1d) ** 2
    weighted_diff_sq_1d = (vol * diff_sq).rolling(288).sum()
    vwsd_1d = np.sqrt(weighted_diff_sq_1d / vol_sum_1d)
    
    vwsd_1d = np.where(vol_sum_1d == 0, 0.0, vwsd_1d)
    
    val_proxy = (close - vwap_1d) / vwsd_1d
    df_res['value_area_proxy'] = np.where(vwsd_1d == 0.0, 0.0, val_proxy)
    
    return df_res
