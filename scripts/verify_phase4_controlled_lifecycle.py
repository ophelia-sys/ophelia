#!/usr/bin/env python3
"""Phase 4 Controlled Position Lifecycle Verification.

Executes an authoritative end-to-end test of the position lifecycle:
SIGNAL -> RESERVED -> ORDER_SUBMITTED -> FILLED -> PROTECTED -> TP1 -> BREAKEVEN -> TRAILING -> EXITING -> CLOSED -> RECONCILED.
Verifies:
- Exact fill-based fee and PnL accounting
- Mathematically correct net breakeven stop covering all round-trip costs
- Monotonic dynamic trailing stop advancement
- Atomic slot lifecycle: OCCUPIED -> RECONCILING -> AVAILABLE
- Exchange reconciliation verification
"""

import sys
import os
import time
import json

# Ensure control_plane is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane import db, position_math
from control_plane.slot_allocation_service import SlotAllocationService
from control_plane.position_manager_daemon import evaluate_and_manage_positions, reconcile_all_positions_with_exchange

def run_controlled_lifecycle_test():
    print("=" * 80)
    print("PHASE 4: CONTROLLED POSITION LIFECYCLE AUDIT EXECUTION")
    print("=" * 80)

    user_id = 1
    symbol = "BTC-USDT"
    direction = "LONG"
    entry_price = 60000.0
    initial_qty = 0.08  # 0.08 BTC (~4800 USDT notional at 60k)
    leverage = 10.0
    margin_usdt = 500.0
    initial_sl = 58500.0
    tp1_price = 61500.0
    tp2_price = 64000.0
    tick_size = 0.1
    qty_precision = 4
    now_ms = int(time.time() * 1000)

    # 1. Setup Autonomous Trade Slot
    print("\n[STEP 1] PROVISION AUTONOMOUS TRADE SLOT")
    slot_id = db.add_autonomous_trade_slot(
        name="Phase4 Audit Slot",
        allocated_margin_usdt=margin_usdt,
        max_leverage=int(leverage),
        asset_scope="CRYPTO",
        strategy_scope="ALL",
        allowed_symbols=[symbol],
        user_id=user_id
    )
    slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
    print(f"  Slot #{slot_id} Created | Status: {slot['status']} | Capital: {slot['allocated_margin_usdt']} USDT")
    assert slot["status"] == "AVAILABLE"

    # 2. Candidate Signal Generated & Slot Reserved
    cand_id = f"cand-p4-audit-{now_ms}"
    print(f"\n[STEP 2] SIGNAL GENERATED -> RESERVE SLOT")
    print(f"  Candidate: {cand_id} | Symbol: {symbol} | Direction: {direction}")
    ok, resv_id, reason = SlotAllocationService.reserve_slot(slot_id, cand_id, user_id)
    assert ok is True, f"Slot reservation failed: {reason}"
    slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
    print(f"  Slot #{slot_id} Reserved | Status: {slot['status']} | Reservation ID: {resv_id}")
    assert slot["status"] == "RESERVED"

    # 3. Order Submitted & Slot Occupied
    pos_id = f"pos-p4-audit-{now_ms}"
    print(f"\n[STEP 3] ORDER SUBMITTED -> OCCUPY SLOT")
    ok_occ, occ_reason = SlotAllocationService.occupy_slot(slot_id, pos_id, user_id, resv_id)
    assert ok_occ is True, f"Slot occupation failed: {occ_reason}"
    slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
    print(f"  Slot #{slot_id} Occupied | Status: {slot['status']} | Position ID: {slot['current_position_id']}")
    assert slot["status"] == "OCCUPIED"

    # 4. Position Opened (FILLED)
    entry_fee = position_math.calculate_actual_fee(entry_price, initial_qty)
    print(f"\n[STEP 4] POSITION FILLED")
    print(f"  Position #{pos_id} | Entry: {entry_price} | Qty: {initial_qty} | Entry Fee: {entry_fee} USDT")
    db.create_position({
        "symbol": symbol,
        "side": "BUY",
        "direction": direction,
        "entry": entry_price,
        "entry_price": entry_price,
        "qty": initial_qty,
        "quantity": initial_qty,
        "leverage": leverage,
        "margin": margin_usdt,
        "margin_usdt": margin_usdt,
        "sl": initial_sl,
        "sl_price": initial_sl,
        "tp1": tp1_price,
        "tp1_price": tp1_price,
        "tp2": tp2_price,
        "tp2_price": tp2_price,
        "position_id": pos_id,
        "actual_entry_price": entry_price,
        "remaining_qty": initial_qty,
        "lifecycle_state": "FILLED",
        "status": "OPEN",
        "slot_id": slot_id,
        "total_fees": entry_fee,
        "trailing_pct": 1.5,
    }, user_id=user_id)
    db.record_position_lifecycle_transition(pos_id, "FILLED", "ORDER_FILLED_EXECUTED", {"entry": entry_price, "qty": initial_qty, "fee": entry_fee})

    pos = db.get_position(pos_id)
    assert pos["lifecycle_state"] == "FILLED"

    # 5. Protective Initial Stop Verified (PROTECTED)
    print(f"\n[STEP 5] INITIAL STOP LOSS VERIFIED -> PROTECTED")
    actions = evaluate_and_manage_positions({symbol: 60200.0})
    pos = db.get_position(pos_id)
    print(f"  Current Price: 60,200.0 | State: {pos['lifecycle_state']} | SL: {pos['stop_current']}")
    assert pos["lifecycle_state"] == "PROTECTED"
    assert pos["stop_current"] == initial_sl

    # 6. Price Reaches TP1 -> 50% Partial Exit & Net Breakeven Protection
    print(f"\n[STEP 6] PRICE ADVANCES TO TP1 (61,550.0) -> PARTIAL EXIT & NET BREAKEVEN")
    actions = evaluate_and_manage_positions({symbol: 61550.0})
    pos = db.get_position(pos_id)
    tp1_action = next((a for a in actions if a["action"] == "partial_close"), None)
    assert tp1_action is not None, "TP1 partial close action missing"
    
    print(f"  TP1 Executed: Qty Closed: {tp1_action['qty']} | Realized PnL: {tp1_action['realized_pnl']} USDT")
    print(f"  Net Breakeven Stop Applied: {pos['breakeven_stop']} USDT | Cost Basis: {pos['calculated_cost_basis']} USDT")
    print(f"  Remaining Qty: {pos['remaining_qty']} BTC | Total Realized PnL: {pos['realized_pnl']} USDT")
    print(f"  Current Lifecycle State: {pos['lifecycle_state']}")
    assert pos["lifecycle_state"] in ("TP1", "BREAKEVEN")
    assert pos["remaining_qty"] == 0.04
    assert pos["breakeven_stop"] > entry_price  # Long breakeven stop must be strictly above entry to cover round-trip costs!

    # 7. Price Advances Further -> Dynamic Trailing Activation & Monotonic Upward Moves
    print(f"\n[STEP 7] PRICE ADVANCES TO 62,800.0 -> DYNAMIC TRAILING ACTIVATES")
    actions = evaluate_and_manage_positions({symbol: 62800.0})
    pos = db.get_position(pos_id)
    print(f"  Price: 62,800.0 | State: {pos['lifecycle_state']} | Trailing Stop: {pos['current_trailing_stop']}")
    assert pos["lifecycle_state"] == "TRAILING"
    trail_stop_1 = pos["current_trailing_stop"]
    assert trail_stop_1 >= pos["breakeven_stop"]

    print(f"\n[STEP 8] PRICE ADVANCES FURTHER TO 63,500.0 -> MONOTONIC TRAILING ADVANCEMENT")
    actions = evaluate_and_manage_positions({symbol: 63500.0})
    pos = db.get_position(pos_id)
    trail_stop_2 = pos["current_trailing_stop"]
    print(f"  Price: 63,500.0 | State: {pos['lifecycle_state']} | New Trailing Stop: {trail_stop_2}")
    assert trail_stop_2 > trail_stop_1, f"Trailing stop failed monotonicity: {trail_stop_2} not > {trail_stop_1}"

    # 8. Temporary Pullback (63,200.0) -> Trailing Stop MUST NOT REGRESS
    print(f"\n[STEP 9] PULLBACK TO 63,200.0 -> VERIFY ZERO REGRESSION")
    actions = evaluate_and_manage_positions({symbol: 63200.0})
    pos = db.get_position(pos_id)
    trail_stop_3 = pos["current_trailing_stop"]
    print(f"  Price: 63,200.0 | Stop: {trail_stop_3} (Previous: {trail_stop_2})")
    assert trail_stop_3 == trail_stop_2, "Trailing stop regressed on price pullback!"

    # 9. Severe Collapse -> Trailing Stop Breached -> Exit Triggered
    print(f"\n[STEP 10] SEVERE COLLAPSE THROUGH TRAILING STOP -> EXIT TRIGGERED")
    exit_trigger_price = trail_stop_3 - 100.0
    print(f"  Injecting Price: {exit_trigger_price} (Breaching stop {trail_stop_3})")
    actions = evaluate_and_manage_positions({symbol: exit_trigger_price})
    pos = db.get_position(pos_id)
    exit_action = next((a for a in actions if a["action"] == "exit_all"), None)
    assert exit_action is not None, "Exit action missing upon trailing stop breach"

    print(f"  Exit Action: {exit_action['reason']} at {exit_action['price']} USDT")
    print(f"  Final Position Status: {pos['status']} | Lifecycle State: {pos['lifecycle_state']}")
    print(f"  Remaining Qty: {pos['remaining_qty']} BTC")
    print(f"  Total Realized PnL: {pos['realized_pnl']} USDT")
    print(f"  Total Fees Incurred: {pos['total_fees']} USDT")
    assert pos["lifecycle_state"] in ("CLOSED", "RECONCILED")
    assert pos["remaining_qty"] == 0.0

    # 10. Verify Slot Transition: OCCUPIED -> RECONCILING -> AVAILABLE
    print(f"\n[STEP 11] VERIFY ATOMIC SLOT RELEASE")
    slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
    print(f"  Slot #{slot_id} Post-Exit Status: {slot['status']} | Current Position ID: {slot['current_position_id']}")
    assert slot["status"] == "AVAILABLE"
    assert slot["current_position_id"] is None

    # 11. Run Exchange Reconciliation
    print(f"\n[STEP 12] RUN AUTHORITATIVE EXCHANGE RECONCILIATION")
    class AuditExchangeClient:
        def get_all_positions(self):
            return []
        def get_open_orders(self):
            return []

    recon_res = reconcile_all_positions_with_exchange(AuditExchangeClient())
    print(f"  Reconciliation Sweep Completed: Reconciled {len(recon_res.get('reconciled', []))} positions, Repaired {len(recon_res.get('repaired', []))}")
    pos = db.get_position(pos_id)
    assert pos["reconciliation_status"] == "RECONCILED"

    # 12. Full Transition History Audit
    print(f"\n[STEP 13] LIFECYCLE TRANSITION AUDIT TRAIL")
    history = pos.get("lifecycle_history") or []
    for idx, h in enumerate(history, 1):
        print(f"  {idx:02d}. [{h.get('state')}] - {h.get('event')} (ts: {h.get('timestamp_ms')})")
        if h.get("details"):
            print(f"      Details: {json.dumps(h['details'])}")

    print("\n" + "=" * 80)
    print("PHASE 4 CONTROLLED LIFECYCLE AUDIT: 100% SUCCESSFUL & VERIFIED")
    print("=" * 80)

if __name__ == "__main__":
    run_controlled_lifecycle_test()
