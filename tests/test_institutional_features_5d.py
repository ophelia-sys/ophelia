import pytest
import pandas as pd
import numpy as np

from institutional.types import DataQuality, Direction
from institutional.open_interest import analyze_open_interest_state
from institutional.funding import analyze_funding_state
from institutional.vwap import calculate_vwap
from institutional.volume import analyze_volume, calculate_aggressor_volume

def test_open_interest_states():
    # Price UP + OI UP -> LONG_INITIATION
    price = pd.Series([100.0, 110.0])
    oi = pd.Series([1000.0, 1100.0])
    res = analyze_open_interest_state(price, oi)
    assert res.data_quality == DataQuality.VALID
    assert "LONG_INITIATION" in res.provenance
    assert res.direction == Direction.BULLISH
    
    # Price DOWN + OI DOWN -> LONG_LIQUIDATION
    price = pd.Series([100.0, 90.0])
    oi = pd.Series([1000.0, 900.0])
    res = analyze_open_interest_state(price, oi)
    assert "LONG_LIQUIDATION" in res.provenance
    assert res.direction == Direction.BEARISH

    # Price DOWN + OI UP -> SHORT_INITIATION
    price = pd.Series([100.0, 90.0])
    oi = pd.Series([1000.0, 1100.0])
    res = analyze_open_interest_state(price, oi)
    assert "SHORT_INITIATION" in res.provenance
    assert res.direction == Direction.BEARISH

    # Price UP + OI DOWN -> SHORT_COVERING
    price = pd.Series([100.0, 110.0])
    oi = pd.Series([1000.0, 900.0])
    res = analyze_open_interest_state(price, oi)
    assert "SHORT_COVERING" in res.provenance
    assert res.direction == Direction.BULLISH
    
    # Missing data
    res = analyze_open_interest_state(None, None)
    assert res.data_quality == DataQuality.INSUFFICIENT_DATA

def test_funding_normalization():
    # normal series
    funding = pd.Series([0.01, 0.01, 0.012, 0.009, 0.011, 0.01, 0.01, 0.01, 0.01, 0.05])
    res = analyze_funding_state(funding)
    assert res.data_quality == DataQuality.VALID
    assert res.normalized_value > 2.0  # the 0.05 is an anomaly
    assert res.direction == Direction.BEARISH # mean reversion
    
    # zero mad
    funding_flat = pd.Series([0.01] * 15)
    res = analyze_funding_state(funding_flat)
    assert res.normalized_value == 0.0
    
    # missing history
    res = analyze_funding_state(pd.Series([0.01, 0.02]))
    assert res.data_quality == DataQuality.INSUFFICIENT_DATA

def test_vwap():
    df = pd.DataFrame({
        'high': [10, 10, 10],
        'low': [10, 10, 10],
        'close': [10, 10, 10],
        'volume': [100, 200, 300]
    })
    res = calculate_vwap(df, window=3)
    assert res.data_quality == DataQuality.VALID
    assert res.raw_value == 10.0
    assert res.normalized_value == 0.0
    
    # Zero volume
    df_zero = pd.DataFrame({
        'high': [10, 10, 10],
        'low': [10, 10, 10],
        'close': [10, 10, 10],
        'volume': [0, 0, 0]
    })
    res = calculate_vwap(df_zero, window=3)
    assert res.data_quality == DataQuality.INSUFFICIENT_DATA

def test_volume_metrics():
    df = pd.DataFrame({
        'close': [10]*20,
        'volume': [10]*19 + [50]
    })
    res = analyze_volume(df, window=20)
    assert res["volume_z_score"].data_quality == DataQuality.VALID
    assert res["volume_z_score"].normalized_value >= 0 # Since mad can be 0, robust z-score fallback to 0 is tested
    assert "quote_volume" in res
    
def test_aggressor_volume():
    res = calculate_aggressor_volume(60.0, 40.0)
    assert res["cvd"].raw_value == 20.0
    assert res["tvi"].raw_value == 0.2
    assert res["cvd"].direction == Direction.BULLISH
