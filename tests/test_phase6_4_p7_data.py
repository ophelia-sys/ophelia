import pytest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.ml4t_benchmark.features.p7_volume_acceptance import engineer_p7_volume_acceptance_features

def test_p7_zero_volume_behavior():
    # Test handling of 0 volume (which causes zero denominators in VWAP)
    dates = pd.date_range("2023-01-01 00:00:00", periods=500, freq="5min")
    df_ohlcv = pd.DataFrame({
        'timestamp': dates,
        'close': np.ones(500) * 20000,
        'volume': np.zeros(500) # EXACTLY ZERO VOLUME
    })
    
    df_feat = engineer_p7_volume_acceptance_features(df_ohlcv)
    
    assert 'price_to_vwap_8h' in df_feat.columns
    assert 'price_to_vwap_1d' in df_feat.columns
    assert 'volume_concentration_1d' in df_feat.columns
    assert 'value_area_proxy' in df_feat.columns
    
    # Check that it gracefully outputs 0 or 1.0 depending on the registry spec
    assert df_feat['price_to_vwap_8h'].iloc[-1] == 0.0
    assert df_feat['price_to_vwap_1d'].iloc[-1] == 0.0
    assert df_feat['volume_concentration_1d'].iloc[-1] == 1.0 # 0 / 0 defaults to 1.0 as specified
    assert df_feat['value_area_proxy'].iloc[-1] == 0.0
    
def test_p7_normal_behavior():
    dates = pd.date_range("2023-01-01 00:00:00", periods=500, freq="5min")
    df_ohlcv = pd.DataFrame({
        'timestamp': dates,
        'close': np.linspace(20000, 21000, 500),
        'volume': np.random.uniform(10, 100, 500)
    })
    
    df_feat = engineer_p7_volume_acceptance_features(df_ohlcv)
    
    assert df_feat['price_to_vwap_8h'].isna().sum() == 95 # Rolling 96 requires 95 NaNs
    assert df_feat['price_to_vwap_1d'].isna().sum() == 287 # Rolling 288 requires 287 NaNs
