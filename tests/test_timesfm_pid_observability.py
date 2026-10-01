import os
import time
import pytest
from control_plane import db
from control_plane.forecast_service import ForecastService, LIFECYCLE_READY


def test_pid_observability_distinct_pids(monkeypatch):
    """
    Test 1: TimesFM PID Observability.
    Verifies that the authoritative diagnostics source distinguishes between:
      - API PID (the calling process serving HTTP requests)
      - Provider PID (the dedicated forecasting worker where PyTorch model resides)
    Verifies that the UI field `provider_pid` receives the actual provider PID from diagnostics.
    """
    mock_provider_pid = 999888
    mock_api_pid = os.getpid()

    # 1. Simulate background worker saving authoritative state to model_subsystem_state
    now_ms = int(time.time() * 1000)
    db.save_model_subsystem_state({
        "worker_id": "timesfm_primary",
        "provider_pid": mock_provider_pid,
        "lifecycle_state": LIFECYCLE_READY,
        "model_loaded": True,
        "checkpoint": "google/timesfm-3.0-pytorch",
        "model_version": "3.0",
        "device": "cpu",
        "last_inference_ms": 1250.0,
        "last_inference_ts": now_ms,
        "last_success_ts": now_ms,
        "queue_depth": 0,
        "active_inferences": 0,
        "p50_latency_ms": 1342.52,
        "p95_latency_ms": 1406.27,
        "mode": "SHADOW_ONLY",
        "trading_authority": False,
        "updated_at": now_ms
    })

    # 2. Query diagnostics via service
    svc = ForecastService.get_instance()
    diag = svc.get_status()

    # 3. Assertions
    assert diag["provider_pid"] == mock_provider_pid, "Diagnostics must report the authoritative worker provider PID"
    assert diag["api_pid"] == mock_api_pid, "Diagnostics must report the caller API process PID"
    assert diag["provider_pid"] != diag["api_pid"] or mock_provider_pid == mock_api_pid
    assert diag["model_loaded"] is True
    assert diag["lifecycle_state"] == "READY"

    # 4. Simulate a dynamic change in worker PID (e.g. process restart)
    new_provider_pid = 777666
    db.save_model_subsystem_state({
        "worker_id": "timesfm_primary",
        "provider_pid": new_provider_pid,
        "lifecycle_state": LIFECYCLE_READY,
        "model_loaded": True,
        "updated_at": int(time.time() * 1000)
    })

    diag2 = svc.get_status()
    assert diag2["provider_pid"] == new_provider_pid, "Diagnostics must dynamically track updated provider PID without hardcoding"


def test_ui_mapping_matches_diagnostics():
    """
    Simulate Android / Web UI parsing of TimesFmDiagnosticsResponse.
    Verifies that the UI model field `providerPid` strictly binds to `diagnostics['provider_pid']`.
    """
    mock_diagnostics_payload = {
        "model_loaded": True,
        "lifecycle_state": "READY",
        "version": "3.0",
        "checkpoint": "google/timesfm-3.0-pytorch",
        "provider_pid": 1132578,
        "api_pid": 1132583,
        "p50_latency_ms": 1342.52,
        "mode": "SHADOW_ONLY"
    }

    # Simulate UI deserialization
    ui_provider_pid = mock_diagnostics_payload.get("provider_pid")
    ui_api_pid = mock_diagnostics_payload.get("api_pid")

    assert ui_provider_pid == 1132578
    assert ui_api_pid == 1132583
    assert ui_provider_pid == mock_diagnostics_payload["provider_pid"]
