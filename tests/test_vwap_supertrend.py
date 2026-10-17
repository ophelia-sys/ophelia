import pandas as pd
import numpy as np
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, calc_supertrend

def test_session_vwap_reset():
    # 2 days of 5m data
    dr1 = pd.date_range("2024-01-01 23:00", "2024-01-01 23:55", freq="5min")
    dr2 = pd.date_range("2024-01-02 00:00", "2024-01-02 00:55", freq="5min")
    timestamps = dr1.union(dr2)
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0,
        "volume": 10.0
    })
    
    vwap = calc_session_vwap(df)
    
    # Check that VWAP at 2024-01-02 00:00 resets completely.
    # Tp is 100 every candle. Volume is 10.
    # At index 12 (first of day 2), vwap should be exactly 100 regardless of previous history
    # We will test reset by setting the second day to different values.
    
    df.loc[df['timestamp'].dt.date == pd.to_datetime('2024-01-02').date(), ['high', 'low', 'close']] = [210.0, 190.0, 200.0]
    
    vwap = calc_session_vwap(df)
    assert np.isclose(vwap.iloc[0], 100.0)
    assert np.isclose(vwap.iloc[12], 200.0)  # First candle of new day, reset to 200

def test_supertrend_parity():
    # Simple test for Supertrend calculation
    df = pd.DataFrame({
        "high": [10.0, 12.0, 11.0, 15.0, 14.0] * 5,
        "low": [8.0, 9.0, 8.0, 12.0, 11.0] * 5,
        "close": [9.0, 11.0, 9.0, 14.0, 13.0] * 5,
    })
    
    st_df = calc_supertrend(df, length=10, factor=3.0)
    assert 'Supertrend' in st_df.columns
    assert 'ST_Direction' in st_df.columns
    # Basic bounds check
    assert len(st_df) == 25
    assert not np.isnan(st_df['ST_Direction'].iloc[-1])
