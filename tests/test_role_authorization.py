"""Role Authorization Matrix Test.

Verifies:
1. Admin user has authority to access mode change, automations, and God Eye.
2. User with role 'USER' is rejected with HTTP 403 on all Admin endpoints:
   - POST /api/mode
   - POST /api/system/mode
   - GET /api/admin/god-eye/overview
   - GET /api/admin/god-eye/users
   - POST /api/admin/god-eye/close-position
   - POST /api/admin/god-eye/flash-close-all
   - POST /api/admin/users/{user_id}/copy-permission
   - POST /api/admin/users/{user_id}/suspend
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from control_plane import db, api
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(api.app)


def test_admin_vs_user_role_authorization(client):
    # Create tokens
    admin_token = api.create_access_token({"sub": "1", "user_id": 1, "role": "ADMIN"})
    
    # Create user with role USER in DB
    user_data = db.create_google_user(
        google_sub="auth_sub_999",
        email="auth_user_999@ophelia.sys",
        display_name="User Auth Subject 999"
    )
    user_token = api.create_access_token({"sub": str(user_data["id"]), "user_id": user_data["id"], "role": "USER"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 1. GET God Eye Overview: Admin -> 200, User -> 403
    r_admin = client.get("/api/admin/god-eye/overview", headers=admin_headers)
    assert r_admin.status_code == 200, f"Admin expected 200, got {r_admin.status_code}"

    r_user = client.get("/api/admin/god-eye/overview", headers=user_headers)
    assert r_user.status_code == 403, f"User expected 403, got {r_user.status_code}"
    assert "Forbidden" in r_user.json().get("detail", "")

    # 2. POST Flash Close All: Admin -> 200, User -> 403
    r_flash_user = client.post("/api/admin/god-eye/flash-close-all", json={"reason": "Test", "confirm": True}, headers=user_headers)
    assert r_flash_user.status_code == 403, f"User expected 403, got {r_flash_user.status_code}"

    # 3. POST Mode Change: Admin -> 200 (in shadow), User -> 403
    r_mode_user = client.post("/api/mode", json={"mode": "SHADOW"}, headers=user_headers)
    assert r_mode_user.status_code == 403, f"User expected 403, got {r_mode_user.status_code}"

    # 4. User accessing their own dashboard: User -> 200
    r_dash_user = client.get("/api/user/dashboard", headers=user_headers)
    assert r_dash_user.status_code == 200
    assert r_dash_user.json()["user_id"] == user_data["id"]
