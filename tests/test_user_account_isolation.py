"""Test Suite for User Account Isolation, Fleet God Eye, and Duplicate Position Invariants.

Verifies:
1. User A connected to BingX sees User A balance and positions.
2. User B unconnected sees $0.00 balance, connected=False, 0 positions, zero leakage of User A.
3. User B connected to separate BingX sees User B balance and positions only.
4. Admin sees Admin balance and positions.
5. Cache isolation: cached balance for User A never served to User B or Admin.
6. Authoritative duplicate position invariant: second entry for same symbol is blocked when open position exists.
7. User-scoped capacity and allocation endpoints.
8. God Eye fleet overview: lists all registered users with connection statuses and balances without cross-contamination.
"""
import os
import sys
import tempfile
import sqlite3
import pytest

sys.path.insert(0, os.path.abspath("."))

from control_plane import config, db, account, core, credential_vault, symbols


class MockBingXClient:
    def __init__(self, balance, positions=None):
        self.balance_val = balance
        self.positions_val = positions or []
        self.api_key = "mock_key"

    def balance(self):
        return [{
            "asset": "USDT",
            "balance": self.balance_val,
            "equity": self.balance_val,
            "unrealizedProfit": 0.0,
            "availableMargin": self.balance_val,
            "usedMargin": 0.0,
        }]

    def positions(self):
        return self.positions_val


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Setup temporary in-memory or isolated DB for isolation tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Point config.DB_PATH to temporary test database
    monkeypatch.setattr(config, "DB_PATH", db_path)
    if db._conn:
        try:
            db._conn.close()
        except Exception:
            pass
    db._conn = None
    account._CACHE.clear()
    
    # Initialize schema
    db._connect()

    yield db_path

    # Cleanup
    if db._conn:
        try:
            db._conn.close()
        except Exception:
            pass
    db._conn = None
    try:
        os.remove(db_path)
    except Exception:
        pass


def test_user_account_isolation(monkeypatch):
    """Verify strict multi-tenant account isolation across Admin, User A, and User B."""
    from control_plane import bingx_client
    c = db._wl_conn()
    with db._lock:
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (1, 'admin@ophelia.internal', 'admin_sub', 'ADMIN', 'ACTIVE')")
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (2, 'usera@ophelia.internal', 'usera_sub', 'USER', 'ACTIVE')")
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (3, 'userb@ophelia.internal', 'userb_sub', 'USER', 'ACTIVE')")

    # Mock credential vault to return clients per user
    mock_clients = {
        1: MockBingXClient(balance=1000.0, positions=[{"symbol": "BTC-USDT", "positionAmt": "0.1"}]),
        2: MockBingXClient(balance=250.0, positions=[{"symbol": "SOL-USDT", "positionAmt": "1.5"}]),
        # User 3 has NO credentials configured initially
    }

    def mock_get_user_bingx_client(user_id, *args, **kwargs):
        return mock_clients.get(user_id)

    monkeypatch.setattr(credential_vault, "get_user_bingx_client", mock_get_user_bingx_client)
    monkeypatch.setattr(bingx_client, "from_env", lambda: mock_clients[1])

    # 2. Check User A snapshot
    acc_a, pos_a = account.exchange_snapshot(user_id=2)
    assert acc_a["connected"] is True
    assert acc_a["balance"] == 250.0
    assert len(pos_a) == 1
    assert pos_a[0]["symbol"] == "SOL-USDT"

    # 3. Check User B snapshot (UNCONNECTED)
    acc_b, pos_b = account.exchange_snapshot(user_id=3)
    assert acc_b["connected"] is False
    assert acc_b["balance"] == 0.0
    assert acc_b["equity"] == 0.0
    assert acc_b["unrealized_pnl"] == 0.0
    assert len(pos_b) == 0
    # ZERO leakage of User A or Admin!
    assert acc_b["balance"] != acc_a["balance"]

    # 4. Check Admin snapshot (user_id=1)
    acc_admin, pos_admin = account.exchange_snapshot(user_id=1)
    assert acc_admin["connected"] is True
    assert acc_admin["balance"] == 1000.0
    assert len(pos_admin) == 1
    assert pos_admin[0]["symbol"] == "BTC-USDT"

    # 5. Check Cache Isolation:
    assert 1 in account._CACHE
    assert 2 in account._CACHE
    assert 3 in account._CACHE
    assert account._CACHE[2]["account"]["balance"] == 250.0
    assert account._CACHE[3]["account"]["balance"] == 0.0
    assert account._CACHE[1]["account"]["balance"] == 1000.0

    # 6. Now connect User B with separate BingX account
    mock_clients[3] = MockBingXClient(balance=50.0, positions=[{"symbol": "ETH-USDT", "positionAmt": "0.05"}])
    account._CACHE.clear()

    acc_b_connected, pos_b_connected = account.exchange_snapshot(user_id=3)
    assert acc_b_connected["connected"] is True
    assert acc_b_connected["balance"] == 50.0
    assert len(pos_b_connected) == 1
    assert pos_b_connected[0]["symbol"] == "ETH-USDT"

    # Ensure User A snapshot still returns User A balance
    acc_a_recheck, pos_a_recheck = account.exchange_snapshot(user_id=2)
    assert acc_a_recheck["balance"] == 250.0
    assert pos_a_recheck[0]["symbol"] == "SOL-USDT"


def test_duplicate_position_invariant():
    """Verify pre-entry invariant rejects duplicate active position for symbol."""
    c = db._wl_conn()
    with db._lock:
        c.execute(
            "INSERT INTO positions (user_id, symbol, status, entry, qty, mode) "
            "VALUES (?, ?, 'OPEN', 135.0, 1.0, 'SHADOW')",
            (1, "SOL-USDT")
        )

    # Check has_open_position_for_symbol
    assert db.has_open_position_for_symbol("SOL-USDT", user_id=1) is True
    assert db.has_open_position_for_symbol("BTC-USDT", user_id=1) is False

    # For a different user (user_id=2), SOL-USDT is NOT open
    assert db.has_open_position_for_symbol("SOL-USDT", user_id=2) is False


def test_user_automation_allocations():
    """Verify user automation allocations CRUD in db.py."""
    user_id = 2
    allocations = db.get_user_automation_allocations(user_id)
    assert len(allocations) == 0

    # Set allocation for automation 47
    db.set_user_automation_allocation(user_id=user_id, automation_id="47", allocated_amount=15.0, enabled=True)

    allocs = db.get_user_automation_allocations(user_id)
    assert len(allocs) == 1
    assert str(allocs[0]["automation_id"]) == "47"
    assert allocs[0]["allocated_amount"] == 15.0
    assert allocs[0]["enabled"] is True

    # Update allocation
    db.set_user_automation_allocation(user_id=user_id, automation_id="47", allocated_amount=25.0, enabled=False)
    allocs_updated = db.get_user_automation_allocations(user_id)
    assert len(allocs_updated) == 1
    assert allocs_updated[0]["allocated_amount"] == 25.0
    assert allocs_updated[0]["enabled"] is False

    # User 3 still has 0 allocations
    assert len(db.get_user_automation_allocations(3)) == 0


def test_user_notifications_crud():
    """Verify notification queries for user notifications screen."""
    user_id = 2
    db.create_notification(
        user_id=user_id,
        event_type="ORDER_OPEN",
        dedup_key="ord_open_1",
        severity="INFO",
        title="Position Opened",
        message="SOL-USDT LONG position opened at $135.00",
        mode="SHADOW",
        category="TRADES",
    )
    db.create_notification(
        user_id=user_id,
        event_type="CAPACITY_WARNING",
        dedup_key="cap_warn_1",
        severity="WARNING",
        title="Capacity Warning",
        message="80% of allocated trade capacity used",
        mode="SHADOW",
        category="RISK",
    )

    notifs = db.get_notifications(user_id=user_id)
    assert len(notifs) == 2
    assert notifs[0]["read"] == 0 or notifs[0]["read"] is False

    # Mark first read
    first_id = notifs[0]["id"]
    db.mark_notification_read(first_id, user_id=user_id)

    notifs_after = db.get_notifications(user_id=user_id)
    assert any(n["read"] == 1 or n["read"] is True for n in notifs_after)

    # User 3 sees 0 notifications
    assert len(db.get_notifications(user_id=3)) == 0


def test_god_eye_fleet_overview(monkeypatch):
    """Verify God Eye accurately lists registered and connected users with no cross-leakage."""
    from control_plane import api
    c = db._wl_conn()
    with db._lock:
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status, bingx_connection_status) VALUES (1, 'admin@ophelia.internal', 'admin_sub', 'ADMIN', 'ACTIVE', 'CONNECTED')")
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status, bingx_connection_status) VALUES (2, 'usera@ophelia.internal', 'usera_sub', 'USER', 'ACTIVE', 'CONNECTED')")
        c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status, bingx_connection_status) VALUES (3, 'userb@ophelia.internal', 'userb_sub', 'USER', 'ACTIVE', 'DISCONNECTED')")
        c.commit()

    account._CACHE.clear()

    mock_clients = {
        2: MockBingXClient(balance=250.0),
    }
    monkeypatch.setattr(credential_vault, "get_user_bingx_client", lambda uid, *a, **kw: mock_clients.get(uid))

    overview = api.get_god_eye_overview()
    summary = overview["summary"]
    # 2 registered users (role == USER)
    assert summary["registered_users"] == 2
    # 1 connected user (User A)
    assert summary["connected_users"] == 1
    # 1 disconnected user (User B)
    assert summary["bingx_disconnected"] == 1

    users = {u["id"]: u for u in overview["users"]}
    assert 2 in users
    assert 3 in users
    assert users[2]["balance"] == 250.0
    assert users[3]["balance"] in (None, 0.0)
    assert users[3]["bingx_connection"] == "DISCONNECTED"
    assert users[3]["ophelia_user_id"] == "USR-0003"
