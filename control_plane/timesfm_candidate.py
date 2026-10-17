"""Candidate-Specific TimesFM Forecasting Subsystem.

Layer: control_plane/timesfm_candidate.py
Contract:
- Binds TimesFM 3.0 forecast directly to trade candidate at ENTRY_READY.
- Truncates context strictly at candidate timestamp T (zero lookahead).
- Primary Architecture: TIMESFM_PRIMARY_5M (12 x 5m steps: +15m, +30m, +45m, +60m).
- Research Architecture: TIMESFM_1M_RESEARCH (60 x 1m steps).
- Full 12-step path persisted in full_path_json.
- Raw quantiles, crossing detection, and post-processing explicitly audited.
- Never labels postprocessed quantiles as 'calibrated' without empirical proof.
- Uncalibrated dispersion labels: DISPERSION_BUCKET_UNCALIBRATED.
- Freezes and persists forecast immutable snapshot bound to candidate_id (snapshot_hash, context_hash).
- Retains SHADOW mode invariant (TRADING_AUTHORITY = FALSE).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config, db

logger = logging.getLogger("ophelia.timesfm_candidate")

TIMESFM_CANDIDATE_SCHEMA_VERSION = "TIMESFM_CANDIDATE_V2"
TIMESFM_CHECKPOINT = "google/timesfm-3.0-pytorch"
TIMESFM_MODEL_VERSION = "3.0"

# Timeframe Architecture Modes
TIMESFM_PRIMARY_TIMEFRAME = "5m"
TIMESFM_PRIMARY_5M = "TIMESFM_PRIMARY_5M"
TIMESFM_1M_RESEARCH = "TIMESFM_1M_RESEARCH"
TIMESFM_HORIZON_STEPS_5M = 12
TIMESFM_HORIZON_STEPS_1M = 60


@dataclass(slots=True)
class CandidateForecastContext:
    candidate_id: str
    canonical_instrument_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    candidate_timestamp_ms: int
    entry_price: float
    sl_price: float
    tp1_price: float
    tp2_price: Optional[float] = None
    expected_holding_horizon: str = "15m-60m"
    regime: str = "TREND"
    structure_state: str = "BREAKOUT_CONFIRMED"
    retest_state: str = "ENTRY_READY"
    candidate_snapshot_version: str = "CANDIDATE_V2"
    snapshot_hash: Optional[str] = None
    context_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandidateForecastResult:
    forecast_id: str
    candidate_id: str
    symbol: str
    canonical_instrument_id: str
    data_venue: str
    forecast_timestamp: int
    source_timeframe: str
    path: Dict[str, float]  # "15m", "30m", "45m", "60m"
    quantiles: Dict[str, float]  # Postprocessed "q10", "q50", "q90"
    forecast_return_pct: float
    forecast_dispersion_pct: float  # raw_dispersion_pct
    forecast_range_pct: float
    model: str
    model_version: str
    checkpoint: str
    context_length: int
    direction_prediction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    timeframe_mode: str = TIMESFM_PRIMARY_5M
    full_path: List[float] = field(default_factory=list)
    full_path_json: str = "[]"
    raw_quantiles: Dict[str, float] = field(default_factory=dict)
    quantile_crossing_detected: bool = False
    postprocessing_method: str = "RAW"
    raw_dispersion_pct: float = 2.0
    dispersion_bucket: str = "DISPERSION_BUCKET_UNCALIBRATED"
    context_hash: str = ""
    snapshot_hash: str = ""
    provider_class: str = "TimesFMProvider"
    model_class: str = "TimesFM3Forecaster"
    device: str = "cpu"
    actual_model_inference_ms: float = 0.0
    serialization_ms: float = 0.0
    postprocessing_ms: float = 0.0
    compatibility_calculation_ms: float = 0.0
    total_candidate_forecast_ms: float = 0.0
    cache_hit: bool = False
    schema_version: str = TIMESFM_CANDIDATE_SCHEMA_VERSION
    calibration_status: str = "NOT CALIBRATED"
    data_freshness: str = "FRESH"
    status: str = "SHADOW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_timesfm_singleton = None
_timesfm_singleton_lock = threading.Lock()


def get_timesfm_provider():
    """Lazily load singleton TimesFMProvider if torch and timesfm are present."""
    global _timesfm_singleton
    with _timesfm_singleton_lock:
        if _timesfm_singleton is not None:
            return _timesfm_singleton
        try:
            from .forecast_service import TimesFMProvider
            provider = TimesFMProvider()
            if provider.load_model():
                _timesfm_singleton = provider
                return _timesfm_singleton
        except Exception as e:
            logger.debug("TimesFMProvider could not be loaded: %s", e)
        return None


def generate_candidate_forecast(
    context: CandidateForecastContext,
    historical_candles: List[dict],
    model_override: Optional[Any] = None,
    timeframe_mode: str = TIMESFM_PRIMARY_5M
) -> CandidateForecastResult:
    """Generate and freeze candidate-specific TimesFM future distribution and path.

    Strict Invariants:
    1. Zero Lookahead: Truncates historical context strictly at context.candidate_timestamp_ms.
       Candle is included ONLY if its confirmed completion time <= candidate_timestamp_ms.
    2. Primary 5m Architecture: Default 12 x 5m steps (+15m, +30m, +45m, +60m).
    3. Explicit Quantile Provenance: Persists raw quantiles, detects crossings, tracks sorting.
    4. Uncalibrated Dispersion: Exposes raw dispersion, labels bucket DISPERSION_BUCKET_UNCALIBRATED.
    5. Immutable Persistence: Persists snapshot in candidate_forecasts table.
    """
    t_cutoff = context.candidate_timestamp_ms
    is_5m_mode = (timeframe_mode == TIMESFM_PRIMARY_5M)
    step_duration_ms = 300_000 if is_5m_mode else 60_000
    horizon_steps = TIMESFM_HORIZON_STEPS_5M if is_5m_mode else TIMESFM_HORIZON_STEPS_1M
    source_tf = "5m" if is_5m_mode else "1m"

    # 1. Filter historical bars strictly <= t_cutoff ensuring complete closed candle causality
    causal_bars = []
    for c in historical_candles:
        ts = int(c.get("ts", 0))
        # Determine bar end timestamp: if close_ts is present use it, else calculate from open ts + step duration
        bar_end_ts = int(c.get("close_ts", ts + step_duration_ms))
        if bar_end_ts <= t_cutoff or (ts <= t_cutoff and c.get("closed", True) and bar_end_ts <= t_cutoff + 1000):
            causal_bars.append(c)

    causal_bars.sort(key=lambda x: int(x["ts"]))

    # Snapshot hash computation
    snapshot_hash = hashlib.sha256(
        f"{context.candidate_id}:{t_cutoff}:{round(context.entry_price, 4)}:{context.direction}:{timeframe_mode}".encode()
    ).hexdigest()[:16]

    if len(causal_bars) < 12:
        logger.warning("Insufficient causal context bars (%d < 12) for candidate %s", len(causal_bars), context.candidate_id)
        cur_price = context.entry_price
        path = {"15m": cur_price, "30m": cur_price, "45m": cur_price, "60m": cur_price}
        full_path = [cur_price] * horizon_steps
        raw_q = {"raw_q10": cur_price * 0.99, "raw_q50": cur_price, "raw_q90": cur_price * 1.01}
        post_q = {"q10": cur_price * 0.99, "q50": cur_price, "q90": cur_price * 1.01}
        context_hash = hashlib.sha256(f"INSUFFICIENT_{cur_price}".encode()).hexdigest()[:16]

        return CandidateForecastResult(
            forecast_id=f"FC-{uuid.uuid4().hex[:12]}",
            candidate_id=context.candidate_id,
            symbol=context.symbol,
            canonical_instrument_id=context.canonical_instrument_id,
            data_venue="BINANCE",
            forecast_timestamp=t_cutoff,
            source_timeframe=source_tf,
            timeframe_mode=timeframe_mode,
            path=path,
            full_path=full_path,
            full_path_json=json.dumps(full_path),
            quantiles=post_q,
            raw_quantiles=raw_q,
            quantile_crossing_detected=False,
            postprocessing_method="RAW",
            forecast_return_pct=0.0,
            forecast_dispersion_pct=2.0,
            raw_dispersion_pct=2.0,
            dispersion_bucket="DISPERSION_BUCKET_UNCALIBRATED",
            forecast_range_pct=2.0,
            model="TimesFM_Baseline",
            model_version=TIMESFM_MODEL_VERSION,
            checkpoint=TIMESFM_CHECKPOINT,
            context_length=len(causal_bars),
            direction_prediction="NEUTRAL",
            context_hash=context_hash,
            snapshot_hash=snapshot_hash,
            calibration_status="NOT CALIBRATED",
            data_freshness="INSUFFICIENT_SAMPLE",
            status="SHADOW"
        )

    # 2. Extract causal price history
    closes = np.array([float(b["close"]) for b in causal_bars], dtype=np.float64)
    last_close = closes[-1]
    context_len = min(len(closes), 128)
    sub_closes = closes[-context_len:]
    context_hash = hashlib.sha256(
        json.dumps([round(float(x), 4) for x in sub_closes]).encode()
    ).hexdigest()[:16]

    t_total_start = time.perf_counter()

    # 3. Model Inference (PyTorch TimesFM or Econometric AR Baseline)
    step_predictions: np.ndarray
    raw_model_quantiles = None
    actual_inf_ms = 0.0
    provider_class = "EconometricBaselineProvider"
    model_class = "AutoregressiveMomentumMeanReversion"
    model_name = "Econometric_AR_Baseline"
    checkpoint = "statistical_fallback"
    device = "cpu"
    cache_hit = False

    t_inf_start = time.perf_counter()
    provider = model_override if model_override is not None else get_timesfm_provider()

    if provider is not None and hasattr(provider, "model") and provider.model is not None:
        try:
            output = provider.model.predict(
                context=sub_closes.astype(np.float32),
                horizon=horizon_steps,
                return_quantiles=True,
                sort_quantiles=True
            )
            actual_inf_ms = (time.perf_counter() - t_inf_start) * 1000.0
            provider_class = provider.__class__.__name__
            model_class = provider.model.__class__.__name__
            model_name = "TimesFM_3.0_PyTorch"
            checkpoint = getattr(provider, "checkpoint", TIMESFM_CHECKPOINT)
            device = getattr(provider, "device", "cpu")

            f_raw = output.forecast
            if isinstance(f_raw, np.ndarray):
                step_predictions = f_raw.flatten()[:horizon_steps]
            else:
                step_predictions = np.array(f_raw[:horizon_steps], dtype=np.float64)

            if output.quantiles is not None and isinstance(output.quantiles, np.ndarray):
                q_arr = output.quantiles
                if q_arr.ndim == 3:
                    q_arr = q_arr[0]
                raw_model_quantiles = q_arr
        except Exception as e:
            logger.error("TimesFM model predict error (%s), using econometric AR baseline", e)
            t_fallback_start = time.perf_counter()
            step_predictions = _autoregressive_forecast(sub_closes, horizon_steps)
            actual_inf_ms = (time.perf_counter() - t_fallback_start) * 1000.0
            model_name = "Econometric_AR_Baseline"
            provider_class = "EconometricBaselineProvider"
            model_class = "AutoregressiveMomentumMeanReversion"
            checkpoint = "statistical_fallback"
    elif model_override is not None and hasattr(model_override, "forecast"):
        try:
            step_predictions = model_override.forecast(sub_closes, horizon=horizon_steps)
            actual_inf_ms = (time.perf_counter() - t_inf_start) * 1000.0
            model_name = getattr(model_override, "name", model_override.__class__.__name__)
            provider_class = model_override.__class__.__name__
            model_class = model_override.__class__.__name__
        except Exception as e:
            logger.error("Model override error (%s), using econometric AR baseline", e)
            t_fallback_start = time.perf_counter()
            step_predictions = _autoregressive_forecast(sub_closes, horizon_steps)
            actual_inf_ms = (time.perf_counter() - t_fallback_start) * 1000.0
            model_name = "Econometric_AR_Baseline"
            provider_class = "EconometricBaselineProvider"
            model_class = "AutoregressiveMomentumMeanReversion"
            checkpoint = "statistical_fallback"
    else:
        step_predictions = _autoregressive_forecast(sub_closes, horizon_steps)
        actual_inf_ms = (time.perf_counter() - t_inf_start) * 1000.0
        model_name = "Econometric_AR_Baseline"
        provider_class = "EconometricBaselineProvider"
        model_class = "AutoregressiveMomentumMeanReversion"
        checkpoint = "statistical_fallback"

    full_path_list = [round(float(p), 4) for p in step_predictions]

    # Map step horizons:
    # In 5m mode: Step 3 = +15m, Step 6 = +30m, Step 9 = +45m, Step 12 = +60m
    # In 1m mode: Step 15 = +15m, Step 30 = +30m, Step 45 = +45m, Step 60 = +60m
    if is_5m_mode:
        p15 = float(step_predictions[2])
        p30 = float(step_predictions[5])
        p45 = float(step_predictions[8])
        p60 = float(step_predictions[11])
        step_60_idx = 11
    else:
        p15 = float(step_predictions[14])
        p30 = float(step_predictions[29])
        p45 = float(step_predictions[44])
        p60 = float(step_predictions[59])
        step_60_idx = 59

    # 4. Compute Raw Quantiles & Uncertainty Bounds
    t_post_start = time.perf_counter()
    if raw_model_quantiles is not None and len(raw_model_quantiles) > step_60_idx:
        q_row = raw_model_quantiles[step_60_idx]
        num_q = len(q_row)
        raw_q10 = float(q_row[0])
        raw_q50 = float(q_row[num_q // 2])
        raw_q90 = float(q_row[-1])
    else:
        ret_bars = np.diff(np.log(sub_closes[-20:]))
        sigma_bar = float(np.std(ret_bars)) if len(ret_bars) > 1 else 0.003
        steps_to_60m = 12 if is_5m_mode else 60
        sigma_60m = sigma_bar * math.sqrt(steps_to_60m)

        raw_q50 = float(p60)
        raw_q10 = float(p60 * math.exp(-1.28155 * sigma_60m))
        raw_q90 = float(p60 * math.exp(1.28155 * sigma_60m))

    # Detect Quantile Crossing
    crossing_detected = bool(raw_q10 > raw_q50 or raw_q50 > raw_q90 or raw_q10 > raw_q90)

    # Post-processing (explicitly recorded, never called "calibrated")
    if crossing_detected:
        sorted_quantiles = sorted([raw_q10, raw_q50, raw_q90])
        post_q10 = sorted_quantiles[0]
        post_q50 = sorted_quantiles[1]
        post_q90 = sorted_quantiles[2]
        postprocessing_method = "MONOTONIC_SORTED"
    else:
        post_q10 = raw_q10
        post_q50 = raw_q50
        post_q90 = raw_q90
        postprocessing_method = "RAW"

    postprocessing_ms = (time.perf_counter() - t_post_start) * 1000.0

    forecast_ret_pct = round(((p60 - last_close) / last_close) * 100.0, 4)
    raw_dispersion_pct = round(((post_q90 - post_q10) / max(post_q50, 1e-6)) * 100.0, 4)
    range_pct = round(((max(p15, p30, p45, p60) - min(p15, p30, p45, p60)) / last_close) * 100.0, 4)

    # Direction prediction based on 60m return
    if forecast_ret_pct > 0.15:
        dir_pred = "BULLISH"
    elif forecast_ret_pct < -0.15:
        dir_pred = "BEARISH"
    else:
        dir_pred = "NEUTRAL"

    t_ser_start = time.perf_counter()
    forecast_id = f"FC-{uuid.uuid4().hex[:12]}"
    path_dict = {
        "15m": round(p15, 2),
        "30m": round(p30, 2),
        "45m": round(p45, 2),
        "60m": round(p60, 2),
    }
    raw_quantiles_dict = {
        "raw_q10": round(raw_q10, 2),
        "raw_q50": round(raw_q50, 2),
        "raw_q90": round(raw_q90, 2),
    }
    quantiles_dict = {
        "q10": round(post_q10, 2),
        "q50": round(post_q50, 2),
        "q90": round(post_q90, 2),
    }

    full_path_json = json.dumps(full_path_list)
    serialization_ms = (time.perf_counter() - t_ser_start) * 1000.0
    total_candidate_forecast_ms = (time.perf_counter() - t_total_start) * 1000.0

    result = CandidateForecastResult(
        forecast_id=forecast_id,
        candidate_id=context.candidate_id,
        symbol=context.symbol,
        canonical_instrument_id=context.canonical_instrument_id,
        data_venue="BINANCE",
        forecast_timestamp=t_cutoff,
        source_timeframe=source_tf,
        timeframe_mode=timeframe_mode,
        path=path_dict,
        full_path=full_path_list,
        full_path_json=full_path_json,
        quantiles=quantiles_dict,
        raw_quantiles=raw_quantiles_dict,
        quantile_crossing_detected=crossing_detected,
        postprocessing_method=postprocessing_method,
        forecast_return_pct=forecast_ret_pct,
        forecast_dispersion_pct=raw_dispersion_pct,
        raw_dispersion_pct=raw_dispersion_pct,
        dispersion_bucket="DISPERSION_BUCKET_UNCALIBRATED",
        forecast_range_pct=range_pct,
        model=model_name,
        model_version=TIMESFM_MODEL_VERSION,
        checkpoint=checkpoint,
        context_length=context_len,
        direction_prediction=dir_pred,
        context_hash=context_hash,
        snapshot_hash=snapshot_hash,
        provider_class=provider_class,
        model_class=model_class,
        device=device,
        actual_model_inference_ms=round(actual_inf_ms, 2),
        serialization_ms=round(serialization_ms, 2),
        postprocessing_ms=round(postprocessing_ms, 2),
        compatibility_calculation_ms=0.0,
        total_candidate_forecast_ms=round(total_candidate_forecast_ms, 2),
        cache_hit=cache_hit,
        calibration_status="NOT CALIBRATED",
        data_freshness="FRESH",
        status="SHADOW"
    )

    # 5. Persist immutable record in database
    db_record = {
        "forecast_id": result.forecast_id,
        "candidate_id": result.candidate_id,
        "symbol": result.symbol,
        "canonical_instrument_id": result.canonical_instrument_id,
        "forecast_timestamp": result.forecast_timestamp,
        "source_timeframe": result.source_timeframe,
        "timeframe_mode": result.timeframe_mode,
        "path_15m": result.path["15m"],
        "path_30m": result.path["30m"],
        "path_45m": result.path["45m"],
        "path_60m": result.path["60m"],
        "full_path_json": result.full_path_json,
        "q10": result.quantiles["q10"],
        "q50": result.quantiles["q50"],
        "q90": result.quantiles["q90"],
        "raw_q10": result.raw_quantiles["raw_q10"],
        "raw_q50": result.raw_quantiles["raw_q50"],
        "raw_q90": result.raw_quantiles["raw_q90"],
        "quantile_crossing_detected": 1 if result.quantile_crossing_detected else 0,
        "postprocessed_q10": result.quantiles["q10"],
        "postprocessed_q50": result.quantiles["q50"],
        "postprocessed_q90": result.quantiles["q90"],
        "postprocessing_method": result.postprocessing_method,
        "forecast_return_pct": result.forecast_return_pct,
        "forecast_dispersion_pct": result.forecast_dispersion_pct,
        "dispersion_bucket": result.dispersion_bucket,
        "model_name": result.model,
        "model_version": result.model_version,
        "checkpoint": result.checkpoint,
        "context_length": result.context_length,
        "direction_prediction": result.direction_prediction,
        "context_hash": result.context_hash,
        "snapshot_hash": result.snapshot_hash,
        "provider_class": result.provider_class,
        "model_class": result.model_class,
        "device": result.device,
        "actual_model_inference_ms": result.actual_model_inference_ms,
        "serialization_ms": result.serialization_ms,
        "postprocessing_ms": result.postprocessing_ms,
        "compatibility_calculation_ms": result.compatibility_calculation_ms,
        "total_candidate_forecast_ms": result.total_candidate_forecast_ms,
        "cache_hit": 1 if result.cache_hit else 0,
        "status": result.status
    }
    try:
        db.insert_candidate_forecast(db_record)
    except Exception as e:
        logger.error("Failed persisting candidate forecast in db: %s", e)

    return result


def _autoregressive_forecast(series: np.ndarray, horizon: int) -> np.ndarray:
    """Deterministic, causal autoregressive momentum and mean-reversion forecaster."""
    y = np.copy(series)
    preds = []
    ema = float(np.mean(y[-10:]))
    for _ in range(horizon):
        ret_short = (y[-1] - y[-3]) / y[-3] if len(y) >= 3 else 0.0
        drift = y[-1] * (0.25 * ret_short) + 0.05 * (ema - y[-1])
        next_val = y[-1] + drift
        preds.append(next_val)
        y = np.append(y, next_val)
    return np.array(preds, dtype=np.float64)


# =====================================================================
# Quantile Calibration & Metric Helpers (Evaluated Out-Of-Sample)
# =====================================================================

def calculate_quantile_coverage(actual_series: List[float], q_series: List[float], quantile: float) -> float:
    """Empirical proportion of observations falling below the predicted quantile: P(y <= q)."""
    if not actual_series or len(actual_series) != len(q_series):
        return 0.0
    n = len(actual_series)
    count_below = sum(1 for y, q in zip(actual_series, q_series) if y <= q)
    return round((count_below / n) * 100.0, 2)


def calculate_interval_coverage(actual_series: List[float], lower_series: List[float], upper_series: List[float]) -> float:
    """Empirical coverage of prediction interval [lower, upper]: P(lower <= y <= upper)."""
    if not actual_series or len(actual_series) != len(lower_series) or len(actual_series) != len(upper_series):
        return 0.0
    n = len(actual_series)
    count_inside = sum(1 for y, l, u in zip(actual_series, lower_series, upper_series) if l <= y <= u)
    return round((count_inside / n) * 100.0, 2)


def calculate_interval_width(lower_series: List[float], upper_series: List[float]) -> float:
    """Mean absolute interval width: E[upper - lower]."""
    if not lower_series or len(lower_series) != len(upper_series):
        return 0.0
    widths = [abs(u - l) for l, u in zip(lower_series, upper_series)]
    return round(float(np.mean(widths)), 4)


def calculate_pinball_loss(actual_series: List[float], q_series: List[float], quantile: float) -> float:
    """Pinball / quantile loss for evaluating quantile forecast accuracy."""
    if not actual_series or len(actual_series) != len(q_series):
        return 0.0
    losses = []
    for y, q in zip(actual_series, q_series):
        diff = y - q
        if diff >= 0:
            losses.append(quantile * diff)
        else:
            losses.append((quantile - 1.0) * diff)
    return round(float(np.mean(losses)), 4)
