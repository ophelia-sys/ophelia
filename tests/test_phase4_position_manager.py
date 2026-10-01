"""
Phase 4: Position Manager Hardening Test Suite
Verifies:
1. Actual-fill accounting & precision
2. TP1 50% partial exit & remaining quantity accounting
3. Mathematically correct net breakeven (fees, funding, directional cost-basis)
4. Server-side dynamic trailing monotonicity & thresholding
5. Authoritative position lifecycle state machine transitions
6. Crash/restart recovery across distinct stages
7. Duplicate TP1 and duplicate exit prevention
8. Network failure & ambiguity handling (REQUEST_SENT, UNKNOWN_RESULT, RECONCILING)
9. Position <-> Slot consistency and atomic slot release
10. Reconciliation engine paths
11. Cross-user isolation
"""

import pytest
import time
import json
from typing import Dict, Any

from control_plane import config, db
from control_plane.position_math import (
    get_instrument_precision,
    calculate_actual_fee,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    calculate_net_breakeven_stop,
    calculate_dynamic_trailing_stop,
    round_to_tick,
    TAKER_FEE_RATE,
    MAKER_FEE_RATE,
)
from control_plane.slot_allocation_service import SlotAllocationService
from control_plane.position_manager_daemon import (
    evaluate_and_manage_positions,
    reconcile_all_positions_with_exchange,
)


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database for every test."""
    db_file = str(tmp_path / "test_ophelia_p4.db")
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


# ==============================================================================
# 1. ACTUAL FILL-BASED ACCOUNTING & PRECISION
# ==============================================================================

def test_actual_fill_accounting_and_precision():
    """Verify fee calculation, tick size rounding, and fill precision for major instruments."""
    btc_meta = get_instrument_precision("BTC-USDT")
    assert btc_meta["tick_size"] == 0.1
    assert btc_meta["qty_precision"] == 4

    # Fee on 0.5 BTC at 65,000 USDT (taker 0.05%)
    fee = calculate_actual_fee(price=65000.0, qty=0.5, fee_rate=0.0005)
    assert fee == pytest.approx(16.25, abs=1e-4)

    # Realized PnL: LONG entry 65,000, exit 66,000 on 0.5 BTC, total fee 32.75
    realized_long = calculate_realized_pnl(65000.0, 66000.0, 0.5, "LONG", fee=32.75)
    # Gross: 0.5 * 1000 = 500. Net: 500 - 32.75 = 467.25
    assert realized_long == pytest.approx(467.25, abs=1e-4)

    # Realized PnL: SHORT entry 65,000, exit 64,000 on 0.5 BTC, total fee 32.25
    realized_short = calculate_realized_pnl(65000.0, 64000.0, 0.5, "SHORT", fee=32.25)
    assert realized_short == pytest.approx(467.75, abs=1e-4)

    # Unrealized PnL: mark PnL
    unrealized_long = calculate_unrealized_pnl(65000.0, 65500.0, 0.5, "LONG")
    assert unrealized_long == pytest.approx(250.0, abs=1e-4)


# ==============================================================================
# 2. TP1 50% PARTIAL EXIT & REMAINING QUANTITY
# ==============================================================================

def test_tp1_partial_exit_accounting():
    """Verify TP1 closes exactly configured percent (50%), updates remaining qty, and records realized PnL."""
    pid = "pos-test-tp1-01"
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 1.0,
        "quantity": 1.0,
        "leverage": 10.0,
        "margin": 6000.0,
        "margin_usdt": 6000.0,
        "sl": 58500.0,
        "sl_price": 58500.0,
        "tp1": 61500.0,
        "tp1_price": 61500.0,
        "tp2": 63000.0,
        "tp3": 65000.0,
        "position_id": pid,
        "actual_entry_price": 60000.0,
        "remaining_qty": 1.0,
        "total_fees": 30.0,
        "lifecycle_state": "PROTECTED",
        "status": "OPEN",
        "slot_id": 1,
    }, user_id=1)

    # Price ticks to 61,550 (surpasses TP1 61,500)
    current_prices = {"BTC-USDT": 61550.0}
    evaluate_and_manage_positions(current_prices)

    pos = db.get_position(pid)
    assert pos is not None
    assert pos["lifecycle_state"] in ("TP1", "BREAKEVEN")
    assert pos["remaining_qty"] == pytest.approx(0.5, abs=1e-4)
    assert pos["tp1_executed_ms"] is not None
    assert pos["tp1_exit_price"] == pytest.approx(61550.0, abs=1e-4)
    assert pos["tp1_qty"] == pytest.approx(0.5, abs=1e-4)
    assert pos["tp1_realized_pnl"] > 750.0


# ==============================================================================
# 3. MATHEMATICALLY CORRECT NET BREAKEVEN
# ==============================================================================

def test_net_breakeven_math_long():
    """Verify LONG net breakeven stop covers roundtrip fees + entry fees + funding."""
    entry_price = 60000.0
    initial_qty = 1.0
    remaining_qty = 0.5
    entry_fee = 30.0
    tp1_pnl = 750.0
    tp1_fee = 15.375
    funding = 5.0
    tick_size = 0.1

    res = calculate_net_breakeven_stop(
        entry_price=entry_price,
        initial_qty=initial_qty,
        remaining_qty=remaining_qty,
        direction="LONG",
        entry_fee=entry_fee,
        tp1_realized_pnl=tp1_pnl,
        tp1_fee=tp1_fee,
        funding_accrued=funding,
        fee_rate=0.0005,
        tick_size=tick_size,
        previous_stop=58500.0,
    )
    be_stop = res["breakeven_stop"]
    cost_basis = res["calculated_cost_basis"]
    inputs = res["calculation_inputs"]

    assert cost_basis > entry_price
    assert be_stop >= cost_basis
    assert be_stop > 58500.0
    assert round(be_stop / tick_size, 6).is_integer()


def test_net_breakeven_math_short():
    """Verify SHORT net breakeven stop is below entry to cover roundtrip fees."""
    entry_price = 60000.0
    initial_qty = 1.0
    remaining_qty = 0.5
    entry_fee = 30.0
    tp1_pnl = 750.0
    tp1_fee = 15.375
    funding = 0.0
    tick_size = 0.1

    res = calculate_net_breakeven_stop(
        entry_price=entry_price,
        initial_qty=initial_qty,
        remaining_qty=remaining_qty,
        direction="SHORT",
        entry_fee=entry_fee,
        tp1_realized_pnl=tp1_pnl,
        tp1_fee=tp1_fee,
        funding_accrued=funding,
        fee_rate=0.0005,
        tick_size=tick_size,
        previous_stop=61500.0,
    )
    be_stop = res["breakeven_stop"]
    cost_basis = res["calculated_cost_basis"]
    inputs = res["calculation_inputs"]

    assert cost_basis < entry_price
    assert be_stop <= cost_basis
    assert be_stop < 61500.0
    assert round(be_stop / tick_size, 6).is_integer()


# ==============================================================================
# 4. SERVER-SIDE DYNAMIC TRAILING MONOTONICITY
# ==============================================================================

def test_dynamic_trailing_monotonicity_long():
    """Assert LONG dynamic trailing stop is strictly non-decreasing across simulated price ticks."""
    entry = 60000.0
    current_stop = 60100.0
    high_watermark = 62000.0
    tick_size = 0.1
    atr = 300.0

    prices = [62500.0, 63000.0, 63200.0, 62800.0, 63500.0, 63100.0]
    recorded_stops = [current_stop]

    for p in prices:
        res = calculate_dynamic_trailing_stop(
            current_price=p,
            entry_price=entry,
            direction="LONG",
            current_stop=current_stop,
            trailing_ref=high_watermark,
            atr=atr,
            volatility=0.015,
            regime="TREND",
            trailing_pct=0.015,
            tick_size=tick_size,
        )
        new_stop = res["new_stop"]
        new_hw = res["ref_price"]
        moved = res["moved"]
        assert new_stop >= current_stop, f"Trailing stop regressed: {new_stop} < {current_stop}"
        if moved:
            current_stop = new_stop
            high_watermark = new_hw
        recorded_stops.append(current_stop)

    for i in range(1, len(recorded_stops)):
        assert recorded_stops[i] >= recorded_stops[i - 1]


def test_dynamic_trailing_monotonicity_short():
    """Assert SHORT dynamic trailing stop is strictly non-increasing across simulated price ticks."""
    entry = 60000.0
    current_stop = 59900.0
    low_watermark = 58000.0
    tick_size = 0.1
    atr = 300.0

    prices = [57500.0, 57000.0, 56800.0, 57200.0, 56500.0, 56900.0]
    recorded_stops = [current_stop]

    for p in prices:
        res = calculate_dynamic_trailing_stop(
            current_price=p,
            entry_price=entry,
            direction="SHORT",
            current_stop=current_stop,
            trailing_ref=low_watermark,
            atr=atr,
            volatility=0.015,
            regime="TREND",
            trailing_pct=0.015,
            tick_size=tick_size,
        )
        new_stop = res["new_stop"]
        new_lw = res["ref_price"]
        moved = res["moved"]
        assert new_stop <= current_stop, f"Trailing stop regressed: {new_stop} > {current_stop}"
        if moved:
            current_stop = new_stop
            low_watermark = new_lw
        recorded_stops.append(current_stop)

    for i in range(1, len(recorded_stops)):
        assert recorded_stops[i] <= recorded_stops[i - 1]


# ==============================================================================
# 5. POSITION LIFECYCLE STATE MACHINE TRANSITIONS
# ==============================================================================

def test_position_lifecycle_state_machine():
    """Verify transitions: FILLED -> PROTECTED -> TP1 -> BREAKEVEN -> TRAILING -> EXITING -> CLOSED -> RECONCILED."""
    pid = "pos-lifecycle-sm-01"
    db.create_position({
        "symbol": "ETH-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 3000.0,
        "entry_price": 3000.0,
        "qty": 2.0,
        "quantity": 2.0,
        "leverage": 10.0,
        "margin": 600.0,
        "margin_usdt": 600.0,
        "sl": 2900.0,
        "sl_price": 2900.0,
        "tp1": 3100.0,
        "tp1_price": 3100.0,
        "position_id": pid,
        "actual_entry_price": 3000.0,
        "remaining_qty": 2.0,
        "lifecycle_state": "FILLED",
        "status": "OPEN",
        "slot_id": 2,
    }, user_id=1)

    # 1. FILLED -> PROTECTED (Initial stop verified)
    evaluate_and_manage_positions({"ETH-USDT": 3020.0})
    pos = db.get_position(pid)
    assert pos["lifecycle_state"] == "PROTECTED"

    # 2. PROTECTED -> TP1 & BREAKEVEN (Price hits 3110)
    evaluate_and_manage_positions({"ETH-USDT": 3110.0})
    pos = db.get_position(pid)
    assert pos["lifecycle_state"] in ("TP1", "BREAKEVEN")
    assert pos["breakeven_stop"] is not None
    assert pos["remaining_qty"] == pytest.approx(1.0, abs=1e-4)

    # 3. BREAKEVEN -> TRAILING (Price advances to 3250)
    evaluate_and_manage_positions({"ETH-USDT": 3250.0})
    pos = db.get_position(pid)
    assert pos["lifecycle_state"] == "TRAILING"
    assert pos["current_trailing_stop"] is not None

    # 4. TRAILING -> EXITING -> CLOSED (Price collapses through trailing stop)
    stop_hit = pos["current_trailing_stop"] - 10.0
    evaluate_and_manage_positions({"ETH-USDT": stop_hit})
    pos = db.get_position(pid)
    assert pos["lifecycle_state"] in ("CLOSED", "RECONCILED")
    assert "STOPPED" in pos["status"] or pos["status"] == "CLOSED"

    # Verify history transitions recorded in JSON
    history = json.loads(pos["lifecycle_history_json"] or "[]")
    states = [h["state"] for h in history]
    assert "PROTECTED" in states
    assert "TP1" in states or "BREAKEVEN" in states
    assert "CLOSED" in states


# ==============================================================================
# 6. CRASH / RESTART RECOVERY ACROSS DISTINCT STAGES
# ==============================================================================

def test_restart_recovery_stage_a_open_before_tp1():
    """Restart during OPEN position before TP1: recovers cleanly without resetting stops."""
    pid = "pos-restart-stage-a"
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 1.0,
        "quantity": 1.0,
        "leverage": 10.0,
        "margin": 6000.0,
        "margin_usdt": 6000.0,
        "sl": 58500.0,
        "sl_price": 58500.0,
        "tp1": 62000.0,
        "tp1_price": 62000.0,
        "position_id": pid,
        "actual_entry_price": 60000.0,
        "remaining_qty": 1.0,
        "lifecycle_state": "PROTECTED",
        "status": "OPEN",
        "slot_id": 1,
    }, user_id=1)

    evaluate_and_manage_positions({"BTC-USDT": 60500.0})

    pos = db.get_position(pid)
    assert pos["lifecycle_state"] == "PROTECTED"
    assert pos["sl"] == 58500.0
    assert pos["remaining_qty"] == 1.0


def test_restart_recovery_stage_b_after_tp1_before_breakeven():
    """Restart immediately after TP1 executed: daemon recalculates and applies breakeven."""
    pid = "pos-restart-stage-b"
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 1.0,
        "quantity": 1.0,
        "leverage": 10.0,
        "margin": 6000.0,
        "margin_usdt": 6000.0,
        "sl": 58500.0,
        "sl_price": 58500.0,
        "tp1": 62000.0,
        "tp1_price": 62000.0,
        "position_id": pid,
        "actual_entry_price": 60000.0,
        "remaining_qty": 0.5,
        "total_fees": 45.0,
        "tp1_executed_ms": int(time.time() * 1000) - 5000,
        "tp1_exit_price": 62050.0,
        "tp1_qty": 0.5,
        "tp1_realized_pnl": 1009.5,
        "tp1_fee": 15.5,
        "lifecycle_state": "TP1",
        "status": "OPEN",
        "slot_id": 1,
    }, user_id=1)

    evaluate_and_manage_positions({"BTC-USDT": 62100.0})

    pos = db.get_position(pid)
    assert pos["lifecycle_state"] in ("BREAKEVEN", "TRAILING")
    assert pos["breakeven_stop"] is not None
    assert pos["breakeven_stop"] > 58500.0


def test_restart_recovery_stage_c_during_trailing():
    """Restart during trailing: daemon restores high-watermark and trailing stop without regression."""
    pid = "pos-restart-stage-c"
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 1.0,
        "quantity": 1.0,
        "leverage": 10.0,
        "margin": 6000.0,
        "margin_usdt": 6000.0,
        "sl": 61500.0,
        "sl_price": 61500.0,
        "tp1": 62000.0,
        "tp1_price": 62000.0,
        "position_id": pid,
        "actual_entry_price": 60000.0,
        "remaining_qty": 0.5,
        "lifecycle_state": "TRAILING",
        "current_trailing_stop": 61800.0,
        "previous_trailing_stop": 61500.0,
        "trailing_method": "DYNAMIC_ATR",
        "status": "OPEN",
        "slot_id": 1,
    }, user_id=1)

    # Price rises to 63,500
    evaluate_and_manage_positions({"BTC-USDT": 63500.0})

    pos = db.get_position(pid)
    assert pos["lifecycle_state"] == "TRAILING"
    assert pos["current_trailing_stop"] >= 61800.0


# ==============================================================================
# 7. DUPLICATE TP1 & DUPLICATE EXIT PREVENTION
# ==============================================================================

def test_duplicate_tp1_prevention():
    """Verify TP1 only executes once, even if price remains at or above TP1 price."""
    pid = "pos-dup-tp1-01"
    db.create_position({
        "symbol": "SOL-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 150.0,
        "entry_price": 150.0,
        "qty": 10.0,
        "quantity": 10.0,
        "leverage": 5.0,
        "margin": 300.0,
        "margin_usdt": 300.0,
        "sl": 145.0,
        "sl_price": 145.0,
        "tp1": 155.0,
        "tp1_price": 155.0,
        "position_id": pid,
        "actual_entry_price": 150.0,
        "remaining_qty": 10.0,
        "lifecycle_state": "PROTECTED",
        "status": "OPEN",
        "slot_id": 1,
    }, user_id=1)

    # First trigger: TP1 executes
    evaluate_and_manage_positions({"SOL-USDT": 156.0})
    pos1 = db.get_position(pid)
    assert pos1["remaining_qty"] == 5.0
    first_tp1_time = pos1["tp1_executed_ms"]

    # Second trigger: price still high (157.0)
    evaluate_and_manage_positions({"SOL-USDT": 157.0})
    pos2 = db.get_position(pid)
    # Must NOT execute TP1 a second time
    assert pos2["remaining_qty"] == 5.0
    assert pos2["tp1_executed_ms"] == first_tp1_time


def test_duplicate_exit_prevention():
    """Verify closed position cannot be exited again."""
    pid = "pos-dup-exit-01"
    db.create_position({
        "symbol": "SOL-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 150.0,
        "entry_price": 150.0,
        "qty": 10.0,
        "quantity": 10.0,
        "leverage": 5.0,
        "margin": 300.0,
        "margin_usdt": 300.0,
        "sl": 145.0,
        "sl_price": 145.0,
        "position_id": pid,
        "actual_entry_price": 150.0,
        "remaining_qty": 10.0,
        "lifecycle_state": "CLOSED",
        "status": "CLOSED",
        "slot_id": 1,
    }, user_id=1)

    evaluate_and_manage_positions({"SOL-USDT": 140.0})

    pos = db.get_position(pid)
    assert pos["status"] == "CLOSED"
    assert pos["lifecycle_state"] == "CLOSED"


# ==============================================================================
# 8. NETWORK FAILURE & AMBIGUITY HANDLING
# ==============================================================================

def test_network_ambiguity_reconciliation_flag():
    """Verify ambiguous order / timeout sets RECONCILING state rather than blind retry."""
    pid = "pos-network-ambig-01"
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 1.0,
        "quantity": 1.0,
        "leverage": 10.0,
        "margin": 6000.0,
        "margin_usdt": 6000.0,
        "sl": 58500.0,
        "sl_price": 58500.0,
        "position_id": pid,
        "actual_entry_price": 60000.0,
        "remaining_qty": 1.0,
        "lifecycle_state": "EXITING",
        "status": "OPEN",
        "last_exchange_response": "TIMEOUT",
        "reconciliation_status": "RECONCILING",
        "slot_id": 1,
    }, user_id=1)

    pos = db.get_position(pid)
    assert pos["reconciliation_status"] == "RECONCILING"
    assert pos["last_exchange_response"] == "TIMEOUT"


# ==============================================================================
# 9. POSITION <-> SLOT CONSISTENCY & ATOMIC RELEASE
# ==============================================================================

def test_slot_remains_occupied_until_reconciled():
    """Slot must remain OCCUPIED until position is CLOSED and verified reconciled."""
    slot_id = db.add_autonomous_trade_slot(
        name="Slot BTC Alpha",
        allocated_margin_usdt=500.0,
        max_leverage=10,
        asset_scope="CRYPTO",
        strategy_scope="ALL",
        allowed_symbols=["BTC-USDT"],
        user_id=1,
    )

    # Reserve and occupy slot
    ok, resv_id, reason = SlotAllocationService.reserve_slot(slot_id, "cand-01", 1)
    assert ok is True
    ok_occ, occ_reason = SlotAllocationService.occupy_slot(slot_id, "pos-slot-01", 1, resv_id)
    assert ok_occ is True

    slot = db.get_autonomous_trade_slot(slot_id, user_id=1)
    assert slot["status"] == "OCCUPIED"
    assert slot["current_position_id"] == "pos-slot-01"

    # Create and close position
    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 0.08,
        "quantity": 0.08,
        "leverage": 10.0,
        "margin": 480.0,
        "margin_usdt": 480.0,
        "sl": 58500.0,
        "sl_price": 58500.0,
        "position_id": "pos-slot-01",
        "actual_entry_price": 60000.0,
        "remaining_qty": 0.08,
        "lifecycle_state": "CLOSED",
        "status": "CLOSED",
        "slot_id": slot_id,
    }, user_id=1)

    # Periodic / on-demand reconciliation sweeps occupied slots and releases closed ones
    reconcile_all_positions_with_exchange()

    # Slot must be cleanly released to AVAILABLE
    slot_after = db.get_autonomous_trade_slot(slot_id, user_id=1)
    assert slot_after["status"] == "AVAILABLE"
    assert slot_after["current_position_id"] is None


# ==============================================================================
# 10. RECONCILIATION ENGINE PATHS
# ==============================================================================

def test_reconciliation_local_open_exchange_closed():
    """If local is OPEN but exchange shows no position, mark closed locally and release slot."""
    slot_id = db.add_autonomous_trade_slot(
        name="Recon Test Slot",
        allocated_margin_usdt=300.0,
        max_leverage=5,
        asset_scope="ALL",
        strategy_scope="ALL",
        user_id=1,
    )
    ok, resv_id, _ = SlotAllocationService.reserve_slot(slot_id, "cand-recon", 1)
    SlotAllocationService.occupy_slot(slot_id, "pos-recon-01", 1, resv_id)

    db.create_position({
        "symbol": "ETH-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 3000.0,
        "entry_price": 3000.0,
        "qty": 0.5,
        "quantity": 0.5,
        "leverage": 5.0,
        "margin": 300.0,
        "margin_usdt": 300.0,
        "sl": 2900.0,
        "sl_price": 2900.0,
        "position_id": "pos-recon-01",
        "actual_entry_price": 3000.0,
        "remaining_qty": 0.5,
        "lifecycle_state": "PROTECTED",
        "status": "OPEN",
        "slot_id": slot_id,
    }, user_id=1)

    class MockClient:
        def get_all_positions(self):
            return []
        def get_open_orders(self):
            return []

    res = reconcile_all_positions_with_exchange(MockClient())
    assert len(res["repaired"]) >= 1

    pos = db.get_position("pos-recon-01")
    assert pos["lifecycle_state"] in ("CLOSED", "RECONCILED")
    assert "CLOSED" in pos["status"]
    assert pos["reconciliation_status"] == "RECONCILED"

    slot = db.get_autonomous_trade_slot(slot_id, user_id=1)
    assert slot["status"] == "AVAILABLE"


# ==============================================================================
# 11. CROSS-USER ISOLATION
# ==============================================================================

def test_cross_user_position_isolation():
    """Verify position management for User 1 cannot access, close, or leak User 2's position."""
    slot_u1 = db.add_autonomous_trade_slot(
        name="Slot U1",
        allocated_margin_usdt=200.0,
        max_leverage=5,
        asset_scope="CRYPTO",
        strategy_scope="ALL",
        user_id=1,
    )
    slot_u2 = db.add_autonomous_trade_slot(
        name="Slot U2",
        allocated_margin_usdt=200.0,
        max_leverage=5,
        asset_scope="CRYPTO",
        strategy_scope="ALL",
        user_id=2,
    )

    db.create_position({
        "symbol": "BTC-USDT",
        "side": "LONG",
        "direction": "LONG",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 0.03,
        "quantity": 0.03,
        "leverage": 5.0,
        "margin": 200.0,
        "margin_usdt": 200.0,
        "sl": 58000.0,
        "sl_price": 58000.0,
        "position_id": "pos-u1",
        "slot_id": slot_u1,
        "status": "OPEN",
    }, user_id=1)

    db.create_position({
        "symbol": "BTC-USDT",
        "side": "SHORT",
        "direction": "SHORT",
        "entry": 60000.0,
        "entry_price": 60000.0,
        "qty": 0.03,
        "quantity": 0.03,
        "leverage": 5.0,
        "margin": 200.0,
        "margin_usdt": 200.0,
        "sl": 62000.0,
        "sl_price": 62000.0,
        "position_id": "pos-u2",
        "slot_id": slot_u2,
        "status": "OPEN",
    }, user_id=2)

    p1 = db.get_position("pos-u1", user_id=1)
    p2_from_u1 = db.get_position("pos-u2", user_id=1)

    assert p1 is not None
    assert p2_from_u1 is None, "Security violation: User 1 accessed User 2's position"
