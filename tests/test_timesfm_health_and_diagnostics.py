"""
Verification of authoritative TimesFM health check and diagnostics state transitions.
Validates:
- Explicit lifecycle states: UNINITIALIZED, LOADING, READY, DEGRADED, ERROR, STOPPED
- Health check verification of checkpoint, model version, schema, and monotonic quantiles
- Cross-process state synchronization via model_subsystem_state database table
"""

import os
import time
import pytest
import numpy as np

from control_plane import db
from control_plane.forecast_service import (
    ForecastService,
    TimesFMProvider,
    StatisticalBaselineProvider,
    LIFECYCLE_UNINITIALIZED,
    LIFECYCLE_LOADING,
    LIFECYCLE_READY,
    LIFECYCLE_DEGRADED,
    LIFECYCLE_ERROR,
    LIFECYCLE_STOPPED,
    TIMESFM_CHECKPOINT,
    TIMESFM_MODEL_VERSION
)


def test_provider_health_check_success_and_lifecycle():
    provider = TimesFMProvider(checkpoint=TIMESFM_CHECKPOINT)
    assert provider.lifecycle_state == LIFECYCLE_UNINITIALIZED

    # Mock the internal model to simulate successful weights and inference
    class FakeOutput:
        def __init__(self, horizon):
            self.forecast = np.array([50000.0 + i for i in range(horizon)], dtype=np.float32)
            # Shape (1, horizon, 3) for q10, q50, q90
            q = np.zeros((1, horizon, 3), dtype=np.float32)
            for i in range(horizon):
                q[0, i, 0] = 49000.0 + i  # q10
                q[0, i, 1] = 50000.0 + i  # q50
                q[0, i, 2] = 51000.0 + i  # q90
            self.quantiles = q

    class FakeTimesFMModel:
        def predict(self, context, horizon, return_quantiles=True, sort_quantiles=True):
            return FakeOutput(horizon)

    provider.model = FakeTimesFMModel()
    
    # Run health check
    res = provider.run_health_check()
    assert res["status"] == "HEALTHY"
    assert provider.lifecycle_state == LIFECYCLE_READY
    assert provider.last_health_check_status == "HEALTHY"
    assert provider.last_success_ts is not None

    # Check persisted state in SQLite
    state = db.get_model_subsystem_state("timesfm_primary")
    assert state is not None
    assert state["lifecycle_state"] == LIFECYCLE_READY
    assert state["model_loaded"] is True
    assert state["checkpoint"] == TIMESFM_CHECKPOINT
    assert state["model_version"] == TIMESFM_MODEL_VERSION
    assert state["provider_pid"] == os.getpid()


def test_provider_health_check_failure_simulation():
    provider = TimesFMProvider(checkpoint=TIMESFM_CHECKPOINT)

    # Simulate inference crash during health check
    class BrokenTimesFMModel:
        def predict(self, context, horizon, return_quantiles=True, sort_quantiles=True):
            raise RuntimeError("CUDA device out of memory during health probe")

    provider.model = BrokenTimesFMModel()

    res = provider.run_health_check()
    assert res["status"] == "UNHEALTHY"
    assert "CUDA device out of memory" in res["error"]
    assert provider.lifecycle_state == LIFECYCLE_ERROR

    # Check that error state is persisted to database
    state = db.get_model_subsystem_state("timesfm_primary")
    assert state is not None
    assert state["lifecycle_state"] == LIFECYCLE_ERROR
    assert state["model_loaded"] is False
    assert "CUDA device out of memory" in state["last_error"]


def test_forecast_service_diagnostics_fields():
    svc = ForecastService()
    status = svc.get_status()

    # Mandatory diagnostics fields per requirement Item 1
    assert "model_loaded" in status
    assert "lifecycle_state" in status
    assert "checkpoint" in status
    assert "version" in status
    assert "provider_pid" in status
    assert "last_inference_ts" in status
    assert "last_success_timestamp" in status
    assert "last_error" in status
    assert "queue_depth" in status
    assert "active_inferences" in status
    assert "cached_forecasts" in status
    assert status["trading_authority"] is False
    assert status["mode"] == "SHADOW_ONLY"

    # Resource telemetry fields per requirement Item 1 & 3
    assert "system_ram_total_mb" in status
    assert "system_ram_available_mb" in status
    assert "system_ram_used_pct" in status
    assert "system_swap_used_mb" in status
    assert "system_cpu_pct" in status
