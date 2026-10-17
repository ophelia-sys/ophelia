import pytest
import pandas as pd
import numpy as np

from research.ml4t_benchmark.features.cross_asset import generate_p5_features, PRIMARY_LEADER_MAP

@pytest.fixture
def mock_universe():
    # Create 10 rows of mock OHLCV data for all 6 symbols
    timestamps = pd.date_range("2022-01-01 00:00:00", periods=10, freq="5min").astype(int) // 10**6
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
    dfs = {}
    
    # We will use simple sequential close prices to make return arithmetic testable
    # BTC closes: 100, 110, 121, ... (10% return each bar)
    # ETH closes: 100, 105, 110.25, ... (5% return each bar)
    # SOL closes: 100, 102, 104.04, ... (2% return each bar)
    
    rates = {
        "BTCUSDT": 0.10,
        "ETHUSDT": 0.05,
        "SOLUSDT": 0.02,
        "XRPUSDT": 0.01,
        "BNBUSDT": -0.01,
        "ADAUSDT": -0.02
    }
    
    for sym in symbols:
        rate = rates[sym]
        closes = 100 * (1 + rate)**np.arange(10)
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": closes,
            "volume": 1000.0
        })
        dfs[sym] = df
        
    return dfs

def test_p5_timestamp_alignment(mock_universe):
    target = "BTCUSDT"
    features = generate_p5_features(target, mock_universe)
    
    # Must have same length and timestamps as the input target
    assert len(features) == len(mock_universe[target])
    np.testing.assert_array_equal(features['timestamp'].values, mock_universe[target]['timestamp'].values)

def test_p5_no_self_reference(mock_universe):
    # BTC uses ETH as leader
    btc_features = generate_p5_features("BTCUSDT", mock_universe)
    # The BTC return is 10%, ETH return is 5%. 
    # Since ETH is leader, primary_lead_return_5m should be 5% (0.05).
    # If it were self-referential, it would be 0.10.
    np.testing.assert_allclose(btc_features['primary_lead_return_5m'].dropna().values, 0.05)
    
    # ADA uses BTC as leader
    ada_features = generate_p5_features("ADAUSDT", mock_universe)
    np.testing.assert_allclose(ada_features['primary_lead_return_5m'].dropna().values, 0.10)

def test_p5_return_arithmetic(mock_universe):
    target = "ETHUSDT" # Leader is BTC (0.10 per bar)
    features = generate_p5_features(target, mock_universe)
    
    # primary_lead_return_15m (3 bars of 10% compounding)
    # (1.1^3 - 1) = 1.331 - 1 = 0.331
    expected_15m_lead = 0.331
    np.testing.assert_allclose(features['primary_lead_return_15m'].values[3:], expected_15m_lead)
    
    # target_relative_strength_to_primary_15m
    # target is ETH (0.05 per bar)
    # ETH 15m return = (1.05^3 - 1) = 0.157625
    expected_rs = 0.157625 - 0.331
    np.testing.assert_allclose(features['target_relative_strength_to_primary_15m'].values[3:], expected_rs)

def test_p5_missing_data_propagation():
    timestamps = pd.date_range("2022-01-01 00:00:00", periods=5, freq="5min").astype(int) // 10**6
    symbols = ["BTCUSDT", "ETHUSDT"]
    dfs = {}
    
    # Missing data in ETH
    dfs["BTCUSDT"] = pd.DataFrame({"timestamp": timestamps, "close": [10, 20, 30, 40, 50]})
    dfs["ETHUSDT"] = pd.DataFrame({"timestamp": timestamps, "close": [10, np.nan, 30, 40, 50]})
    
    # Target BTC, leader ETH
    features = generate_p5_features("BTCUSDT", dfs)
    
    # Return at index 1 involves C_1 / C_0 - 1 = nan / 10 - 1 = nan
    # Return at index 2 involves C_2 / C_1 - 1 = 30 / nan - 1 = nan
    # Return at index 3 involves C_3 / C_2 - 1 = 40 / 30 - 1 = 0.333
    lead_5m = features['primary_lead_return_5m'].values
    assert np.isnan(lead_5m[0])
    assert np.isnan(lead_5m[1])
    assert np.isnan(lead_5m[2])
    assert not np.isnan(lead_5m[3])
    
    # Target ETH, leader BTC (cross_asset metrics)
    features_eth = generate_p5_features("ETHUSDT", dfs)
    cross_median = features_eth['cross_asset_median_return_5m'].values
    assert np.isnan(cross_median[0])
    # BTC return is 20/10 - 1 = 1.0. It's the only other asset, so median is 1.0.
    assert cross_median[1] == 1.0 

def test_p5_deterministic_repeatability(mock_universe):
    run1 = generate_p5_features("BTCUSDT", mock_universe)
    run2 = generate_p5_features("BTCUSDT", mock_universe)
    pd.testing.assert_frame_equal(run1, run2)
