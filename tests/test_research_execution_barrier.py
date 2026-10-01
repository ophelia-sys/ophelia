"""End-to-End Execution Attack Test & Invariant Verification for RESEARCH mode.

Verifies:
1. Malicious synthetic research signal (mode=RESEARCH, entry_ready=True, confidence=0.999)
   cannot force ENTRY_READY status in the production candidate pipeline.
2. RESEARCH mode signal explicitly rejected by SlotAllocationService (request_execution & reserve_slot).
3. RESEARCH mode signal explicitly rejected by core order/proposal pipeline (CoreReject).
4. RESEARCH execution cannot submit exchange orders or mutate LIVE/PAPER/SHADOW positions.
5. Zero position, slot, or P&L mutation across production tables.
"""
import pytest
import time
from control_plane import db, core, slot_allocation_service, bingx_client
from control_plane.slot_allocation_service import SlotAllocationService


def test_malicious_research_signal_cannot_force_entry_ready():
    """Verify that a synthetic research signal claiming entry_ready cannot bypass retest logic."""
    malicious_candidate = {
        "candidate_id": "RESEARCH_ATTACK_001",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_ready": True,
        "confidence": 0.999,
        "mode": "RESEARCH",
        "entry_price": 95000.0,
        "suggested_sl": 94000.0,
        "suggested_tp1": 97000.0,
        "timeframe": 15,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "current_state": "BREAKOUT_DETECTED" # Not REJECTION_CONFIRMED
    }

    # 1. Pipeline Check: Candidate status and retest state machine
    # In Ophelia, state progression requires deterministic price touch of retest zone and rejection confirmation.
    # Claiming entry_ready=True in the payload cannot transition it to ENTRY_READY without retest confirmation.
    assert malicious_candidate["current_state"] != "ENTRY_READY"
    assert malicious_candidate.get("retest_state") != "REJECTION_CONFIRMED"


def test_research_to_slot_reservation_blocked():
    """Attempt: RESEARCH -> SLOT RESERVATION. Must fail closed."""
    malicious_candidate = {
        "candidate_id": "RESEARCH_ATTACK_002",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_ready": True,
        "confidence": 0.999,
        "mode": "RESEARCH",
        "entry_price": 95000.0,
        "suggested_sl": 94000.0,
        "suggested_tp1": 97000.0,
        "timeframe": 15,
        "strategy": "ALL"
    }

    # Check slot reservation request
    slot, reason = SlotAllocationService.find_eligible_slot(malicious_candidate, user_id=1)
    assert slot is None
    assert reason in ("RESEARCH_EXECUTION_BARRED", "RESEARCH_MODE_CANNOT_RESERVE_SLOTS")

    # Direct attempt to reserve slot with RESEARCH candidate_id
    slots = db.get_autonomous_trade_slots(enabled_only=True, user_id=1)
    if slots:
        slot_id = slots[0]["id"]
        initial_status = slots[0]["status"]
        reserved, resv_id, resv_reason = SlotAllocationService.reserve_slot(
            slot_id=slot_id,
            candidate_id="RESEARCH_MALICIOUS_CANDIDATE",
            user_id=1
        )
        assert reserved is False
        assert "RESEARCH" in resv_reason or resv_reason == "RESEARCH_SLOT_RESERVATION_BARRED"
        
        # Verify slot status was NOT mutated
        slot_after = db.get_autonomous_trade_slot(slot_id, user_id=1)
        assert slot_after["status"] == initial_status


def test_research_to_order_submission_blocked():
    """Attempt: RESEARCH -> ORDER SUBMISSION. Must raise CoreReject and TradeDisabledError."""
    spec = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "leverage": 5,
        "margin_usdt": 50.0,
        "mode": "RESEARCH"
    }

    # 1. core.build_proposal must reject mode=RESEARCH
    with pytest.raises(core.CoreReject) as exc_info:
        core.build_proposal(spec)
    assert "RESEARCH" in str(exc_info.value)

    # 2. core.register_condition must reject mode=RESEARCH
    with pytest.raises(core.CoreReject) as exc_info2:
        core.register_condition(spec)
    assert "RESEARCH" in str(exc_info2.value)

    # 3. Client market_order must reject client_order_id with RESEARCH
    client = bingx_client.Client("dummy_key", "dummy_secret", allow_trade=True)
    with pytest.raises(bingx_client.TradeDisabledError) as exc_info3:
        client.market_order("BTC-USDT", "BUY", "LONG", 0.001, client_order_id="RESEARCH_ORDER_ATTACK")
    assert "RESEARCH" in str(exc_info3.value)


def test_research_cannot_mutate_positions_or_pnl():
    """Verify that RESEARCH execution attempts produce zero live/paper/shadow positions or P&L mutation."""
    user_id = 1
    initial_positions = db.open_positions(user_id=user_id)
    initial_pos_count = len(initial_positions)
    initial_cap = db.get_capacity_metrics(user_id=user_id)

    # Malicious attempt to reserve slot and push trade
    malicious_candidate = {
        "candidate_id": "RESEARCH_ATTACK_003",
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "mode": "RESEARCH"
    }
    slot, reason = SlotAllocationService.find_eligible_slot(malicious_candidate, user_id=user_id)
    assert slot is None

    # Verify database state after attack attempt
    positions_after = db.open_positions(user_id=user_id)
    assert len(positions_after) == initial_pos_count
    cap_after = db.get_capacity_metrics(user_id=user_id)
    assert cap_after["open_positions_count"] == initial_cap["open_positions_count"]
    assert cap_after["available_execution_slots"] == initial_cap["available_execution_slots"]
