import pytest
import pandas as pd
import numpy as np
import time

from institutional.institutional_math import InstitutionalMathEngine
from institutional.types import DataQuality
from institutional.data.models import MarketDataSnapshot, OHLCVBar

@pytest.fixture
def sample_df():
    # 500 rows to satisfy the normalization window
    dates = pd.date_range("2024-01-01", periods=500, freq="1min")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": np.linspace(100, 200, 500),
        "high": np.linspace(101, 201, 500),
        "low": np.linspace(99, 199, 500),
        "close": np.linspace(100.5, 200.5, 500),
        "volume": np.ones(500) * 10
    })
    return df

@pytest.fixture
def flat_df():
    # Zero variance dataframe
    dates = pd.date_range("2024-01-01", periods=500, freq="1min")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 10.0
    })
    return df

def test_engine_initializes():
    engine = InstitutionalMathEngine(normalization_window=100)
    assert engine is not None

def test_insufficient_data():
    engine = InstitutionalMathEngine(normalization_window=500)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, 100, 10, "TEST") for i in range(50)]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars)
    state = engine.analyze(snapshot)
    assert state.data_quality == DataQuality.INSUFFICIENT_DATA

def test_engine_runs_successfully(sample_df):
    engine = InstitutionalMathEngine(normalization_window=100)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, row["close"], 10, "TEST") for i, row in sample_df.iterrows()]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars)
    state = engine.analyze(snapshot)
    assert state.data_quality == DataQuality.VALID
    assert state.volatility_score is not None

def test_zero_variance_handles_gracefully(flat_df):
    engine = InstitutionalMathEngine(normalization_window=100)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, row["close"], 10, "TEST") for i, row in flat_df.iterrows()]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars)
    state = engine.analyze(snapshot)
    assert state.data_quality == DataQuality.VALID

def test_semantic_defaults_are_none(sample_df):
    engine = InstitutionalMathEngine(normalization_window=100)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, row["close"], 10, "TEST") for i, row in sample_df.iterrows()]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars)
    state = engine.analyze(snapshot)
    
    # 1. unavailable direction probability is None
    assert state.direction_probability is None
    # 2. unavailable structural break is None
    assert state.structural_break is None
    # 3. unavailable HMM probability is None
    assert state.regime_probability is None
    
    # 5. no >0.6 bullish classification exists in Institutional Math
    # 6. math engine does not emit BUY / SELL
    assert state.direction not in ["BULLISH", "BEARISH", "BUY", "SELL"]
    assert state.direction == "UNKNOWN"

def test_unavailable_external_data(sample_df):
    engine = InstitutionalMathEngine(normalization_window=100)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, row["close"], 10, "TEST") for i, row in sample_df.iterrows()]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars, order_book=None)
    state = engine.analyze(snapshot)
    
    # 4. unavailable external market data does not become zero
    assert state.liquidity_state == "UNAVAILABLE"
    assert state.order_flow_state == "UNAVAILABLE"

def test_freshness_semantics(sample_df):
    engine = InstitutionalMathEngine(normalization_window=100)
    bars = [OHLCVBar("BTC-USDT", i, 100, 100, 100, row["close"], 10, "TEST") for i, row in sample_df.iterrows()]
    snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "1m", ohlcv=bars)
    state = engine.analyze(snapshot)
    
    # 9. stale data is explicitly marked
    assert state.slow_path_freshness == "UNAVAILABLE"
    assert state.slow_path_calculated_at is None

def test_canonical_reference_values():
    from institutional.volatility import calculate_realized_volatility
    
    # RV Test
    df_rv = pd.DataFrame({"close": [100, 101, 98.98, 100.4647, 99.962]})
    # Log returns:
    # ln(101/100) = 0.00995033
    # ln(98.98/101) = -0.02020271
    # ln(100.4647/98.98) = 0.01488825
    # ln(99.962/100.4647) = -0.00501625
    rv = calculate_realized_volatility(df_rv, window=4).iloc[-1]
    expected_rv = np.sqrt(0.00995033**2 + (-0.02020271)**2 + 0.01488825**2 + (-0.00501625)**2)
    assert np.isclose(rv, expected_rv, atol=1e-5)
