"""Tests for Phase 5.6 Unified Manual Order Terminal & Venue Instrument Resolution."""
import os
import sys
sys.path.insert(0, os.path.abspath("."))

import pytest
from fastapi.testclient import TestClient

from control_plane import api, db, credential_vault
from control_plane.instruments import get_instrument_resolver


@pytest.fixture(scope="module")
def client():
    db.init_db()
    return TestClient(api.app)


@pytest.fixture(scope="module")
def auth_headers():
    admin = db.get_user_by_id(1)
    if not admin:
        admin = db.create_google_user("admin_sub_001", "admin@ophelia.internal", "Ophelia Admin")
        c = db._connect()
        c.execute("UPDATE users SET role='ADMIN' WHERE id=?", (admin["id"],))
        c.commit()
    admin_token = api.create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def second_user_headers():
    u2 = db.get_user_by_google_sub("user_sub_test_002")
    if not u2:
        u2 = db.create_google_user("user_sub_test_002", "trader2@ophelia.internal", "Trader Two")
    token = api.create_access_token({"sub": str(u2["id"]), "user_id": u2["id"], "role": "USER"})
    return {"Authorization": f"Bearer {token}"}


def test_market_search_canonical_instruments(client, auth_headers):
    """Search endpoint returns clean display_symbol and authoritative bingx_symbol."""
    res = client.get("/api/market/search?q=NFLX", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    nflx_item = next((item for item in data["results"] if item["symbol"] == "NFLX"), None)
    assert nflx_item is not None
    assert nflx_item["symbol"] == "NFLX"
    assert nflx_item["bingx_symbol"] == "NCSKNETFLIX2USD-USDT"
    assert nflx_item["venue_product"] == "TRADFI_PERPETUAL"
    assert nflx_item["executable"] is True

    # Crypto search
    res_btc = client.get("/api/market/search?q=BTC", headers=auth_headers)
    assert res_btc.status_code == 200
    btc_item = next((item for item in res_btc.json()["results"] if item["symbol"] == "BTC-USDT"), None)
    assert btc_item is not None
    assert btc_item["bingx_symbol"] == "BTC-USDT"

    # Commodities search
    res_gold = client.get("/api/market/search?q=GOLD", headers=auth_headers)
    assert res_gold.status_code == 200
    gold_item = next((item for item in res_gold.json()["results"] if "GOLD" in item["symbol"]), None)
    assert gold_item is not None
    assert gold_item["bingx_symbol"] == "NCCOGOLD2USD-USDT"


def test_netflix_manual_order_execution_and_venue_symbol(client, auth_headers):
    """User selects NFLX -> executes with authoritative venue symbol NCSKNETFLIX2USD-USDT."""
    order_payload = {
        "symbol": "NFLX",
        "side": "BUY",
        "order_type": "MARKET",
        "entry_price": 600.0,
        "margin": 50.0,
        "leverage": 5,
        "sl": 500.0,
        "tp1": 700.0,
        "reason": "Test Netflix Order Execution"
    }
    res = client.post("/api/orders/manual", json=order_payload, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["display_symbol"] == "NFLX"
    assert data["venue_symbol"] == "NCSKNETFLIX2USD-USDT"
    assert data["venue"] == "BINGX"
    assert data["venue_product"] == "TRADFI_PERPETUAL"
    assert data["asset_class"] == "US_EQUITY"
    assert data["status"] == "ACKNOWLEDGED"

    internal_id = data["internal_order_id"]
    persisted = db.get_manual_order(internal_id)
    assert persisted is not None
    assert persisted["venue_symbol"] == "NCSKNETFLIX2USD-USDT"
    assert persisted["asset_class"] == "US_EQUITY"
    assert persisted["status"] == "ACKNOWLEDGED"
    assert persisted["reconciliation_status"] == "RECONCILED"


def test_crypto_manual_order_matrix(client, auth_headers):
    """Crypto instruments (BTC, ETH, SOL) resolve and execute accurately."""
    for sym in ["BTC-USDT", "ETH-USDT", "SOL-USDT"]:
        payload = {
            "symbol": sym,
            "side": "LONG",
            "order_type": "MARKET",
            "margin": 50.0,
            "leverage": 5
        }
        res = client.post("/api/orders/manual", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Failed for {sym}: {res.text}"
        data = res.json()
        assert data["ok"] is True
        assert data["asset_class"] == "CRYPTO"
        assert data["venue_symbol"] == sym
        assert data["status"] == "ACKNOWLEDGED"


def test_us_equities_manual_order_matrix(client, auth_headers):
    """US equities (AAPL, NVDA) resolve to their authoritative BingX contracts."""
    for sym, expected_venue in [("AAPL", "NCSKAAPL2USD-USDT"), ("NVDA", "NCSKNVDA2USD-USDT")]:
        payload = {
            "symbol": sym,
            "side": "LONG",
            "order_type": "MARKET",
            "margin": 50.0,
            "leverage": 5
        }
        res = client.post("/api/orders/manual", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Failed for {sym}: {res.text}"
        data = res.json()
        assert data["ok"] is True
        assert data["asset_class"] == "US_EQUITY"
        assert data["venue_symbol"] == expected_venue
        assert data["status"] == "ACKNOWLEDGED"


def test_commodities_manual_order_matrix(client, auth_headers):
    """Commodities (GOLD, SILVER) resolve to their authoritative TradFi contracts."""
    for sym, expected_venue in [("GOLD", "NCCOGOLD2USD-USDT"), ("SILVER", "NCCOXAG2USD-USDT")]:
        payload = {
            "symbol": sym,
            "side": "LONG",
            "order_type": "MARKET",
            "margin": 50.0,
            "leverage": 5
        }
        res = client.post("/api/orders/manual", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Failed for {sym}: {res.text}"
        data = res.json()
        assert data["ok"] is True
        assert data["asset_class"] == "COMMODITIES"
        assert data["venue_symbol"] == expected_venue
        assert data["status"] == "ACKNOWLEDGED"


def test_multi_user_order_isolation(client, auth_headers, second_user_headers):
    """User 2 cannot see or access User 1's orders."""
    # User 1 submits an order
    order_payload = {
        "symbol": "BTC-USDT",
        "side": "BUY",
        "order_type": "MARKET",
        "margin": 50.0,
        "leverage": 5
    }
    res1 = client.post("/api/orders/manual", json=order_payload, headers=auth_headers)
    assert res1.status_code == 200
    u1_order_id = res1.json()["internal_order_id"]

    # User 2 lists orders
    u2_res = client.get("/api/orders/manual", headers=second_user_headers)
    assert u2_res.status_code == 200
    u2_orders = u2_res.json()["orders"]
    assert not any(o["internal_order_id"] == u1_order_id for o in u2_orders)

    # User 2 attempts to get User 1's order
    u2_get = client.get(f"/api/orders/manual/{u1_order_id}", headers=second_user_headers)
    assert u2_get.status_code == 404

    # User 1 gets their own order
    u1_get = client.get(f"/api/orders/manual/{u1_order_id}", headers=auth_headers)
    assert u1_get.status_code == 200
    assert u1_get.json()["internal_order_id"] == u1_order_id


def test_preflight_validation_failures(client, auth_headers):
    """Preflight validation properly enforces errors with strict codes."""
    # 1. Invalid instrument
    res_sym = client.post(
        "/api/orders/manual",
        json={"symbol": "NONEXISTENT_XYZ_123", "side": "BUY", "margin": 50.0, "leverage": 5},
        headers=auth_headers
    )
    assert res_sym.status_code == 400
    assert "INSTRUMENT_NOT_AVAILABLE" in res_sym.text or "INSTRUMENT_NOT_FOUND" in res_sym.text

    # 2. Leverage exceeds max allowed (BingX US equities max leverage is 20x)
    res_lev = client.post(
        "/api/orders/manual",
        json={"symbol": "NFLX", "side": "BUY", "margin": 50.0, "leverage": 50},
        headers=auth_headers
    )
    assert res_lev.status_code == 400
    assert "LEVERAGE_NOT_ALLOWED" in res_lev.text

    # 3. Minimum size failed (tiny margin producing notional < min_notional)
    res_min = client.post(
        "/api/orders/manual",
        json={"symbol": "BTC-USDT", "side": "BUY", "margin": 0.01, "leverage": 1},
        headers=auth_headers
    )
    assert res_min.status_code == 400
    assert "MINIMUM_SIZE_FAILED" in res_min.text

    # 4. Invalid geometry: LONG SL above entry
    res_geom_sl = client.post(
        "/api/orders/manual",
        json={"symbol": "BTC-USDT", "side": "LONG", "margin": 50.0, "leverage": 5, "sl": 90000.0},
        headers=auth_headers
    )
    assert res_geom_sl.status_code == 400
    assert "INVALID_GEOMETRY" in res_geom_sl.text

    # 5. Invalid geometry: LONG TP1 below entry
    res_geom_tp = client.post(
        "/api/orders/manual",
        json={"symbol": "BTC-USDT", "side": "LONG", "margin": 50.0, "leverage": 5, "tp1": 10000.0},
        headers=auth_headers
    )
    assert res_geom_tp.status_code == 400
    assert "INVALID_GEOMETRY" in res_geom_tp.text

    # 6. Invalid precision on LIMIT price
    res_prec = client.post(
        "/api/orders/manual",
        json={
            "symbol": "BTC-USDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "entry_price": 65000.12345678,
            "margin": 50.0,
            "leverage": 5
        },
        headers=auth_headers
    )
    assert res_prec.status_code == 400
    assert "INVALID_PRECISION" in res_prec.text
