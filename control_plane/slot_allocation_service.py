"""Authoritative Slot Allocation and Reservation Service for Ophelia.

Invariants:
1. Deterministic Authority: Single authoritative service for slot eligibility,
   atomic reservation, release, reconciliation, auto-provisioning, and recovery.
2. Zero Bypasses: Neither strategy modules, opportunity_bus, US Market, Crypto, Gold,
   nor API handlers may independently implement their own slot selection.
3. Concurrency Safety: Atomic conditional reservation preventing double allocation.
4. Auto-Provisioning: Autonomous creation of slots WITHIN authorized user envelopes;
   ML NEVER dictates margin or leverage.
5. Lifecycle States:
   AVAILABLE -> RESERVED -> OCCUPIED -> RECONCILING -> AVAILABLE
   Explicit states: DISABLED, ERROR, RECOVERY_REQUIRED.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import config, db

logger = logging.getLogger("ophelia.slot_allocation_service")

# Authorized System Ceilings
SYSTEM_MAX_SLOTS = 10
SYSTEM_MAX_CAPITAL = 2500.0
SYSTEM_MAX_LEVERAGE = 10.0
SYSTEM_MAX_LOSS_PCT = 10.0
STALE_RESERVATION_TIMEOUT_S = 60


class SlotAllocationService:
    """Authoritative service for finding, reserving, occupying, reconciling,
    and auto-provisioning autonomous trade slots."""

    @staticmethod
    def find_eligible_slot(
        candidate: dict,
        user_id: int,
        account_id: Optional[int] = None
    ) -> Tuple[Optional[dict], str]:
        """Find an eligible AVAILABLE slot for the given candidate and user.
        
        Evaluates deterministic invariants:
        - belongs to authenticated user
        - belongs to correct exchange account
        - enabled
        - AVAILABLE
        - correct asset scope
        - correct strategy scope
        - allocated margin > 0
        - permitted leverage
        - within max loss
        - compatible with instrument
        - global autonomous switch enabled
        - trading mode permits execution
        - concurrent-position limits permit it
        - no conflicting existing position for symbol
        - no stale reservation
        - slot is not disabled/error/recovery-required
        
        Returns:
            (slot_dict, "OK") if eligible slot found.
            (None, rejection_reason) if rejected.
        """
        # 1. Global autonomous switch check
        if not db.is_global_autonomous_enabled():
            return None, "GLOBAL_AUTONOMOUS_DISABLED"

        # 2. Authenticated user validation
        if not user_id or user_id < 1:
            return None, "INVALID_USER"

        # 3. Trading mode safety check
        mode = db.get_mode()
        if mode not in ("SHADOW", "PAPER", "LIVE"):
            return None, "INVALID_TRADING_MODE"
        if mode == "LIVE":
            try:
                from . import core
                pf = core.run_preflight(user_id=user_id)
                if not pf.get("ready_for_live"):
                    return None, "ACCOUNT_NOT_CONNECTED"
            except Exception as e:
                logger.warning(f"Preflight check exception: {e}")
                return None, "ACCOUNT_NOT_CONNECTED"

        # 4. Global capital & concurrent position limits
        try:
            from . import core
            block = core.one_trade_block(user_id=user_id)
            if block:
                return None, "CONCURRENT_POSITION_LIMIT"
        except Exception:
            pass

        cap = db.get_max_open_trades(user_id=user_id)
        open_positions = db.open_positions(user_id=user_id)
        if len(open_positions) >= cap:
            return None, "CONCURRENT_POSITION_LIMIT"

        # 5. Conflicting active position for same symbol
        symbol = candidate.get("symbol", "").strip().upper()
        if symbol:
            allow_pyramiding = bool(candidate.get("allow_pyramiding", False))
            if not allow_pyramiding and db.has_open_position_for_symbol(symbol, user_id=user_id):
                return None, "CONFLICTING_POSITION"

        # 6. Instrument & Asset Scope resolution
        asset_class = candidate.get("asset_class")
        if not asset_class:
            if "XAU" in symbol or "GOLD" in symbol:
                asset_class = "COMMODITIES"
            elif any(c in symbol for c in ("-USDT", "/USDT", "BTC", "ETH", "SOL", "XRP")):
                asset_class = "CRYPTO"
            else:
                asset_class = "US_MARKET"
        asset_upper = asset_class.strip().upper()

        strategy = (candidate.get("strategy") or "ALL").strip().upper()

        # 7. Check existing slots
        slots = db.get_autonomous_trade_slots(enabled_only=True, user_id=user_id)

        # If user has no slots at all, attempt autonomous provisioning from template
        if not slots:
            new_slot, prov_reason = SlotAllocationService.auto_provision_slot(
                user_id=user_id,
                asset_class=asset_upper,
                strategy=strategy,
                account_id=account_id
            )
            if new_slot:
                slots = [new_slot]
            else:
                return None, prov_reason

        # 8. Evaluate each slot against candidate requirements
        candidate_entry = float(candidate.get("entry_price") or candidate.get("entry") or 0.0)
        candidate_sl = float(candidate.get("sl_price") or candidate.get("sl") or candidate.get("suggested_sl") or 0.0)

        scope_mismatches = 0
        occupied_count = 0
        reserved_count = 0
        disabled_count = 0

        for s in slots:
            status = s.get("status", "AVAILABLE").strip().upper()

            # Status check
            if status in ("DISABLED", "ERROR", "RECOVERY_REQUIRED"):
                disabled_count += 1
                continue

            if status == "OCCUPIED":
                occupied_count += 1
                continue

            if status == "RESERVED":
                # Check if stale reservation
                resv_at = s.get("reserved_at") or 0
                now_ms = int(time.time() * 1000)
                if resv_at > 0 and (now_ms - resv_at) > (STALE_RESERVATION_TIMEOUT_S * 1000):
                    # Recover stale reservation
                    SlotAllocationService.release_slot(s["id"], user_id=user_id, reason="STALE_RESERVATION_RECOVERED")
                    s["status"] = "AVAILABLE"
                else:
                    reserved_count += 1
                    continue

            # Account isolation check
            if account_id is not None and s.get("account_id") is not None:
                if int(s["account_id"]) != int(account_id):
                    continue

            # Scope / Asset Class compatibility
            s_scope = (s.get("scope") or s.get("asset_scope") or "ALL").strip().upper()
            allowed_classes = [x.strip().upper() for x in (s.get("allowed_asset_classes") or "ALL").split(",") if x.strip()]
            if s_scope != "ALL" and asset_upper not in s_scope and asset_upper not in allowed_classes and "ALL" not in allowed_classes:
                scope_mismatches += 1
                continue

            # Symbol compatibility
            allowed_syms = [x.strip().upper() for x in (s.get("allowed_symbols") or "").split(",") if x.strip()]
            if allowed_syms and symbol and symbol not in allowed_syms:
                scope_mismatches += 1
                continue

            # Strategy Scope compatibility
            strat_scope = (s.get("strategy_scope") or "ALL_STRATEGIES").strip().upper()
            if strat_scope not in ("ALL", "ALL_STRATEGIES") and strategy not in ("ALL", "ALL_STRATEGIES") and strategy not in strat_scope:
                scope_mismatches += 1
                continue

            # Margin validity
            margin = float(s.get("allocated_margin_usdt") or 0.0)
            if margin <= 0.0:
                continue

            # Leverage validity
            leverage = float(s.get("max_leverage") or 5.0)
            if leverage <= 0.0 or leverage > SYSTEM_MAX_LEVERAGE:
                continue

            # Max Loss validation
            if candidate_entry > 0.0 and candidate_sl > 0.0:
                unit_risk_pct = abs(candidate_entry - candidate_sl) / candidate_entry
                est_loss_usdt = unit_risk_pct * (margin * leverage)
                max_loss_usdt = float(s.get("max_loss_usdt") or 0.0)
                max_loss_pct = float(s.get("maximum_loss_percent") or s.get("max_loss_pct") or 10.0)
                if max_loss_usdt <= 0.0:
                    max_loss_usdt = margin * (max_loss_pct / 100.0)
                if est_loss_usdt > max_loss_usdt * 1.5:  # Cannot safely resize if risk is >150% of cap
                    return None, "RISK_LIMIT"

            # Found valid eligible slot!
            return s, "OK"

        # If all slots were occupied or reserved, attempt to auto-provision an additional slot
        new_slot, prov_reason = SlotAllocationService.auto_provision_slot(
            user_id=user_id,
            asset_class=asset_upper,
            strategy=strategy,
            account_id=account_id
        )
        if new_slot:
            return new_slot, "OK"

        if scope_mismatches > 0 and occupied_count == 0 and reserved_count == 0:
            return None, "SCOPE_MISMATCH"

        if occupied_count > 0 or reserved_count > 0:
            return None, "NO_AVAILABLE_SLOT"

        return None, "WAITING_FOR_SLOT_CONFIG"

    @staticmethod
    def reserve_slot(
        slot_id: int,
        candidate_id: str,
        user_id: int,
        account_id: Optional[int] = None,
        reservation_id: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """Atomically reserve an AVAILABLE slot for candidate.
        
        Returns:
            (True, reservation_id, "OK") if successfully reserved.
            (False, "", rejection_reason) if failed or contested.
        """
        if not user_id or user_id < 1:
            return False, "", "INVALID_USER"

        now_ms = int(time.time() * 1000)
        resv_id = reservation_id or f"resv_{uuid.uuid4().hex[:12]}"

        c = db._connect()
        with db._lock:
            cur = c.execute("""
                UPDATE autonomous_trade_slots
                SET status='RESERVED',
                    current_trade_id=?,
                    reservation_id=?,
                    reserved_at=?,
                    updated_at=?,
                    last_error=NULL,
                    last_error_reason=NULL
                WHERE id=? AND status='AVAILABLE' AND enabled=1 AND user_id=?
            """, (str(candidate_id), resv_id, now_ms, now_ms, slot_id, user_id))
            c.commit()

            if cur.rowcount == 1:
                db.audit(
                    "slot_allocation_service",
                    "SLOT_RESERVED",
                    {"slot_id": slot_id, "candidate_id": candidate_id, "reservation_id": resv_id},
                    user_id=user_id
                )
                return True, resv_id, "OK"

        # Check why update failed
        slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
        if not slot:
            return False, "", "SLOT_NOT_FOUND"
        if not slot.get("enabled"):
            return False, "", "SLOT_DISABLED"
        if slot.get("status") == "RESERVED":
            return False, "", "SLOT_RESERVATION_CONFLICT"
        if slot.get("status") == "OCCUPIED":
            return False, "", "SLOT_OCCUPIED"

        return False, "", "RESERVATION_FAILED"

    @staticmethod
    def occupy_slot(
        slot_id: int,
        position_id: str,
        user_id: int,
        reservation_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Mark slot as OCCUPIED once trade/position is created.
        
        Transitions RESERVED -> OCCUPIED.
        """
        now_ms = int(time.time() * 1000)
        c = db._connect()
        with db._lock:
            q = """
                UPDATE autonomous_trade_slots
                SET status='OCCUPIED',
                    current_position_id=?,
                    updated_at=?,
                    last_used_at=?
                WHERE id=? AND user_id=? AND status IN ('RESERVED', 'AVAILABLE')
            """
            args = [str(position_id), now_ms, now_ms, slot_id, user_id]
            if reservation_id:
                q += " AND (reservation_id=? OR reservation_id IS NULL)"
                args.append(reservation_id)

            cur = c.execute(q, args)
            c.commit()

            if cur.rowcount == 1:
                db.audit(
                    "slot_allocation_service",
                    "SLOT_OCCUPIED",
                    {"slot_id": slot_id, "position_id": str(position_id)},
                    user_id=user_id
                )
                return True, "OK"

        return False, "OCCUPY_FAILED"

    @staticmethod
    def release_slot(
        slot_id: int,
        user_id: Optional[int] = None,
        reason: str = ""
    ) -> Tuple[bool, str]:
        """Release slot back to AVAILABLE state.
        
        Transitions OCCUPIED / RESERVED / RECONCILING -> AVAILABLE.
        """
        if not user_id or int(user_id) <= 0:
            return False, "INVALID_OWNERSHIP_USER_ID_REQUIRED"

        uid = int(user_id)
        now_ms = int(time.time() * 1000)
        c = db._connect()
        with db._lock:
            q = """
                UPDATE autonomous_trade_slots
                SET status='AVAILABLE',
                    current_trade_id=NULL,
                    current_position_id=NULL,
                    reservation_id=NULL,
                    released_at=?,
                    updated_at=?,
                    last_error_reason=?
                WHERE id=? AND user_id=?
            """
            args = [now_ms, now_ms, reason or None, slot_id, uid]

            cur = c.execute(q, args)
            c.commit()

            if cur.rowcount > 0:
                db.audit(
                    "slot_allocation_service",
                    "SLOT_RELEASED",
                    {"slot_id": slot_id, "reason": reason},
                    user_id=uid
                )
                return True, "OK"

        return False, "RELEASE_FAILED"

    @staticmethod
    def reconcile_slot(slot_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Reconcile slot status against actual database position and reservation states."""
        slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
        if not slot:
            return {"action": "NOT_FOUND", "slot_id": slot_id}

        slot_uid = slot.get("user_id")
        if not slot_uid or int(slot_uid) <= 0:
            return {"action": "REQUIRES_RECONCILIATION", "slot_id": slot_id, "error": "MISSING_USER_ID"}
        slot_uid = int(slot_uid)

        status = slot.get("status", "AVAILABLE")
        now_ms = int(time.time() * 1000)

        # 1. Stale reservation check
        if status == "RESERVED":
            resv_at = slot.get("reserved_at") or 0
            if resv_at > 0 and (now_ms - resv_at) > (STALE_RESERVATION_TIMEOUT_S * 1000):
                # Check if there is an active execution intent still submitting
                trade_id = slot.get("current_trade_id")
                is_submitting = False
                if trade_id:
                    c = db._connect()
                    with db._lock:
                        row = c.execute(
                            "SELECT status FROM execution_intents WHERE (candidate_id=? OR execution_intent_id=?) AND status IN ('SUBMITTING', 'SUBMITTED', 'RISK_CHECKING')",
                            (trade_id, trade_id)
                        ).fetchone()
                        if row:
                            is_submitting = True

                if not is_submitting:
                    SlotAllocationService.release_slot(
                        slot_id,
                        user_id=slot_uid,
                        reason="STALE_RESERVATION_TIMEOUT"
                    )
                    return {"action": "RELEASED_STALE_RESERVATION", "slot_id": slot_id}

        # 2. OCCUPIED position existence check
        elif status == "OCCUPIED":
            pos_id = slot.get("current_position_id")
            if not pos_id:
                SlotAllocationService.release_slot(slot_id, user_id=slot_uid, reason="OCCUPIED_WITHOUT_POSITION")
                return {"action": "RELEASED_MISSING_POSITION", "slot_id": slot_id}

            pos = db.get_position(pos_id, user_id=slot_uid)
            if not pos:
                unscoped_pos = db.get_position(pos_id)
                if unscoped_pos and unscoped_pos.get("user_id") != slot_uid:
                    return {"action": "REQUIRES_RECONCILIATION", "slot_id": slot_id, "error": "CROSS_USER_OWNERSHIP_MISMATCH"}
                SlotAllocationService.release_slot(slot_id, user_id=slot_uid, reason="POSITION_NOT_FOUND")
                return {"action": "RELEASED_MISSING_POSITION", "slot_id": slot_id}

            if pos.get("status") in ("CLOSED", "CANCELLED", "LIQUIDATED") or pos.get("lifecycle_state") == "CLOSED":
                SlotAllocationService.release_slot(slot_id, user_id=slot_uid, reason="POSITION_CLOSED")
                return {"action": "RELEASED_CLOSED_POSITION", "slot_id": slot_id}

            return {"action": "CONFIRMED_OCCUPIED", "slot_id": slot_id, "position_id": pos_id}

        return {"action": "NOOP", "slot_id": slot_id, "status": status}

    @staticmethod
    def recover_stale_reservations(timeout_s: int = STALE_RESERVATION_TIMEOUT_S, user_id: Optional[int] = None) -> int:
        """Find and recover all stale RESERVED slots across all users (or specific user)."""
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - (timeout_s * 1000)

        c = db._connect()
        q = "SELECT id, user_id, current_trade_id FROM autonomous_trade_slots WHERE status='RESERVED' AND (reserved_at IS NULL OR reserved_at < ?)"
        args = [cutoff_ms]
        if user_id is not None:
            q += " AND user_id=?"
            args.append(user_id)

        with db._lock:
            stale_rows = c.execute(q, args).fetchall()

        recovered_count = 0
        for slot_id, uid, trade_id in stale_rows:
            # Check if active execution intent is in flight
            is_submitting = False
            if trade_id:
                with db._lock:
                    row = c.execute(
                        "SELECT status FROM execution_intents WHERE (candidate_id=? OR execution_intent_id=?) AND status IN ('SUBMITTING', 'SUBMITTED', 'RISK_CHECKING')",
                        (trade_id, trade_id)
                    ).fetchone()
                    if row:
                        is_submitting = True

            if not is_submitting:
                ok, _ = SlotAllocationService.release_slot(slot_id, user_id=uid, reason="STALE_RESERVATION_RECOVERED")
                if ok:
                    recovered_count += 1
                    logger.info(f"Recovered stale reserved slot #{slot_id} for user #{uid}")

        return recovered_count

    @staticmethod
    def auto_provision_slot(
        user_id: int,
        asset_class: str = "CRYPTO",
        strategy: str = "ALL",
        account_id: Optional[int] = None
    ) -> Tuple[Optional[dict], str]:
        """Provision a usable autonomous trade slot WITHIN authorized user template and capital envelope.
        
        Invariants:
        - ML NEVER selects margin or leverage.
        - Strict adherence to authorized user slot template.
        - If no template exists: returns (None, "WAITING_FOR_SLOT_CONFIG").
        - Server ceilings (max_slots, max_capital, max_leverage, max_loss) are non-negotiable.
        """
        if not user_id or user_id < 1:
            return None, "INVALID_USER"

        asset_upper = asset_class.strip().upper()
        strat_upper = strategy.strip().upper()

        # 1. Fetch authorized user slot template
        template = db.get_user_slot_template(user_id=user_id, scope=asset_upper)
        if not template:
            template = db.get_user_slot_template(user_id=user_id, scope="ALL")
        if not template:
            all_templates = db.get_user_slot_templates(user_id=user_id)
            if all_templates:
                template = all_templates[0]

        if not template:
            # No authorized user configuration exists
            return None, "WAITING_FOR_SLOT_CONFIG"

        # 2. Extract and clamp template parameters against system limits
        t_max_slots = min(int(template.get("max_slots") or 5), SYSTEM_MAX_SLOTS)
        t_max_capital = min(float(template.get("max_autonomous_capital") or 500.0), SYSTEM_MAX_CAPITAL)
        t_margin = float(template.get("margin") or 50.0)
        t_leverage = min(float(template.get("leverage") or 5.0), SYSTEM_MAX_LEVERAGE)
        t_max_loss_pct = min(float(template.get("max_loss_pct") or 2.0), SYSTEM_MAX_LOSS_PCT)
        t_tp1_pct = float(template.get("tp1_pct") or 50.0)
        t_breakeven = bool(template.get("breakeven", 1))
        t_trailing = bool(template.get("trailing", 1))
        t_trailing_pct = float(template.get("trailing_pct") or 1.5)

        if t_margin <= 0.0:
            return None, "INVALID_MARGIN"

        # 3. Check existing user slot capacity
        existing_slots = db.get_autonomous_trade_slots(user_id=user_id)
        if len(existing_slots) >= t_max_slots:
            return None, "CONCURRENT_POSITION_LIMIT"

        total_margin = sum(float(s.get("allocated_margin_usdt") or 0.0) for s in existing_slots)
        if (total_margin + t_margin) > t_max_capital:
            return None, "CAPITAL_LIMIT"

        # 4. Provision new slot
        slot_number = len(existing_slots) + 1
        slot_name = f"{asset_upper} AUTO SLOT {slot_number}"
        eff_account_id = account_id or template.get("account_id") or 1

        try:
            slot_id = db.add_autonomous_trade_slot(
                name=slot_name,
                allocated_margin_usdt=t_margin,
                max_leverage=t_leverage,
                asset_scope=asset_upper,
                strategy_scope=strat_upper if strat_upper != "ALL" else "ALL_STRATEGIES",
                enabled=True,
                user_id=user_id,
                max_loss_pct=t_max_loss_pct,
                trailing_enabled=t_trailing,
                trailing_pct=t_trailing_pct,
                tp1_enabled=True,
                tp1_pct=t_tp1_pct,
                breakeven_enabled=t_breakeven,
                breakeven_mode="AFTER_TP1",
                slot_mode="AUTONOMOUS"
            )
            # Update account_id on slot
            c = db._connect()
            with db._lock:
                c.execute("UPDATE autonomous_trade_slots SET account_id=? WHERE id=?", (eff_account_id, slot_id))
                c.commit()

            new_slot = db.get_autonomous_trade_slot(slot_id, user_id=user_id)
            db.audit(
                "slot_allocation_service",
                "SLOT_AUTO_PROVISIONED",
                {"slot_id": slot_id, "name": slot_name, "margin": t_margin, "leverage": t_leverage},
                user_id=user_id
            )
            logger.info(f"Auto-provisioned slot #{slot_id} ({slot_name}) for user #{user_id}")
            return new_slot, "OK"
        except Exception as e:
            logger.error(f"Failed to auto-provision slot: {e}")
            return None, f"UNKNOWN_ERROR: {e}"
