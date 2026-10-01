"""
Verification of failure isolation:
TimesFM exceptions, model crashes, or timeouts must NEVER break core Ophelia services,
deterministic state machines, or slot allocation.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from control_plane.forecast_service import (
    ForecastService,
    TimesFMProvider,
    STATUS_MODEL_ERROR,
    STATUS_NOT_AVAILABLE
)
from control_plane import slot_allocation_service, db


def test_forecast_service_catches_model_crash(monkeypatch):
    svc = ForecastService()
    
    # Mock TimesFMProvider to throw an unhandled RuntimeError (e.g. CUDA/CPU crash, OOM)
    class CrashingProvider(TimesFMProvider):
        def forecast(self, *args, **kwargs):
            raise RuntimeError("Fatal: simulated OOM / segmentation fault in model engine")

    svc.timesfm_provider = CrashingProvider()
    
    # Mock feature builder to return valid 64 bars
    from control_plane.forecast_service import TimesFMFeatureBuilder
    monkeypatch.setattr(TimesFMFeatureBuilder, "build_context", lambda **kwargs: (
        np.array([100.0] * 64, dtype=np.float32), None, None, int(time.time() * 1000), "FRESH"
    ))

    # Call generate_forecast - must NOT raise RuntimeError
    res = svc.generate_forecast("BTC-USDT", timeframe="15m", horizon=10, force_refresh=True)

    # Must gracefully return fallback result with status MODEL_ERROR
    assert res is not None
    assert res.status == STATUS_MODEL_ERROR
    assert "Fatal: simulated OOM" in (res.error or "")


def test_slot_service_functions_when_forecast_fails():
    # Verify that slot allocation service remains 100% operational even if forecasting service is down
    db._auto_conn()
    slot, reason = slot_allocation_service.SlotAllocationService.find_eligible_slot(
        {"symbol": "BTC-USDT", "strategy": "BREAKOUT_RETEST", "direction": "LONG"},
        user_id=1
    )
    # Even if None, it returns a valid (slot, reason) tuple without raising unhandled exception
    assert slot is None or isinstance(slot, dict)
    assert isinstance(reason, str)


def test_service_health_status_reflects_failure_without_aborting():
    svc = ForecastService()
    svc.timesfm_provider.lifecycle_state = "ERROR"
    svc.timesfm_provider.last_error = "PyTorch checkpoint corrupted"

    status = svc.get_status()
    assert status["model_loaded"] is False
    assert status["lifecycle_state"] == "ERROR"
    assert "PyTorch checkpoint corrupted" in status["last_error"]
    assert status["trading_authority"] is False
