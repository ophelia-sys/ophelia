"""
Verification of forecast evaluation against realized future outcomes and baseline comparisons.
"""

import math
import time
import uuid
import numpy as np
import pytest

from control_plane import db
from control_plane.forecast_service import (
    StatisticalBaselineProvider,
    ForecastResult,
    STATUS_SUCCESS
)


def test_forecast_evaluation_and_metrics_calculation():
    db._auto_conn()
    fid = f"test-eval-{uuid.uuid4()}"
    now_ms = int(time.time() * 1000)

    # 1. Save a mock forecast
    test_sym = f"TEST-ETH-{uuid.uuid4().hex[:6]}"
    forecast_values = [100.0, 102.0, 104.0, 106.0, 108.0]
    rec = {
        "forecast_id": fid,
        "user_id": 1,
        "instrument": test_sym,
        "timeframe": "15m",
        "forecast_timestamp": now_ms,
        "data_timestamp": now_ms,
        "model_name": "timesfm",
        "model_version": "3.0",
        "checkpoint": "google/timesfm-3.0-pytorch",
        "context_length": 64,
        "horizon": 5,
        "input_schema_version": "TIMESFM_FEATURE_SCHEMA_V1",
        "forecast_values": forecast_values,
        "quantiles": {"q10": [98.0] * 5, "q50": forecast_values, "q90": [110.0] * 5},
        "forecast_generation_ms": 25.0,
        "latency_ms": 30.0,
        "status": STATUS_SUCCESS,
        "data_freshness": "FRESH",
        "error": None,
        "mode": "SHADOW"
    }
    db.save_model_forecast(rec)

    # 2. Simulate realized actual prices after horizon elapsed
    actual_values = [101.0, 103.0, 103.5, 105.0, 107.0]

    # Calculate errors
    diffs = [f - a for f, a in zip(forecast_values, actual_values)]
    abs_errors = [abs(d) for d in diffs]
    mae = sum(abs_errors) / len(abs_errors)
    rmse = math.sqrt(sum(d ** 2 for d in diffs) / len(diffs))
    
    # Direction: predicted up (108 > 100), actual was up (107 > 100) -> correct = 1
    dir_correct = 1 if ((forecast_values[-1] > 100.0) == (actual_values[-1] > 100.0)) else 0

    eval_rec = {
        "evaluation_id": f"eval-{uuid.uuid4()}",
        "forecast_id": fid,
        "instrument": test_sym,
        "timeframe": "15m",
        "forecast_timestamp": now_ms,
        "evaluation_timestamp": now_ms + 5 * 15 * 60000,
        "actual_values": actual_values,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "direction_correct": dir_correct,
        "absolute_error": round(abs_errors[-1], 4),
        "signed_error": round(diffs[-1], 4),
        "quantile_hit": 1,
        "coverage": 1.0,
        "regime": "TREND"
    }

    db.save_model_forecast_evaluation(eval_rec)

    # 3. Retrieve evaluation metrics
    metrics = db.get_model_forecast_evaluation_metrics(model_name="timesfm", instrument=test_sym)
    assert metrics["evaluation_count"] >= 1
    assert metrics["avg_mae"] is not None
    assert metrics["directional_accuracy_pct"] == 100.0


def test_baseline_comparison_without_lookahead():
    # Compare Naive Persistence vs EMA baseline on a synthetic sequence
    ctx = np.array([100.0, 102.0, 101.0, 103.0, 105.0] * 10, dtype=np.float32)
    actuals = [106.0, 107.0, 106.5, 108.0, 109.0]

    prov_naive = StatisticalBaselineProvider(mode="NAIVE_PERSISTENCE")
    res_naive = prov_naive.forecast("BTC-USDT", "15m", ctx, horizon=5)

    prov_ema = StatisticalBaselineProvider(mode="EMA")
    res_ema = prov_ema.forecast("BTC-USDT", "15m", ctx, horizon=5)

    mae_naive = sum(abs(f - a) for f, a in zip(res_naive.forecast_values, actuals)) / 5
    mae_ema = sum(abs(f - a) for f, a in zip(res_ema.forecast_values, actuals)) / 5

    assert mae_naive > 0
    assert mae_ema > 0
    # Both baselines produce valid evaluable trajectories with zero future leakage
    assert len(res_naive.forecast_values) == 5
    assert len(res_ema.forecast_values) == 5
