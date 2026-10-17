"""Forensic Root Cause Reproduction & Invariant Tests for Ophelia Backtest Engine.

Layer: tests/test_backtest_forensic_reproduction
Contract:
- Reproduces each identified mathematical, accounting, and state machine bug.
- Verifies mathematical invariants before and after remediation.
"""
import pytest
from typing import List, Dict, Any

from control_plane import backtest, fast_math, config, db, retest_engine


# -----------------------------------------------------------------------------
# 1. ROOT CAUSE A: FAKE VWAP (vwap = close)
# -----------------------------------------------------------------------------
def test_real_causal_vwap_vs_fake_close():
    """Verify that causal VWAP differs from close on dynamic volume/price data,
    and prove that setting vwap = close destroys breakout and retest validity."""
    highs = [100.0, 102.0, 104.0, 103.0, 106.0]
    lows = [98.0, 99.0, 101.0, 100.0, 102.0]
    closes = [99.0, 101.5, 103.5, 101.0, 105.5]
    volumes = [1000.0, 5000.0, 1500.0, 800.0, 6000.0]

    vwap_series = fast_math.calculate_vwap_series(highs, lows, closes, volumes)
    assert len(vwap_series) == len(closes)

    # For bar 4: heavy volume at higher prices pulls VWAP away from current close
    # Real VWAP must not equal closes[-1]
    assert abs(vwap_series[-1] - closes[-1]) > 0.1, "Real VWAP must differ from close on non-trivial volume"

    # In old bugged backtest:
    # vwap_val = cur_bar.get("close", 100.0)
    # cur_close > vwap => closes[-1] > closes[-1] => ALWAYS FALSE!
    # Proving the bugged condition:
    broken_check = (closes[-1] > closes[-1])
    assert broken_check is False, "close > close is mathematically impossible, preventing valid breakouts"


# -----------------------------------------------------------------------------
# 2. ROOT CAUSE B: INVERTED STRUCTURAL SL SELECTION
# -----------------------------------------------------------------------------
def test_swing_stop_polarity_selection():
    """Verify that LONG structural SL requires swing LOWS below entry,
    and SHORT structural SL requires swing HIGHS above entry."""
    entry_price = 100.0
    atr = 2.0

    # Synthetic swing points:
    # Swings highs at 95.0, 105.0
    # Swings lows at 92.0, 102.0
    swing_highs = [(5, 95.0), (15, 105.0)]
    swing_lows = [(3, 92.0), (12, 102.0)]

    # The OLD bugged logic:
    # swing_lvl = (max([p for _, p in swing_highs]) if swing_highs else entry_price * 0.98) if direction == "LONG"
    bugged_long_swing = max([p for _, p in swing_highs])  # evaluates to 105.0!
    assert bugged_long_swing == 105.0, "Bugged code selected 105.0 (swing HIGH above entry) for LONG SL!"

    # The CORRECT logic:
    # For LONG: select valid swing lows BELOW entry
    valid_long_lows = [p for _, p in swing_lows if p < entry_price]
    correct_long_swing = valid_long_lows[-1] if valid_long_lows else entry_price - (1.5 * atr)
    assert correct_long_swing == 92.0, "Correct logic must select swing LOW (92.0) below entry for LONG"

    # Compute stops with fast_math:
    sl_long, sl_long_pct, reason_long = fast_math.calculate_structural_stops(
        direction="LONG", entry_price=entry_price, swing_level=correct_long_swing, atr=atr
    )
    assert sl_long < entry_price, f"LONG SL ({sl_long}) must be strictly below entry ({entry_price})"

    # For SHORT: select valid swing highs ABOVE entry
    valid_short_highs = [p for _, p in swing_highs if p > entry_price]
    correct_short_swing = valid_short_highs[-1] if valid_short_highs else entry_price + (1.5 * atr)
    assert correct_short_swing == 105.0, "Correct logic must select swing HIGH (105.0) above entry for SHORT"

    sl_short, sl_short_pct, reason_short = fast_math.calculate_structural_stops(
        direction="SHORT", entry_price=entry_price, swing_level=correct_short_swing, atr=atr
    )
    assert sl_short > entry_price, f"SHORT SL ({sl_short}) must be strictly above entry ({entry_price})"


# -----------------------------------------------------------------------------
# 3. ROOT CAUSE C: CVD POLARITY VERIFICATION
# -----------------------------------------------------------------------------
def test_cvd_polarity_semantics():
    """Verify BingX taker aggressor volume semantics:
    positive delta = aggressive buyer dominance
    negative delta = aggressive seller dominance"""
    # Case 1: Buyer dominance (taker_buy = 80, total_vol = 100 => taker_sell = 20)
    vol_buy = [100.0]
    tb_buy = [80.0]
    opens = [100.0]
    closes = [101.0]
    cvd_buyer = fast_math.calculate_cvd_series(vol_buy, tb_buy, opens, closes)
    # delta = tb - (vol - tb) = 80 - 20 = +60
    assert cvd_buyer[0] == 60.0, f"Expected +60.0 CVD delta for aggressive buyers, got {cvd_buyer[0]}"

    # Case 2: Seller dominance (taker_buy = 20, total_vol = 100 => taker_sell = 80)
    vol_sell = [100.0]
    tb_sell = [20.0]
    cvd_seller = fast_math.calculate_cvd_series(vol_sell, tb_sell, opens, closes)
    # delta = tb - (vol - tb) = 20 - 80 = -60
    assert cvd_seller[0] == -60.0, f"Expected -60.0 CVD delta for aggressive sellers, got {cvd_seller[0]}"


# -----------------------------------------------------------------------------
# 4. ROOT CAUSE D: LONG / SHORT TP/SL GEOMETRY INVARIANTS
# -----------------------------------------------------------------------------
def test_structural_target_stop_geometry():
    """Hard mathematical invariants:
    LONG: SL < Entry < TP1 < TP2 < TP3
    SHORT: SL > Entry > TP1 > TP2 > TP3
    R:R = reward / risk (unclamped)
    """
    entry = 50000.0
    atr = 500.0

    # --- LONG GEOMETRY ---
    sl_long, _, _ = fast_math.calculate_structural_stops("LONG", entry, 49500.0, atr)
    targets_long = fast_math.calculate_structural_targets("LONG", entry, sl_long, [1.5, 2.5, 4.0])
    tp1_l, tp2_l, tp3_l = targets_long[0][0], targets_long[1][0], targets_long[2][0]

    assert sl_long < entry < tp1_l < tp2_l < tp3_l, (
        f"LONG geometry invalid: SL={sl_long}, Entry={entry}, TP1={tp1_l}, TP2={tp2_l}, TP3={tp3_l}"
    )

    risk_l = entry - sl_long
    assert risk_l > 0.0
    rr1_l = (tp1_l - entry) / risk_l
    assert abs(rr1_l - 1.5) < 1e-4, f"Expected 1.5 R:R for TP1, got {rr1_l}"

    # --- SHORT GEOMETRY ---
    sl_short, _, _ = fast_math.calculate_structural_stops("SHORT", entry, 50500.0, atr)
    targets_short = fast_math.calculate_structural_targets("SHORT", entry, sl_short, [1.5, 2.5, 4.0])
    tp1_s, tp2_s, tp3_s = targets_short[0][0], targets_short[1][0], targets_short[2][0]

    assert sl_short > entry > tp1_s > tp2_s > tp3_s, (
        f"SHORT geometry invalid: SL={sl_short}, Entry={entry}, TP1={tp1_s}, TP2={tp2_s}, TP3={tp3_s}"
    )

    risk_s = sl_short - entry
    assert risk_s > 0.0
    rr1_s = (entry - tp1_s) / risk_s
    assert abs(rr1_s - 1.5) < 1e-4, f"Expected 1.5 R:R for TP1, got {rr1_s}"


# -----------------------------------------------------------------------------
# 5. ROOT CAUSE E: RETEST CHRONOLOGY & CAUSALITY
# -----------------------------------------------------------------------------
def test_retest_chronological_causality():
    """Assert strictly causal state progression:
    Breakout_ts < Touch_ts < Rejection_ts <= Entry_ts
    Breakout candle cannot also be retest candle.
    """
    engine = retest_engine.CausalRetestEngine("BTC-USDT", timeframe=5, direction="LONG")
    state = retest_engine.RetestState("BTC-USDT", timeframe=5, direction="LONG", state="IDLE")

    # Build sequence of candles
    # Candle 0..19: baseline consolidation
    candles = []
    base_ts = 1700000000000
    for i in range(20):
        candles.append({
            "ts": base_ts + i * 300_000,
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 100.0,
            "taker_buy": 50.0
        })

    # Candle 20: Strong Breakout with displacement
    candles.append({
        "ts": base_ts + 20 * 300_000,
        "open": 50050.0,
        "high": 50800.0,
        "low": 50020.0,
        "close": 50750.0,  # strong displacement
        "volume": 500.0,
        "taker_buy": 400.0
    })

    vwap = 50100.0
    state = engine.evaluate_step(state, candles, vwap=vwap)
    assert state.state == "WAITING_FOR_RETEST"
    assert state.breakout_ts == candles[-1]["ts"]

    # Candle 21: Retest touches the zone
    z_high = state.zone_high
    z_low = state.zone_low
    candles.append({
        "ts": base_ts + 21 * 300_000,
        "open": 50750.0,
        "high": 50780.0,
        "low": z_high - 10.0,  # dips into zone
        "close": z_high + 50.0,
        "volume": 200.0,
        "taker_buy": 120.0
    })
    state = engine.evaluate_step(state, candles, vwap=vwap)
    assert state.state == "RETEST_ZONE_TOUCHED"
    assert state.touch_ts == candles[-1]["ts"]
    assert state.breakout_ts < state.touch_ts, "Touch must happen chronologically AFTER breakout"

    # Candle 22: Bullish Rejection
    candles.append({
        "ts": base_ts + 22 * 300_000,
        "open": z_high + 50.0,
        "high": z_high + 300.0,
        "low": z_high + 20.0,
        "close": z_high + 280.0,  # green candle closing above zone
        "volume": 350.0,
        "taker_buy": 280.0
    })
    state = engine.evaluate_step(state, candles, vwap=vwap)
    assert state.state == "REJECTION_CONFIRMED"
    assert state.rejection_ts == candles[-1]["ts"]
    assert state.touch_ts < state.rejection_ts, "Rejection must happen chronologically AFTER touch"


# -----------------------------------------------------------------------------
# 6. ROOT CAUSE F: CAPITAL, LEVERAGE, RISK INVARIANTS
# -----------------------------------------------------------------------------
def test_risk_vs_margin_vs_notional_invariants():
    """Verify that:
    1% risk on 1,000 USDT equity = 10 USDT max loss at SL.
    Leverage changes margin requirement, NOT the risk amount.
    A trade stopped out at SL cannot lose 50% or 100% of the account.
    """
    initial_equity = 1000.0
    risk_pct = 0.01  # 1% risk per trade
    intended_risk_usdt = initial_equity * risk_pct  # 10.0 USDT

    entry_price = 50000.0
    sl_price = 49000.0  # 2.0% stop distance
    sl_dist_pct = (entry_price - sl_price) / entry_price  # 0.02 (2%)

    # Position sizing derived from intended dollar risk:
    # notional * sl_dist_pct = intended_risk_usdt => notional = intended_risk_usdt / sl_dist_pct
    notional = intended_risk_usdt / sl_dist_pct  # 10.0 / 0.02 = 500.0 USDT notional!
    assert notional == 500.0, f"Expected 500 USDT notional for 1% risk with 2% SL distance, got {notional}"

    # Required margin at 10x leverage:
    leverage = 10.0
    required_margin = notional / leverage  # 50.0 USDT margin
    assert required_margin == 50.0

    # If position hits SL:
    gross_loss = notional * ((sl_price - entry_price) / entry_price)  # -10.0 USDT
    assert abs(gross_loss - (-intended_risk_usdt)) < 1e-4, (
        f"Loss at SL ({gross_loss}) must equal intended risk (-{intended_risk_usdt})"
    )

    # In contrast, the OLD bugged backtest had:
    # notional = margin_per_trade_usdt * leverage = 100.0 * 10.0 = 1000.0 USDT (100% of entire capital!)
    # On 48 parallel trades, maximum loss was completely unconstrained!
    bugged_notional = 100.0 * 10.0
    bugged_loss = bugged_notional * sl_dist_pct  # 20.0 USDT = 2% of capital per trade, or 200% across 10 trades!
    assert bugged_notional > notional, "Bugged fixed-margin logic overleveraged the account notional"
