import pytest
import pandas as pd
import numpy as np
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
from research.ml4t_benchmark.features.spot_perp import compute_p3_spot_perp_features

def test_p3_spot_missingness():
    """Missing spot data must immediately induce NaN in all features."""
    fut_close = [100.0, 101.0, 102.0, 103.0, 104.0]
    spot_close = [100.0, 101.0, np.nan, 103.0, 104.0]
    
    idx = pd.date_range('2022-01-01', periods=5, freq='5min')
    df_fut = pd.DataFrame({'close': fut_close}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close}, index=idx)
    
    features = compute_p3_spot_perp_features(df_fut, df_spot)
    
    # Check index 2 (the nan spot value)
    assert pd.isna(features['basis_bps'].iloc[2])
    # Next returns also depend on previous values, so they may be nan too depending on diff, 
    # but strictly the one where spot is missing must be nan
    assert pd.isna(features['spot_perp_return_spread_5m'].iloc[2])

def test_p3_spot_basis_bps_arithmetic():
    fut_close = [10000.0, 10000.0, 10010.0]
    spot_close = [10000.0, 10010.0, 10000.0]
    idx = pd.date_range('2022-01-01', periods=3, freq='5min')
    df_fut = pd.DataFrame({'close': fut_close}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close}, index=idx)
    
    features = compute_p3_spot_perp_features(df_fut, df_spot)
    
    # 1. Equal price -> 0 basis
    assert features['basis_bps'].iloc[0] == 0.0
    
    # 2. Fut < Spot -> negative basis
    # (10000/10010 - 1) * 10000 = -9.99
    np.testing.assert_almost_equal(features['basis_bps'].iloc[1], (10000.0/10010.0 - 1) * 10000)
    
    # 3. Fut > Spot -> positive basis
    np.testing.assert_almost_equal(features['basis_bps'].iloc[2], (10010.0/10000.0 - 1) * 10000)

def test_p3_spot_zero_variance():
    """Zero spot close must result in NaN, not Inf"""
    fut_close = [100.0]
    spot_close = [0.0]
    idx = pd.date_range('2022-01-01', periods=1, freq='5min')
    df_fut = pd.DataFrame({'close': fut_close}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close}, index=idx)
    
    features = compute_p3_spot_perp_features(df_fut, df_spot)
    assert pd.isna(features['basis_bps'].iloc[0])

def test_p3_spot_zscore():
    """Z-score window should strictly require 288 periods."""
    fut_close = np.linspace(100, 110, 300)
    spot_close = np.linspace(100, 110, 300) + np.random.normal(0, 0.1, 300)
    
    idx = pd.date_range('2022-01-01', periods=300, freq='5min')
    df_fut = pd.DataFrame({'close': fut_close}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close}, index=idx)
    
    features = compute_p3_spot_perp_features(df_fut, df_spot)
    
    # Before 288, should be NaN
    assert pd.isna(features['basis_zscore_1d'].iloc[286])
    
    # At 287 (which is the 288th item since 0-indexed), should be not NaN
    assert not pd.isna(features['basis_zscore_1d'].iloc[287])

def test_p3_spot_return_spread():
    fut_close = [100.0, 101.0, 102.0]
    spot_close = [100.0, 102.0, 105.0]
    
    idx = pd.date_range('2022-01-01', periods=3, freq='5min')
    df_fut = pd.DataFrame({'close': fut_close}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close}, index=idx)
    
    features = compute_p3_spot_perp_features(df_fut, df_spot)
    
    # Returns at index 1:
    # spot = 102/100 - 1 = 0.02
    # fut = 101/100 - 1 = 0.01
    # spread = 0.01
    np.testing.assert_almost_equal(features['spot_perp_return_spread_5m'].iloc[1], 0.01)

