"""Unit tests for Candidate-Level Outcome Tracking and Comparative Engine.

Layer: tests/test_candidate_research.py
"""
import pytest
from control_plane import db
from control_plane.candidate_research import (
    CandidateOutcomeTracker,
    ComparativeMarketEngine,
)


def test_outcome_tracker_long_tp1_win():
    cand = {
        "direction": "LONG",
        "entry_price": 100.0,
        "sl_price": 95.0,
        "tp1_price": 110.0,
        "tp2_price": 115.0,
    }
    # Future bars where price climbs to 112 without dropping below 98
    future_bars = [
        {"ts": 1000, "open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0},
        {"ts": 2000, "open": 102.0, "high": 106.0, "low": 101.0, "close": 105.0},
        {"ts": 3000, "open": 105.0, "high": 112.0, "low": 104.0, "close": 111.0},  # TP1 hit at bar 3 (15m)
        {"ts": 4000, "open": 111.0, "high": 113.0, "low": 108.0, "close": 110.0},
    ]

    res = CandidateOutcomeTracker.evaluate_outcome(cand, future_bars)
    assert res["tp1_hit"] == 1
    assert res["sl_hit"] == 0
    assert res["exit_reason"] == "TP1"
    assert res["time_to_exit_min"] == 15
    assert res["mfe"] == 13.0  # max high (113) - entry (100)
    assert res["mae"] == -1.0  # min low (99) - entry (100)
    assert res["realized_r_multiple"] == 2.0  # (110 - 100) / (100 - 95) = 10 / 5 = 2.0


def test_outcome_tracker_long_sl_loss():
    cand = {
        "direction": "LONG",
        "entry_price": 100.0,
        "sl_price": 95.0,
        "tp1_price": 110.0,
    }
    # Future bars where price drops to 94 before reaching TP1
    future_bars = [
        {"ts": 1000, "open": 100.0, "high": 101.0, "low": 97.0, "close": 98.0},
        {"ts": 2000, "open": 98.0, "high": 99.0, "low": 94.0, "close": 95.0},  # SL hit at bar 2 (10m)
        {"ts": 3000, "open": 95.0, "high": 112.0, "low": 94.0, "close": 110.0},
    ]

    res = CandidateOutcomeTracker.evaluate_outcome(cand, future_bars)
    assert res["tp1_hit"] == 0
    assert res["sl_hit"] == 1
    assert res["exit_reason"] == "SL"
    assert res["time_to_exit_min"] == 10
    assert res["realized_r_multiple"] == -1.0


def test_outcome_tracker_short_tp1_win():
    cand = {
        "direction": "SHORT",
        "entry_price": 100.0,
        "sl_price": 105.0,
        "tp1_price": 90.0,
    }
    future_bars = [
        {"ts": 1000, "open": 100.0, "high": 101.0, "low": 97.0, "close": 98.0},
        {"ts": 2000, "open": 98.0, "high": 99.0, "low": 88.0, "close": 89.0},  # TP1 hit
    ]

    res = CandidateOutcomeTracker.evaluate_outcome(cand, future_bars)
    assert res["tp1_hit"] == 1
    assert res["sl_hit"] == 0
    assert res["exit_reason"] == "TP1"
    assert res["mfe"] == 12.0  # entry (100) - min low (88) = 12.0
    assert res["realized_r_multiple"] == 2.0


def test_comparative_market_engine_matching():
    binance_cands = [
        {"candidate_id": "BN-1", "symbol": "BTCUSDT", "direction": "LONG", "timestamp_ms": 1700000000000, "entry_price": 86000.0},
        {"candidate_id": "BN-2", "symbol": "ETHUSDT", "direction": "SHORT", "timestamp_ms": 1700000600000, "entry_price": 3000.0},
    ]
    bingx_cands = [
        # BTC matched within 5 minutes
        {"candidate_id": "BX-1", "symbol": "BTCUSDT", "direction": "LONG", "timestamp_ms": 1700000300000, "entry_price": 86015.0},
    ]

    comparisons = ComparativeMarketEngine.match_candidates(binance_cands, bingx_cands, window_tolerance_ms=600_000)
    assert len(comparisons) == 2

    # BTC is paired
    btc_comp = comparisons[0]
    assert btc_comp["status"] == "PAIRED"
    assert btc_comp["timestamp_delta_ms"] == 300_000
    assert btc_comp["entry_price_delta"] == 15.0
    assert btc_comp["direction_match"] is True

    # ETH is Binance only
    eth_comp = comparisons[1]
    assert eth_comp["status"] == "BINANCE_ONLY"
    assert eth_comp["bingx_candidate_id"] is None


def test_candidate_research_db_persistence():
    row = {
        "candidate_id": "TEST-CAND-DB-001",
        "symbol": "TEST-BTCUSDT",
        "timestamp_ms": 1700000000000,
        "direction": "LONG",
        "entry_price": 86000.0,
        "sl_price": 85000.0,
        "tp1_price": 88000.0,
        "tp2_price": 89000.0,
        "expected_horizon": "15m-60m",
        "regime": "TREND",
        "data_venue": "BINANCE",
        "execution_venue": "BINGX",
        "forecast_id": "FC-123",
        "q10": 85500.0,
        "q50": 87000.0,
        "q90": 88500.0,
        "dispersion_pct": 3.4,
        "forecast_direction": "BULLISH",
        "trade_compatibility": "COMPATIBLE",
        "mfe": 2200.0,
        "mae": -200.0,
        "tp1_hit": 1,
        "tp2_hit": 0,
        "sl_hit": 0,
        "exit_reason": "TP1",
        "time_to_exit_min": 25,
        "realized_r_multiple": 2.0,
        "return_15m": 1.2,
        "return_30m": 2.3,
        "return_45m": 2.1,
        "return_60m": 2.0,
        "binance_price_at_entry": 86000.0,
        "bingx_price_at_entry": 86010.0,
        "basis_pct_at_entry": 0.0116,
        "evaluation_status": "COMPLETE"
    }

    db.insert_candidate_outcome(row)
    outcomes = db.list_candidate_outcomes(symbol="TEST-BTCUSDT", limit=10)
    assert len(outcomes) >= 1
    found = next((o for o in outcomes if o["candidate_id"] == "TEST-CAND-DB-001"), None)
    assert found is not None
    assert found["direction"] == "LONG"
    assert found["trade_compatibility"] == "COMPATIBLE"
    assert found["tp1_hit"] == 1
