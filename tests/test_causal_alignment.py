import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from research.pipeline.temporal_alignment import align_higher_timeframe
from scratch.validate_resampling import resample_ohlcv

def test_causal_alignment_boundaries():
    # Create a synthetic 1m dataset
    # We will test 00:00 to 04:15
    times = pd.date_range(start='2026-08-01 00:00:00', end='2026-08-01 04:15:00', freq='1min', tz='UTC')
    
    df_1m = pd.DataFrame({
        'timestamp': times.astype(np.int64) // 10**6, # unix ms
        'candle_open_time_utc': times,
        'candle_close_time_utc': times + pd.Timedelta(minutes=1) - pd.Timedelta(milliseconds=1),
        'open': np.random.randn(len(times)),
        'high': np.random.randn(len(times)),
        'low': np.random.randn(len(times)),
        'close': np.random.randn(len(times)),
        'volume': np.random.randn(len(times)),
    })
    
    # Generate 15m timeframe
    df_15m = resample_ohlcv(df_1m, '15min', 15)
    df_1h = resample_ohlcv(df_1m, '1h', 60)
    df_4h = resample_ohlcv(df_1m, '4h', 240)
    
    # Align
    aligned_15m = align_higher_timeframe(df_1m, df_15m)
    aligned_1h = align_higher_timeframe(df_1m, df_1h)
    aligned_4h = align_higher_timeframe(df_1m, df_4h)
    
    # Helper to check a specific 1m candle (by its open time string)
    def check_1m_candle(time_str, df_aligned, expected_htf_open_time_str):
        row = df_aligned[df_aligned['candle_open_time_utc'] == pd.Timestamp(time_str, tz='UTC')].iloc[0]
        if expected_htf_open_time_str is None:
            assert pd.isna(row.get('candle_open_time_utc_htf'))
        else:
            assert row['candle_open_time_utc_htf'] == pd.Timestamp(expected_htf_open_time_str, tz='UTC')
            
    # 00:00 1m candle (closes at 00:00:59.999). 
    # At this point, the 15m candle (00:00-00:14) is NOT finished.
    # So there should be NO 15m candle observable yet (since it's the start of the data).
    check_1m_candle('2026-08-01 00:00:00', aligned_15m, None)
    
    # 00:01 1m candle
    check_1m_candle('2026-08-01 00:01:00', aligned_15m, None)
    
    # 00:14 1m candle (closes at 00:14:59.999).
    # This is exactly the moment the 00:00 15m candle finishes!
    # So at 00:14, the 15m candle for 00:00-00:14 is observable.
    check_1m_candle('2026-08-01 00:14:00', aligned_15m, '2026-08-01 00:00:00')
    
    # 00:15 1m candle (closes at 00:15:59.999).
    # The observable 15m candle is still the 00:00 one. The 00:15 15m candle is not finished yet.
    check_1m_candle('2026-08-01 00:15:00', aligned_15m, '2026-08-01 00:00:00')
    
    # 00:59 1m candle (closes at 00:59:59.999)
    # The 00:00 1h candle finishes exactly now!
    check_1m_candle('2026-08-01 00:59:00', aligned_1h, '2026-08-01 00:00:00')
    
    # 01:00 1m candle (closes at 01:00:59.999)
    # Still the 00:00 1h candle.
    check_1m_candle('2026-08-01 01:00:00', aligned_1h, '2026-08-01 00:00:00')
    
    # 03:59 1m candle (closes at 03:59:59.999)
    # The 00:00 4h candle finishes exactly now!
    check_1m_candle('2026-08-01 03:59:00', aligned_4h, '2026-08-01 00:00:00')
    
    # 04:00 1m candle
    check_1m_candle('2026-08-01 04:00:00', aligned_4h, '2026-08-01 00:00:00')
    
    print("All causal alignment boundary tests PASSED.")

if __name__ == '__main__':
    test_causal_alignment_boundaries()
