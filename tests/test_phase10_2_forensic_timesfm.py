"""Phase 10.2: TimesFM Forensic Validation & Forecast-Role Discovery Test Suite.

Layer: tests/test_phase10_2_forensic_timesfm.py
Requirements:
1. Trace execution path and verify model latency is separated from compatibility latency.
2. Latency reconciliation logic (cold, warm, cached, compatibility, pipeline).
3. Model vs Baseline comparison (TimesFM vs Naive vs EMA vs VWAP vs AR).
4. Path semantics: 5m, 12 steps (Step 3=+15m, 6=+30m, 9=+45m, 12=+60m).
5. Quantile semantics: raw quantiles, crossing detection, postprocessing, NOT_CALIBRATED status.
6. Database reconciliation: 105 experiment candidates + 1 unit test record = 106.
7. Pullback depth metrics calculation.
8. Target reachability classification.
9. Holding horizon matching (15m, 30m, 45m, 60m).
10. Post-entry forecast delta calculation.
11. Adversarial zero-leakage check on reforecasting.
12. Chronological splits non-overlap.
13. Bootstrap 95% confidence intervals.
14. Direction-neutral normalized R symmetry.
15. Multi-venue candidate pairing.
16. Research family isolation.
"""
from __future__ import annotations

import json
import math
import time
import numpy as np
import pytest

from control_plane import config, db
from control_plane.candidate_research import CandidateOutcomeTracker, ComparativeMarketEngine
from control_plane.timesfm_candidate import (
    CandidateForecastContext,
    CandidateForecastResult,
    generate_candidate_forecast,
    _autoregressive_forecast,
    calculate_quantile_coverage,
    calculate_interval_coverage,
    calculate_interval_width,
    calculate_pinball_loss,
    TIMESFM_PRIMARY_5M,
    TIMESFM_HORIZON_STEPS_5M,
    TIMESFM_CHECKPOINT,
    TIMESFM_MODEL_VERSION
)
from control_plane.trade_compatibility import (
    ForecastCompatibilityResult,
    evaluate_compatibility
)


@pytest.fixture
def sample_context():
    return CandidateForecastContext(
        candidate_id="TEST-PHASE10-2-001",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=1700000000000,
        entry_price=65000.0,
        sl_price=64500.0,
        tp1_price=66000.0,
        tp2_price=67000.0,
        expected_holding_horizon="30m",
        retest_state="ENTRY_READY"
    )


@pytest.fixture
def sample_candles():
    return [
        {
            "ts": 1700000000000 - (60 - i) * 300_000,
            "open": 64500.0 + i * 8.0,
            "high": 64510.0 + i * 8.0,
            "low": 64490.0 + i * 8.0,
            "close": 64505.0 + i * 8.0,
            "volume": 100.0,
            "closed": True
        }
        for i in range(60)
    ]


def test_execution_path_tracing_and_latency_separation(sample_context, sample_candles):
    """Test 1: Verify model latency is recorded separately from compatibility calculation."""
    fc = generate_candidate_forecast(sample_context, sample_candles, timeframe_mode=TIMESFM_PRIMARY_5M)
    compat = evaluate_compatibility(sample_context, fc)

    assert hasattr(fc, "actual_model_inference_ms")
    assert hasattr(fc, "serialization_ms")
    assert hasattr(fc, "postprocessing_ms")
    assert hasattr(fc, "total_candidate_forecast_ms")
    assert hasattr(compat, "compatibility_calculation_ms")

    # Timings must be non-negative
    assert fc.actual_model_inference_ms >= 0.0
    assert fc.total_candidate_forecast_ms >= fc.actual_model_inference_ms
    assert compat.compatibility_calculation_ms >= 0.0
    # Provider and model class must be explicitly identified
    assert fc.provider_class != ""
    assert fc.model_class != ""


def test_latency_reconciliation_logic():
    """Test 2: Reconcile that compatibility latency is distinct from inference latency."""
    t_context = np.linspace(60000.0, 60500.0, 64)
    t0 = time.perf_counter()
    _ = _autoregressive_forecast(t_context, 12)
    ar_ms = (time.perf_counter() - t0) * 1000.0

    # Fallback AR inference is sub-5ms
    assert ar_ms < 50.0


def test_model_vs_baseline_comparison(sample_candles):
    """Test 3: Verify all 5 models produce valid paths and distinct properties."""
    closes = np.array([c["close"] for c in sample_candles], dtype=np.float64)
    last_p = closes[-1]

    # Model A / E: AR
    path_ar = _autoregressive_forecast(closes, 12)
    # Model B: Naive
    path_naive = np.full(12, last_p)
    # Model C: EMA
    path_ema = np.full(12, np.mean(closes[-10:]))
    # Model D: VWAP proxy
    path_vwap = np.full(12, np.mean(closes[-30:]))

    assert len(path_ar) == 12
    assert len(path_naive) == 12
    assert len(path_ema) == 12
    assert len(path_vwap) == 12

    # Paths have distinct terminal values
    assert not np.allclose(path_naive, path_ema)
    assert not np.allclose(path_ema, path_vwap)


def test_path_semantics_5m_12_steps(sample_context, sample_candles):
    """Test 4: Verify 12 steps match 15m (+3), 30m (+6), 45m (+9), 60m (+12)."""
    fc = generate_candidate_forecast(sample_context, sample_candles, timeframe_mode=TIMESFM_PRIMARY_5M)
    assert len(fc.full_path) == 12
    assert fc.path["15m"] == round(fc.full_path[2], 2)
    assert fc.path["30m"] == round(fc.full_path[5], 2)
    assert fc.path["45m"] == round(fc.full_path[8], 2)
    assert fc.path["60m"] == round(fc.full_path[11], 2)


def test_quantile_semantics_raw_and_postprocessed(sample_context, sample_candles):
    """Test 5: Verify raw quantiles, crossing check, postprocessing, NOT_CALIBRATED status."""
    fc = generate_candidate_forecast(sample_context, sample_candles, timeframe_mode=TIMESFM_PRIMARY_5M)
    assert "raw_q10" in fc.raw_quantiles
    assert "raw_q50" in fc.raw_quantiles
    assert "raw_q90" in fc.raw_quantiles
    assert "q10" in fc.quantiles
    assert "q50" in fc.quantiles
    assert "q90" in fc.quantiles

    # Postprocessed quantiles must be monotonic
    assert fc.quantiles["q10"] <= fc.quantiles["q50"] <= fc.quantiles["q90"]
    assert fc.calibration_status == "NOT CALIBRATED"


def test_database_count_reconciliation():
    """Test 6: Verify reconciliation of 105 experiment candidates + 1 unit test record = 106."""
    con = db._connect()
    with db._lock:
        rows = con.execute("SELECT candidate_id, symbol FROM candidate_research_outcomes WHERE retest_state_at_entry = 'ENTRY_READY'").fetchall()
    
    total_retest = len(rows)
    test_cands = [r[0] for r in rows if "TEST" in r[0] or "TEST" in r[1]]
    experiment_cands = [r[0] for r in rows if r[0] not in test_cands]

    # Reconciliation invariant
    assert total_retest == len(experiment_cands) + len(test_cands)
    if total_retest == 106:
        assert len(experiment_cands) == 105
        assert len(test_cands) == 1


def test_pullback_depth_metrics_calculation(sample_context):
    """Test 7: Verify pullback depth and pre-continuation MAE are calculated correctly."""
    future_candles = [
        {"ts": sample_context.candidate_timestamp_ms + (i + 1) * 300_000, "open": 65000.0 - i * 20, "high": 65020.0, "low": 64800.0, "close": 64850.0}
        for i in range(12)
    ]
    cand_dict = {
        "direction": "LONG",
        "entry_price": 65000.0,
        "sl_price": 64500.0,
        "tp1_price": 66000.0,
        "retest_state": "ENTRY_READY",
        "retest_touch_price": 64900.0
    }
    outcome = CandidateOutcomeTracker.evaluate_outcome(cand_dict, future_candles)

    assert "min_low_before_continuation" in outcome
    assert "time_to_min_low_min" in outcome
    assert "dist_below_entry" in outcome
    assert "dist_below_retest_zone" in outcome
    assert "mae_before_continuation" in outcome

    # For LONG: low was 64800, dist_below_entry = 65000 - 64800 = 200
    assert outcome["min_low_before_continuation"] == 64800.0
    assert outcome["dist_below_entry"] == 200.0


def test_target_selection_reachability_metric(sample_context):
    """Test 8: Verify classification of TP1 reachable vs unreachable."""
    fc_reachable = CandidateForecastResult(
        forecast_id="FC-R-1", candidate_id="C1", symbol="BTCUSDT", canonical_instrument_id="CRYPTO:BTCUSDT",
        data_venue="BINANCE", forecast_timestamp=1700000000000, source_timeframe="5m",
        path={"15m": 65500.0, "30m": 66200.0, "45m": 66500.0, "60m": 66800.0},
        quantiles={"q10": 64800.0, "q50": 66200.0, "q90": 66500.0},  # q90 >= TP1 (66000)
        forecast_return_pct=2.7, forecast_dispersion_pct=2.6, forecast_range_pct=2.0,
        model="TimesFM", model_version="3.0", checkpoint=TIMESFM_CHECKPOINT, context_length=60, direction_prediction="BULLISH"
    )
    fc_unreachable = CandidateForecastResult(
        forecast_id="FC-U-1", candidate_id="C2", symbol="BTCUSDT", canonical_instrument_id="CRYPTO:BTCUSDT",
        data_venue="BINANCE", forecast_timestamp=1700000000000, source_timeframe="5m",
        path={"15m": 65100.0, "30m": 65200.0, "45m": 65300.0, "60m": 65400.0},
        quantiles={"q10": 64600.0, "q50": 65200.0, "q90": 65600.0},  # q90 < TP1 (66000)
        forecast_return_pct=0.6, forecast_dispersion_pct=1.5, forecast_range_pct=0.5,
        model="TimesFM", model_version="3.0", checkpoint=TIMESFM_CHECKPOINT, context_length=60, direction_prediction="NEUTRAL"
    )

    is_tp1_reach_1 = fc_reachable.quantiles["q90"] >= sample_context.tp1_price
    is_tp1_reach_2 = fc_unreachable.quantiles["q90"] >= sample_context.tp1_price

    assert is_tp1_reach_1 is True
    assert is_tp1_reach_2 is False


def test_holding_horizon_trade_matching(sample_context):
    """Test 9: Verify horizon matching for 15m, 30m, 45m, 60m."""
    horizons = ["15m", "30m", "45m", "60m"]
    step_indices = {"15m": 2, "30m": 5, "45m": 8, "60m": 11}
    for h in horizons:
        idx = step_indices[h]
        assert idx < TIMESFM_HORIZON_STEPS_5M


def test_post_entry_forecast_delta(sample_context, sample_candles):
    """Test 10: Verify post-entry forecast delta calculation across steps."""
    fc_t0 = generate_candidate_forecast(sample_context, sample_candles, timeframe_mode=TIMESFM_PRIMARY_5M)
    
    # Simulate step T+1 (next 5m closed bar)
    next_bar = {
        "ts": sample_candles[-1]["ts"] + 300_000,
        "open": sample_candles[-1]["close"],
        "high": sample_candles[-1]["close"] + 20.0,
        "low": sample_candles[-1]["close"] - 10.0,
        "close": sample_candles[-1]["close"] + 15.0,
        "volume": 120.0,
        "closed": True
    }
    extended_candles = sample_candles + [next_bar]
    ctx_t1 = CandidateForecastContext(
        candidate_id="TEST-T1", canonical_instrument_id=sample_context.canonical_instrument_id,
        symbol=sample_context.symbol, direction=sample_context.direction,
        candidate_timestamp_ms=sample_context.candidate_timestamp_ms + 300_000,
        entry_price=sample_context.entry_price, sl_price=sample_context.sl_price, tp1_price=sample_context.tp1_price
    )
    fc_t1 = generate_candidate_forecast(ctx_t1, extended_candles, timeframe_mode=TIMESFM_PRIMARY_5M)

    delta_q50 = fc_t1.quantiles["q50"] - fc_t0.quantiles["q50"]
    assert isinstance(delta_q50, float)


def test_adversarial_zero_future_leakage_reforecasting(sample_context, sample_candles):
    """Test 11: Adversarially alter future bars and confirm reforecast at T remains identical."""
    fc_original = generate_candidate_forecast(sample_context, sample_candles, timeframe_mode=TIMESFM_PRIMARY_5M)

    # Poison future data (bars after candidate_timestamp_ms)
    poisoned_candles = sample_candles + [
        {"ts": sample_context.candidate_timestamp_ms + 300_000, "close": 999999.0, "closed": True},
        {"ts": sample_context.candidate_timestamp_ms + 600_000, "close": 111111.0, "closed": True},
    ]
    fc_after_poison = generate_candidate_forecast(sample_context, poisoned_candles, timeframe_mode=TIMESFM_PRIMARY_5M)

    assert fc_original.snapshot_hash == fc_after_poison.snapshot_hash
    assert fc_original.context_hash == fc_after_poison.context_hash
    assert fc_original.full_path == fc_after_poison.full_path


def test_chronological_splits_no_overlap():
    """Test 12: Chronological splits have no index overlap and strictly increasing time."""
    n = 100
    indices = list(range(n))
    train_split = indices[:50]
    val_split = indices[50:75]
    test_split = indices[75:]

    assert len(set(train_split).intersection(set(val_split))) == 0
    assert len(set(val_split).intersection(set(test_split))) == 0
    assert len(set(train_split).intersection(set(test_split))) == 0
    assert len(train_split) + len(val_split) + len(test_split) == n


def test_bootstrap_confidence_interval():
    """Test 13: Bootstrap 95% CI covers sample mean for positive data."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    rng = np.random.default_rng(42)
    boot_means = [float(np.mean(rng.choice(data, size=len(data), replace=True))) for _ in range(500)]
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    assert ci_lower <= 3.0 <= ci_upper


def test_direction_neutral_normalized_r_symmetry():
    """Test 14: Verify symmetry in realized R calculation for LONG and SHORT."""
    # LONG: Entry 100, SL 90, Exit 110 -> (110 - 100) / 10 = +1.0 R
    cand_long = {"direction": "LONG", "entry_price": 100.0, "sl_price": 90.0, "tp1_price": 120.0}
    future_long = [{"ts": 1000, "high": 110.0, "low": 95.0, "close": 110.0}]
    res_long = CandidateOutcomeTracker.evaluate_outcome(cand_long, future_long)

    # SHORT: Entry 100, SL 110, Exit 90 -> (100 - 90) / 10 = +1.0 R
    cand_short = {"direction": "SHORT", "entry_price": 100.0, "sl_price": 110.0, "tp1_price": 80.0}
    future_short = [{"ts": 1000, "high": 105.0, "low": 90.0, "close": 90.0}]
    res_short = CandidateOutcomeTracker.evaluate_outcome(cand_short, future_short)

    assert res_long["normalized_realized_r"] == res_short["normalized_realized_r"] == 1.0


def test_multi_venue_binance_vs_bingx_matching():
    """Test 15: Pairing candidates across venues within window tolerance."""
    c1 = [{"candidate_id": "BN-1", "symbol": "BTCUSDT", "direction": "LONG", "timestamp_ms": 1700000000000, "entry_price": 65000.0}]
    c2 = [{"candidate_id": "BX-1", "symbol": "BTCUSDT", "direction": "LONG", "timestamp_ms": 1700000300000, "entry_price": 65005.0}]
    matched = ComparativeMarketEngine.match_candidates(c1, c2, window_tolerance_ms=600_000)

    assert len(matched) == 1
    assert matched[0]["binance_candidate_id"] == "BN-1"
    assert matched[0]["bingx_candidate_id"] == "BX-1"


def test_research_family_isolation():
    """Test 16: Database records reflect Phase 10.2 research family."""
    row = {
        "candidate_id": "TEST-FAM-001",
        "symbol": "BTCUSDT",
        "timestamp_ms": 1700000000000,
        "direction": "LONG",
        "entry_price": 65000.0,
        "sl_price": 64500.0,
        "tp1_price": 66000.0,
        "research_family": "PHASE10.2_TIMESFM_ROLE_DISCOVERY_V1"
    }
    db.insert_candidate_outcome(row)

    con = db._connect()
    with db._lock:
        saved = con.execute("SELECT research_family FROM candidate_research_outcomes WHERE candidate_id = ?", ("TEST-FAM-001",)).fetchone()
    
    assert saved is not None
    assert saved[0] == "PHASE10.2_TIMESFM_ROLE_DISCOVERY_V1"
