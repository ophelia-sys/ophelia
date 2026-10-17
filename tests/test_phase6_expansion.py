import pytest
import pandas as pd
import numpy as np
from research.data.normalize_parquet import ParquetNormalizer
from research.phase6.events import EventGenerator
from institutional.normalization import calculate_robust_z_score

def test_causal_as_of_join_adversarial():
    """
    Test that the OI join strictly prevents future data leakage.
    For candle t, only OI_t' <= t is selected.
    """
    normalizer = ParquetNormalizer()
    
    # Klines: t=1000, 2000, 3000
    klines = pd.DataFrame({
        'timestamp': [1000, 2000, 3000],
        'close': [10, 11, 12]
    })
    
    # Adversarial OI:
    # t=500 (before all, should join to 1000)
    # t=2000 (exact match)
    # t=2500 (should join to 3000)
    # t=3500 (future data, should NOT join to 3000)
    oi = pd.DataFrame({
        'timestamp': [500, 2000, 2500, 3500],
        'sum_open_interest': [50, 60, 70, 80],
        'sum_open_interest_value': [500, 660, 840, 960]
    })
    
    joined = normalizer.join_open_interest(klines, oi)
    
    # Expected:
    # 1000 -> 500
    # 2000 -> 2000
    # 3000 -> 2500
    assert joined.loc[0, 'sum_open_interest'] == 50
    assert joined.loc[1, 'sum_open_interest'] == 60
    assert joined.loc[2, 'sum_open_interest'] == 70
    
    # Also verify that max(joined_OI_timestamp - candle_timestamp) <= 0
    joined_valid = joined.dropna(subset=['oi_timestamp'])
    assert (joined_valid['oi_timestamp'] <= joined_valid['timestamp']).all(), "CRITICAL: Future OI leaked!"

def test_causal_as_of_join_missing():
    """
    Test missing OI handling and NaN propagation.
    """
    normalizer = ParquetNormalizer()
    klines = pd.DataFrame({
        'timestamp': [1000, 2000],
        'close': [10, 11]
    })
    oi = pd.DataFrame({
        'timestamp': [2500], # All in the future!
        'sum_open_interest': [50],
        'sum_open_interest_value': [500]
    })
    
    joined = normalizer.join_open_interest(klines, oi)
    assert np.isnan(joined.loc[0, 'sum_open_interest'])
    assert np.isnan(joined.loc[1, 'sum_open_interest'])

def test_cross_symbol_isolation_in_events():
    """
    Test that symbol boundaries and data gaps trigger state resets in EventGenerator.
    """
    gen = EventGenerator(alpha=1.0, gamma=1.0, w=2, epsilon=0.5, beta=0.1)
    
    # We will simulate a continuous sequence but with a symbol change at index 5
    # and a time gap at index 10.
    
    # Baseline normal data, let's just make everything normal.
    # W=2 requires 5 candles to detect a pool.
    
    # First 5 candles for BTCUSDT (t=100..500)
    # Then 5 candles for ETHUSDT (t=600..1000)
    # The symbol change itself isn't intrinsically detected by EventGenerator unless we feed it separately.
    # WAIT: Pipeline feeds symbols separately by doing df.groupby('symbol').
    # But if we were to feed them together, the 1-hour gap would reset it.
    
    # Let's test the GAP cold start explicitly.
    timestamps = [1000, 2000, 3000, 4000, 5000, 6000] 
    # Create a swing low at 3000
    lows = [10, 8, 5, 8, 10, 11]
    
    df_continuous = pd.DataFrame({
        'timestamp': timestamps,
        'open': lows,
        'high': [x+2 for x in lows],
        'low': lows,
        'close': [x+1 for x in lows],
        'symbol': 'BTCUSDT'
    })
    atr = pd.Series([1.0]*6)
    
    events_cont = gen.generate_events(df_continuous, atr)
    print("ACTIVE POOLS:", gen.active_pools)
    assert len(gen.active_pools) == 1, "Pool should be active"
    
    # Now simulate a gap > 3600000ms
    timestamps_gap = [1000, 2000, 3000, 4000, 5000, 5000 + 3600001]
    df_gap = pd.DataFrame({
        'timestamp': timestamps_gap,
        'open': lows,
        'high': [x+2 for x in lows],
        'low': lows,
        'close': [x+1 for x in lows],
        'symbol': 'BTCUSDT'
    })
    
    events_gap = gen.generate_events(df_gap, atr)
    # At the last candle (gap), the pool should be reset because of the gap
    assert len(gen.active_pools) == 0, "Pool should have been reset by the gap"

