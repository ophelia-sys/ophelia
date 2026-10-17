import numpy as np
import pandas as pd
import os
import glob

def load_funding_data(symbol: str) -> pd.DataFrame:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../data/raw/positioning/funding'))
    pattern = os.path.join(base_dir, f"{symbol}-fundingRate-*.zip")
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame(columns=['funding_time', 'funding_rate'])
        
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        # Usually 'calc_time' is millisecond timestamp when funding actually settled
        df['funding_time'] = pd.to_datetime(df['calc_time'], unit='ms')
        df['funding_rate'] = df['last_funding_rate']
        dfs.append(df[['funding_time', 'funding_rate']])
        
    res = pd.concat(dfs, ignore_index=True)
    res = res.sort_values('funding_time').drop_duplicates('funding_time')
    return res

def engineer_p6_funding_features(df_ohlcv: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Engineers Phase 6.4 P6 Funding / Positioning Pressure features.
    Strictly uses LAST-KNOWN-AVAILABLE FUNDING via backward merge_asof on T_decision.
    """
    df_res = df_ohlcv.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_res['timestamp']):
        df_res['timestamp'] = pd.to_datetime(df_res['timestamp'], unit='ms')
        
    # Decision time is strictly the end of the 5m candle
    df_res['decision_time'] = df_res['timestamp'] + pd.Timedelta(minutes=5)
    
    df_funding = load_funding_data(symbol)
    if df_funding.empty:
        # Fill with NaN if no data is found for the symbol
        for col in ['funding_rate', 'funding_rate_zscore_1d', 'funding_rate_change_8h', 'funding_price_interaction']:
            df_res[col] = np.nan
        return df_res
        
    df_res = df_res.sort_values('decision_time')
    df_funding = df_funding.sort_values('funding_time')
    
    # Align dtypes to prevent pandas merge_asof '<M8[us]' vs '<M8[ms]' error
    df_res['decision_time'] = df_res['decision_time'].astype('datetime64[ns]')
    df_funding['funding_time'] = df_funding['funding_time'].astype('datetime64[ns]')
    
    # merge_asof backward ensures we only pick funding_time <= decision_time
    df_merged = pd.merge_asof(
        df_res, 
        df_funding, 
        left_on='decision_time', 
        right_on='funding_time', 
        direction='backward'
    )
    
    fr = df_merged['funding_rate']
    
    # 2. funding_rate_zscore_1d (288 periods of 5m)
    fr_mean = fr.rolling(288).mean()
    fr_std = fr.rolling(288).std()
    zscore = (fr - fr_mean) / fr_std
    zscore = np.where(fr_std == 0.0, 0.0, zscore)
    df_merged['funding_rate_zscore_1d'] = zscore
    
    # 3. funding_rate_change_8h (96 periods of 5m)
    df_merged['funding_rate_change_8h'] = fr - fr.shift(96)
    
    # 4. funding_price_interaction
    # log_return_1h = ln(close(T) / close(T-12))
    log_ret_1h = np.log(df_merged['close'] / df_merged['close'].shift(12))
    df_merged['funding_price_interaction'] = fr * log_ret_1h
    
    df_merged.drop(columns=['decision_time', 'funding_time'], inplace=True, errors='ignore')
    return df_merged
