"""Unit and Adversarial Leakage tests for Candidate TimesFM and Trade Compatibility Engine.

Layer: tests/test_timesfm_trade_compatibility.py
"""
import copy
import pytest
from control_plane.timesfm_candidate import (
    CandidateForecastContext,
    CandidateForecastResult,
    generate_candidate_forecast,
)
from control_plane.trade_compatibility import (
    ForecastCompatibilityResult,
    ForecastTradeCompatibilityEngine,
    evaluate_compatibility,
)


def _create_sample_5m_candles(count: int = 50, start_ts: int = 1700000000000, base_price: float = 86000.0):
    candles = []
    for i in range(count):
        ts = start_ts + (i * 300_000)
        p = base_price + (i * 10.0)
        candles.append({
            "ts": ts,
            "close_ts": ts + 299_999,
            "open": p - 5.0,
            "high": p + 15.0,
            "low": p - 10.0,
            "close": p,
            "volume": 25.0,
            "is_closed": True,
        })
    return candles


def test_candidate_forecast_generation_and_monotonicity():
    candles = _create_sample_5m_candles(count=40)
    t_candidate = candles[-1]["ts"]

    ctx = CandidateForecastContext(
        candidate_id="CAND-TEST-001",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=t_candidate,
        entry_price=86400.0,
        sl_price=85500.0,
        tp1_price=87500.0,
        tp2_price=88500.0,
        expected_holding_horizon="15m-60m",
        regime="TREND",
        structure_state="BREAKOUT_CONFIRMED",
        retest_state="RETEST_TOUCHED",
    )

    result = generate_candidate_forecast(ctx, candles)
    assert result.candidate_id == "CAND-TEST-001"
    assert result.forecast_timestamp == t_candidate
    assert result.source_timeframe == "5m"
    assert "15m" in result.path
    assert "60m" in result.path

    # Monotonic quantiles: q10 <= q50 <= q90
    q10 = result.quantiles["q10"]
    q50 = result.quantiles["q50"]
    q90 = result.quantiles["q90"]
    assert q10 <= q50 <= q90, f"Quantiles non-monotonic: q10={q10}, q50={q50}, q90={q90}"
    assert result.status == "SHADOW"


def test_trade_compatibility_engine_long_compatible():
    ctx = CandidateForecastContext(
        candidate_id="CAND-LONG-OK",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=1700000000000,
        entry_price=100.0,
        sl_price=95.0,
        tp1_price=110.0,
        tp2_price=115.0,
    )
    # Forecast that projects upward path
    fc = CandidateForecastResult(
        forecast_id="FC-001",
        candidate_id="CAND-LONG-OK",
        symbol="BTCUSDT",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        data_venue="BINANCE",
        forecast_timestamp=1700000000000,
        source_timeframe="5m",
        path={"15m": 102.0, "30m": 104.0, "45m": 106.0, "60m": 108.0},
        quantiles={"q10": 98.0, "q50": 108.0, "q90": 115.0},
        forecast_return_pct=8.0,
        forecast_dispersion_pct=15.7,
        forecast_range_pct=6.0,
        model="TimesFM",
        model_version="3.0",
        checkpoint="google/timesfm-3.0-pytorch",
        context_length=50,
        direction_prediction="BULLISH",
        data_freshness="FRESH",
        status="SHADOW"
    )

    res = evaluate_compatibility(ctx, fc)
    assert res.forecast_direction == "BULLISH"
    assert res.trade_compatibility == "COMPATIBLE"
    assert res.forecast_directional_alignment is True
    assert res.tail_risk_warning is False
    assert res.calibration_status == "NOT CALIBRATED"


def test_trade_compatibility_engine_long_incompatible():
    ctx = CandidateForecastContext(
        candidate_id="CAND-LONG-FAIL",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=1700000000000,
        entry_price=100.0,
        sl_price=95.0,
        tp1_price=110.0,
    )
    # Forecast that projects downward path (opposing direction)
    fc = CandidateForecastResult(
        forecast_id="FC-002",
        candidate_id="CAND-LONG-FAIL",
        symbol="BTCUSDT",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        data_venue="BINANCE",
        forecast_timestamp=1700000000000,
        source_timeframe="5m",
        path={"15m": 98.0, "30m": 96.0, "45m": 94.0, "60m": 92.0},
        quantiles={"q10": 88.0, "q50": 92.0, "q90": 97.0},
        forecast_return_pct=-8.0,
        forecast_dispersion_pct=9.7,
        forecast_range_pct=6.0,
        model="TimesFM",
        model_version="3.0",
        checkpoint="google/timesfm-3.0-pytorch",
        context_length=50,
        direction_prediction="BEARISH",
        data_freshness="FRESH",
        status="SHADOW"
    )

    res = evaluate_compatibility(ctx, fc)
    assert res.forecast_direction == "BEARISH"
    assert res.trade_compatibility == "INCOMPATIBLE"
    assert res.forecast_directional_alignment is False
    assert res.tail_risk_warning is True  # q10 (88.0) is below SL (95.0)


def test_trade_compatibility_engine_short_compatible():
    ctx = CandidateForecastContext(
        candidate_id="CAND-SHORT-OK",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        symbol="BTCUSDT",
        direction="SHORT",
        candidate_timestamp_ms=1700000000000,
        entry_price=100.0,
        sl_price=105.0,
        tp1_price=90.0,
    )
    # Forecast that projects downward path
    fc = CandidateForecastResult(
        forecast_id="FC-003",
        candidate_id="CAND-SHORT-OK",
        symbol="BTCUSDT",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        data_venue="BINANCE",
        forecast_timestamp=1700000000000,
        source_timeframe="5m",
        path={"15m": 98.0, "30m": 96.0, "45m": 94.0, "60m": 92.0},
        quantiles={"q10": 88.0, "q50": 92.0, "q90": 98.0},
        forecast_return_pct=-8.0,
        forecast_dispersion_pct=10.8,
        forecast_range_pct=6.0,
        model="TimesFM",
        model_version="3.0",
        checkpoint="google/timesfm-3.0-pytorch",
        context_length=50,
        direction_prediction="BEARISH",
        data_freshness="FRESH",
        status="SHADOW"
    )

    res = evaluate_compatibility(ctx, fc)
    assert res.forecast_direction == "BEARISH"
    assert res.trade_compatibility == "COMPATIBLE"
    assert res.forecast_directional_alignment is True
    assert res.tail_risk_warning is False  # q90 (98.0) < SL (105.0)


def test_adversarial_zero_future_leakage():
    """Adversarial Test: Modifying future data post-T MUST NOT change forecast at T."""
    candles = _create_sample_5m_candles(count=40)
    # Cutoff at index 25
    t_candidate = candles[25]["ts"]

    ctx = CandidateForecastContext(
        candidate_id="CAND-LEAK-TEST",
        canonical_instrument_id="CRYPTO:BTC-USDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=t_candidate,
        entry_price=float(candles[25]["close"]),
        sl_price=float(candles[25]["close"]) * 0.98,
        tp1_price=float(candles[25]["close"]) * 1.03,
    )

    # 1. Generate baseline forecast with normal future data
    forecast_baseline = generate_candidate_forecast(ctx, candles)

    # 2. Corrupt future data severely (indices 26..39)
    corrupted_candles = copy.deepcopy(candles)
    for i in range(26, len(corrupted_candles)):
        corrupted_candles[i]["close"] *= 5.0    # +400% massive price spike
        corrupted_candles[i]["high"] *= 5.0
        corrupted_candles[i]["volume"] *= 100.0  # +10,000% volume shock

    # 3. Re-run forecast at timestamp T on corrupted dataset
    forecast_adversarial = generate_candidate_forecast(ctx, corrupted_candles)

    # 4. Strict proof: Path, quantiles, and predictions MUST BE 100% IDENTICAL
    assert forecast_baseline.path == forecast_adversarial.path
    assert forecast_baseline.quantiles == forecast_adversarial.quantiles
    assert forecast_baseline.forecast_return_pct == forecast_adversarial.forecast_return_pct
    assert forecast_baseline.direction_prediction == forecast_adversarial.direction_prediction
    assert forecast_baseline.context_length == forecast_adversarial.context_length
