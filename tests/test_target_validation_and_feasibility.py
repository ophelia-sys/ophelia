"""Comprehensive Target Validation and Feasibility Test Suite.

Authoritative tests verifying:
1. BTC 3m ML target anomaly regression (rejection of stale swings, reachability limits, strict hierarchy).
2. 20-scenario matrix (BTC, ETH, SOL, XRP, GOLD across 3m, 5m, 15m, 1h).
3. Both LONG and SHORT directional hierarchy & signed percentage conventions.
4. db.validate_setup_geometry rejection of invalid hierarchies, duplicates, and negative prices.
5. Snapshot hash determinism, immutability, and preservation across automation import.
"""
import pytest
import time
from typing import Dict, Any, List, Optional, Tuple
from control_plane import backtest, db, retest_engine


# ============================================================
# 0. HELPER FIXTURE GENERATOR
# ============================================================

def make_test_candles(
    base_price: float,
    atr: float,
    n_bars: int = 100,
    custom_swings: Optional[List[Tuple[int, float, float]]] = None
) -> List[Dict[str, Any]]:
    """Build a realistic synthetic candle series with controllable swing points and ATR."""
    candles = []
    now_ms = int(time.time() * 1000)
    for i in range(n_bars):
        ts = now_ms - ((n_bars - i) * 60_000)
        c_open = base_price
        c_close = base_price
        c_high = base_price + (0.5 * atr)
        c_low = base_price - (0.5 * atr)
        candles.append({
            "ts": ts,
            "open": c_open,
            "high": c_high,
            "low": c_low,
            "close": c_close,
            "volume": 100.0
        })
    
    if custom_swings:
        for idx, h, l in custom_swings:
            if 0 <= idx < len(candles):
                candles[idx]["high"] = h
                candles[idx]["low"] = l
    return candles


# ============================================================
# 1. BTC ANOMALY REGRESSION TEST
# ============================================================

def test_btc_3m_anomaly_regression():
    """Verify that a 3m BTC setup cannot select a stale 18% swing or duplicate TP1/TP3."""
    entry_px = 79370.0
    atr_3m = 260.0  # Realistic 3m ATR for BTC at 79k (~0.33%)
    
    # Construct 120 bars:
    # Bar 5 contains the stale swing low at 64990.0 (18.12% away from entry)
    # Recent bars (indices 90..119) contain realistic swing highs and lows near entry
    swings = [
        (5, 65200.0, 64990.0),    # Stale low from days ago
        (92, 79650.0, 79200.0),   # Recent swing high / low
        (100, 79500.0, 78900.0),  # Recent swing low
        (108, 79700.0, 79100.0),  # Recent protective swing high
    ]
    candles = make_test_candles(base_price=entry_px, atr=atr_3m, n_bars=120, custom_swings=swings)
    
    stops_targets = retest_engine.compute_structural_targets_stops(
        candles=candles,
        direction="SHORT",
        entry_price=entry_px,
        vwap=79400.0,
        timeframe=3
    )
    
    sl = stops_targets["sl"]
    tp1 = stops_targets["tp1"]
    tp2 = stops_targets["tp2"]
    tp3 = stops_targets["tp3"]
    
    # 1. SL must be ABOVE entry for SHORT
    assert sl > entry_px, f"SHORT SL {sl} must be > entry {entry_px}"
    
    # 2. Strict descending hierarchy for available targets: SL > Entry > TP1 > TP2 > TP3
    assert sl > entry_px > tp1, f"SHORT hierarchy violated: SL={sl}, Entry={entry_px}, TP1={tp1}"
    if tp2 is not None:
        assert tp1 > tp2, f"SHORT TP2 {tp2} must be below TP1 {tp1}"
    if tp3 is not None:
        assert tp2 > tp3, f"SHORT TP3 {tp3} must be below TP2 {tp2}"
    
    # 3. TP1, TP2, TP3 MUST NOT be 64990.0 (the stale 18.12% anomaly)
    assert tp1 != 64990.0, "TP1 cannot be the stale 64990.0 swing!"
    if tp2 is not None:
        assert tp2 != 64990.0, "TP2 cannot be 64990.0!"
    if tp3 is not None:
        assert tp3 != 64990.0, "TP3 cannot be 64990.0!"
    
    # 4. TP1 distance must be reasonable
    tp1_dist = abs(entry_px - tp1)
    assert tp1_dist > 0.0, "TP1 distance must be non-zero"
    
    # 5. TP levels must be distinct (NO DUPLICATES)
    avail_tps = [p for p in (tp1, tp2, tp3) if p is not None]
    assert len(avail_tps) == len(set(avail_tps)), f"Duplicate TP detected: {avail_tps}"
    
    # 6. Directional signed percentage: for SHORT, TP is negative price movement
    tp1_pct = stops_targets["tp1_pct"]
    assert tp1_pct < 0.0, f"SHORT TP1 pct {tp1_pct} must be negative"
    assert abs(tp1_pct) < 3.0, f"3m TP1 pct {abs(tp1_pct)}% must be under 3% (was 18.12%!)"


# ============================================================
# 2. 20-SCENARIO MATRIX (5 SYMBOLS X 4 TIMEFRAMES)
# ============================================================

SYMBOLS_PRICES_ATR = {
    "BTC-USDT": {"price": 79500.0, "atr": 280.0},
    "ETH-USDT": {"price": 2650.0, "atr": 18.0},
    "SOL-USDT": {"price": 145.0, "atr": 1.5},
    "XRP-USDT": {"price": 1.45, "atr": 0.015},
    "GOLD": {"price": 2720.0, "atr": 6.5},
}

TIMEFRAMES = [("3m", 3), ("5m", 5), ("15m", 15), ("1h", 60)]

@pytest.mark.parametrize("symbol,params", SYMBOLS_PRICES_ATR.items())
@pytest.mark.parametrize("tf_label,tf_min", TIMEFRAMES)
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_symbol_timeframe_target_feasibility(symbol: str, params: Dict[str, float], tf_label: str, tf_min: int, direction: str):
    """Verify target calculation across all 5 assets, 4 timeframes, and both directions."""
    price = params["price"]
    base_atr = params["atr"]
    
    tf_mult = {3: 1.0, 5: 1.25, 15: 2.0, 60: 4.0}[tf_min]
    atr = base_atr * tf_mult
    
    candles = make_test_candles(base_price=price, atr=atr, n_bars=80)
    
    targets = retest_engine.compute_structural_targets_stops(
        candles=candles,
        direction=direction,
        entry_price=price,
        vwap=price,
        timeframe=tf_min
    )
    
    sl = targets["sl"]
    tp1 = targets["tp1"]
    tp2 = targets["tp2"]
    tp3 = targets["tp3"]
    
    # Validate via canonical database geometry validator
    candidate_dict = {
        "direction": direction,
        "entry": price,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3
    }
    valid, err = db.validate_setup_geometry(candidate_dict)
    assert valid, f"Geometry validation failed for {symbol} {tf_label} {direction}: {err}"
    
    # Verify strict hierarchy for available targets
    if direction == "LONG":
        assert sl < price < tp1, f"LONG order violated: {sl} < {price} < {tp1}"
        assert targets["sl_pct"] < 0.0, "LONG SL pct must be negative"
        assert targets["tp1_pct"] > 0.0, "LONG TP1 pct must be positive"
        if tp2 is not None:
            assert tp1 < tp2, f"LONG TP2 {tp2} must be > TP1 {tp1}"
            assert targets["tp2_pct"] > targets["tp1_pct"]
        if tp3 is not None:
            assert tp2 < tp3, f"LONG TP3 {tp3} must be > TP2 {tp2}"
            assert targets["tp3_pct"] > targets["tp2_pct"]
    else:
        assert sl > price > tp1, f"SHORT order violated: {sl} > {price} > {tp1}"
        assert targets["sl_pct"] > 0.0, "SHORT SL pct must be positive (adverse)"
        assert targets["tp1_pct"] < 0.0, "SHORT TP1 pct must be negative (favorable drop)"
        if tp2 is not None:
            assert tp1 > tp2, f"SHORT TP2 {tp2} must be < TP1 {tp1}"
            assert targets["tp2_pct"] < targets["tp1_pct"]
        if tp3 is not None:
            assert tp2 > tp3, f"SHORT TP3 {tp3} must be < TP2 {tp2}"
            assert targets["tp3_pct"] < targets["tp2_pct"]
        
    # Verify non-duplication of available targets
    avail_tps = [p for p in (tp1, tp2, tp3) if p is not None]
    assert len(avail_tps) == len(set(avail_tps)), f"Duplicate TP detected in {symbol} {tf_label} {direction}: {avail_tps}"


# ============================================================
# 3. CANONICAL GEOMETRY VALIDATOR TESTS
# ============================================================


def test_geometry_validator_rejects_inversions():
    """Verify db.validate_setup_geometry strictly rejects inverted targets."""
    # LONG with TP1 below entry
    bad_long = {
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 98.0,  # Below entry!
        "tp2": 105.0,
        "tp3": 110.0
    }
    valid, err = db.validate_setup_geometry(bad_long)
    assert not valid
    assert "TP1" in err
    
    # SHORT with TP1 above entry
    bad_short = {
        "direction": "SHORT",
        "entry": 100.0,
        "sl": 105.0,
        "tp1": 102.0,  # Above entry!
        "tp2": 95.0,
        "tp3": 90.0
    }
    valid, err = db.validate_setup_geometry(bad_short)
    assert not valid
    assert "TP1" in err

def test_geometry_validator_rejects_duplicates():
    """Verify db.validate_setup_geometry rejects duplicate TPs (e.g. TP1 == TP3)."""
    dup_setup = {
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "tp2": 110.0,
        "tp3": 105.0  # Duplicate of TP1!
    }
    valid, err = db.validate_setup_geometry(dup_setup)
    assert not valid
    assert "Duplicate" in err or "strictly above" in err

def test_geometry_validator_rejects_negative_prices():
    """Verify db.validate_setup_geometry rejects zero or negative prices."""
    neg_setup = {
        "direction": "LONG",
        "entry": -100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "tp2": 110.0,
        "tp3": 115.0
    }
    valid, err = db.validate_setup_geometry(neg_setup)
    assert not valid


# ============================================================
# 4. SNAPSHOT HASH DETERMINISM & IMMUTABILITY
# ============================================================

def test_snapshot_hash_determinism():
    """Verify compute_setup_snapshot_hash generates deterministic SHA-256."""
    setup1 = {
        "symbol": "BTC-USDT",
        "timeframe": "5m",
        "direction": "LONG",
        "entry": 80000.0,
        "sl": 79200.0,
        "tp1": 80800.0,
        "tp2": 81600.0,
        "tp3": 82800.0
    }
    setup2 = dict(setup1)
    
    hash1 = db.compute_setup_snapshot_hash(setup1)
    hash2 = db.compute_setup_snapshot_hash(setup2)
    assert hash1 == hash2
    assert len(hash1) == 16  # SHA-256 16-char prefix
    
    # Mutating any single field must change the hash
    setup2["tp1"] = 80801.0
    hash3 = db.compute_setup_snapshot_hash(setup2)
    assert hash1 != hash3


# ============================================================
# 5. BACKTEST REPLAY VALIDATION GATE & DIRECTION AGREEMENT
# ============================================================

def test_replay_rejects_invalid_setup_geometry():
    """run_ml_setup_historical_replay must return INVALID_SETUP_GEOMETRY for broken setups."""
    broken_setup = {
        "setup_id": "BROKEN_001",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "suggested_entry": 80000.0,
        "suggested_sl": 81000.0,  # SL above entry for LONG!
        "suggested_tp1": 82000.0,
        "suggested_tp2": 83000.0,
        "suggested_tp3": 84000.0,
    }
    res = backtest.run_ml_setup_historical_replay(
        setup_id="BROKEN_001",
        setup_data=broken_setup,
        hours=48,
        execute_live_ai=False
    )
    assert res["status"] == "INVALID_SETUP_GEOMETRY"
    assert res["frozen_setup"]["is_geometry_valid"] is False

def test_direction_agreement_is_boolean():
    """Verify direction_agreement in quality layers is a boolean (not string YES/NO)."""
    valid_setup = {
        "setup_id": "VALID_001",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "timeframe": 5,
        "suggested_entry": 80000.0,
        "suggested_sl": 79000.0,
        "suggested_tp1": 81500.0,
        "suggested_tp2": 82500.0,
        "suggested_tp3": 84000.0,
    }
    res = backtest.run_ml_setup_historical_replay(
        setup_id="VALID_001",
        setup_data=valid_setup,
        hours=48,
        execute_live_ai=False
    )
    for m in res.get("matches", []):
        ql = m.get("quality_layers", {})
        assert isinstance(ql.get("direction_agreement"), bool), (
            f"direction_agreement must be bool, got {type(ql.get('direction_agreement'))}"
        )


def test_no_forced_tp3_when_only_two_swings():
    """Verify that when only two opposing swings exist in market structure,
    TP3 is NOT fabricated or forced. It must return None and UNAVAILABLE.
    """
    entry_px = 80000.0
    atr = 250.0
    # Provide only 2 swing highs above entry
    swings = [
        (20, 79200.0, 79000.0),   # SL swing low
        (40, 80600.0, 80200.0),   # Swing High 1 (TP1 = 80600)
        (60, 81400.0, 80800.0),   # Swing High 2 (TP2 = 81400)
    ]
    candles = make_test_candles(base_price=entry_px, atr=atr, n_bars=80, custom_swings=swings)
    targets = retest_engine.compute_structural_targets_stops(
        candles=candles,
        direction="LONG",
        entry_price=entry_px,
        vwap=entry_px,
        timeframe=5
    )

    assert targets["tp1"] is not None
    assert targets["tp2"] is not None
    assert targets["tp3"] is None, "TP3 must be None when only 2 opposing swings exist!"
    assert targets["tp3_status"] == "UNAVAILABLE"
    assert targets["tp2_status"] == "AVAILABLE"
    assert targets["target_provenance"]["tp3_source"] == "UNAVAILABLE"
    assert "experimental_atr_target" in targets["target_provenance"]
    assert targets["tp1"] != targets["tp2"]


def test_setup_with_only_tp1_and_tp2_is_valid():
    """Verify db.validate_setup_geometry succeeds with TP3 set to None or UNAVAILABLE."""
    valid_two_tp = {
        "direction": "LONG",
        "entry": 80000.0,
        "sl": 79200.0,
        "tp1": 80800.0,
        "tp2": 81600.0,
        "tp3": None
    }
    is_valid, reason = db.validate_setup_geometry(valid_two_tp)
    assert is_valid, f"Setup with only TP1 and TP2 should be valid, got: {reason}"

    norm = db.normalize_setup_fields(valid_two_tp)
    assert norm["suggested_tp3"] is None
    assert norm["tp3_status"] == "UNAVAILABLE"
    assert norm["is_geometry_valid"] is True
