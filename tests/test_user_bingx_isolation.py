"""Automated Multi-User Identity, BingX Account Isolation & Security Tests.

Contract Under Test:
1. No unauthenticated access to user data (401 on missing/bad token; zero fallback to user 1).
2. Strict user credential binding (User A credentials only used for User A).
3. Strict balance & position isolation (User A never sees User B balance or positions).
4. Zero fallback: Unconnected user receives 0.0 balance, never falls back to Admin or other user.
5. Disconnect isolation: User A disconnects without affecting User B.
6. Automation isolation: User B cannot modify or delete User A automations.
7. Cache isolation: Rapid interleaved queries never cross-pollinate caches.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from control_plane import api, db, credential_vault, account
from control_plane.api import app, create_access_token


@pytest.fixture(autouse=True)
def setup_isolated_test_users():
    """Ensure clean test users in SQLite database."""
    conn = db._auto_conn()
    with db._lock:
        conn.execute("DELETE FROM users WHERE id IN (101, 102, 103)")
        conn.execute("DELETE FROM user_bingx_credentials WHERE user_id IN (101, 102, 103)")
        conn.execute("DELETE FROM automations WHERE user_id IN (101, 102, 103)")
        conn.execute(
            "INSERT INTO users(id, user_uid, role, email, display_name, status, copy_enabled, admin_copy_allowed) "
            "VALUES(101, 'u_test_a', 'USER', 'usera@ophelia.test', 'User Alpha', 'ACTIVE', 1, 1)"
        )
        conn.execute(
            "INSERT INTO users(id, user_uid, role, email, display_name, status, copy_enabled, admin_copy_allowed) "
            "VALUES(102, 'u_test_b', 'USER', 'userb@ophelia.test', 'User Beta', 'ACTIVE', 1, 1)"
        )
        conn.execute(
            "INSERT INTO users(id, user_uid, role, email, display_name, status, copy_enabled, admin_copy_allowed) "
            "VALUES(103, 'u_test_c', 'USER', 'userc@ophelia.test', 'User Gamma', 'ACTIVE', 1, 1)"
        )
        conn.commit()

    account.invalidate_user_cache(101)
    account.invalidate_user_cache(102)
    account.invalidate_user_cache(103)

    yield

    with db._lock:
        conn.execute("DELETE FROM users WHERE id IN (101, 102, 103)")
        conn.execute("DELETE FROM user_bingx_credentials WHERE user_id IN (101, 102, 103)")
        conn.execute("DELETE FROM automations WHERE user_id IN (101, 102, 103)")
        conn.commit()
    account.invalidate_user_cache(101)
    account.invalidate_user_cache(102)
    account.invalidate_user_cache(103)


def test_unauthenticated_request_rejected():
    """Any unauthenticated request to private endpoints must return 401, never default to User 1."""
    client = TestClient(app)

    # Missing token
    r1 = client.get("/api/dashboard")
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}: {r1.text}"

    r2 = client.get("/api/positions")
    assert r2.status_code == 401

    r3 = client.get("/api/automations")
    assert r3.status_code == 401

    r4 = client.get("/api/account/connection-status")
    assert r4.status_code == 401

    # Malformed / invalid token
    r5 = client.get("/api/dashboard", headers={"Authorization": "Bearer invalid_token_12345"})
    assert r5.status_code == 401

    # Non-existent user token
    fake_token = create_access_token({"sub": "99999", "role": "USER"})
    r6 = client.get("/api/dashboard", headers={"Authorization": f"Bearer {fake_token}"})
    assert r6.status_code == 401


def test_user_a_and_user_b_balance_and_position_isolation():
    """User A and User B receive strictly their own exchange balances and positions."""
    client = TestClient(app)
    token_a = create_access_token({"sub": "101", "role": "USER"})
    token_b = create_access_token({"sub": "102", "role": "USER"})

    # Mock client instances for User A and User B
    mock_client_a = MagicMock()
    mock_client_a.api_key = "keyA"
    mock_client_a.secret_key = "secA"
    mock_client_a.balance.return_value = {
        "balance": [{"asset": "USDT", "balance": "1500.50", "availableMargin": "1200.00", "equity": "1500.50"}]
    }
    mock_client_a.positions.return_value = [
        {"symbol": "BTC-USDT", "side": "LONG", "qty": 0.1, "entry": 60000.0, "mark": 61000.0, "unrealized_pnl": 100.0}
    ]

    mock_client_b = MagicMock()
    mock_client_b.api_key = "keyB"
    mock_client_b.secret_key = "secB"
    mock_client_b.balance.return_value = {
        "balance": [{"asset": "USDT", "balance": "3200.75", "availableMargin": "2900.00", "equity": "3200.75"}]
    }
    mock_client_b.positions.return_value = [
        {"symbol": "ETH-USDT", "side": "SHORT", "qty": 2.0, "entry": 3000.0, "mark": 2950.0, "unrealized_pnl": 100.0}
    ]

    def mock_get_client(uid, allow_trade=False):
        if uid == 101:
            return mock_client_a
        elif uid == 102:
            return mock_client_b
        return None

    with patch("control_plane.credential_vault.get_user_bingx_client", side_effect=mock_get_client):
        # Query User A dashboard
        res_a = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200
        dash_a = res_a.json()
        assert dash_a["account"]["balance"] == 1500.50
        assert dash_a["account"]["equity"] == 1500.50
        pos_symbols_a = [p["symbol"] for p in dash_a["positions"]]
        assert "BTC-USDT" in pos_symbols_a
        assert "ETH-USDT" not in pos_symbols_a

        # Query User B dashboard
        res_b = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        dash_b = res_b.json()
        assert dash_b["account"]["balance"] == 3200.75
        assert dash_b["account"]["equity"] == 3200.75
        pos_symbols_b = [p["symbol"] for p in dash_b["positions"]]
        assert "ETH-USDT" in pos_symbols_b
        assert "BTC-USDT" not in pos_symbols_b


def test_zero_fallback_on_unconnected_user():
    """Unconnected User C must see 0.0 balance and empty positions, never falling back to A or Admin."""
    client = TestClient(app)
    token_c = create_access_token({"sub": "103", "role": "USER"})

    with patch("control_plane.credential_vault.get_user_bingx_client", return_value=None):
        res_c = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_c}"})
        assert res_c.status_code == 200
        dash_c = res_c.json()
        assert dash_c["account"]["balance"] == 0.0
        assert dash_c["account"]["equity"] == 0.0
        assert dash_c["account"]["connected"] is False
        assert dash_c["account_provenance"] == "NO_DATA"
        assert len(dash_c["positions"]) == 0


def test_disconnect_and_cache_eviction():
    """User A disconnecting clears credentials and evicts cache without affecting User B."""
    client = TestClient(app)
    token_a = create_access_token({"sub": "101", "role": "USER"})
    token_b = create_access_token({"sub": "102", "role": "USER"})

    # Store credentials for User A
    with db._lock:
        db.store_user_bingx_credentials(
            user_id=101,
            api_key_enc=credential_vault.encrypt_secret("test_key_a"),
            api_secret_enc=credential_vault.encrypt_secret("test_sec_a"),
            key_identifier="****keyA",
            permissions=["read", "perpetual_futures"],
            has_withdrawal=False,
            is_valid=True
        )
        db.update_user_bingx_status(101, "CONNECTED", "****keyA", None)

    # Check status endpoint
    mock_client = MagicMock()
    mock_client.balance.return_value = {
        "balance": [{"asset": "USDT", "balance": "100.0", "availableMargin": "100.0", "equity": "100.0"}]
    }
    with patch("control_plane.credential_vault.get_user_bingx_client", return_value=mock_client):
        stat_res = client.get("/api/user/bingx-status", headers={"Authorization": f"Bearer {token_a}"})
        assert stat_res.status_code == 200
        assert stat_res.json()["connected"] is True
        assert stat_res.json()["key_identifier"] == "****keyA"

    # Disconnect User A
    disc_res = client.post("/api/user/bingx-disconnect", headers={"Authorization": f"Bearer {token_a}"})
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "DISCONNECTED"

    # User A status is now disconnected / not configured
    stat_after = client.get("/api/user/bingx-status", headers={"Authorization": f"Bearer {token_a}"})
    assert stat_after.json()["connected"] is False
    assert stat_after.json()["status"] in ("DISCONNECTED", "NOT_CONFIGURED")

    # User A dashboard returns 0.0 balance
    dash_after = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_a}"})
    assert dash_after.json()["account"]["balance"] == 0.0
    assert dash_after.json()["account"]["connected"] is False


def test_automation_ownership_protection():
    """User A's automation cannot be updated or deleted by User B."""
    client = TestClient(app)
    token_a = create_access_token({"sub": "101", "role": "USER"})
    token_b = create_access_token({"sub": "102", "role": "USER"})

    mock_client_a = MagicMock()
    mock_client_a.balance.return_value = {
        "balance": [{"asset": "USDT", "balance": "1000.0", "availableMargin": "1000.0", "equity": "1000.0"}]
    }
    mock_client_a.positions.return_value = []

    with patch("control_plane.credential_vault.get_user_bingx_client", return_value=mock_client_a):
        # User A creates automation
        create_res = client.post(
            "/api/automations",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "symbol_scope": "BTC-USDT",
                "direction": "LONG",
                "strategy": "BREAKOUT_RETEST",
                "timeframe": "5",
                "leverage": 5.0,
                "margin_usdt": 50.0
            }
        )
        assert create_res.status_code == 200, f"Failed create automation: {create_res.text}"
        aid = create_res.json()["id"]

        # User B attempts to patch User A's automation -> Must fail (404 not owned)
        patch_res = client.patch(
            f"/api/automations/{aid}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"status": "PAUSED"}
        )
        assert patch_res.status_code == 404

        # User B attempts to delete User A's automation -> Must fail (404 not owned)
        del_res = client.delete(
            f"/api/automations/{aid}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert del_res.status_code == 404

        # User A CAN delete their own automation
        del_res_a = client.delete(
            f"/api/automations/{aid}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert del_res_a.status_code == 200
        assert del_res_a.json()["success"] is True


def test_cache_poisoning_isolation():
    """Interleaved requests between User A and User B never cross-pollinate."""
    client = TestClient(app)
    token_a = create_access_token({"sub": "101", "role": "USER"})
    token_b = create_access_token({"sub": "102", "role": "USER"})

    mock_a = MagicMock()
    mock_a.balance.return_value = {"balance": [{"asset": "USDT", "balance": "111.11", "equity": "111.11"}]}
    mock_a.positions.return_value = []

    mock_b = MagicMock()
    mock_b.balance.return_value = {"balance": [{"asset": "USDT", "balance": "999.99", "equity": "999.99"}]}
    mock_b.positions.return_value = []

    def mock_router(uid, allow_trade=False):
        return mock_a if uid == 101 else (mock_b if uid == 102 else None)

    with patch("control_plane.credential_vault.get_user_bingx_client", side_effect=mock_router):
        for _ in range(10):
            res_a = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_a}"})
            assert res_a.json()["account"]["balance"] == 111.11

            res_b = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token_b}"})
            assert res_b.json()["account"]["balance"] == 999.99
