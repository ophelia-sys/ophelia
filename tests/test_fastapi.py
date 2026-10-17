import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from control_plane.api import app, create_access_token

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_protected_routes_without_token():
    response = client.get("/api/market/watchlist")
    assert response.status_code in (401, 403)

def test_automation_creation_schema(monkeypatch):
    # We just want to check if Pydantic accepts our schema
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "strategy": "BOTH",
        "symbol_scope": {
            "mode": "SINGLE",
            "symbols": ["BTC-USDT"]
        },
        "strategy_timeframes": {
            "VWAP_SUPERTREND": 3,
            "EMA_CROSSOVER": 1
        },
        "margin_usage_pct": 45.0,
        "leverage": 15.0,
        "mode": "SHADOW",
        "strategy_risk": {
            "VWAP_SUPERTREND": {"stops": [{"type": "hard_pct", "value": 1.0}]}
        },
        "targets": [{"type": "trailing", "pct": 100.0}]
    }
    
    # Mock db/core logic so we just test routing/validation
    import control_plane.core as core
    import control_plane.db as db
    monkeypatch.setattr(core, "build_proposal", lambda spec: {"prop": True})
    monkeypatch.setattr(db, "create_automation", lambda spec, user_id: 999)
    
    response = client.post("/api/automations", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["automation_id"] == 999
    assert "proposal" in data

def test_position_edit_schema(monkeypatch):
    import control_plane.db as db
    monkeypatch.setattr(db, "get_position", lambda pid, user_id=1: {"id": pid, "symbol": "BTC-USDT", "status": "OPEN", "user_id": user_id, "stops": [], "targets": []})
    monkeypatch.setattr(db, "update_position", lambda *a, **kw: True)
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "hard_stop_pct": 1.5,
        "structural_stop_type": "VWAP",
        "structural_buffer_pct": 0.2
    }
    
    response = client.post("/api/positions/123/edit", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_mode_toggle_schema(monkeypatch):
    import control_plane.core as core
    import control_plane.db as db
    monkeypatch.setattr(core, "run_preflight", lambda user_id=1: {"ready_for_live": True, "checklist": [], "blocking_reasons": []})
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "target": "ACCOUNT",
        "target_id": 1,
        "mode": "LIVE"
    }
    
    try:
        response = client.post("/api/mode", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["mode"] == "LIVE"
        assert response.json()["target"] == "ACCOUNT"
    finally:
        db.set_mode("SHADOW")


def test_simulate_endpoint(monkeypatch):
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "strategy": "VWAP_SUPERTREND",
        "symbol": "BTC-USDT",
        "timeframe": "3m",
        "direction": "ANY",
        "vwap_gate_enabled": True
    }
    
    response = client.post("/api/automations/simulate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("OK", "SUCCESS")
    assert data["strategy"] in ("VWAP_SUPERTREND", "CURRENT_BASELINE")
    assert "signals_count" in data
    assert "simulated_trades_count" in data


def test_world_context_endpoint():
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/world/context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "feed_status" in data or "world" in data or "macro" in data or "sentiment" in data


def test_live_readiness_and_mode_endpoints(monkeypatch):
    import control_plane.core as core
    import control_plane.db as db
    monkeypatch.setattr(core, "run_preflight", lambda user_id=1: {"ready_for_live": True, "checklist": [], "blocking_reasons": []})
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check readiness
    res_ready = client.get("/api/system/live-readiness", headers=headers)
    assert res_ready.status_code == 200
    assert res_ready.json().get("ready_for_live") is True

    # Check mode
    res_mode = client.get("/api/mode", headers=headers)
    assert res_mode.status_code == 200
    assert "mode" in res_mode.json()
    assert "execution_gate" in res_mode.json()


def test_notifications_clear_endpoint(monkeypatch):
    token = create_access_token({"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/notifications/clear", headers=headers)
    assert response.status_code == 200
    assert response.json().get("success") is True


