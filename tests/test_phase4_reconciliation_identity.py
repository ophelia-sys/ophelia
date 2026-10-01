"""
Phase 4 Gate Review — Dedicated Reconciliation Identity Safety & Fee Model Governance Tests.

Verifies:
1. Missing position.user_id fails closed (REQUIRES_RECONCILIATION, no exchange call, no slot release).
2. Missing slot.user_id fails closed (REQUIRES_RECONCILIATION, no mutation).
3. Missing account_id in LIVE fails closed (no exchange call).
4. Ownership mismatch between position and slot fails closed (CROSS_USER_OWNERSHIP_MISMATCH).
5. Explicit proof: NO fallback to user 1 under any circumstances.
6. Cross-user reconciliation isolation (User A vs User B).
7. FeeModel governance: changing FeeModel dynamically changes calculated breakeven stops.
"""

import pytest
import time
import json
from unittest.mock import MagicMock

from control_plane import config, db
from control_plane import position_math
from control_plane.position_math import FeeModel
from control_plane import position_manager_daemon
from control_plane.slot_allocation_service import SlotAllocationService


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database for every test."""
    db_file = str(tmp_path / "test_recon_identity.db")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr(db, "_conn", None)
    db._connect()
    db.set_global_autonomous_enabled(True)
    db.set_mode("SHADOW")
    yield
    with db._lock:
        if db._conn is not None:
            try:
                db._conn.close()
            except Exception:
                pass
            db._conn = None


def test_reconciliation_refuses_when_position_user_id_missing():
    """A. position.user_id is missing -> reconciliation refuses to process it."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # Insert position with user_id = NULL
    cur = c.execute("""
        INSERT INTO positions (
            symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms
        ) VALUES ('BTC-USDT', 'LONG', 65000.0, 0.1, 0.1, 'OPEN', 'PROTECTED', NULL, 1, 'SHADOW', ?)
    """, (now_ms,))
    c.commit()
    pid = cur.lastrowid

    # Reconcile
    res = position_manager_daemon.reconcile_all_positions_with_exchange()

    # Verify fail-closed
    pos = db.get_position(pid)
    assert pos["reconciliation_status"] == "REQUIRES_RECONCILIATION"
    assert pos["last_management_event"] == "INVALID_OWNERSHIP_FAIL_CLOSED"
    assert pos["user_id"] is None, "Must never infer or assign user_id"

    # Verify event logged
    recon_errs = [e for e in res["reconciled"] if e.get("position_id") == pid]
    assert len(recon_errs) == 1
    assert recon_errs[0]["state"] == "REQUIRES_RECONCILIATION"
    assert recon_errs[0]["error"] == "MISSING_USER_ID"


def test_reconciliation_refuses_when_slot_user_id_missing():
    """B. slot.user_id is missing -> reconciliation refuses to process/mutate it."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # Insert slot with user_id = NULL in OCCUPIED state without position
    cur = c.execute("""
        INSERT INTO autonomous_trade_slots (
            name, status, user_id, account_id, enabled, current_position_id, created_at, updated_at, allocated_margin_usdt
        ) VALUES ('Orphan Slot', 'OCCUPIED', NULL, 1, 1, NULL, ?, ?, 100.0)
    """, (now_ms, now_ms))
    c.commit()
    sid = cur.lastrowid

    # Reconcile
    res = position_manager_daemon.reconcile_all_positions_with_exchange()

    # Verify slot was NOT released or modified
    slot = db.get_autonomous_trade_slot(sid)
    assert slot["status"] == "OCCUPIED", "Unowned slot must NOT be mutated"
    assert slot["user_id"] is None

    # Verify error recorded in repaired
    slot_errs = [r for r in res["repaired"] if r.get("slot_id") == sid]
    assert len(slot_errs) == 1
    assert slot_errs[0]["state"] == "REQUIRES_RECONCILIATION"
    assert slot_errs[0]["error"] == "MISSING_USER_ID"


def test_reconciliation_live_mode_refuses_when_account_id_missing():
    """C. account_id is missing in LIVE mode -> no exchange call."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # Insert LIVE position with valid user_id=42 but NULL account_id
    cur = c.execute("""
        INSERT INTO positions (
            symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms
        ) VALUES ('SOL-USDT', 'LONG', 150.0, 1.0, 1.0, 'OPEN', 'PROTECTED', 42, NULL, 'LIVE', ?)
    """, (now_ms,))
    c.commit()
    pid = cur.lastrowid

    # Reconcile without client (would attempt live client creation)
    res = position_manager_daemon.reconcile_all_positions_with_exchange(client=None)

    pos = db.get_position(pid, user_id=42)
    assert pos["reconciliation_status"] == "REQUIRES_RECONCILIATION"
    assert pos["last_management_event"] == "MISSING_ACCOUNT_ID"

    recon_errs = [e for e in res["reconciled"] if e.get("position_id") == pid]
    assert len(recon_errs) == 1
    assert recon_errs[0]["error"] == "MISSING_ACCOUNT_ID"


def test_reconciliation_cross_user_slot_position_mismatch():
    """D & E. User does not own the slot referenced by position -> no mutation, mark REQUIRES_RECONCILIATION."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # User 200's legitimate open position
    c.execute("""
        INSERT INTO positions (
            client_order_id, symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms
        ) VALUES ('pos_200', 'ETH-USDT', 'LONG', 3400.0, 0.5, 0.5, 'OPEN', 'PROTECTED', 200, 1, 'SHADOW', ?)
    """, (now_ms,))

    # Slot owned by User 200 and occupied by pos_200
    cur = c.execute("""
        INSERT INTO autonomous_trade_slots (
            name, status, user_id, account_id, enabled, current_position_id, created_at, updated_at, allocated_margin_usdt
        ) VALUES ('Slot User 200', 'OCCUPIED', 200, 1, 1, 'pos_200', ?, ?, 100.0)
    """, (now_ms, now_ms))
    c.commit()
    sid = cur.lastrowid

    # Position owned by User 100, mistakenly pointing to slot of User 200
    detail = json.dumps({"slot_id": sid})
    cur2 = c.execute("""
        INSERT INTO positions (
            symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms, detail_json
        ) VALUES ('ETH-USDT', 'LONG', 3500.0, 0.5, 0.5, 'OPEN', 'PROTECTED', 100, 1, 'SHADOW', ?, ?)
    """, (now_ms, detail))
    c.commit()
    pid = cur2.lastrowid

    # Reconcile
    res = position_manager_daemon.reconcile_all_positions_with_exchange()

    # Position 100 must be marked REQUIRES_RECONCILIATION
    pos = db.get_position(pid, user_id=100)
    assert pos["reconciliation_status"] == "REQUIRES_RECONCILIATION"
    assert pos["last_management_event"] == "CROSS_USER_OWNERSHIP_MISMATCH"

    # Slot 200 must NOT be released by position 100
    slot = db.get_autonomous_trade_slot(sid, user_id=200)
    assert slot["status"] == "OCCUPIED"


def test_explicit_no_fallback_to_user_1():
    """F. Explicit proof: Missing user_id NEVER falls back to User 1."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # Create legitimate User 1
    c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (1, 'user1@ophelia.internal', 'sub_1', 'USER', 'ACTIVE')")
    cur_u1 = c.execute("""
        INSERT INTO autonomous_trade_slots (
            name, status, user_id, account_id, enabled, created_at, updated_at, max_loss_usdt, allocated_margin_usdt
        ) VALUES ('Legit User 1 Slot', 'AVAILABLE', 1, 1, 1, ?, ?, 50.0, 100.0)
    """, (now_ms, now_ms))
    u1_slot_id = cur_u1.lastrowid

    # Create orphan position and orphan slot with NULL user_id
    c.execute("""
        INSERT INTO positions (
            symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms
        ) VALUES ('XRP-USDT', 'LONG', 0.55, 100.0, 100.0, 'OPEN', 'PROTECTED', NULL, NULL, 'SHADOW', ?)
    """, (now_ms,))
    orphan_pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    c.execute("""
        INSERT INTO autonomous_trade_slots (
            name, status, user_id, account_id, enabled, created_at, updated_at, allocated_margin_usdt
        ) VALUES ('Orphan Slot', 'OCCUPIED', NULL, NULL, 1, ?, ?, 100.0)
    """, (now_ms, now_ms))
    orphan_sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()

    # 1. Test position evaluation ignores or fails closed without touching User 1
    orphan_pos = db.get_position(orphan_pid)
    acts = position_manager_daemon.evaluate_single_position(orphan_pos, current_price=0.56)
    assert acts == [], "Must return empty actions on missing user_id"

    # 2. Test reconciliation does NOT assign orphan to User 1
    position_manager_daemon.reconcile_all_positions_with_exchange()

    # Check User 1 open positions: must NOT contain orphan
    u1_positions = db.open_positions(user_id=1)
    u1_pids = [p["id"] for p in u1_positions]
    assert orphan_pid not in u1_pids, "Orphan position must NEVER appear in User 1 positions"

    # Check User 1 slots: must NOT contain orphan slot
    u1_slots = db.get_autonomous_trade_slots(user_id=1)
    u1_sids = [s["id"] for s in u1_slots]
    assert orphan_sid not in u1_sids, "Orphan slot must NEVER appear in User 1 slots"

    # Check direct db state: user_id must remain NULL
    row_pos = c.execute("SELECT user_id, reconciliation_status FROM positions WHERE id=?", (orphan_pid,)).fetchone()
    assert row_pos[0] is None, "Database position user_id must remain NULL"
    assert row_pos[1] == "REQUIRES_RECONCILIATION"

    row_slot = c.execute("SELECT user_id FROM autonomous_trade_slots WHERE id=?", (orphan_sid,)).fetchone()
    assert row_slot[0] is None, "Database slot user_id must remain NULL"


def test_cross_user_reconciliation_isolation():
    """User A only reconciles User A; User B only reconciles User B."""
    c = db._connect()
    now_ms = int(time.time() * 1000)

    # User A (id=101)
    c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (101, 'usera@test.com', 'sub101', 'USER', 'ACTIVE')")
    cur_sa = c.execute("""
        INSERT INTO autonomous_trade_slots (name, status, current_position_id, user_id, account_id, enabled, created_at, updated_at, allocated_margin_usdt)
        VALUES ('Slot User A', 'OCCUPIED', 'pos_a', 101, 1, 1, ?, ?, 100.0)
    """, (now_ms, now_ms))
    sid_a = cur_sa.lastrowid
    detail_a = json.dumps({"slot_id": sid_a})
    cur_a = c.execute("""
        INSERT INTO positions (
            client_order_id, symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms, detail_json
        ) VALUES ('pos_a', 'BTC-USDT', 'LONG', 60000.0, 0.1, 0.1, 'OPEN', 'PROTECTED', 101, 1, 'SHADOW', ?, ?)
    """, (now_ms, detail_a))
    c.commit()
    pid_a = cur_a.lastrowid

    # User B (id=202)
    c.execute("INSERT OR REPLACE INTO users (id, email, google_subject, role, status) VALUES (202, 'userb@test.com', 'sub202', 'USER', 'ACTIVE')")
    cur_sb = c.execute("""
        INSERT INTO autonomous_trade_slots (name, status, current_position_id, user_id, account_id, enabled, created_at, updated_at, allocated_margin_usdt)
        VALUES ('Slot User B', 'OCCUPIED', 'pos_b', 202, 1, 1, ?, ?, 100.0)
    """, (now_ms, now_ms))
    sid_b = cur_sb.lastrowid
    detail_b = json.dumps({"slot_id": sid_b})
    cur_b = c.execute("""
        INSERT INTO positions (
            client_order_id, symbol, direction, entry, qty, remaining_qty, status, lifecycle_state,
            user_id, account_id, mode, opened_ms, detail_json
        ) VALUES ('pos_b', 'ETH-USDT', 'LONG', 3000.0, 1.0, 1.0, 'OPEN', 'PROTECTED', 202, 1, 'SHADOW', ?, ?)
    """, (now_ms, detail_b))
    c.commit()
    pid_b = cur_b.lastrowid

    # Reconcile ONLY User A
    res_a = position_manager_daemon.reconcile_all_positions_with_exchange(user_id=101)
    recon_pids_a = [e.get("position_id") for e in res_a["reconciled"]]
    assert pid_a in recon_pids_a
    assert pid_b not in recon_pids_a, "User B position must NOT be touched during User A reconciliation"

    # Reconcile ONLY User B
    res_b = position_manager_daemon.reconcile_all_positions_with_exchange(user_id=202)
    recon_pids_b = [e.get("position_id") for e in res_b["reconciled"]]
    assert pid_b in recon_pids_b
    assert pid_a not in recon_pids_b, "User A position must NOT be touched during User B reconciliation"


def test_fee_model_governance_breakeven_shift():
    """Fee Model Governance: Changing configured FeeModel strictly alters calculated breakeven stop."""
    entry = 50000.0
    initial_qty = 0.2
    remaining_qty = 0.1
    direction = "LONG"
    tp1_price = 52000.0
    close_qty = 0.1

    # Standard Shadow Fee Model: taker_fee = 0.0005 (0.05%)
    model_low = FeeModel(
        fee_source="SHADOW_TEST_LOW",
        fee_type="PERCENTAGE",
        maker_fee=0.0002,
        taker_fee=0.0005,
        mode="SHADOW"
    )

    # High VIP/Exchange Fee Model: taker_fee = 0.0010 (0.10%)
    model_high = FeeModel(
        fee_source="SHADOW_TEST_HIGH",
        fee_type="PERCENTAGE",
        maker_fee=0.0005,
        taker_fee=0.0010,
        mode="SHADOW"
    )

    # Low fee calculations
    tp1_fee_low = position_math.calculate_actual_fee(tp1_price, close_qty, fee_model=model_low)
    tp1_pnl_low = position_math.calculate_realized_pnl(entry, tp1_price, close_qty, direction, fee=tp1_fee_low)
    entry_fee_low = position_math.calculate_actual_fee(entry, initial_qty, fee_model=model_low)

    be_calc_low = position_math.calculate_net_breakeven_stop(
        entry_price=entry,
        initial_qty=initial_qty,
        remaining_qty=remaining_qty,
        direction=direction,
        entry_fee=entry_fee_low,
        tp1_realized_pnl=tp1_pnl_low,
        tp1_fee=tp1_fee_low,
        fee_model=model_low,
        tick_size=0.01
    )

    # High fee calculations
    tp1_fee_high = position_math.calculate_actual_fee(tp1_price, close_qty, fee_model=model_high)
    tp1_pnl_high = position_math.calculate_realized_pnl(entry, tp1_price, close_qty, direction, fee=tp1_fee_high)
    entry_fee_high = position_math.calculate_actual_fee(entry, initial_qty, fee_model=model_high)

    be_calc_high = position_math.calculate_net_breakeven_stop(
        entry_price=entry,
        initial_qty=initial_qty,
        remaining_qty=remaining_qty,
        direction=direction,
        entry_fee=entry_fee_high,
        tp1_realized_pnl=tp1_pnl_high,
        tp1_fee=tp1_fee_high,
        fee_model=model_high,
        tick_size=0.01
    )

    # Invariant: Higher taker fee requires a strictly HIGHER cost basis for LONG
    assert be_calc_high["calculated_cost_basis"] > be_calc_low["calculated_cost_basis"]
    assert be_calc_high["calculation_inputs"]["fee_rate"] == 0.0010
    assert be_calc_low["calculation_inputs"]["fee_rate"] == 0.0005
    assert be_calc_high["calculation_inputs"]["fee_source"] == "SHADOW_TEST_HIGH"
    assert be_calc_low["calculation_inputs"]["fee_source"] == "SHADOW_TEST_LOW"


def test_fee_model_governance_short_shift():
    """Fee Model Governance: For SHORT, higher taker fee pushes cost basis strictly LOWER."""
    entry = 50000.0
    model_low = FeeModel(fee_source="TEST_LOW", fee_type="PERCENTAGE", maker_fee=0.0002, taker_fee=0.0005)
    model_high = FeeModel(fee_source="TEST_HIGH", fee_type="PERCENTAGE", maker_fee=0.0005, taker_fee=0.0010)

    be_low = position_math.calculate_net_breakeven_stop(
        entry_price=entry,
        initial_qty=0.2,
        remaining_qty=0.1,
        direction="SHORT",
        entry_fee=5.0,
        tp1_realized_pnl=200.0,
        tp1_fee=2.5,
        fee_model=model_low
    )

    be_high = position_math.calculate_net_breakeven_stop(
        entry_price=entry,
        initial_qty=0.2,
        remaining_qty=0.1,
        direction="SHORT",
        entry_fee=10.0,
        tp1_realized_pnl=200.0,
        tp1_fee=5.0,
        fee_model=model_high
    )

    # For SHORT, cost basis = entry * (1 - fee) / (1 + fee) -> higher fee means lower exit price needed
    assert be_high["calculated_cost_basis"] < be_low["calculated_cost_basis"]


def test_slot_auto_provisioning_never_falls_back_to_account_id_1():
    """Verify that auto-provisioned slot retains account_id=None if not provided, never defaulting to 1."""
    # User 500 without configured account_id
    user_id = 500
    db.set_user_slot_template(
        user_id=user_id,
        scope="CRYPTO",
        strategy_scope="ALL",
        max_slots=3,
        max_autonomous_capital=500.0,
        margin=50.0,
        leverage=5.0,
        account_id=None
    )

    slot, err = SlotAllocationService.auto_provision_slot(
        user_id=user_id,
        asset_class="CRYPTO",
        strategy="ALL",
        account_id=None
    )
    assert err == "OK"
    assert slot is not None
    assert slot["user_id"] == 500
    assert slot["account_id"] is None, "Slot account_id must be None and NEVER fall back to 1"

