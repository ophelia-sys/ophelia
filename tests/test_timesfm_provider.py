"""
Unit tests for TimesFMProvider and ForecastProvider contracts.
"""

import time
import numpy as np
import pytest

from control_plane.forecast_service import (
    TimesFMProvider,
    StatisticalBaselineProvider,
    STATUS_SUCCESS,
    STATUS_INSUFFICIENT_DATA,
    TIMESFM_CHECKPOINT,
    TIMESFM_MODEL_VERSION
)


def test_baseline_provider_naive():
    prov = StatisticalBaselineProvider(mode="NAIVE_PERSISTENCE")
    context = np.array([100.0, 101.0, 102.0, 103.0, 104.0] * 10, dtype=np.float32)
    res = prov.forecast(
        instrument="BTC-USDT",
        timeframe="15m",
        context_series=context,
        horizon=10,
        forecast_ts=int(time.time() * 1000),
        data_ts=int(time.time() * 1000) - 60000,
        freshness="FRESH"
    )

    assert res.status == STATUS_SUCCESS
    assert res.model_name == "baseline_naive_persistence"
    assert len(res.forecast_values) == 10
    # Naive persistence projects the last price
    assert res.forecast_values[0] == pytest.approx(104.0, abs=0.01)
    assert "q10" in res.quantiles and "q50" in res.quantiles and "q90" in res.quantiles
    assert len(res.quantiles["q10"]) == 10
    # Enforce quantile monotonicity
    for i in range(10):
        assert res.quantiles["q10"][i] <= res.quantiles["q50"][i] <= res.quantiles["q90"][i]


def test_baseline_provider_insufficient_data():
    prov = StatisticalBaselineProvider(mode="NAIVE_PERSISTENCE")
    res = prov.forecast(
        instrument="BTC-USDT",
        timeframe="15m",
        context_series=np.array([]),
        horizon=10
    )
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert len(res.forecast_values) == 0


def test_timesfm_provider_insufficient_context():
    prov = TimesFMProvider(checkpoint=TIMESFM_CHECKPOINT)
    # Context with less than 32 elements must be rejected with INSUFFICIENT_DATA
    short_ctx = np.array([50000.0, 50100.0, 50200.0], dtype=np.float32)
    res = prov.forecast(
        instrument="BTC-USDT",
        timeframe="15m",
        context_series=short_ctx,
        horizon=10
    )
    assert res.status == STATUS_INSUFFICIENT_DATA
    assert "less than minimum 32" in res.error


def test_timesfm_quantile_monotonicity_fallback():
    # Test that if a mock model returns quantiles, monotonicity q10 <= q50 <= q90 is strictly validated
    prov = TimesFMProvider()
    
    class MockTimesFmOutput:
        def __init__(self):
            self.forecast = np.array([105.0] * 10, dtype=np.float32)
            # Invert quantiles intentionally to test monotonic sorting
            # q10 = 110 (higher), q50 = 105, q90 = 100 (lower)
            self.quantiles = np.array([[[110.0, 105.0, 100.0]] * 10], dtype=np.float32)

    class MockForecaster:
        def predict(self, **kwargs):
            return MockTimesFmOutput()

    prov.model = MockForecaster()
    ctx = np.linspace(100.0, 104.0, 64, dtype=np.float32)
    res = prov.forecast(
        instrument="ETH-USDT",
        timeframe="15m",
        context_series=ctx,
        horizon=10
    )
    assert res.status == STATUS_SUCCESS
    for i in range(10):
        # Must have been sorted so q10 <= q50 <= q90
        assert res.quantiles["q10"][i] <= res.quantiles["q50"][i] <= res.quantiles["q90"][i]
        assert res.quantiles["q10"][i] == pytest.approx(100.0, abs=0.01)
        assert res.quantiles["q90"][i] == pytest.approx(110.0, abs=0.01)
