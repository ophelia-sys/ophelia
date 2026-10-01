"""
Verification of forecast result schema and database persistence contract.
"""

import time
import uuid
import pytest

from control_plane import db
from control_plane.forecast_service import (
    ForecastResult,
    STATUS_SUCCESS,
    STATUS_STALE_INPUT,
    STATUS_INSUFFICIENT_DATA,
    STATUS_MODEL_ERROR,
    STATUS_TIMEOUT,
    STATUS_NOT_AVAILABLE,
    TIMESFM_CHECKPOINT,
    TIMESFM_MODEL_VERSION,
    FEATURE_SCHEMA_VERSION
)


def test_forecast_result_contract_fields_and_persistence():
    db._auto_conn()
    fid = f"test-f-{uuid.uuid4()}"
    now_ms = int(time.time() * 1000)

    result = ForecastResult(
        forecast_id=fid,
        instrument="BTC-USDT",
        timeframe="15m",
        forecast_timestamp=now_ms,
        data_timestamp=now_ms - 60000,
        model_name="timesfm",
        model_version=TIMESFM_MODEL_VERSION,
        checkpoint=TIMESFM_CHECKPOINT,
        context_length=128,
        horizon=10,
        input_schema_version=FEATURE_SCHEMA_VERSION,
        forecast_values=[65000.0 + i * 50 for i in range(10)],
        quantiles={
            "q10": [64500.0 + i * 40 for i in range(10)],
            "q50": [65000.0 + i * 50 for i in range(10)],
            "q90": [65500.0 + i * 60 for i in range(10)]
        },
        forecast_generation_ms=123.4,
        latency_ms=130.2,
        status=STATUS_SUCCESS,
        data_freshness="FRESH",
        error=None,
        mode="SHADOW",
        user_id=1
    )

    # Convert to dict and verify all mandatory keys
    data = result.to_dict()
    required_keys = [
        "forecast_id", "user_id", "instrument", "timeframe", "forecast_timestamp",
        "data_timestamp", "model_name", "model_version", "checkpoint", "context_length",
        "horizon", "input_schema_version", "forecast_values", "quantiles",
        "forecast_generation_ms", "latency_ms", "status", "data_freshness", "error", "mode"
    ]
    for k in required_keys:
        assert k in data, f"Missing required contract field: {k}"

    # Persist to database
    db.save_model_forecast(data)

    # Retrieve and verify exact fields
    stored = db.get_model_forecast(fid)
    assert stored is not None
    assert stored["forecast_id"] == fid
    assert stored["instrument"] == "BTC-USDT"
    assert stored["timeframe"] == "15m"
    assert stored["status"] == STATUS_SUCCESS
    assert stored["mode"] == "SHADOW"
    assert len(stored["forecast_values"]) == 10
    assert "q10" in stored["quantiles"]
    assert stored["quantiles"]["q10"][0] == 64500.0


def test_allowed_status_codes():
    valid_statuses = {
        STATUS_SUCCESS,
        STATUS_STALE_INPUT,
        STATUS_INSUFFICIENT_DATA,
        STATUS_MODEL_ERROR,
        STATUS_TIMEOUT,
        STATUS_NOT_AVAILABLE
    }

    # Verify each status can be saved and retrieved without being replaced by 0 or invalid strings
    db._auto_conn()
    for st in valid_statuses:
        fid = f"test-st-{uuid.uuid4()}"
        res = ForecastResult(
            forecast_id=fid,
            instrument="ETH-USDT",
            timeframe="5m",
            forecast_timestamp=int(time.time() * 1000),
            data_timestamp=int(time.time() * 1000),
            model_name="timesfm",
            model_version=TIMESFM_MODEL_VERSION,
            checkpoint=TIMESFM_CHECKPOINT,
            context_length=64,
            horizon=5,
            input_schema_version=FEATURE_SCHEMA_VERSION,
            forecast_values=[],
            quantiles={},
            forecast_generation_ms=0.0,
            latency_ms=0.0,
            status=st,
            data_freshness="UNKNOWN",
            error=f"Testing status {st}"
        )
        db.save_model_forecast(res.to_dict())
        rec = db.get_model_forecast(fid)
        assert rec is not None
        assert rec["status"] == st
        assert rec["error"] == f"Testing status {st}"
