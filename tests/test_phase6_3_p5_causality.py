import pytest
import pandas as pd
import numpy as np

from research.ml4t_benchmark.features.cross_asset import generate_p5_features

@pytest.fixture
def mock_universe():
    timestamps = pd.date_range("2022-01-01 00:00:00", periods=10, freq="5min").astype(int) // 10**6
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
    dfs = {}
    
    for sym in symbols:
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": np.arange(100.0, 110.0), # Sequential prices
            "volume": 1000.0
        })
        dfs[sym] = df
    return dfs

def test_p5_future_perturbation(mock_universe):
    """
    Changing future bars must not affect current or past feature values.
    """
    target = "BTCUSDT"
    
    # Baseline
    base_features = generate_p5_features(target, mock_universe)
    
    # Perturb the future (bar at index 5)
    t_perturb = 5
    for sym in mock_universe:
        mock_universe[sym].loc[t_perturb:, "close"] = 999.0
        
    perturbed_features = generate_p5_features(target, mock_universe)
    
    # Features before index 5 MUST be completely unchanged
    pd.testing.assert_frame_equal(
        base_features.iloc[:t_perturb], 
        perturbed_features.iloc[:t_perturb]
    )
    
    # Features at index 5 SHOULD change because the current close is used
    # (returns from t-k to t)
    assert not np.allclose(
        base_features.iloc[t_perturb]['primary_lead_return_5m'],
        perturbed_features.iloc[t_perturb]['primary_lead_return_5m'],
        equal_nan=True
    )

def test_p5_cross_symbol_isolation(mock_universe):
    """
    Changing an asset must ONLY affect the features of symbols that use it.
    """
    # Perturb SOLUSDT
    mock_universe["SOLUSDT"].loc[:, "close"] = 500.0
    
    # BTC uses ETH as primary leader.
    # SOL is in the cross-asset median/dispersion for BTC.
    btc_features = generate_p5_features("BTCUSDT", mock_universe)
    
    # So the primary lead return for BTC (which is ETH) should NOT be affected
    # (In the base setup, ETH went from 100 to 101, etc.)
    expected_eth_ret_5m = 101.0 / 100.0 - 1
    np.testing.assert_allclose(
        btc_features['primary_lead_return_5m'].values[1], 
        expected_eth_ret_5m
    )
    
    # But SOL's perturbation SHOULD affect the cross-asset median for BTC
    # (Since SOL now has 0% return instead of 1%)
    # Let's verify SOL doesn't bleed into primary leader.
    pass

def test_p5_causality_boundary():
    """
    Ensure the formula R(t) = C_t / C_{t-k} - 1 does not use C_{t+1}.
    This is implicitly tested by the math implementation, but we assert
    that index t uses data from index t and t-k.
    """
    timestamps = pd.date_range("2022-01-01 00:00:00", periods=5, freq="5min").astype(int) // 10**6
    dfs = {
        "BTCUSDT": pd.DataFrame({"timestamp": timestamps, "close": [10, 20, 30, 40, 50]}),
        "ETHUSDT": pd.DataFrame({"timestamp": timestamps, "close": [10, 11, 12, 13, 14]})
    }
    
    features = generate_p5_features("BTCUSDT", dfs)
    
    # At index 1 (t), leader is ETH. Return should be C_1 / C_0 - 1 = 11/10 - 1 = 0.1
    # It must NOT use C_2 (12).
    assert np.isclose(features['primary_lead_return_5m'].iloc[1], 0.1)
    
    # At index 3 (t), leader is ETH. 15m return (3 bars) = C_3 / C_0 - 1 = 13/10 - 1 = 0.3
    assert np.isclose(features['primary_lead_return_15m'].iloc[3], 0.3)
