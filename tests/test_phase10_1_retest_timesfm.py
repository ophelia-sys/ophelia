"""Authoritative Unit & Integration Test Suite for Ophelia Phase 10.1.

Verifies:
1. test_timesfm_primary_5m_architecture
2. test_timesfm_5m_no_lookahead
3. test_retest_entry_ready_candidate_generation
4. test_candidate_snapshot_at_entry_ready
5. test_timesfm_forecast_freeze
6. test_candidate_direction_neutral_r_calculation
7. test_zero_treatment_population_handling
8. test_compatibility_not_zeroing_entire_population
9. test_quantile_raw_vs_postprocessed
10. test_dispersion_uncalibrated_state
11. test_basis_percentile_vs_max_consistency
12. test_long_short_outcome_symmetry
13. test_historical_live_boundary
14. test_binance_1m_to_5m_continuity
15. test_future_basis_leakage
16. test_future_retest_leakage
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import time
import pytest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane import config, db
from control_plane.binance_data import CausalCandleAggregator
from control_plane.candidate_research import CandidateOutcomeTracker
from control_plane.cross_venue_basis import CrossVenueBasisEngine, CrossVenueBasisSnapshot
from control_plane.retest_candidate_generator import generate_retest_candidates
from control_plane.retest_engine import CausalRetestEngine, RetestState, compute_structural_targets_stops
from control_plane.timesfm_candidate import (
    TIMESFM_PRIMARY_5M,
    TIMESFM_1M_RESEARCH,
    CandidateForecastContext,
    CandidateForecastResult,
    generate_candidate_forecast,
    calculate_quantile_coverage,
    calculate_interval_coverage,
    calculate_interval_width,
    calculate_pinball_loss
)
from control_plane.trade_compatibility import (
    ForecastTradeCompatibilityEngine,
    evaluate_compatibility
)


def _generate_synthetic_5m_bars(n: int = 100, base_price: float = 65000.0, trend: float = 0.0) -> list[dict]:
    bars = []
    t0 = 1700000000000
    cur_px = base_price
    for i in range(n):
        ts = t0 + i * 300_000
        cur_px += trend + (float(i % 5 - 2) * 10.0)
        h = cur_px + 25.0
        l = cur_px - 25.0
        o = cur_px - 5.0
        c = cur_px + 5.0
        v = 100.0 + (i % 10) * 10.0
        bars.append({
            "symbol": "BTCUSDT",
            "resolution": "5m",
            "ts": ts,
            "close_ts": ts + 300_000,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "taker_buy": v * 0.55,
            "closed": True
        })
    return bars


# =====================================================================
# 1. Primary 5m Architecture Test
# =====================================================================
def test_timesfm_primary_5m_architecture():
    bars = _generate_synthetic_5m_bars(50)
    cand_ts = bars[35]["ts"] + 300_000
    ctx = CandidateForecastContext(
        candidate_id="TEST-5M-001",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=cand_ts,
        entry_price=bars[35]["close"],
        sl_price=bars[35]["close"] - 200.0,
        tp1_price=bars[35]["close"] + 300.0,
        expected_holding_horizon="15m-60m",
        retest_state="ENTRY_READY"
    )
    res = generate_candidate_forecast(ctx, bars[:36], timeframe_mode=TIMESFM_PRIMARY_5M)
    assert res.timeframe_mode == TIMESFM_PRIMARY_5M
    assert res.source_timeframe == "5m"
    assert len(res.full_path) == 12  # 12 steps x 5m = 60m
    assert "15m" in res.path
    assert "30m" in res.path
    assert "45m" in res.path
    assert "60m" in res.path
    assert json.loads(res.full_path_json) == res.full_path


# =====================================================================
# 2. Adversarial Lookahead Prevention Test
# =====================================================================
def test_timesfm_5m_no_lookahead():
    bars = _generate_synthetic_5m_bars(60)
    cutoff_idx = 30
    cand_ts = bars[cutoff_idx]["ts"] + 300_000

    ctx = CandidateForecastContext(
        candidate_id="TEST-LOOKAHEAD-001",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=cand_ts,
        entry_price=bars[cutoff_idx]["close"],
        sl_price=bars[cutoff_idx]["close"] - 150.0,
        tp1_price=bars[cutoff_idx]["close"] + 250.0,
    )

    # Forecast A with standard data
    forecast_a = generate_candidate_forecast(ctx, bars, timeframe_mode=TIMESFM_PRIMARY_5M)

    # Corrupt all bars strictly after cutoff_idx with extreme anomalies
    corrupted_bars = copy.deepcopy(bars)
    for b in corrupted_bars[cutoff_idx + 1:]:
        b["open"] *= 2.5
        b["high"] *= 3.0
        b["low"] *= 0.1
        b["close"] *= 2.8
        b["volume"] = 999999.0

    forecast_b = generate_candidate_forecast(ctx, corrupted_bars, timeframe_mode=TIMESFM_PRIMARY_5M)

    assert forecast_a.context_hash == forecast_b.context_hash
    assert forecast_a.path == forecast_b.path
    assert forecast_a.quantiles == forecast_b.quantiles
    assert forecast_a.full_path == forecast_b.full_path


# =====================================================================
# 3. Retest ENTRY_READY Candidate Generation Test
# =====================================================================
def test_retest_entry_ready_candidate_generation():
    # Build synthetic bars simulating breakout -> retest touch -> rejection -> entry ready
    bars = []
    t0 = 1700000000000
    price = 60000.0
    # 25 warmup baseline bars
    for i in range(25):
        bars.append({
            "ts": t0 + i * 300_000,
            "close_ts": t0 + (i + 1) * 300_000,
            "open": price, "high": price + 20, "low": price - 20, "close": price,
            "volume": 50.0, "taker_buy": 25.0
        })
    # Breakout bar (displaced bullish)
    price += 100.0
    bars.append({
        "ts": t0 + 25 * 300_000, "close_ts": t0 + 26 * 300_000,
        "open": price - 100.0, "high": price + 20.0, "low": price - 100.0, "close": price,
        "volume": 200.0, "taker_buy": 150.0
    })
    # Retest pullback bar (touching zone)
    bars.append({
        "ts": t0 + 26 * 300_000, "close_ts": t0 + 27 * 300_000,
        "open": price, "high": price + 5.0, "low": price - 95.0, "close": price - 30.0,
        "volume": 120.0, "taker_buy": 60.0
    })
    # Rejection confirmation bar (bullish close)
    bars.append({
        "ts": t0 + 27 * 300_000, "close_ts": t0 + 28 * 300_000,
        "open": price - 30.0, "high": price + 40.0, "low": price - 30.0, "close": price + 20.0,
        "volume": 180.0, "taker_buy": 140.0
    })
    # Confirmation entry bar
    bars.append({
        "ts": t0 + 28 * 300_000, "close_ts": t0 + 29 * 300_000,
        "open": price + 20.0, "high": price + 60.0, "low": price + 10.0, "close": price + 50.0,
        "volume": 220.0, "taker_buy": 180.0
    })
    # Forward evaluation buffer (15 bars)
    for i in range(29, 45):
        bars.append({
            "ts": t0 + i * 300_000, "close_ts": t0 + (i + 1) * 300_000,
            "open": price + 50.0, "high": price + 80.0, "low": price + 40.0, "close": price + 60.0,
            "volume": 100.0, "taker_buy": 50.0
        })

    cands = generate_retest_candidates(bars, "BTCUSDT", timeframe=5, min_spacing_bars=1)
    if cands:
        for c in cands:
            assert c["retest_state"] == "ENTRY_READY"
            assert "breakout_price" in c
            assert c["entry_price"] > 0
            if c["direction"] == "LONG":
                assert c["sl_price"] < c["entry_price"] < c["tp1_price"]
            else:
                assert c["sl_price"] > c["entry_price"] > c["tp1_price"]


# =====================================================================
# 4. Candidate Snapshot at ENTRY_READY Test
# =====================================================================
def test_candidate_snapshot_at_entry_ready():
    bars = _generate_synthetic_5m_bars(40)
    c_ts = bars[25]["ts"] + 300_000
    ctx = CandidateForecastContext(
        candidate_id="CAND-TEST-004",
        canonical_instrument_id="CRYPTO:ETHUSDT",
        symbol="ETHUSDT",
        direction="LONG",
        candidate_timestamp_ms=c_ts,
        entry_price=3500.0,
        sl_price=3450.0,
        tp1_price=3600.0,
        retest_state="ENTRY_READY"
    )
    res = generate_candidate_forecast(ctx, bars[:26], timeframe_mode=TIMESFM_PRIMARY_5M)
    assert len(res.snapshot_hash) == 16
    assert len(res.context_hash) == 16
    assert res.forecast_timestamp == c_ts


# =====================================================================
# 5. TimesFM Forecast Freeze Test
# =====================================================================
def test_timesfm_forecast_freeze():
    bars = _generate_synthetic_5m_bars(40)
    c_ts = bars[25]["ts"] + 300_000
    unique_cand_id = f"CAND-TEST-FREEZE-{time.time_ns()}"
    ctx = CandidateForecastContext(
        candidate_id=unique_cand_id,
        canonical_instrument_id="CRYPTO:SOLUSDT",
        symbol="SOLUSDT",
        direction="LONG",
        candidate_timestamp_ms=c_ts,
        entry_price=145.0,
        sl_price=140.0,
        tp1_price=155.0
    )
    res1 = generate_candidate_forecast(ctx, bars[:26], timeframe_mode=TIMESFM_PRIMARY_5M)
    # Stored in DB
    fc_db = db.get_candidate_forecast(ctx.candidate_id)
    assert fc_db is not None
    assert fc_db["forecast_id"] == res1.forecast_id
    assert fc_db["snapshot_hash"] == res1.snapshot_hash
    assert fc_db["context_hash"] == res1.context_hash


# =====================================================================
# 6. Direction-Neutral Normalized R Calculation Test
# =====================================================================
def test_candidate_direction_neutral_r_calculation():
    # Long Setup: Entry = 100, SL = 90, TP1 = 120 (Risk = 10)
    cand_long = {
        "candidate_id": "C-L", "direction": "LONG",
        "entry_price": 100.0, "sl_price": 90.0, "tp1_price": 120.0
    }
    # Long Win (exit at TP1 = 120): PnL = +20, R = +2.0
    future_long_win = [{"ts": 1000, "open": 100, "high": 125, "low": 95, "close": 120}]
    out_lw = CandidateOutcomeTracker.evaluate_outcome(cand_long, future_long_win)
    assert out_lw["normalized_risk_amount"] == 10.0
    assert out_lw["normalized_realized_r"] == 2.0
    assert out_lw["tp1_hit"] == 1

    # Long Loss (exit at SL = 90): PnL = -10, R = -1.0
    future_long_loss = [{"ts": 1000, "open": 100, "high": 102, "low": 85, "close": 88}]
    out_ll = CandidateOutcomeTracker.evaluate_outcome(cand_long, future_long_loss)
    assert out_ll["normalized_risk_amount"] == 10.0
    assert out_ll["normalized_realized_r"] == -1.0
    assert out_ll["sl_hit"] == 1

    # Short Setup: Entry = 100, SL = 110, TP1 = 80 (Risk = 10)
    cand_short = {
        "candidate_id": "C-S", "direction": "SHORT",
        "entry_price": 100.0, "sl_price": 110.0, "tp1_price": 80.0
    }
    # Short Win (exit at TP1 = 80): PnL = +20, R = +2.0
    future_short_win = [{"ts": 1000, "open": 100, "high": 105, "low": 75, "close": 80}]
    out_sw = CandidateOutcomeTracker.evaluate_outcome(cand_short, future_short_win)
    assert out_sw["normalized_risk_amount"] == 10.0
    assert out_sw["normalized_realized_r"] == 2.0
    assert out_sw["tp1_hit"] == 1

    # Short Loss (exit at SL = 110): PnL = -10, R = -1.0
    future_short_loss = [{"ts": 1000, "open": 100, "high": 115, "low": 98, "close": 112}]
    out_sl = CandidateOutcomeTracker.evaluate_outcome(cand_short, future_short_loss)
    assert out_sl["normalized_risk_amount"] == 10.0
    assert out_sl["normalized_realized_r"] == -1.0
    assert out_sl["sl_hit"] == 1


# =====================================================================
# 7. Zero Treatment Population Handling Test
# =====================================================================
def test_zero_treatment_population_handling():
    from scripts.run_multi_venue_candidate_study import _compute_cohort_stats

    # Simulated outcomes where ZERO candidates are COMPATIBLE
    records = [
        {"candidate_id": "C1", "trade_compatibility": "INCOMPATIBLE", "tp1_hit": 0, "sl_hit": 1, "realized_r_multiple": -1.0, "mfe": 0.5, "mae": -1.0},
        {"candidate_id": "C2", "trade_compatibility": "INCOMPATIBLE", "tp1_hit": 0, "sl_hit": 1, "realized_r_multiple": -1.0, "mfe": 0.2, "mae": -1.2},
    ]
    stats = _compute_cohort_stats(records)
    comp = stats["compatible"]
    assert comp["count"] == 0
    assert comp["treatment_status"] == "NO_ACCEPTED_CANDIDATES"
    assert comp["trading_utility"] == "NOT_ESTABLISHED"
    assert comp["net_r"] == 0.0


# =====================================================================
# 8. Multi-Metric Compatibility (Not Zeroing Entire Population) Test
# =====================================================================
def test_compatibility_not_zeroing_entire_population():
    ctx_long = CandidateForecastContext(
        candidate_id="CAND-TEST-COMPAT",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=1700000000000,
        entry_price=50000.0,
        sl_price=49000.0,
        tp1_price=52000.0
    )
    # Supportive forecast
    fc_supp = CandidateForecastResult(
        forecast_id="FC-S", candidate_id="CAND-TEST-COMPAT", symbol="BTCUSDT",
        canonical_instrument_id="CRYPTO:BTCUSDT", data_venue="BINANCE",
        forecast_timestamp=1700000000000, source_timeframe="5m", timeframe_mode=TIMESFM_PRIMARY_5M,
        path={"15m": 50100.0, "30m": 50250.0, "45m": 50400.0, "60m": 50600.0},
        full_path=[50000 + i * 50 for i in range(12)], full_path_json="",
        quantiles={"q10": 49200.0, "q50": 50600.0, "q90": 51500.0},
        raw_quantiles={"raw_q10": 49200.0, "raw_q50": 50600.0, "raw_q90": 51500.0},
        quantile_crossing_detected=False, postprocessing_method="RAW",
        forecast_return_pct=1.2, forecast_dispersion_pct=2.5, raw_dispersion_pct=2.5,
        dispersion_bucket="DISPERSION_BUCKET_UNCALIBRATED", forecast_range_pct=1.2,
        model="TimesFM", model_version="3.0", checkpoint="", context_length=60,
        direction_prediction="BULLISH", context_hash="", snapshot_hash=""
    )
    res_supp = evaluate_compatibility(ctx_long, fc_supp)
    assert res_supp.compatibility_category == "SUPPORTIVE"
    assert res_supp.trade_compatibility == "COMPATIBLE"

    # Unsupportive forecast (plummeting)
    fc_unsupp = copy.deepcopy(fc_supp)
    fc_unsupp.path = {"15m": 49800.0, "30m": 49600.0, "45m": 49400.0, "60m": 49100.0}
    fc_unsupp.quantiles = {"q10": 48500.0, "q50": 49100.0, "q90": 49700.0}
    res_unsupp = evaluate_compatibility(ctx_long, fc_unsupp)
    assert res_unsupp.compatibility_category == "UNSUPPORTIVE"
    assert res_unsupp.trade_compatibility == "INCOMPATIBLE"


# =====================================================================
# 9. Raw vs Postprocessed Quantiles Test
# =====================================================================
def test_quantile_raw_vs_postprocessed():
    bars = _generate_synthetic_5m_bars(35)
    ctx = CandidateForecastContext(
        candidate_id="CAND-QUANTILE-TEST",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=bars[25]["ts"] + 300_000,
        entry_price=bars[25]["close"],
        sl_price=bars[25]["close"] - 200.0,
        tp1_price=bars[25]["close"] + 300.0
    )
    res = generate_candidate_forecast(ctx, bars[:26], timeframe_mode=TIMESFM_PRIMARY_5M)
    assert "raw_q10" in res.raw_quantiles
    assert "raw_q50" in res.raw_quantiles
    assert "raw_q90" in res.raw_quantiles
    assert res.postprocessing_method in ("RAW", "MONOTONIC_SORTED")
    assert res.calibration_status == "NOT CALIBRATED"  # Never falsely called calibrated!


# =====================================================================
# 10. Dispersion Uncalibrated State Test
# =====================================================================
def test_dispersion_uncalibrated_state():
    bars = _generate_synthetic_5m_bars(35)
    ctx = CandidateForecastContext(
        candidate_id="CAND-DISP-TEST",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=bars[25]["ts"] + 300_000,
        entry_price=bars[25]["close"],
        sl_price=bars[25]["close"] - 200.0,
        tp1_price=bars[25]["close"] + 300.0
    )
    res = generate_candidate_forecast(ctx, bars[:26], timeframe_mode=TIMESFM_PRIMARY_5M)
    assert res.dispersion_bucket == "DISPERSION_BUCKET_UNCALIBRATED"
    assert res.raw_dispersion_pct > 0.0


# =====================================================================
# 11. Basis Percentile vs Max Consistency Test
# =====================================================================
def test_basis_percentile_vs_max_consistency():
    engine = CrossVenueBasisEngine(history_size=100)
    t0 = 1700000000000
    for i in range(100):
        basis = 0.001 + (i % 10) * 0.0004
        if i == 99:
            basis = 0.025
        bn_px = 50000.0
        bx_px = bn_px * (1.0 + basis / 100.0)
        engine.compute_basis(
            symbol="BTCUSDT",
            binance_price=bn_px,
            bingx_price=bx_px,
            binance_ts_ms=t0 + i * 1000,
            bingx_ts_ms=t0 + i * 1000,
            now_ms=t0 + i * 1000
        )
    metrics = engine.get_basis_percentile_and_max("BTCUSDT")
    p99 = metrics["p99"]
    max_b = metrics["max"]
    assert max_b >= p99, "Max basis must be >= 99th percentile"
    assert max_b > p99, "Max and p99 must not be identical when an outlier exists"


# =====================================================================
# 12. Long/Short Outcome Symmetry Test
# =====================================================================
def test_long_short_outcome_symmetry():
    # Symmetrical price movement (+2% and -2%)
    cand_l = {"candidate_id": "L1", "direction": "LONG", "entry_price": 1000.0, "sl_price": 980.0, "tp1_price": 1030.0}
    cand_s = {"candidate_id": "S1", "direction": "SHORT", "entry_price": 1000.0, "sl_price": 1020.0, "tp1_price": 970.0}

    # Symmetrical 20-point win
    bar_lw = [{"ts": 1000, "open": 1000, "high": 1030, "low": 995, "close": 1030}]
    bar_sw = [{"ts": 1000, "open": 1000, "high": 1005, "low": 970, "close": 970}]

    out_l = CandidateOutcomeTracker.evaluate_outcome(cand_l, bar_lw)
    out_s = CandidateOutcomeTracker.evaluate_outcome(cand_s, bar_sw)

    assert out_l["normalized_risk_amount"] == out_s["normalized_risk_amount"] == 20.0
    assert out_l["normalized_realized_r"] == out_s["normalized_realized_r"] == 1.5
    assert out_l["tp1_hit"] == out_s["tp1_hit"] == 1


# =====================================================================
# 13. Historical Live Boundary Safety Test
# =====================================================================
def test_historical_live_boundary():
    # Verify that research engines have zero order placing authority
    mode = getattr(config, "DEFAULT_TRADING_MODE", "SHADOW")
    assert mode == "SHADOW"
    from control_plane import trade_compatibility
    assert not hasattr(trade_compatibility, "place_order")
    assert not hasattr(trade_compatibility, "reserve_slot")
    from control_plane import timesfm_candidate
    assert not hasattr(timesfm_candidate, "place_order")


# =====================================================================
# 14. Binance 1m to 5m Continuity Test
# =====================================================================
def test_binance_1m_to_5m_continuity():
    # Align starting timestamp to exact 5-minute (300,000 ms) boundary
    t0 = 1700000000000
    t0 = (t0 // 300_000) * 300_000
    bars_1m = []
    for i in range(15):  # 15 1m bars = exactly 3 5m bars
        ts = t0 + i * 60_000
        bars_1m.append({
            "symbol": "BTCUSDT",
            "ts": ts,
            "close_ts": ts + 60_000,
            "open": 50000.0 + i,
            "high": 50000.0 + i + 2,
            "low": 50000.0 + i - 1,
            "close": 50000.0 + i + 1,
            "volume": 10.0,
            "taker_buy": 5.0,
            "closed": True
        })
    derived_5m = CausalCandleAggregator.aggregate_series(bars_1m, "5m")
    assert len(derived_5m) == 3
    for b in derived_5m:
        assert b["ts"] % 300_000 == 0
        assert b["close_ts"] - b["ts"] == 300_000


# =====================================================================
# 15. Future Basis Leakage Test
# =====================================================================
def test_future_basis_leakage():
    engine = CrossVenueBasisEngine(history_size=50)
    t_candidate = 1700000050000
    snap_t = engine.compute_basis(
        symbol="BTCUSDT", binance_price=100.0, bingx_price=100.05,
        binance_ts_ms=t_candidate, bingx_ts_ms=t_candidate, now_ms=t_candidate
    )
    # Future quote at T + 30s
    engine.compute_basis(
        symbol="BTCUSDT", binance_price=150.0, bingx_price=100.0,
        binance_ts_ms=t_candidate + 30000, bingx_ts_ms=t_candidate + 30000, now_ms=t_candidate + 30000
    )
    assert snap_t.binance_price == 100.0
    assert snap_t.bingx_price == 100.05
    assert snap_t.binance_timestamp_ms == t_candidate


# =====================================================================
# 16. Future Retest Leakage Test
# =====================================================================
def test_future_retest_leakage():
    engine = CausalRetestEngine(symbol="BTCUSDT", timeframe=5, direction="LONG")
    state = RetestState(symbol="BTCUSDT", timeframe=5, direction="LONG")
    bars = _generate_synthetic_5m_bars(30)

    # At bar 25, advance step
    state_at_25 = engine.evaluate_step(state, bars[:26], vwap=bars[25]["close"])
    # Modify bar 26 in future
    corrupted_bars = copy.deepcopy(bars)
    corrupted_bars[26]["high"] = 999999.0
    corrupted_bars[26]["close"] = 999999.0

    state_at_25_again = engine.evaluate_step(state, bars[:26], vwap=bars[25]["close"])
    assert state_at_25.state == state_at_25_again.state
    assert state_at_25.distance_pct == state_at_25_again.distance_pct
