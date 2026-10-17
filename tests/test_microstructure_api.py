"""Tests for Phase 6A Microstructure API endpoints."""
import pytest
from fastapi.testclient import TestClient
from control_plane.api import app, create_access_token
from control_plane import db


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_microstructure_endpoints_auth():
    client = TestClient(app)

    # 1. Unauthenticated requests fail with 401
    resp1 = client.get("/api/microstructure/trade-flow?instrument=BTC-USDT")
    assert resp1.status_code in (401, 403)

    resp2 = client.get("/api/microstructure/trade-duration?instrument=BTC-USDT")
    assert resp2.status_code in (401, 403)

    resp3 = client.get("/api/microstructure/summary?instrument=BTC-USDT")
    assert resp3.status_code in (401, 403)

    # 2. Authenticated user request succeeds
    admin = db.get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    summary_resp = client.get("/api/microstructure/summary?instrument=BTC-USDT", headers=headers)
    assert summary_resp.status_code == 200
    data = summary_resp.json()
    assert data["instrument"] == "BTC-USDT"
    assert data["mode"] == "RESEARCH"
    assert data["methodology_version"] == "1.0.0"
    assert "trade_flow" in data
    assert "trade_duration" in data

    flow_resp = client.get("/api/microstructure/trade-flow?instrument=BTC-USDT", headers=headers)
    assert flow_resp.status_code == 200
    flow_data = flow_resp.json()
    assert flow_data["mode"] == "RESEARCH"
    assert "signed_flow" in flow_data
    assert "flow_innovation" in flow_data
    assert "flow_zscore" in flow_data
    assert "quality_state" in flow_data
    assert "freshness_state" in flow_data

    dur_resp = client.get("/api/microstructure/trade-duration?instrument=BTC-USDT", headers=headers)
    assert dur_resp.status_code == 200
    dur_data = dur_resp.json()
    assert dur_data["mode"] == "RESEARCH"
    assert "duration_ms" in dur_data
    assert "arrival_intensity" in dur_data
    assert "duration_pressure" in dur_data
