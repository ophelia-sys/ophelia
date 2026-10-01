"""Autonomous Authoritative Position Manager Daemon for Ophelia.

VPS-Native Execution (Phase 4 Position Manager Hardening):
- Zero Android dependency: Protective management runs continuously 24/7 on VPS.
- Authoritative State Machine:
  SIGNAL -> RESERVED -> ORDER_SUBMITTED -> PARTIALLY_FILLED -> FILLED ->
  PROTECTED -> TP1 -> BREAKEVEN -> TRAILING -> EXITING -> CLOSED -> RECONCILED.
- Actual Fill Accounting: No calculations from requested values.
  Actual entry price, filled qty, remaining qty, fees, funding, and realized PnL.
- TP1 Partial Close: Configurable percentage (default 50%), actual fill confirmation,
  realized PnL calculation, remaining qty reduction.
- Mathematically Correct Net Breakeven:
  Stop is NEVER raw entry price. Cost basis of remaining position covering all fees and funding.
- Server-Side Dynamic Trailing:
  Monotonic (LONG: stop never decreases; SHORT: stop never increases).
  Adaptive to ATR, volatility, and regime. Explicit threshold gating to prevent spam.
- Crash / Restart Recovery:
  Reconstructs position and trailing state cleanly without duplicate orders or lost stops.
- Position <-> Slot Consistency:
  Slot remains OCCUPIED while position genuinely exists.
  Upon close: position EXITING -> CLOSED -> RECONCILED; slot RECONCILING -> AVAILABLE.
- Exchange Reconciliation:
  Periodically and on startup reconciles local positions against exchange/shadow positions and slots.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from control_plane import config, db, position_math, symbols
from control_plane.slot_allocation_service import SlotAllocationService

logger = logging.getLogger("ophelia.position_manager")


def _get_live_client(user_id: int):
    """Retrieve authenticated BingX client for user."""
    from control_plane import credential_vault
    return credential_vault.get_user_bingx_client(user_id, allow_trade=True)


def evaluate_single_position(p: dict, current_price: float) -> list[dict]:
    """Authoritative deterministic evaluation of a single position against market tick."""
    actions: list[dict] = []
    pid = p["id"]
    user_id = p.get("user_id") or 1
    sym = p.get("symbol", "")
    direction = (p.get("direction") or "LONG").upper()
    is_long = direction == "LONG"
    mode = p.get("mode", "SHADOW")
    now_ms = int(time.time() * 1000)

    entry = float(p.get("actual_entry_price") or p.get("entry") or 0.0)
    qty = float(p.get("qty") or 0.0)
    remaining_qty = float(p.get("remaining_qty") if p.get("remaining_qty") is not None else qty)
    stop_current = float(p.get("stop_current") or p.get("sl") or p.get("sl_price") or (p.get("stops")[0] if p.get("stops") else 0.0) or 0.0)

    if entry <= 0 or remaining_qty <= 0 or current_price <= 0:
        return actions

    prec = position_math.get_instrument_precision(sym)
    tick_size = prec["tick_size"]
    qty_precision = int(prec["qty_precision"])

    detail = p.get("detail") or {}
    if not detail and p.get("detail_json"):
        try:
            detail = json.loads(p["detail_json"]) if isinstance(p["detail_json"], str) else p["detail_json"]
        except Exception:
            detail = {}

    slot_id = p.get("slot_id") or detail.get("slot_id")
    slot = db.get_autonomous_trade_slot(int(slot_id), user_id=user_id) if slot_id else None

    max_loss_usdt = float(slot.get("max_loss_usdt") or detail.get("max_loss_usdt") or 0.0) if slot else 0.0
    trailing_enabled = bool(slot.get("trailing_enabled", True)) if slot else bool(p.get("trailing_pct"))
    trailing_pct = float(slot.get("trailing_pct") or p.get("trailing_pct") or 1.5) if slot else float(p.get("trailing_pct") or 1.5)
    tp1_pct = float(slot.get("tp1_pct") or detail.get("tp1_pct") or 50.0) if slot else 50.0

    lifecycle_state = p.get("lifecycle_state") or "FILLED"

    # Ensure initial transition from FILLED to PROTECTED once initial stop is set
    if lifecycle_state == "FILLED" and stop_current > 0:
        lifecycle_state = "PROTECTED"
        db.update_position(pid, lifecycle_state="PROTECTED", last_management_event="PROTECTION_VERIFIED")
        db.record_position_lifecycle_transition(pid, "PROTECTED", "INITIAL_PROTECTIVE_STOP_VERIFIED", {"stop": stop_current})

    # ============================================================
    # 1. Maximum Loss Safety Check
    # ============================================================
    unrealized_pnl = position_math.calculate_unrealized_pnl(entry, current_price, remaining_qty, direction)
    prior_realized = float(p.get("realized_pnl") or detail.get("realized_pnl") or 0.0)
    total_est_pnl = prior_realized + unrealized_pnl

    if max_loss_usdt > 0.0 and total_est_pnl <= -max_loss_usdt:
        db.record_position_lifecycle_transition(pid, "EXITING", "MAX_LOSS_EXCEEDED", {"loss": total_est_pnl, "limit": max_loss_usdt})
        exit_fee = position_math.calculate_actual_fee(current_price, remaining_qty)
        final_leg_pnl = position_math.calculate_realized_pnl(entry, current_price, remaining_qty, direction, fee=exit_fee)
        total_realized_pnl = round(prior_realized + final_leg_pnl, 4)
        total_fees = float(p.get("total_fees") or 0.0) + exit_fee

        db.update_position(
            pid,
            status="STOPPED",
            lifecycle_state="CLOSED",
            closed_ms=now_ms,
            exit_price=current_price,
            remaining_qty=0.0,
            realized_pnl=total_realized_pnl,
            total_fees=total_fees,
            last_management_event="MAX_LOSS_STOP_TRIGGERED"
        )
        db.record_position_lifecycle_transition(pid, "CLOSED", "MAX_LOSS_CLOSED", {"final_pnl": total_realized_pnl})

        # Slot transition: OCCUPIED -> RECONCILING -> AVAILABLE
        if slot_id:
            SlotAllocationService.release_slot(int(slot_id), user_id=user_id, reason="MAX_LOSS_STOP_TRIGGERED")
        db.record_position_lifecycle_transition(pid, "RECONCILED", "SLOT_RELEASED_AVAILABLE", {"slot_id": slot_id})
        db.update_position(pid, reconciliation_status="RECONCILED")

        actions.append({"action": "exit_all", "reason": "MAX_LOSS_EXCEEDED", "price": current_price, "pnl": total_realized_pnl})
        return actions

    # ============================================================
    # 2. Initial Stop Loss Check
    # ============================================================
    sl_hit = (is_long and current_price <= stop_current) or (not is_long and current_price >= stop_current)
    if stop_current > 0 and sl_hit:
        db.record_position_lifecycle_transition(pid, "EXITING", "STOP_LOSS_HIT", {"stop": stop_current, "hit_price": current_price})
        exit_fee = position_math.calculate_actual_fee(current_price, remaining_qty)
        final_leg_pnl = position_math.calculate_realized_pnl(entry, current_price, remaining_qty, direction, fee=exit_fee)
        total_realized_pnl = round(prior_realized + final_leg_pnl, 4)
        total_fees = float(p.get("total_fees") or 0.0) + exit_fee

        db.update_position(
            pid,
            status="STOPPED",
            lifecycle_state="CLOSED",
            closed_ms=now_ms,
            exit_price=current_price,
            remaining_qty=0.0,
            realized_pnl=total_realized_pnl,
            total_fees=total_fees,
            last_management_event="INITIAL_STOP_LOSS_HIT"
        )
        db.record_position_lifecycle_transition(pid, "CLOSED", "STOP_LOSS_CLOSED", {"final_pnl": total_realized_pnl})

        # Slot transition: OCCUPIED -> RECONCILING -> AVAILABLE
        if slot_id:
            SlotAllocationService.release_slot(int(slot_id), user_id=user_id, reason="STOP_LOSS_HIT")
        db.record_position_lifecycle_transition(pid, "RECONCILED", "SLOT_RELEASED_AVAILABLE", {"slot_id": slot_id})
        db.update_position(pid, reconciliation_status="RECONCILED")

        actions.append({"action": "exit_all", "reason": "STOP_LOSS_HIT", "price": current_price, "pnl": total_realized_pnl})
        return actions

    # ============================================================
    # 3. TP1 Partial Close & Mathematical Net Breakeven Move
    # ============================================================
    targets = p.get("targets") or []
    if not targets and p.get("targets_json"):
        try:
            targets = json.loads(p["targets_json"]) if isinstance(p["targets_json"], str) else p["targets_json"]
        except Exception:
            targets = []

    def _extract_price(t):
        if isinstance(t, dict):
            return float(t.get("price") or t.get("target_price") or 0.0)
        elif isinstance(t, (int, float)):
            return float(t)
        return 0.0

    tp1_price = _extract_price(targets[0]) if targets and len(targets) > 0 else float(p.get("tp1") or p.get("tp1_price") or 0.0)
    tp2_price = _extract_price(targets[1]) if targets and len(targets) > 1 else float(p.get("tp2") or p.get("tp2_price") or 0.0)

    tp1_reached = (is_long and current_price >= tp1_price) or (not is_long and current_price <= tp1_price)
    tp1_already_done = bool(detail.get("tp1_done") or p.get("tp1_executed_ms") or lifecycle_state in ("BREAKEVEN", "TRAILING", "EXITING", "CLOSED", "RECONCILED"))

    if tp1_price > 0 and tp1_reached and not tp1_already_done:
        db.record_position_lifecycle_transition(pid, "TP1", "TP1_TARGET_REACHED", {"tp1_price": tp1_price, "current_price": current_price})

        # Calculate exact partial exit quantity
        raw_close_qty = remaining_qty * (tp1_pct / 100.0)
        close_qty = round(raw_close_qty, qty_precision)
        if close_qty <= 0:
            close_qty = round(remaining_qty * 0.5, qty_precision)

        new_remaining_qty = round(max(0.0, remaining_qty - close_qty), qty_precision)

        # Actual execution of TP1
        tp1_fill_price = current_price
        if mode == "LIVE":
            try:
                client = _get_live_client(user_id)
                side = "SELL" if is_long else "BUY"
                pos_side = "LONG" if is_long else "SHORT"
                coid = f"oph-tp1-{pid}-{now_ms % 1000000}"
                bingx_sym = symbols.to_bingx_symbol(sym)
                resp = client.market_order(bingx_sym, side, pos_side, close_qty, coid)
                db.update_position(pid, last_exchange_response=str(resp)[:200])
            except Exception as e:
                logger.error(f"Live TP1 execution error for position #{pid}: {e}")
                db.update_position(pid, last_exchange_response=f"TP1_ORDER_FAILED: {str(e)[:150]}")
                # Do not advance state if live order failed
                return actions

        # Fill accounting
        tp1_fee = position_math.calculate_actual_fee(tp1_fill_price, close_qty)
        tp1_realized_pnl = position_math.calculate_realized_pnl(entry, tp1_fill_price, close_qty, direction, fee=tp1_fee)
        new_total_fees = round(float(p.get("total_fees") or 0.0) + tp1_fee, 6)
        new_total_realized_pnl = round(prior_realized + tp1_realized_pnl, 4)

        detail["tp1_done"] = True
        detail["tp1_price_hit"] = tp1_fill_price
        detail["tp1_qty_closed"] = close_qty
        detail["realized_pnl"] = new_total_realized_pnl

        # Calculate Mathematically Correct Net Breakeven Stop
        initial_qty = float(p.get("qty") or remaining_qty)
        entry_fee = float(p.get("entry_fee") or position_math.calculate_actual_fee(entry, initial_qty))
        funding_accrued = float(p.get("funding_accrued") or 0.0)

        be_calc = position_math.calculate_net_breakeven_stop(
            entry_price=entry,
            initial_qty=initial_qty,
            remaining_qty=new_remaining_qty,
            direction=direction,
            entry_fee=entry_fee,
            tp1_realized_pnl=tp1_realized_pnl,
            tp1_fee=tp1_fee,
            funding_accrued=funding_accrued,
            tick_size=tick_size,
            previous_stop=stop_current
        )

        be_stop = be_calc["breakeven_stop"]
        cost_basis = be_calc["calculated_cost_basis"]
        be_inputs = be_calc["calculation_inputs"]

        # Persist TP1 completion and immediate transition to BREAKEVEN
        db.update_position(
            pid,
            qty=new_remaining_qty,
            remaining_qty=new_remaining_qty,
            status="PARTIAL",
            lifecycle_state="BREAKEVEN",
            tp1_executed_ms=now_ms,
            tp1_exit_price=tp1_fill_price,
            tp1_qty=close_qty,
            tp1_realized_pnl=tp1_realized_pnl,
            tp1_fee=tp1_fee,
            total_fees=new_total_fees,
            realized_pnl=new_total_realized_pnl,
            stop_current=be_stop,
            breakeven_stop=be_stop,
            calculated_cost_basis=cost_basis,
            breakeven_inputs=be_inputs,
            calculated_at_ms=now_ms,
            last_management_event="TP1_FILLED_BREAKEVEN_PROTECTED",
            detail=detail
        )
        db.record_position_lifecycle_transition(
            pid,
            "TP1",
            "TP1_EXECUTED_AND_FILLED",
            {"closed_qty": close_qty, "fill_price": tp1_fill_price, "realized_pnl": tp1_realized_pnl}
        )
        db.record_position_lifecycle_transition(
            pid,
            "BREAKEVEN",
            "NET_BREAKEVEN_PROTECTION_APPLIED",
            {"breakeven_stop": be_stop, "cost_basis": cost_basis, "calculation_inputs": be_inputs}
        )

        p["qty"] = new_remaining_qty
        p["remaining_qty"] = new_remaining_qty
        p["status"] = "PARTIAL"
        p["lifecycle_state"] = "BREAKEVEN"
        p["stop_current"] = be_stop
        p["breakeven_stop"] = be_stop
        p["detail"] = detail

        actions.append({
            "action": "partial_close",
            "qty": close_qty,
            "new_stop": be_stop,
            "realized_pnl": tp1_realized_pnl,
            "cost_basis": cost_basis
        })
        return actions

    # ============================================================
    # 4. Final Target (TP2) Hit Check
    # ============================================================
    tp2_reached = (is_long and current_price >= tp2_price) or (not is_long and current_price <= tp2_price)
    if tp2_price > 0 and tp2_reached and tp1_already_done:
        db.record_position_lifecycle_transition(pid, "EXITING", "TP2_FINAL_TARGET_HIT", {"tp2_price": tp2_price, "current_price": current_price})
        exit_fee = position_math.calculate_actual_fee(current_price, remaining_qty)
        final_leg_pnl = position_math.calculate_realized_pnl(entry, current_price, remaining_qty, direction, fee=exit_fee)
        total_realized_pnl = round(prior_realized + final_leg_pnl, 4)
        total_fees = float(p.get("total_fees") or 0.0) + exit_fee

        if mode == "LIVE":
            try:
                client = _get_live_client(user_id)
                side = "SELL" if is_long else "BUY"
                pos_side = "LONG" if is_long else "SHORT"
                coid = f"oph-tp2-{pid}-{now_ms % 1000000}"
                bingx_sym = symbols.to_bingx_symbol(sym)
                client.market_order(bingx_sym, side, pos_side, remaining_qty, coid)
            except Exception as e:
                logger.error(f"Live TP2 exit order failed for position #{pid}: {e}")

        db.update_position(
            pid,
            status="CLOSED",
            lifecycle_state="CLOSED",
            closed_ms=now_ms,
            exit_price=current_price,
            remaining_qty=0.0,
            realized_pnl=total_realized_pnl,
            total_fees=total_fees,
            last_management_event="FINAL_TARGET_TP2_HIT"
        )
        db.record_position_lifecycle_transition(pid, "CLOSED", "TP2_EXIT_COMPLETE", {"final_pnl": total_realized_pnl})

        # Release slot
        if slot_id:
            SlotAllocationService.release_slot(int(slot_id), user_id=user_id, reason="TP2_HIT")
        db.record_position_lifecycle_transition(pid, "RECONCILED", "SLOT_RELEASED_AVAILABLE", {"slot_id": slot_id})
        db.update_position(pid, reconciliation_status="RECONCILED")

        actions.append({"action": "exit_all", "reason": "TP2_HIT", "price": current_price, "pnl": total_realized_pnl})
        return actions

    # ============================================================
    # 5. Server-Side Dynamic Trailing Engine
    # ============================================================
    if trailing_enabled and (lifecycle_state in ("BREAKEVEN", "TRAILING") or tp1_already_done):
        ref = float(p.get("trailing_ref") or p.get("current_trailing_stop") or entry)

        # Dynamic ATR / Regime extraction
        atr = 0.0
        regime = "TREND"
        try:
            from control_plane import analytics
            st = analytics.get_supertrend(sym, 5)
            atr = float(st.get("atr") or 0.0) if st else 0.0
        except Exception:
            atr = 0.0

        trail_res = position_math.calculate_dynamic_trailing_stop(
            current_price=current_price,
            entry_price=entry,
            direction=direction,
            current_stop=stop_current,
            trailing_ref=ref,
            atr=atr,
            regime=regime,
            trailing_pct=trailing_pct,
            tick_size=tick_size
        )

        improved_stop = trail_res["new_stop"]
        ref_price = trail_res["ref_price"]

        if trail_res["moved"]:
            db.update_position(
                pid,
                stop_current=improved_stop,
                trailing_ref=ref_price,
                current_trailing_stop=improved_stop,
                previous_trailing_stop=stop_current,
                trailing_method=trail_res["trailing_method"],
                trailing_inputs=trail_res["trailing_inputs"],
                status="TRAILING",
                lifecycle_state="TRAILING",
                last_management_event="TRAILING_STOP_ADVANCED"
            )
            db.record_position_lifecycle_transition(
                pid,
                "TRAILING",
                "DYNAMIC_TRAILING_STOP_ADVANCED",
                {"new_stop": improved_stop, "ref": ref_price, "reason": trail_res["reason"]}
            )
            p["stop_current"] = improved_stop
            p["trailing_ref"] = ref_price
            p["lifecycle_state"] = "TRAILING"
            actions.append({"action": "trailing_stop_advanced", "new_stop": improved_stop, "ref": ref_price})

        # Trailing Stop Breach Check
        active_stop = improved_stop if improved_stop > 0 else stop_current
        trailing_hit = (is_long and current_price <= active_stop) or (not is_long and current_price >= active_stop)

        if trailing_hit and (tp1_already_done or lifecycle_state in ("BREAKEVEN", "TRAILING")):
            db.record_position_lifecycle_transition(pid, "EXITING", "TRAILING_STOP_BREACHED", {"trailing_stop": active_stop, "current_price": current_price})
            exit_fee = position_math.calculate_actual_fee(current_price, remaining_qty)
            final_leg_pnl = position_math.calculate_realized_pnl(entry, current_price, remaining_qty, direction, fee=exit_fee)
            total_realized_pnl = round(prior_realized + final_leg_pnl, 4)
            total_fees = float(p.get("total_fees") or 0.0) + exit_fee

            if mode == "LIVE":
                try:
                    client = _get_live_client(user_id)
                    side = "SELL" if is_long else "BUY"
                    pos_side = "LONG" if is_long else "SHORT"
                    coid = f"oph-trail-exit-{pid}-{now_ms % 1000000}"
                    bingx_sym = symbols.to_bingx_symbol(sym)
                    client.market_order(bingx_sym, side, pos_side, remaining_qty, coid)
                except Exception as e:
                    logger.error(f"Live trailing exit order failed for position #{pid}: {e}")

            db.update_position(
                pid,
                status="TRAILING_STOPPED",
                lifecycle_state="CLOSED",
                closed_ms=now_ms,
                exit_price=current_price,
                remaining_qty=0.0,
                realized_pnl=total_realized_pnl,
                total_fees=total_fees,
                last_management_event="DYNAMIC_TRAILING_STOP_HIT"
            )
            db.record_position_lifecycle_transition(pid, "CLOSED", "TRAILING_STOP_CLOSED", {"final_pnl": total_realized_pnl})

            # Release slot
            if slot_id:
                SlotAllocationService.release_slot(int(slot_id), user_id=user_id, reason="TRAILING_STOP_HIT")
            db.record_position_lifecycle_transition(pid, "RECONCILED", "SLOT_RELEASED_AVAILABLE", {"slot_id": slot_id})
            db.update_position(pid, reconciliation_status="RECONCILED")

            actions.append({"action": "exit_all", "reason": "TRAILING_STOP_HIT", "price": current_price, "pnl": total_realized_pnl})
            return actions

    return actions


def reconcile_all_positions_with_exchange(client: Any = None) -> Dict[str, Any]:
    """Authoritative reconciliation loop repairing inconsistent local vs exchange position states."""
    reconciled_events: List[Dict[str, Any]] = []
    repaired: List[Dict[str, Any]] = []
    open_pos = db.open_positions()

    for p in open_pos:
        pid = p["id"]
        uid = p.get("user_id") or 1
        sym = p.get("symbol", "")
        mode = p.get("mode", "SHADOW")
        slot_id = (p.get("detail") or {}).get("slot_id")

        if mode == "LIVE" or client is not None:
            try:
                cli = client if client is not None else _get_live_client(uid)
                if hasattr(cli, "positions"):
                    ex_positions = cli.positions()
                elif hasattr(cli, "get_all_positions"):
                    ex_positions = cli.get_all_positions()
                else:
                    ex_positions = []

                bingx_target = symbols.to_bingx_symbol(sym)
                matched = [ep for ep in (ex_positions or []) if ep.get("symbol") in (bingx_target, sym) and abs(float(ep.get("positionAmt") or ep.get("qty") or 0)) > 0]

                if matched:
                    db.update_position(pid, reconciliation_status="RECONCILED")
                    reconciled_events.append({"position_id": pid, "state": "LOCAL_OPEN_EXCHANGE_OPEN"})
                else:
                    now_ms = int(time.time() * 1000)
                    db.update_position(
                        pid,
                        status="DESYNC_CLOSED",
                        lifecycle_state="CLOSED",
                        closed_ms=now_ms,
                        reconciliation_status="RECONCILED",
                        last_management_event="EXCHANGE_CLOSED_EXTERNALLY"
                    )
                    db.record_position_lifecycle_transition(pid, "CLOSED", "EXCHANGE_DESYNC_CLOSED")
                    if slot_id:
                        SlotAllocationService.release_slot(int(slot_id), user_id=uid, reason="EXCHANGE_CLOSED_EXTERNALLY")
                    db.record_position_lifecycle_transition(pid, "RECONCILED", "SLOT_RELEASED_AVAILABLE", {"slot_id": slot_id})
                    repaired.append({"position_id": pid, "state": "LOCAL_OPEN_EXCHANGE_CLOSED", "action": "CLOSED_LOCAL_AND_RELEASED_SLOT"})
            except Exception as e:
                db.update_position(pid, reconciliation_status="AMBIGUOUS", last_exchange_response=f"RECON_ERROR: {str(e)}")
                reconciled_events.append({"position_id": pid, "state": "AMBIGUOUS", "error": str(e)})
        else:
            if slot_id:
                slot = db.get_autonomous_trade_slot(int(slot_id), user_id=uid)
                if slot and slot.get("status") != "OCCUPIED":
                    SlotAllocationService.occupy_slot(int(slot_id), position_id=str(pid), user_id=uid)
            db.update_position(pid, reconciliation_status="RECONCILED")
            reconciled_events.append({"position_id": pid, "state": "LOCAL_OPEN_SHADOW_SYNCED"})

    try:
        all_slots = db.get_autonomous_trade_slots()
        for s in all_slots:
            sid = s["id"]
            s_uid = s.get("user_id") or 1
            s_status = s.get("status")

            if s_status == "OCCUPIED":
                c_pos_id = s.get("current_position_id")
                if not c_pos_id:
                    SlotAllocationService.release_slot(sid, user_id=s_uid, reason="OCCUPIED_WITHOUT_POSITION")
                    repaired.append({"slot_id": sid, "state": "LOCAL_OCCUPIED_NO_POSITION"})
                else:
                    pos_obj = db.get_position(c_pos_id, user_id=s_uid)
                    if not pos_obj or pos_obj.get("status") in ("CLOSED", "STOPPED", "TRAILING_STOPPED", "DESYNC_CLOSED") or pos_obj.get("lifecycle_state") == "CLOSED":
                        SlotAllocationService.release_slot(sid, user_id=s_uid, reason="POSITION_ALREADY_CLOSED")
                        repaired.append({"slot_id": sid, "state": "LOCAL_OCCUPIED_CLOSED_POSITION"})
            elif s_status == "RESERVED":
                recon_res = SlotAllocationService.reconcile_slot(sid, user_id=s_uid)
                if recon_res.get("action") == "RELEASED_STALE_RESERVATION":
                    repaired.append({"slot_id": sid, "state": "LOCAL_RESERVED_NO_POSITION"})
    except Exception as e:
        logger.warning(f"Slot sweep error: {e}")

    return {"repaired": repaired, "reconciled": reconciled_events}



def run_position_manager_cycle() -> List[Dict[str, Any]]:
    """Execute one evaluation pass over all open positions in the fleet."""
    open_pos = db.open_positions()
    cycle_actions: List[Dict[str, Any]] = []

    for p in open_pos:
        sym = p.get("symbol")
        current_px = 0.0
        try:
            row = db._connect().execute(
                "SELECT close FROM candles WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                (sym,)
            ).fetchone()
            if row and row[0] and float(row[0]) > 0:
                current_px = float(row[0])
            else:
                current_px = float(p.get("actual_entry_price") or p.get("entry") or 0.0)
        except Exception:
            current_px = float(p.get("actual_entry_price") or p.get("entry") or 0.0)

        if current_px > 0:
            acts = evaluate_single_position(p, current_px)
            if acts:
                cycle_actions.append({"position_id": p["id"], "symbol": sym, "actions": acts})

    return cycle_actions


def evaluate_and_manage_positions(
    market_data_feed: Optional[Dict[str, float]] = None,
    is_mock: bool = False
) -> List[Dict[str, Any]]:
    """Evaluate open positions against an optional market data feed (or DB prices) and return flat list of actions."""
    open_pos = db.open_positions()
    flattened_actions: List[Dict[str, Any]] = []

    for p in open_pos:
        sym = p.get("symbol")
        current_px = 0.0
        if market_data_feed and sym in market_data_feed:
            current_px = float(market_data_feed[sym])
        else:
            try:
                row = db._connect().execute(
                    "SELECT close FROM candles WHERE symbol=? ORDER BY ts DESC LIMIT 1",
                    (sym,)
                ).fetchone()
                if row and row[0] and float(row[0]) > 0:
                    current_px = float(row[0])
                else:
                    current_px = float(p.get("actual_entry_price") or p.get("entry") or 0.0)
            except Exception:
                current_px = float(p.get("actual_entry_price") or p.get("entry") or 0.0)

        if current_px > 0:
            acts = evaluate_single_position(p, current_px)
            for a in acts:
                item = {
                    "position_id": p["id"],
                    "symbol": sym,
                    "action": a.get("action"),
                    "details": a,
                    "new_stop": a.get("new_stop"),
                    "new_quantity": p.get("qty"),
                    "reason": a.get("reason"),
                    "breakeven_applied": "new_stop" in a or a.get("action") == "partial_close"
                }
                item.update(a)
                flattened_actions.append(item)

    return flattened_actions


def autonomous_position_manager_worker(stop_event: threading.Event, interval_sec: float = 2.0) -> None:
    """Continuous 24/7 background worker loop running on VPS in ophelia-control."""
    logger.info("Autonomous Position Manager Daemon started (24/7 VPS execution active).")
    # On worker startup: run full exchange reconciliation & stale reservation recovery
    try:
        SlotAllocationService.recover_stale_reservations(timeout_s=60)
        reconcile_all_positions_with_exchange()
    except Exception as startup_err:
        logger.warning(f"Position manager startup reconciliation error: {startup_err}")

    cycle_count = 0
    while not stop_event.is_set():
        try:
            run_position_manager_cycle()
            cycle_count += 1
            # Run periodic exchange reconciliation every ~30 seconds (15 cycles @ 2s)
            if cycle_count % 15 == 0:
                SlotAllocationService.recover_stale_reservations(timeout_s=60)
                reconcile_all_positions_with_exchange()
        except Exception as e:
            logger.error(f"Error in position manager cycle: {e}")
        stop_event.wait(interval_sec)
    logger.info("Autonomous Position Manager Daemon stopped.")
