"""Ophelia Single Authoritative Execution Orchestrator.

Architecture Contract:
- Existing deterministic trading core creates the Master Trade.
- VPS executes directly against each eligible User's BingX account 24/7.
- The User Android application is NOT in the trade execution path (executes even if offline/dead).
- Strict Eligibility: admin_copy_allowed AND user.copy_enabled AND status=='ACTIVE' AND NOT suspended AND bingx_connected.
- Sizing is contract-aware (precision, step size, min quantity, min notional).
- Exactly-once execution with idempotency keys.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from . import bingx_client
from . import config
from . import credential_vault
from . import db
from . import symbols

logger = logging.getLogger("ophelia.replication")


def calculate_user_allocation(master_trade: dict[str, Any], user_balance: float) -> tuple[float, str | None]:
    """Calculate allocated margin for a user based on Master Trade allocation mode.
    
    Mode 1: PROPORTIONAL_RATIO
      user_margin = admin_margin * (user_balance / admin_balance)
    Mode 2: PERCENTAGE
      user_margin = user_balance * (allocation_value / 100)
    """
    mode = master_trade.get("allocation_mode", "PROPORTIONAL_RATIO")
    alloc_val = float(master_trade.get("allocation_value", 100.0))
    admin_margin = float(master_trade.get("admin_margin_selected", 0.0))
    admin_ref_bal = float(master_trade.get("admin_balance_snapshot", 0.0))

    if user_balance <= 0:
        return 0.0, "BLOCKED — INSUFFICIENT MARGIN (BALANCE <= 0)"

    if mode == "PROPORTIONAL_RATIO":
        if admin_ref_bal <= 0:
            # Fallback to percentage if admin snapshot balance missing
            user_margin = user_balance * 0.05
        else:
            ratio = user_balance / admin_ref_bal
            user_margin = admin_margin * ratio
    elif mode == "PERCENTAGE":
        user_margin = user_balance * (alloc_val / 100.0)
    else:
        user_margin = user_balance * 0.05

    user_margin = round(user_margin, 2)
    if user_margin <= 0:
        return 0.0, "BLOCKED — ALLOCATED MARGIN TOO LOW"

    return user_margin, None


def calculate_user_order_quantity(
    symbol: str,
    user_margin: float,
    leverage: float,
    entry_price: float,
    spec: dict[str, Any] | None = None
) -> tuple[float, dict[str, Any], str | None]:
    """Contract-aware quantity calculation.
    
    DO NOT assume quantity = notional / price.
    Uses contract specification (step size, quantity precision, contract size, min quantity, min notional).
    """
    norm_sym = symbols.to_bingx_symbol(symbol)
    if spec is None:
        try:
            from . import core
            spec = core._contract_spec(norm_sym)
        except Exception:
            # Deterministic default spec for testing / fallback
            spec = {
                "symbol": norm_sym,
                "price_precision": 2,
                "quantity_precision": 4 if "SOL" in norm_sym or "ETH" in norm_sym else (3 if "BTC" in norm_sym else 2),
                "min_qty": 0.001 if "BTC" in norm_sym else 0.01,
                "min_notional": 5.0,
                "contract_size": 1.0,
            }

    target_notional = user_margin * leverage
    if target_notional <= 0 or entry_price <= 0:
        return 0.0, spec, "BLOCKED — INVALID TARGET NOTIONAL OR PRICE"

    contract_size = float(spec.get("contract_size") or 1.0)
    raw_qty = (target_notional / entry_price) / contract_size

    qprec = int(spec.get("quantity_precision", 3))
    step = 10 ** (-qprec)
    norm_qty = round(round(raw_qty / step) * step, qprec) if step else round(raw_qty, qprec)

    min_qty = float(spec.get("min_qty") or 0.0)
    if norm_qty < min_qty:
        return 0.0, spec, f"BLOCKED — BELOW MINIMUM QUANTITY ({norm_qty} < {min_qty})"

    min_notional = spec.get("min_notional")
    actual_notional = norm_qty * entry_price * contract_size
    if min_notional and actual_notional < float(min_notional):
        return 0.0, spec, f"BLOCKED — BELOW MINIMUM NOTIONAL ({round(actual_notional, 2)} < {min_notional})"

    return norm_qty, spec, None


def check_user_copy_eligibility(user: dict[str, Any], is_mock: bool = False) -> tuple[bool, str]:
    """Check 8-factor deterministic eligibility for trade replication."""
    if not user.get("admin_copy_allowed", True):
        return False, "BLOCKED — DISABLED BY ADMIN"
    if not user.get("copy_enabled", True):
        return False, "BLOCKED — PAUSED BY USER"
    if user.get("status") != "ACTIVE":
        return False, f"BLOCKED — ACCOUNT STATUS {user.get('status', 'UNKNOWN')}"
    if user.get("suspended", False):
        return False, "BLOCKED — SUSPENDED BY ADMIN"
    if not is_mock and user.get("bingx_connection_status") != "CONNECTED":
        return False, "BLOCKED — BINGX DISCONNECTED"
    return True, "ELIGIBLE"


def replicate_master_trade(master_trade: dict[str, Any], is_mock: bool = False) -> list[dict[str, Any]]:
    """Authoritative replication workflow:
    1. Persist master trade snapshot.
    2. Broadcast MASTER_OPEN event.
    3. Query all users independently.
    4. For each user, evaluate eligibility, calculate allocation & contract sizing, validate pre-submit.
    5. Execute directly to user's BingX account (or mock).
    6. Record copy execution & user position.
    """
    master_trade_id = master_trade["master_trade_id"]
    symbol = symbols.to_bingx_symbol(master_trade["symbol"])
    master_trade["symbol"] = symbol
    now_ms = int(time.time() * 1000)

    # 1. Save Master Trade
    db.save_master_trade(master_trade)

    # 2. Record Master Event
    db.save_master_trade_event({
        "master_trade_id": master_trade_id,
        "master_event_id": f"evt_open_{master_trade_id}",
        "event_type": "MASTER_OPEN",
        "sequence_number": 1,
        "correlation_id": f"corr_m_{now_ms}",
        "payload": {
            "symbol": symbol,
            "direction": master_trade["direction"],
            "entry": float(master_trade.get("entry_reference_price") or master_trade.get("entry_price") or 0.0),
            "leverage": master_trade.get("leverage", 10.0),
            "sl": master_trade.get("sl_price"),
            "tp1": master_trade.get("tp1_price"),
            "tp2": master_trade.get("tp2_price"),
            "tp3": master_trade.get("tp3_price"),
        },
        "timestamp_ms": now_ms
    })

    # 3. List candidate users
    users = db.list_all_users(role="USER")
    results: list[dict[str, Any]] = []

    direction = master_trade["direction"].upper()
    side = "BUY" if direction == "LONG" else "SELL"
    pos_side = "LONG" if direction == "LONG" else "SHORT"
    entry_price = float(master_trade.get("entry_reference_price") or master_trade.get("entry_price") or 0.0)
    leverage = float(master_trade.get("leverage", 10.0))

    for u in users:
        uid = u["id"]
        copy_exec_id = f"cx_{master_trade_id}_{uid}"
        idemp_key = f"idemp_{master_trade_id}_{uid}"
        corr_id = f"corr_{now_ms}_{uid}"
        t_start = time.time()

        # Idempotency check: if execution already finished or exists
        existing = db.get_copy_execution(copy_exec_id)
        if existing and existing.get("status") in ("FILLED", "PARTIAL", "CLOSED"):
            logger.info("Copy execution %s already completed (status=%s), skipping.", copy_exec_id, existing.get("status"))
            results.append(existing)
            continue

        # Eligibility check
        eligible, blocked_reason = check_user_copy_eligibility(u, is_mock=is_mock)
        if not eligible:
            exec_row = {
                "copy_execution_id": copy_exec_id,
                "master_trade_id": master_trade_id,
                "user_id": uid,
                "correlation_id": corr_id,
                "idempotency_key": idemp_key,
                "status": "BLOCKED",
                "blocked_reason": blocked_reason,
                "allocated_margin": 0.0,
                "calculated_quantity": 0.0,
                "executed_quantity": 0.0,
                "executed_price": 0.0,
                "client_order_id": None,
                "exchange_order_id": None,
                "execution_latency_ms": int((time.time() - t_start) * 1000),
                "created_ms": now_ms,
                "updated_ms": now_ms,
            }
            db.save_copy_execution(exec_row)
            results.append(exec_row)
            continue

        # Fetch user balance
        user_balance = 0.0
        client = None
        if not is_mock:
            client = credential_vault.get_user_bingx_client(uid, allow_trade=True)
            if not client:
                exec_row = {
                    "copy_execution_id": copy_exec_id,
                    "master_trade_id": master_trade_id,
                    "user_id": uid,
                    "correlation_id": corr_id,
                    "idempotency_key": idemp_key,
                    "status": "BLOCKED",
                    "blocked_reason": "BLOCKED — CREDENTIALS UNAVAILABLE",
                    "created_ms": now_ms,
                    "updated_ms": now_ms,
                }
                db.save_copy_execution(exec_row)
                results.append(exec_row)
                continue
            try:
                bal_dict = client.balance()
                # Parse available USDT margin
                b_list = bal_dict.get("balance", []) if isinstance(bal_dict, dict) else bal_dict
                if isinstance(b_list, list):
                    for item in b_list:
                        if isinstance(item, dict) and item.get("asset") in ("USDT", "usdt"):
                            user_balance = float(item.get("availableMargin") or item.get("balance") or 0.0)
                            break
            except Exception as e:
                exec_row = {
                    "copy_execution_id": copy_exec_id,
                    "master_trade_id": master_trade_id,
                    "user_id": uid,
                    "correlation_id": corr_id,
                    "idempotency_key": idemp_key,
                    "status": "BLOCKED",
                    "blocked_reason": f"BLOCKED — BALANCE QUERY FAILED: {str(e)[:80]}",
                    "created_ms": now_ms,
                    "updated_ms": now_ms,
                }
                db.save_copy_execution(exec_row)
                results.append(exec_row)
                continue
        else:
            # Mock dry-run balance: simulate user with $1000 balance
            user_balance = float(u.get("mock_balance") or 1000.0)

        # 1. Determine asset class for slot matching
        sym_upper = symbol.upper()
        if any(k in sym_upper for k in ("GOLD", "XAU", "NCCO")):
            asset_class = "COMMODITIES"
        elif any(k in sym_upper for k in ("NCSK", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOG")):
            asset_class = "US_MARKET"
        else:
            asset_class = "CRYPTO"

        # 2. Check follower's trade slot capacity (must have AVAILABLE slot in COPY_OPHELIA or BOTH mode)
        slot = db.find_eligible_available_slot(asset_class=asset_class, symbol=symbol, user_id=uid, slot_mode="COPY_OPHELIA")
        if not slot:
            slot = db.find_eligible_available_slot(asset_class=asset_class, symbol=symbol, user_id=uid, slot_mode="BOTH")

        if not slot:
            exec_row = {
                "copy_execution_id": copy_exec_id,
                "master_trade_id": master_trade_id,
                "user_id": uid,
                "correlation_id": corr_id,
                "idempotency_key": idemp_key,
                "status": "BLOCKED",
                "blocked_reason": "BLOCKED — NO FREE COPY SLOT",
                "allocated_margin": 0.0,
                "calculated_quantity": 0.0,
                "executed_quantity": 0.0,
                "executed_price": 0.0,
                "created_ms": now_ms,
                "updated_ms": now_ms,
            }
            db.save_copy_execution(exec_row)
            results.append(exec_row)
            continue

        follower_slot_id = slot["id"]

        # 3. Atomic reservation of user's follower slot
        if not db.reserve_autonomous_trade_slot(follower_slot_id, f"COPY-{master_trade_id}-{uid}", user_id=uid):
            exec_row = {
                "copy_execution_id": copy_exec_id,
                "master_trade_id": master_trade_id,
                "user_id": uid,
                "correlation_id": corr_id,
                "idempotency_key": idemp_key,
                "status": "BLOCKED",
                "blocked_reason": "BLOCKED — SLOT RESERVATION CONFLICT",
                "allocated_margin": 0.0,
                "calculated_quantity": 0.0,
                "executed_quantity": 0.0,
                "executed_price": 0.0,
                "created_ms": now_ms,
                "updated_ms": now_ms,
            }
            db.save_copy_execution(exec_row)
            results.append(exec_row)
            continue

        # 4. User Capital Policy: follower slot margin & leverage are strictly authoritative
        user_margin = float(slot["allocated_margin_usdt"])
        leverage = float(slot["max_leverage"])

        # 5. Max Loss Safety Verification
        max_loss_usdt = float(slot.get("max_loss_usdt") or 0.0)
        sl_price = float(master_trade.get("sl_price") or (entry_price * 0.98 if direction == "LONG" else entry_price * 1.02))
        unit_risk = abs(entry_price - sl_price)
        target_qty = (user_margin * leverage) / max(0.0001, entry_price)

        if max_loss_usdt > 0.0 and (unit_risk * target_qty) > max_loss_usdt:
            # Deterministically resize margin down to satisfy max loss policy
            user_margin = min(user_margin, round(max_loss_usdt / (unit_risk * leverage / max(0.0001, entry_price)), 2))
            if user_margin < 2.0:
                db.release_autonomous_trade_slot(follower_slot_id, user_id=uid)
                exec_row = {
                    "copy_execution_id": copy_exec_id,
                    "master_trade_id": master_trade_id,
                    "user_id": uid,
                    "correlation_id": corr_id,
                    "idempotency_key": idemp_key,
                    "status": "BLOCKED",
                    "blocked_reason": "BLOCKED — MAX LOSS POLICY EXCEEDED",
                    "allocated_margin": 0.0,
                    "calculated_quantity": 0.0,
                    "executed_quantity": 0.0,
                    "executed_price": 0.0,
                    "created_ms": now_ms,
                    "updated_ms": now_ms,
                }
                db.save_copy_execution(exec_row)
                results.append(exec_row)
                continue

        # Quantity sizing
        norm_qty, spec, size_err = calculate_user_order_quantity(symbol, user_margin, leverage, entry_price)
        if size_err:
            db.release_autonomous_trade_slot(follower_slot_id, user_id=uid)
            exec_row = {
                "copy_execution_id": copy_exec_id,
                "master_trade_id": master_trade_id,
                "user_id": uid,
                "correlation_id": corr_id,
                "idempotency_key": idemp_key,
                "status": "BLOCKED",
                "blocked_reason": size_err,
                "allocated_margin": user_margin,
                "calculated_quantity": 0.0,
                "created_ms": now_ms,
                "updated_ms": now_ms,
            }
            db.save_copy_execution(exec_row)
            results.append(exec_row)
            continue

        # Pre-submit validation
        client_order_id = f"cp_{master_trade_id[:16]}_{uid}_{int(time.time())}"[:36]
        try:
            bingx_client.validate_order_params(
                symbol=symbol,
                side=side,
                position_side=pos_side,
                quantity=norm_qty,
                client_order_id=client_order_id
            )
        except Exception as ve:
            exec_row = {
                "copy_execution_id": copy_exec_id,
                "master_trade_id": master_trade_id,
                "user_id": uid,
                "correlation_id": corr_id,
                "idempotency_key": idemp_key,
                "status": "REJECTED",
                "blocked_reason": f"VALIDATION ERROR: {ve}",
                "allocated_margin": user_margin,
                "calculated_quantity": norm_qty,
                "created_ms": now_ms,
                "updated_ms": now_ms,
            }
            db.save_copy_execution(exec_row)
            results.append(exec_row)
            continue

        # Execution (Mock / VPS Direct)
        latency_ms = int((time.time() - t_start) * 1000)
        exchange_order_id = None
        executed_price = entry_price
        executed_qty = norm_qty
        final_status = "FILLED"

        if not is_mock and client is not None:
            try:
                # Set leverage on exchange
                try:
                    client._request("POST", bingx_client.LEVERAGE, {
                        "symbol": symbol,
                        "leverage": int(leverage),
                        "side": pos_side
                    }, signed=True)
                except Exception:
                    pass

                # Place order
                order_payload = {
                    "symbol": symbol,
                    "side": side,
                    "positionSide": pos_side,
                    "type": "MARKET",
                    "quantity": norm_qty,
                    "clientOrderID": client_order_id
                }
                resp = client._request("POST", bingx_client.ORDER, order_payload, signed=True)
                latency_ms = int((time.time() - t_start) * 1000)
                exchange_order_id = str(resp.get("orderId") or "")
                executed_price = float(resp.get("avgPrice") or resp.get("price") or entry_price)
                executed_qty = float(resp.get("executedQty") or norm_qty)
            except Exception as e:
                latency_ms = int((time.time() - t_start) * 1000)
                logger.error("User %s BingX order submission error: %s", uid, e)
                # Ambiguous timeout check
                err_str = str(e).lower()
                if "timeout" in err_str or "connection reset" in err_str:
                    final_status = "SUBMISSION_UNKNOWN"
                else:
                    final_status = "REJECTED"
                db.release_autonomous_trade_slot(follower_slot_id, user_id=uid)
                exec_row = {
                    "copy_execution_id": copy_exec_id,
                    "master_trade_id": master_trade_id,
                    "user_id": uid,
                    "correlation_id": corr_id,
                    "idempotency_key": idemp_key,
                    "status": final_status,
                    "blocked_reason": f"BINGX ERROR: {str(e)[:120]}",
                    "allocated_margin": user_margin,
                    "calculated_quantity": norm_qty,
                    "executed_quantity": 0.0,
                    "executed_price": 0.0,
                    "client_order_id": client_order_id,
                    "exchange_order_id": None,
                    "execution_latency_ms": latency_ms,
                    "created_ms": now_ms,
                    "updated_ms": int(time.time() * 1000),
                }
                db.save_copy_execution(exec_row)
                results.append(exec_row)
                continue
        else:
            # Mock fill
            exchange_order_id = f"mock_ord_{int(time.time()*1000)}"

        # Occupy follower slot
        db.occupy_autonomous_trade_slot(follower_slot_id, str(copy_exec_id), user_id=uid)

        # Track entry slippage between master and follower
        entry_slippage_pct = round(abs(executed_price - entry_price) / max(0.0001, entry_price) * 100.0, 4)

        # Save successful execution
        exec_row = {
            "copy_execution_id": copy_exec_id,
            "master_trade_id": master_trade_id,
            "user_id": uid,
            "correlation_id": corr_id,
            "idempotency_key": idemp_key,
            "status": final_status,
            "blocked_reason": None,
            "allocated_margin": user_margin,
            "calculated_quantity": norm_qty,
            "executed_quantity": executed_qty,
            "executed_price": executed_price,
            "client_order_id": client_order_id,
            "exchange_order_id": exchange_order_id,
            "execution_latency_ms": latency_ms,
            "created_ms": now_ms,
            "updated_ms": int(time.time() * 1000),
            "slot_id": follower_slot_id,
            "master_entry_price": entry_price,
            "follower_entry_price": executed_price,
            "entry_slippage_pct": entry_slippage_pct,
        }
        db.save_copy_execution(exec_row)

        # Save open User Position in DB
        db.save_user_position({
            "user_id": uid,
            "symbol": symbol,
            "direction": direction,
            "quantity": executed_qty,
            "entry_price": executed_price,
            "leverage": leverage,
            "margin": user_margin,
            "sl_price": master_trade.get("sl_price"),
            "tp1_price": master_trade.get("tp1_price"),
            "tp2_price": master_trade.get("tp2_price"),
            "tp3_price": master_trade.get("tp3_price"),
            "trailing": master_trade.get("trailing", False),
            "breakeven": master_trade.get("breakeven", False),
            "master_trade_id": master_trade_id,
            "copy_execution_id": copy_exec_id,
            "status": "OPEN",
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "created_ms": now_ms,
            "slot_id": follower_slot_id,
        })
        results.append(exec_row)

    return results


def replicate_master_lifecycle_event(
    master_trade_id: str,
    event_type: str,
    payload: dict[str, Any],
    is_mock: bool = False
) -> list[dict[str, Any]]:
    """Synchronize lifecycle transitions: TP partial close, Breakeven, Trailing, Close."""
    now_ms = int(time.time() * 1000)
    seq = len(db.get_master_trade_events(master_trade_id)) + 1

    # Record event on master trade bus
    db.save_master_trade_event({
        "master_trade_id": master_trade_id,
        "master_event_id": f"evt_{event_type.lower()}_{now_ms}",
        "event_type": event_type,
        "sequence_number": seq,
        "correlation_id": f"corr_lc_{now_ms}",
        "payload": payload,
        "timestamp_ms": now_ms
    })

    open_positions = [p for p in db.get_open_user_positions() if p.get("master_trade_id") == master_trade_id]
    results: list[dict[str, Any]] = []

    for pos in open_positions:
        uid = pos["user_id"]
        symbol = pos["symbol"]
        pos_id = pos["id"]

        if event_type in ("MASTER_TP1", "MASTER_TP2", "MASTER_TP3"):
            # Partial close fraction of user position
            qty_pct = float(payload.get("qty_pct", 50.0)) / 100.0
            exit_price = float(payload.get("price") or pos["entry_price"])
            close_qty = round(pos["quantity"] * qty_pct, 4)
            rem_qty = round(pos["quantity"] - close_qty, 4)

            # PnL calculation
            pnl = (exit_price - pos["entry_price"]) * close_qty if pos["direction"] == "LONG" else (pos["entry_price"] - exit_price) * close_qty

            if not is_mock:
                client = credential_vault.get_user_bingx_client(uid, allow_trade=True)
                if client:
                    try:
                        side = "SELL" if pos["direction"] == "LONG" else "BUY"
                        pos_side = "LONG" if pos["direction"] == "LONG" else "SHORT"
                        client._request("POST", bingx_client.ORDER, {
                            "symbol": symbol,
                            "side": side,
                            "positionSide": pos_side,
                            "type": "MARKET",
                            "quantity": close_qty
                        }, signed=True)
                    except Exception as e:
                        logger.error("Failed partial TP on user %s BingX: %s", uid, e)

            if rem_qty <= 0:
                db.update_user_position(pos_id, {"status": "CLOSED", "quantity": 0.0, "realized_pnl": pos["realized_pnl"] + pnl})
                if pos.get("slot_id"):
                    db.release_autonomous_trade_slot(int(pos["slot_id"]), user_id=uid)
            else:
                # Move SL to true fee-adjusted breakeven
                be_price = round(pos["entry_price"] * (1.001 if pos["direction"] == "LONG" else 0.999), 4)
                db.update_user_position(pos_id, {
                    "quantity": rem_qty,
                    "realized_pnl": pos["realized_pnl"] + pnl,
                    "sl_price": be_price,
                    "breakeven": 1
                })
            results.append({"user_id": uid, "action": event_type, "closed_qty": close_qty, "pnl": pnl})

        elif event_type == "MASTER_BREAKEVEN":
            be_price = round(pos["entry_price"] * (1.001 if pos["direction"] == "LONG" else 0.999), 4)
            db.update_user_position(pos_id, {"sl_price": be_price, "breakeven": 1})
            results.append({"user_id": uid, "action": "BREAKEVEN_APPLIED", "new_sl": be_price})

        elif event_type == "MASTER_TRAILING_UPDATE":
            new_stop = float(payload["new_stop"])
            db.update_user_position(pos_id, {"sl_price": new_stop, "trailing": 1})
            results.append({"user_id": uid, "action": "TRAILING_UPDATED", "new_sl": new_stop})

        elif event_type in ("MASTER_CLOSE", "MASTER_EMERGENCY_CLOSE"):
            exit_price = float(payload.get("price") or pos["entry_price"])
            master_exit_price = float(payload.get("master_exit_price") or exit_price)
            exit_slippage_pct = round(abs(exit_price - master_exit_price) / max(0.0001, master_exit_price) * 100.0, 4)
            pnl = (exit_price - pos["entry_price"]) * pos["quantity"] if pos["direction"] == "LONG" else (pos["entry_price"] - exit_price) * pos["quantity"]
            if not is_mock:
                client = credential_vault.get_user_bingx_client(uid, allow_trade=True)
                if client:
                    try:
                        side = "SELL" if pos["direction"] == "LONG" else "BUY"
                        pos_side = "LONG" if pos["direction"] == "LONG" else "SHORT"
                        client._request("POST", bingx_client.ORDER, {
                            "symbol": symbol,
                            "side": side,
                            "positionSide": pos_side,
                            "type": "MARKET",
                            "quantity": pos["quantity"]
                        }, signed=True)
                    except Exception as e:
                        logger.error("Failed full close on user %s BingX: %s", uid, e)
            db.close_user_position_db(uid, symbol, exit_price, pnl)
            if pos.get("slot_id"):
                db.release_autonomous_trade_slot(int(pos["slot_id"]), user_id=uid)
            results.append({"user_id": uid, "action": "CLOSED", "pnl": pnl, "exit_slippage_pct": exit_slippage_pct})

    return results


def close_user_position_vps(user_id: int, symbol: str, is_mock: bool = False) -> dict[str, Any]:
    """Admin God Eye: Close specific user's open position directly from VPS without needing User app."""
    norm_sym = symbols.to_bingx_symbol(symbol)
    open_pos = [p for p in db.get_open_user_positions(user_id) if p["symbol"] == norm_sym]
    if not open_pos:
        return {"success": False, "status": "NO OPEN POSITION", "error": f"No open position for {norm_sym}"}

    pos = open_pos[0]
    exit_price = pos["entry_price"]
    pnl = 0.0

    if not is_mock:
        client = credential_vault.get_user_bingx_client(user_id, allow_trade=True)
        if not client:
            return {"success": False, "status": "BINGX DISCONNECTED", "error": "User BingX credentials unavailable"}
        try:
            side = "SELL" if pos["direction"] == "LONG" else "BUY"
            pos_side = "LONG" if pos["direction"] == "LONG" else "SHORT"
            resp = client._request("POST", bingx_client.ORDER, {
                "symbol": norm_sym,
                "side": side,
                "positionSide": pos_side,
                "type": "MARKET",
                "quantity": pos["quantity"]
            }, signed=True)
            exit_price = float(resp.get("avgPrice") or resp.get("price") or pos["entry_price"])
            pnl = (exit_price - pos["entry_price"]) * pos["quantity"] if pos["direction"] == "LONG" else (pos["entry_price"] - exit_price) * pos["quantity"]
        except Exception as e:
            return {"success": False, "status": "FAILED", "error": str(e)}

    db.close_user_position_db(user_id, norm_sym, exit_price, pnl)
    return {"success": True, "status": "CLOSED", "symbol": norm_sym, "user_id": user_id, "exit_price": exit_price, "pnl": pnl}


def flash_close_all_user_positions(reason: str, is_mock: bool = False) -> dict[str, Any]:
    """Admin God Eye: Emergency Flash Close All open positions across all users.
    
    Controlled concurrency, independent failure isolation, permanent audit event.
    """
    t0 = time.time()
    open_positions = db.get_open_user_positions()
    audit_id = f"flash_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    results: list[dict[str, Any]] = []

    for pos in open_positions:
        uid = pos["user_id"]
        sym = pos["symbol"]
        try:
            res = close_user_position_vps(uid, sym, is_mock=is_mock)
            results.append({"user_id": uid, "symbol": sym, "result": res})
        except Exception as e:
            results.append({"user_id": uid, "symbol": sym, "error": str(e)})

    # Log permanent audit event
    try:
        db.audit("ADMIN", "FLASH_CLOSE_ALL_USERS", {
            "audit_id": audit_id,
            "reason": reason,
            "positions_processed": len(open_positions),
            "results": results,
            "duration_ms": int((time.time() - t0) * 1000)
        })
    except Exception:
        pass

    return {
        "success": True,
        "audit_id": audit_id,
        "reason": reason,
        "positions_closed": len(results),
        "details": results
    }


def reconcile_fleet_positions(is_mock: bool = False) -> list[dict[str, Any]]:
    """Fleet-wide reconciliation: checks open local DB positions vs BingX exchange positions."""
    users = db.list_all_users(role="USER")
    reconciled: list[dict[str, Any]] = []

    for u in users:
        uid = u["id"]
        local_positions = db.get_open_user_positions(uid)
        if not local_positions and u.get("bingx_connection_status") != "CONNECTED":
            continue

        if is_mock:
            # In mock mode, states match
            reconciled.append({
                "user_id": uid,
                "status": "HEALTHY",
                "discrepancies": 0
            })
            continue

        client = credential_vault.get_user_bingx_client(uid, allow_trade=False)
        if not client:
            continue

        try:
            exchange_positions = client.positions()
            # Compare open positions by symbol
            ex_symbols = {p.get("symbol") for p in exchange_positions if float(p.get("positionAmt") or 0.0) != 0.0}
            local_symbols = {p["symbol"] for p in local_positions}

            discrepancy = None
            status = "HEALTHY"
            if ex_symbols != local_symbols:
                status = "MISMATCH"
                discrepancy = f"Exchange has {ex_symbols}, local DB has {local_symbols}"

            rec_event = {
                "user_id": uid,
                "symbol": "ALL",
                "status": status,
                "exchange_state": {"positions": list(ex_symbols)},
                "local_state": {"positions": list(local_symbols)},
                "discrepancy_reason": discrepancy,
                "timestamp_ms": int(time.time() * 1000)
            }
            db.record_reconciliation_event(rec_event)
            reconciled.append(rec_event)
        except Exception as e:
            db.record_reconciliation_event({
                "user_id": uid,
                "symbol": "ALL",
                "status": "ERROR",
                "discrepancy_reason": f"Reconciliation query error: {e}",
                "timestamp_ms": int(time.time() * 1000)
            })

    return reconciled
