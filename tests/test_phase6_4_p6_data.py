import pytest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.ml4t_benchmark.features.p6_funding import load_funding_data, engineer_p6_funding_features

def test_p6_funding_data_loading():
    # Load funding for BTCUSDT
    df = load_funding_data('BTCUSDT')
    assert not df.empty, "Funding data should not be empty"
    assert 'funding_time' in df.columns
    assert 'funding_rate' in df.columns
    
    # Check monotonicity
    assert df['funding_time'].is_monotonic_increasing
    
    # Check no exact duplicates
    assert not df['funding_time'].duplicated().any()

def test_p6_funding_feature_generation():
    # Create dummy OHLCV
    dates = pd.date_range("2023-01-01 00:00:00", "2023-01-05 00:00:00", freq="5min", tz="UTC").tz_localize(None)
    df_ohlcv = pd.DataFrame({
        'timestamp': dates,
        'close': np.linspace(20000, 21000, len(dates))
    })
    
    df_feat = engineer_p6_funding_features(df_ohlcv, 'BTCUSDT')
    
    assert 'funding_rate' in df_feat.columns
    assert 'funding_rate_zscore_1d' in df_feat.columns
    assert 'funding_rate_change_8h' in df_feat.columns
    assert 'funding_price_interaction' in df_feat.columns
    
    # Ensure correct shape
    assert len(df_feat) == len(df_ohlcv)
