"""
Verification of TimesFM API endpoints access control:
- Unauthenticated requests are rejected with 401.
- Regular authenticated Users cannot access system diagnostics (403 Forbidden).
- Regular authenticated Users can access forecasts and evaluations (200 OK).
- Authenticated Admins can access system diagnostics, forecasts, and evaluations (200 OK).
"""

import pytest
from fastapi.testclient import TestClient
from control_plane.api import app, create_access_token
from control_plane import db


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def setup_users():
    # Setup test admin and user
    db.ensure_root_admin()
    admin = db.get_user_by_id(1)
    
    # Create regular user if not exists
    user = db.get_user_by_id(2)
    if not user:
        user = db.create_google_user("google_sub_user_test", "testuser@ophelia.trade", "Test User")
    return {"admin": admin, "user": user}


def test_unauthenticated_requests_fail(client):
    r_diag = client.get("/api/timesfm/diagnostics")
    assert r_diag.status_code == 401

    r_fore = client.get("/api/timesfm/forecasts?instrument=BTC-USDT&timeframe=5m")
    assert r_fore.status_code == 401

    r_eval = client.get("/api/timesfm/evaluations")
    assert r_eval.status_code == 401


def test_authenticated_user_access_matrix(client, setup_users):
    user_id = setup_users["user"]["id"]
    user_token = create_access_token({"sub": str(user_id), "user_id": user_id, "role": "USER"})
    headers = {"Authorization": f"Bearer {user_token}"}

    # Diagnostics should be forbidden for regular users
    r_diag = client.get("/api/timesfm/diagnostics", headers=headers)
    assert r_diag.status_code == 403
    assert "Admin authority required" in r_diag.json()["detail"]

    # Forecasts endpoint should succeed for user
    r_fore = client.get("/api/timesfm/forecasts?instrument=BTC-USDT&timeframe=5m", headers=headers)
    assert r_fore.status_code == 200
    fore_json = r_fore.json()
    assert "forecast_id" in fore_json
    assert "instrument" in fore_json
    assert "quantiles" in fore_json
    assert fore_json["user_id"] == user_id

    # Evaluations endpoint should succeed for user
    r_eval = client.get("/api/timesfm/evaluations", headers=headers)
    assert r_eval.status_code == 200
    eval_json = r_eval.json()
    assert "status" in eval_json
    assert "sample_sufficiency" in eval_json


def test_authenticated_admin_access_matrix(client, setup_users):
    admin_id = setup_users["admin"]["id"]
    admin_token = create_access_token({"sub": str(admin_id), "user_id": admin_id, "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin must see full system diagnostics
    r_diag = client.get("/api/timesfm/diagnostics", headers=headers)
    assert r_diag.status_code == 200
    diag = r_diag.json()
    assert "model_loaded" in diag
    assert "lifecycle_state" in diag
    assert "system_ram_total_mb" in diag
    assert "system_swap_used_mb" in diag
    assert diag["mode"] == "SHADOW_ONLY"
    assert diag["trading_authority"] is False

    # Admin can access forecasts
    r_fore = client.get("/api/timesfm/forecasts?instrument=BTC-USDT&timeframe=5m", headers=headers)
    assert r_fore.status_code == 200

    # Admin can access evaluations
    r_eval = client.get("/api/timesfm/evaluations", headers=headers)
    assert r_eval.status_code == 200
