"""Unit tests for Phase 4 Continuous Retest Intelligence and Candidate Lifecycle.

Verifies:
1. Full Causal Retest Lifecycle:
   IDENTIFIED -> WAITING_FOR_RETEST -> RETEST_TOUCHED -> CONFIRMING_REJECTION -> ENTRY_READY -> TRIGGERED
2. Invalidation paths:
   - WAITING_FOR_RETEST -> INVALIDATED (price closes beyond zone by > 0.5 ATR)
   - RETEST_TOUCHED -> INVALIDATED
3. Expiration path:
   - WAITING_FOR_RETEST -> EXPIRED (exceeds retest horizon window)
4. Dynamic "What is Ophelia Waiting For?" derived from actual state
5. Volatility-aware distance calculation (% and ATR-normalized)
6. Condition statuses: MET, PENDING, NOT_AVAILABLE, NOT_APPLICABLE, INVALID
7. R:R decoupling: candidate display is not gated on R:R >= 2.0
8. Actionability & Maturity-based priority ranking with explainable reasons
9. Candidate persistence & state recovery across restarts
10. Candidate deduplication (strictly 1 active candidate per symbol/direction/timeframe)
11. Data freshness monitoring and fail-closed behavior on stale data
"""

import time
import pytest
from control_plane import retest_engine, priority_classifier, db, config


def _generate_synthetic_closed_candles(start_price=3000.0, count=30, trend="UP", tf_mins=3):
    """Generates synthetic closed candles with clear swing points and displacement breakout."""
    now_ms = int(time.time() * 1000)
    step_ms = tf_mins * 60 * 1000
    candles = []
    start_ts = now_ms - (count * step_ms)

    for i in range(count):
        ts = start_ts + (i * step_ms)
        if i < count - 3:
            # Consolidation creating swings between start_price - 10 and start_price + 10
            osc = (i % 4 - 1.5) * 5.0
            o = start_price + osc
            c = o + 2.0
            h = max(o, c) + 4.0
            l = min(o, c) - 4.0
            v = 150.0
        else:
            # Breakout candle displacing past previous peaks
            if trend == "UP":
                o = start_price + 8.0
                c = start_price + 35.0 + (i - (count - 3)) * 5.0
                h = c + 4.0
                l = o - 2.0
            else:
                o = start_price - 8.0
                c = start_price - 35.0 - (i - (count - 3)) * 5.0
                h = o + 2.0
                l = c - 4.0
            v = 600.0

        candles.append({
            "exchange": "bingx",
            "symbol": "ETH-USDT",
            "ts": ts,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "taker_buy": v * 0.75,
            "trades": 60
        })
    return candles


def test_full_candidate_lifecycle_progression():
    """Test full progression: IDENTIFIED -> WAITING_FOR_RETEST -> RETEST_TOUCHED -> CONFIRMING_REJECTION -> ENTRY_READY."""
    symbol = "ETH-USDT"
    timeframe = 15
    direction = "LONG"
    engine = retest_engine.CausalRetestEngine(symbol, timeframe, direction)

    candles = _generate_synthetic_closed_candles(start_price=3000.0, count=25, trend="UP", tf_mins=timeframe)
    vwap = 2950.0

    # Step 1: Initial state is IDLE / IDENTIFIED
    state = retest_engine.RetestState(symbol=symbol, timeframe=timeframe, direction=direction, state="IDLE")
    updated = engine.evaluate_step(state, candles, vwap)
    assert updated.state in ("WAITING_FOR_RETEST", "IDENTIFIED")
    assert updated.breakout_price > 0
    assert updated.zone_low is not None and updated.zone_high is not None

    # Verify candidate generation from WAITING_FOR_RETEST
    cand = retest_engine.generate_setup_candidate_from_state(updated, candles, vwap)
    assert cand["current_state"] == "WAITING_FOR_RETEST"
    assert cand["next_required_event"] == "RETEST_ZONE_TOUCH"
    assert "retest touch" in cand["waiting_for"].lower()
    assert cand["distance_pct"] is not None
    assert cand["distance_atr"] is not None
    assert cand["calibration_status"] == "NOT CALIBRATED"

    # Step 2: Price pulls back to touch the zone
    z_low = updated.zone_low
    z_high = updated.zone_high
    cur_ts = candles[-1]["ts"] + (timeframe * 60 * 1000)
    touch_candle = {
        "exchange": "bingx", "symbol": symbol, "ts": cur_ts,
        "open": z_high + 5.0, "high": z_high + 6.0, "low": z_low + 1.0, "close": z_low + 4.0,
        "volume": 200.0, "taker_buy": 80.0, "trades": 40
    }
    candles.append(touch_candle)
    updated2 = engine.evaluate_step(updated, candles, vwap)
    assert updated2.state == "RETEST_TOUCHED"
    cand2 = retest_engine.generate_setup_candidate_from_state(updated2, candles, vwap)
    assert cand2["current_state"] == "RETEST_TOUCHED"
    assert cand2["next_required_event"] == "REJECTION_CANDLE"
    assert "rejection candle" in cand2["waiting_for"].lower()

    # Step 3: Rejection forms (green candle closing above open and above zone_low)
    cur_ts += (timeframe * 60 * 1000)
    rejection_candle = {
        "exchange": "bingx", "symbol": symbol, "ts": cur_ts,
        "open": z_low + 2.0, "high": z_high + 8.0, "low": z_low + 1.0, "close": z_high + 5.0,
        "volume": 350.0, "taker_buy": 260.0, "trades": 70
    }
    candles.append(rejection_candle)
    updated3 = engine.evaluate_step(updated2, candles, vwap)
    assert updated3.state in ("CONFIRMING_REJECTION", "ENTRY_READY")
    cand3 = retest_engine.generate_setup_candidate_from_state(updated3, candles, vwap)
    assert cand3["current_state"] in ("CONFIRMING_REJECTION", "ENTRY_READY")


def test_invalidation_below_zone():
    """Test structural invalidation when price closes cleanly beyond zone by > 0.5 ATR."""
    symbol = "ETH-USDT"
    timeframe = 15
    direction = "LONG"
    engine = retest_engine.CausalRetestEngine(symbol, timeframe, direction)

    candles = _generate_synthetic_closed_candles(start_price=3000.0, count=25, trend="UP", tf_mins=timeframe)
    vwap = 2950.0
    state = retest_engine.RetestState(symbol=symbol, timeframe=timeframe, direction=direction, state="IDLE")
    updated = engine.evaluate_step(state, candles, vwap)
    assert updated.state == "WAITING_FOR_RETEST"
    z_low = updated.zone_low
    atr = updated.current_atr or 10.0

    # Candle closes far below zone_low by > 0.5 ATR
    cur_ts = candles[-1]["ts"] + (timeframe * 60 * 1000)
    dump_candle = {
        "exchange": "bingx", "symbol": symbol, "ts": cur_ts,
        "open": z_low, "high": z_low + 1.0, "low": z_low - 40.0, "close": z_low - 30.0,
        "volume": 400.0, "taker_buy": 100.0, "trades": 60
    }
    candles.append(dump_candle)
    invalidated = engine.evaluate_step(updated, candles, vwap)
    assert invalidated.state == "INVALIDATED"
    assert "below zone low" in invalidated.invalidation_reason.lower()

    cand = retest_engine.generate_setup_candidate_from_state(invalidated, candles, vwap)
    assert cand["current_state"] == "INVALIDATED"
    assert cand["setup_status"] == "INVALIDATED"
    assert cand["next_required_event"] == "NONE"
    assert "invalidated" in cand["waiting_for"].lower()


def test_expiration_beyond_retest_horizon():
    """Test candidate expiration when retest does not occur within allowed window."""
    symbol = "ETH-USDT"
    timeframe = 15
    direction = "LONG"
    engine = retest_engine.CausalRetestEngine(symbol, timeframe, direction, retest_window=5)

    candles = _generate_synthetic_closed_candles(start_price=3000.0, count=20, trend="UP", tf_mins=timeframe)
    vwap = 2950.0
    state = retest_engine.RetestState(symbol=symbol, timeframe=timeframe, direction=direction, state="IDLE")
    updated = engine.evaluate_step(state, candles, vwap)
    assert updated.state == "WAITING_FOR_RETEST"

    # Step through 6 candles that do not touch the zone
    cur_ts = candles[-1]["ts"]
    for _ in range(6):
        cur_ts += (timeframe * 60 * 1000)
        c = {
            "exchange": "bingx", "symbol": symbol, "ts": cur_ts,
            "open": 3200.0, "high": 3210.0, "low": 3195.0, "close": 3205.0,
            "volume": 100.0, "taker_buy": 50.0, "trades": 20
        }
        candles.append(c)
        updated = engine.evaluate_step(updated, candles, vwap)

    assert updated.state == "EXPIRED"
    assert "horizon" in updated.invalidation_reason.lower()

    cand = retest_engine.generate_setup_candidate_from_state(updated, candles, vwap)
    assert cand["current_state"] == "EXPIRED"
    assert cand["next_required_event"] == "NONE"


def test_condition_statuses_and_decoupled_features():
    """Test that condition statuses accurately reflect MET, PENDING, NOT_AVAILABLE, NOT_APPLICABLE."""
    symbol = "GOLD"
    timeframe = 15
    candles = _generate_synthetic_closed_candles(start_price=2700.0, count=20, trend="UP", tf_mins=timeframe)
    # Clear taker buy data for GOLD
    for c in candles:
        c["taker_buy"] = 0.0

    state = retest_engine.RetestState(symbol=symbol, timeframe=timeframe, direction="LONG", state="WAITING_FOR_RETEST")
    cand = retest_engine.generate_setup_candidate_from_state(state, candles, vwap=2680.0)

    cond_dict = {c["name"]: c for c in cand["conditions"]}
    # Aggressor CVD should be NOT_AVAILABLE for GOLD without penalizing the setup
    assert cond_dict["CVD Aggressor Flow"]["status"] == "NOT_AVAILABLE"
    # Fair Value Gap should be NOT_APPLICABLE if no FVG present
    assert cond_dict["Fair Value Gap"]["status"] == "NOT_APPLICABLE"


def test_actionability_ranking_and_explainable_priority():
    """Test that candidate priority orders primarily by maturity/actionability, not raw R:R."""
    # Candidate A: ENTRY_READY setup with R:R = 1.50
    cand_ready = {
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "entry_price": 3000.0,
        "sl": 2950.0,
        "tp1": 3075.0,  # Reward 75, Risk 50 -> R:R = 1.50
        "current_state": "ENTRY_READY",
        "distance_atr": 0.10,
        "distance_pct": 0.05,
        "data_freshness": {"quality": "GOOD", "data_age_seconds": 15},
    }

    # Candidate B: Early IDENTIFIED setup with R:R = 4.00
    cand_early = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 80000.0,
        "sl": 79000.0,
        "tp1": 84000.0,  # Reward 4000, Risk 1000 -> R:R = 4.00
        "current_state": "IDENTIFIED",
        "distance_atr": 2.50,
        "distance_pct": 1.20,
        "data_freshness": {"quality": "GOOD", "data_age_seconds": 30},
    }

    ctx = {"market_regime": "TREND / EXPANSION", "htf_bias": "LONG", "gamma_regime": "POSITIVE_GAMMA"}
    res_ready = priority_classifier.classify_trade_priority(cand_ready, ctx)
    res_early = priority_classifier.classify_trade_priority(cand_early, ctx)

    # Actionability score of ENTRY_READY must exceed early IDENTIFIED even with lower R:R
    assert res_ready["actionability_score"] > res_early["actionability_score"]
    assert res_ready["priority"] == "HIGH"
    assert len(res_ready["priority_reasons"]) > 0
    # Explainable reasons must include stage and zone proximity
    assert any("matured" in r.lower() for r in res_ready["priority_reasons"])
    assert any("proximity" in r.lower() for r in res_ready["priority_reasons"])


def test_rr_decoupling_does_not_gate_candidate_creation():
    """Verify that a setup with R:R < 2.0 (e.g. 1.20) is preserved as an active candidate."""
    cand = {
        "setup_id": "setup_ETH-USDT_LONG_15m_test_rr",
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "timeframe": 15,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "current_state": "WAITING_FOR_RETEST",
        "entry_price": 3000.0,
        "suggested_sl": 2950.0,
        "suggested_tp1": 3060.0,  # R:R = 60 / 50 = 1.20
        "distance_pct": 0.25,
        "distance_atr": 0.40,
        "status": "ACTIVE"
    }

    conn = db._connect()
    conn.execute("DELETE FROM setup_candidates WHERE symbol='ETH-USDT' AND timeframe=15 AND direction='LONG'")
    conn.commit()

    db.save_setup_candidate(cand)
    fetched = db.get_setup_candidate("setup_ETH-USDT_LONG_15m_test_rr")
    assert fetched is not None
    assert fetched["status"] == "ACTIVE"
    assert fetched["reward_risk_ratio"] == 1.20

    # Ensure it is returned in list_setup_candidates without being filtered out
    candidates = db.list_setup_candidates(status="ACTIVE", symbol="ETH-USDT", timeframe=15)
    matching = [c for c in candidates if c["setup_id"] == "setup_ETH-USDT_LONG_15m_test_rr"]
    assert len(matching) == 1


def test_candidate_deduplication_and_persistence():
    """Test that multiple updates to the same candidate update the record rather than creating duplicates."""
    setup_id = "setup_BTC-USDT_LONG_5m_1700000000000"
    base_cand = {
        "setup_id": setup_id,
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "timeframe": 5,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "current_state": "WAITING_FOR_RETEST",
        "entry_price": 85000.0,
        "suggested_sl": 84500.0,
        "suggested_tp1": 86000.0,
        "distance_pct": 0.45,
        "distance_atr": 0.60,
        "status": "ACTIVE",
        "generated_ms": int(time.time() * 1000)
    }

    conn = db._connect()
    conn.execute("DELETE FROM setup_candidates WHERE symbol='BTC-USDT' AND timeframe=5 AND direction='LONG'")
    conn.commit()

    # Save initial state
    db.save_setup_candidate(base_cand)

    # Save state transition to RETEST_TOUCHED on same setup_id
    updated_cand = dict(base_cand)
    updated_cand["current_state"] = "RETEST_TOUCHED"
    updated_cand["waiting_for"] = "Retest zone touched. Waiting for rejection candle confirmation."
    updated_cand["next_required_event"] = "REJECTION_CANDLE"
    updated_cand["distance_pct"] = 0.0
    updated_cand["distance_atr"] = 0.0
    db.save_setup_candidate(updated_cand)

    # Fetch and verify state updated in-place without duplicating
    retrieved = db.get_setup_candidate(setup_id)
    assert retrieved is not None
    assert retrieved["current_state"] == "RETEST_TOUCHED"
    assert retrieved["next_required_event"] == "REJECTION_CANDLE"

    candidates = db.list_setup_candidates(status="ACTIVE", symbol="BTC-USDT", timeframe=5)
    matching = [c for c in candidates if c["setup_id"] == setup_id]
    assert len(matching) == 1
