import pandas as pd
import numpy as np

def align_higher_timeframe(df_1m: pd.DataFrame, df_htf: pd.DataFrame) -> pd.DataFrame:
    """
    Given a canonical 1m dataframe and a higher timeframe dataframe (e.g. 15m),
    join the higher timeframe features to the 1m dataframe such that AT time T
    (the close of the 1m candle), only a completely finished HTF candle is observable.
    
    The convention: 
    A 15m candle representing 10:00 - 10:14:59 finishes at 10:14:59.
    It becomes observable EXACTLY AT 10:14:59 (which is the close time of the 10:14 1m candle).
    For any prediction timestamp T (which we define as candle_close_time_utc), 
    we can use an HTF candle if its candle_close_time_utc <= T.
    
    To implement this causally, we use pd.merge_asof.
    """
    
    # Ensure sorted by close time
    df_1m = df_1m.sort_values('candle_close_time_utc')
    df_htf = df_htf.sort_values('candle_close_time_utc')
    
    # We want to join HTF data into the 1m dataframe
    # The condition is HTF.candle_close_time_utc <= 1m.candle_close_time_utc
    
    joined = pd.merge_asof(
        df_1m,
        df_htf,
        on='candle_close_time_utc',
        direction='backward', # Use the latest HTF candle that is <= the 1m candle close time
        suffixes=('', '_htf')
    )
    
    # Ensure incomplete candles are dropped or set to NaN
    if 'is_complete' in joined.columns:
        invalid_mask = joined['is_complete'] != True
        htf_cols = [c for c in joined.columns if c.endswith('_htf')]
        joined.loc[invalid_mask, htf_cols] = np.nan
        
    return joined
