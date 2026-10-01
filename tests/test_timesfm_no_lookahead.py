"""
Verification of strict causality and zero future lookahead.
Constructs a synthetic timeline with known injected future anomalies at t > T
and proves that the forecast feature builder and model context cannot access them.
"""

import numpy as np
import pytest

from control_plane.forecast_service import TimesFMFeatureBuilder, STATUS_INSUFFICIENT_DATA


def test_zero_future_lookahead_synthetic_timeline():
    # Construct synthetic candles with 100 historical bars before cutoff T,
    # and 50 future bars after cutoff T with massive injected anomalies (e.g. price 999999.0)
    cutoff_ts = 1700000000000  # T
    step_ms = 60000  # 1m

    candles = []
    # 100 historical candles: 100.0 to 199.0
    for i in range(100):
        ts = cutoff_ts - (100 - i) * step_ms
        candles.append({
            "ts": ts,
            "open": float(100.0 + i),
            "high": float(101.0 + i),
            "low": float(99.0 + i),
            "close": float(100.5 + i),
            "volume": 10.0 + i,
            "vwap": 100.2 + i
        })

    # Future candles at t > T with massive known anomalies
    FUTURE_ANOMALY_PRICE = 999999.0
    FUTURE_ANOMALY_VOLUME = 888888.0
    for i in range(1, 51):
        ts = cutoff_ts + i * step_ms
        candles.append({
            "ts": ts,
            "open": FUTURE_ANOMALY_PRICE,
            "high": FUTURE_ANOMALY_PRICE + 100,
            "low": FUTURE_ANOMALY_PRICE - 100,
            "close": FUTURE_ANOMALY_PRICE,
            "volume": FUTURE_ANOMALY_VOLUME,
            "vwap": FUTURE_ANOMALY_PRICE
        })

    # Shuffle the input order to prove the builder sorts and filters causally
    import random
    shuffled_candles = candles.copy()
    random.seed(42)
    random.shuffle(shuffled_candles)

    # Build context at exact cutoff T
    context_arr, past_covs, fut_covs, latest_data_ts, freshness = TimesFMFeatureBuilder.build_context(
        candles=shuffled_candles,
        forecast_ts=cutoff_ts,
        context_len=128,
        min_context_len=32
    )

    # Invariants:
    # 1. Latest data timestamp must be <= cutoff_ts
    assert latest_data_ts <= cutoff_ts, f"Latest data ts {latest_data_ts} leaked past cutoff {cutoff_ts}"
    assert latest_data_ts == cutoff_ts - step_ms

    # 2. None of the future anomaly prices or volumes must exist in context
    assert FUTURE_ANOMALY_PRICE not in context_arr
    assert np.all(context_arr < 1000.0), f"Future anomaly price leaked into context: max context value {np.max(context_arr)}"

    # 3. None of the past_only covariates should contain the future volume anomaly
    if past_covs is not None:
        assert FUTURE_ANOMALY_VOLUME not in past_covs
        assert np.all(past_covs[:, 0] < 1000.0), "Future volume anomaly leaked into past_only covariates!"

    # 4. Context length must strictly equal the number of available pre-cutoff bars (100)
    assert len(context_arr) == 100


def test_no_data_at_future_timestamp_returns_insufficient_data():
    # If all candles are strictly in the future (ts > forecast_ts), builder must reject
    cutoff_ts = 1700000000000
    future_candles = [
        {"ts": cutoff_ts + 60000 * i, "close": 200.0, "volume": 10.0}
        for i in range(1, 50)
    ]

    context_arr, past_covs, fut_covs, latest_data_ts, freshness = TimesFMFeatureBuilder.build_context(
        candles=future_candles,
        forecast_ts=cutoff_ts,
        context_len=64,
        min_context_len=32
    )

    assert len(context_arr) == 0
    assert freshness == STATUS_INSUFFICIENT_DATA
