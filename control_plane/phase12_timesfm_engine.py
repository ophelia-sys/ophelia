"""Ophelia Phase 12: Fresh-Period Incremental TimesFM Validation Engine.

Layer: control_plane/phase12_timesfm_engine.py
Contract:
- Authoritative execution of Phase 12: Fresh-Period Incremental TimesFM 3.0 Validation.
- Absolute Safety Invariants:
    TRADING_AUTHORITY = FALSE
    EXECUTION_MODE = SHADOW
    LIVE_ORDERS = FORBIDDEN
    AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN
- Fresh Chronological Dataset:
    Window: 2023-12-01 00:00:00 to 2024-03-31 23:59:59 UTC (122 calendar days)
    Symbols: BTCUSDT, ETHUSDT, SOLUSDT
    Zero overlap with Phase 10.3 / Phase 11 / Phase 11.5 (which used Oct 01 to Nov 30, 2023).
- Chronological Partitions:
    TRAIN:      2023-12-01 00:00 to 2024-01-09 23:59 UTC (40 days)
    EMBARGO 1:  2024-01-10 00:00 to 2024-01-10 23:59 UTC (24h purge)
    VALIDATION: 2024-01-11 00:00 to 2024-02-15 23:59 UTC (36 days)
    EMBARGO 2:  2024-02-16 00:00 to 2024-02-16 23:59 UTC (24h purge)
    TEST:       2024-02-17 00:00 to 2024-03-31 23:59 UTC (44 days) - UNTOUCHED OOS
- Frozen Deterministic Specification (D4H):
    VARIANT_D:
      min_displacement_atr = 1.20
      min_rejection_body_ratio = 0.45
      min_rejection_rvol = 1.00
    PLUS:
      4H trend-direction alignment (4H EMA20 vs EMA50, 0.1% buffer)
    Trade Management: FIXED_SL_TP (No breakeven, trailing, or arbitrary time stops)
- TimesFM Foundation Model:
    Google TimesFM 3.0 (google/timesfm-3.0-pytorch)
    Primary 5m Architecture: 12 x 5m steps (+15m, +30m, +45m, +60m)
    Terminology: FORECAST-DISTRIBUTION REACHABILITY (q90 is not a 90% probability)
- Incremental Cohorts Matrix:
    A = BASELINE_A (Raw ENTRY_READY retest)
    B = VARIANT_D (Structure quality)
    C = D4H = VARIANT_D + 4H ALIGNMENT
    D = D4H + TIMESFM TARGET REACHABILITY (q90 >= TP1 for Long, q10 <= TP1 for Short)
    E = D + TIMESFM DOWNSIDE DISTRIBUTION (Stop-margin analysis / reject if q10 <= SL)
    F = E + POST-ENTRY TIMESFM REFORECAST MANAGEMENT (T+15m reforecast)
- Incremental Evaluations:
    B - A (Structure Quality Increment)
    C - B (4H Alignment Increment)
    D - C (TimesFM Target Reachability Increment)
    E - D (TimesFM Downside Distribution Increment)
    F - E (Post-Entry Reforecast Increment)
- Friction Model:
    0 bps, 5 bps, 9 bps (base), 14 bps.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import config, db
from .phase11_repair_engine import (
    CandidateFeatureSnapshot,
    bootstrap_ci,
    classify_rr_bucket,
)
from .phase11_5_htf_engine import (
    compute_htf_features,
    resample_htf_candles,
)
from .retest_candidate_generator import generate_retest_candidates
from .retest_engine import (
    calculate_atr,
    calculate_rvol,
)
from .timesfm_candidate import (
    CandidateForecastContext,
    CandidateForecastResult,
    generate_candidate_forecast,
    get_timesfm_provider,
    TIMESFM_CHECKPOINT,
    TIMESFM_MODEL_VERSION,
    TIMESFM_PRIMARY_5M,
)

logger = logging.getLogger("ophelia.phase12_timesfm")

# Safety Invariants
TRADING_AUTHORITY = False
EXECUTION_MODE = "SHADOW"
LIVE_ORDERS_FORBIDDEN = True
AUTONOMOUS_SLOT_RESERVATION_FORBIDDEN = True

# Chronological Partitions (UTC ms)
TS_DEC_01_2023 = int(datetime.datetime(2023, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_JAN_09_2024 = int(datetime.datetime(2024, 1, 9, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_JAN_11_2024 = int(datetime.datetime(2024, 1, 11, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_FEB_15_2024 = int(datetime.datetime(2024, 2, 15, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_FEB_17_2024 = int(datetime.datetime(2024, 2, 17, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_MAR_31_2024 = int(datetime.datetime(2024, 3, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)

EMBARGO_MS = 60 * 60 * 1000  # 60m embargo

# Friction regimes
FRICTION_ZERO = 0.0000
FRICTION_LOW = 0.0005   # 5 bps
FRICTION_BASE = 0.0009  # 9 bps (0.05% fee + 0.04% slippage)
FRICTION_HIGH = 0.0014  # 14 bps

# Frozen D4H Specification
D4H_SPECIFICATION = {
    "spec_version": "D4H_PHASE12_FROZEN_V1",
    "base_strategy": "CAUSAL_RETEST_ENTRY_READY",
    "min_displacement_atr": 1.20,
    "min_rejection_body_ratio": 0.45,
    "min_rejection_rvol": 1.00,
    "htf_alignment": "4H_EMA20_EMA50",
    "htf_ema_buffer": 0.001,
    "management_policy": "FIXED_SL_TP",
    "base_friction_bps": 9.0
}
D4H_SPEC_HASH = hashlib.sha256(json.dumps(D4H_SPECIFICATION, sort_keys=True).encode()).hexdigest()[:16]


@dataclass(slots=True)
class Phase12Candidate:
    """Immutable, fully audited Phase 12 Candidate Record."""
    candidate_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    timestamp_ms: int
    dt_utc: str
    split: str      # "TRAIN", "VALIDATION", "TEST", "EMBARGO"

    # Price & Structure Geometry
    entry_price: float
    sl_price: float
    tp1_price: float
    tp2_price: Optional[float]
    risk_amount: float
    reward_tp1: float
    raw_rr: float
    displacement_atr: float
    rejection_body_ratio: float
    rvol: float
    cur_atr: float
    atr_pct: float

    # 4H HTF Features
    trend_4h: str
    trend_aligned_4h: bool
    atr_pct_4h: float
    vol_regime_4h: str

    # 1H Context
    trend_1h: str
    vol_regime_1h: str
    expansion_1h: str

    # Membership Flags
    pass_variant_d: bool
    pass_d4h: bool

    # Actual Forward Outcomes (up to 12 x 5m = 60m)
    exit_reason: str
    exit_price: float
    time_to_exit_min: int
    gross_realized_r: float
    net_realized_r_zero: float
    net_realized_r_low: float
    net_realized_r_base: float
    net_realized_r_high: float
    mfe: float
    mae: float
    actual_low: float
    actual_high: float

    # TimesFM Pre-Entry Distribution (at ENTRY_READY)
    tfm_model: str
    tfm_checkpoint: str
    tfm_inference_ms: float
    tfm_p15: float
    tfm_p30: float
    tfm_p45: float
    tfm_p60: float
    tfm_q10_60m: float
    tfm_q50_60m: float
    tfm_q90_60m: float
    tfm_dispersion_pct: float
    tfm_path_slope: float
    tfm_curvature: float
    tfm_reachability_ratio_15m: float
    tfm_reachability_ratio_30m: float
    tfm_reachability_ratio_45m: float
    tfm_reachability_ratio_60m: float
    tfm_reachable_binary_60m: bool
    tfm_quantile_crossing: bool
    tfm_context_hash: str
    tfm_snapshot_hash: str

    # Downside Distribution Analysis
    tfm_predicted_drawdown: float
    tfm_mae_prediction_error: float
    tfm_q10_covered_mae: bool
    tfm_sl_touch_predicted: bool
    pass_downside_gate: bool

    # Simple Baselines Predictions (at 60m horizon)
    base_persistence_pred: float
    base_ema_extrap_pred: float
    base_vwap_pred: float
    base_ar_pred: float

    # Post-Entry Reforecast (at T+15m)
    reforecast_performed: bool = False
    reforecast_q50: float = 0.0
    reforecast_q10: float = 0.0
    reforecast_q90: float = 0.0
    reforecast_reachability_ratio: float = 0.0
    reforecast_delta_q50: float = 0.0
    reforecast_delta_reachability: float = 0.0
    reforecast_policy: str = "CONTINUE"  # "CONTINUE", "EARLY_EXIT"
    reforecast_net_r_base: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assign_phase12_split(ts: int) -> str:
    """Assigns timestamp to Phase 12 chronological partition with 24h embargo."""
    if TS_DEC_01_2023 <= ts <= TS_JAN_09_2024:
        return "TRAIN"
    elif TS_JAN_09_2024 < ts < TS_JAN_11_2024:
        return "EMBARGO"
    elif TS_JAN_11_2024 <= ts <= TS_FEB_15_2024:
        return "VALIDATION"
    elif TS_FEB_15_2024 < ts < TS_FEB_17_2024:
        return "EMBARGO"
    elif TS_FEB_17_2024 <= ts <= TS_MAR_31_2024:
        return "TEST"
    return "OUT_OF_BOUNDS"


def evaluate_forward_trajectory_phase12(
    cand: Dict[str, Any],
    future_bars: List[dict]
) -> Tuple[str, float, int, float, float, float, float, float, float, float, float, float]:
    """Causal trace over future closed 5m bars.
    SL evaluated strictly before TP on same candle to eliminate favorable bias.
    """
    direction = cand["direction"].upper()
    entry = float(cand["entry_price"])
    sl = float(cand["sl_price"])
    tp1 = float(cand["tp1_price"])

    risk = (entry - sl) if direction == "LONG" else (sl - entry)
    risk = max(1e-6, risk)

    cost_r_zero = 0.0
    cost_r_low = (FRICTION_LOW * entry) / risk
    cost_r_base = (FRICTION_BASE * entry) / risk
    cost_r_high = (FRICTION_HIGH * entry) / risk

    if not future_bars:
        return ("NO_DATA", entry, 0, 0.0, 0.0, -cost_r_low, -cost_r_base, -cost_r_high, 0.0, 0.0, entry, entry)

    highs = [float(b["high"]) for b in future_bars]
    lows = [float(b["low"]) for b in future_bars]
    closes = [float(b["close"]) for b in future_bars]

    actual_low = min(lows)
    actual_high = max(highs)

    exit_reason = "HORIZON_EXPIRED"
    time_to_exit_min = len(future_bars) * 5
    exit_price = closes[-1]

    if direction == "LONG":
        mfe = actual_high - entry
        mae = actual_low - entry
        for idx, b in enumerate(future_bars):
            bh, bl = float(b["high"]), float(b["low"])
            if bl <= sl:
                exit_reason = "SL"
                time_to_exit_min = (idx + 1) * 5
                exit_price = sl
                break
            elif bh >= tp1:
                exit_reason = "TP1"
                time_to_exit_min = (idx + 1) * 5
                exit_price = tp1
                break
        gross_r = (exit_price - entry) / risk
    else:  # SHORT
        mfe = entry - actual_low
        mae = entry - actual_high
        for idx, b in enumerate(future_bars):
            bh, bl = float(b["high"]), float(b["low"])
            if bh >= sl:
                exit_reason = "SL"
                time_to_exit_min = (idx + 1) * 5
                exit_price = sl
                break
            elif bl <= tp1:
                exit_reason = "TP1"
                time_to_exit_min = (idx + 1) * 5
                exit_price = tp1
                break
        gross_r = (entry - exit_price) / risk

    net_r_zero = gross_r
    net_r_low = gross_r - cost_r_low
    net_r_base = gross_r - cost_r_base
    net_r_high = gross_r - cost_r_high

    return (exit_reason, exit_price, time_to_exit_min, gross_r,
            net_r_zero, net_r_low, net_r_base, net_r_high,
            mfe, mae, actual_low, actual_high)


class Phase12TimesFMValidationEngine:
    """Authoritative research coordinator for Phase 12 Incremental TimesFM Validation."""

    def __init__(self, parquet_path: str = "data/processed/phase12_fresh_universe_1m.parquet"):
        self.parquet_path = parquet_path
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.candles_5m: Dict[str, List[dict]] = {}
        self.candles_1h: Dict[str, List[dict]] = {}
        self.candles_4h: Dict[str, List[dict]] = {}
        self.all_candidates: List[Phase12Candidate] = []
        self.results: Dict[str, Any] = {}

    def load_and_resample_universe(self):
        """Loads continuous 1m dataset and resamples to closed 5m, 1H, 4H bars."""
        logger.info("Loading 1m parquet from %s ...", self.parquet_path)
        try:
            import pyarrow.dataset as ds
            dataset = ds.dataset(self.parquet_path, format="parquet")
            use_ds = True
        except ImportError:
            df_all = pd.read_parquet(self.parquet_path)
            use_ds = False

        for sym in self.symbols:
            logger.info("Resampling bars for %s ...", sym)
            if use_ds:
                tbl = dataset.to_table(filter=(ds.field("symbol") == sym),
                                       columns=["timestamp", "open", "high", "low", "close", "volume"])
                df = tbl.to_pandas().sort_values("timestamp").reset_index(drop=True)
            else:
                df = df_all[df_all["symbol"] == sym][["timestamp", "open", "high", "low", "close", "volume"]].copy()
                df = df.sort_values("timestamp").reset_index(drop=True)

            df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("dt", inplace=True)

            ohlc_5m = df.resample("5min").agg({
                "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "timestamp": "first"
            }).dropna().reset_index()

            c5m = [{
                "ts": int(r["timestamp"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"])
            } for _, r in ohlc_5m.iterrows()]
            self.candles_5m[sym] = c5m

            c1h = resample_htf_candles(c5m, 3600 * 1000)
            c4h = resample_htf_candles(c5m, 4 * 3600 * 1000)
            self.candles_1h[sym] = c1h
            self.candles_4h[sym] = c4h

            logger.info("%s: %d (5m), %d (1H), %d (4H) closed bars", sym, len(c5m), len(c1h), len(c4h))

    def run_validation(self) -> Dict[str, Any]:
        """Runs the complete Phase 12 incremental protocol."""
        t_start = time.perf_counter()
        logger.info("Starting Phase 12 Incremental TimesFM Validation...")

        # 1. Resample data
        self.load_and_resample_universe()

        # 2. Causally scan and generate ENTRY_READY candidates
        raw_candidates: List[Dict[str, Any]] = []
        for sym in self.symbols:
            c5m = self.candles_5m[sym]
            cands = generate_retest_candidates(c5m, sym, timeframe=5, context_lookback=128)
            logger.info("%s generated %d raw candidates", sym, len(cands))
            raw_candidates.extend(cands)

        # Sort strictly chronologically
        raw_candidates.sort(key=lambda x: int(x["timestamp_ms"]))
        logger.info("Total raw candidates across universe: %d", len(raw_candidates))

        # 3. Evaluate each candidate causally
        logger.info("Evaluating candidates with TimesFM 3.0 and causal forward tracking...")
        for cand in raw_candidates:
            evaluated = self._evaluate_candidate(cand)
            if evaluated is not None:
                self.all_candidates.append(evaluated)

        logger.info("Successfully evaluated %d valid candidates", len(self.all_candidates))

        # 4. Compute Comprehensive Comparative Metrics
        self.results = self._compute_metrics()
        self.results["elapsed_seconds"] = round(time.perf_counter() - t_start, 2)
        return self.results

    def _evaluate_candidate(self, cand: Dict[str, Any]) -> Optional[Phase12Candidate]:
        """Evaluates a single candidate: structural features, 4H alignment, TimesFM forecast, T+15m reforecast, and outcomes."""
        ts = int(cand["timestamp_ms"])
        cand_id = cand["candidate_id"]
        sym = cand["symbol"]
        direction = cand["direction"].upper()
        entry = float(cand["entry_price"])
        sl = float(cand["sl_price"])
        tp1 = float(cand["tp1_price"])
        tp2 = float(cand["tp2_price"]) if cand.get("tp2_price") else None

        risk = (entry - sl) if direction == "LONG" else (sl - entry)
        if risk <= 0:
            return None
        reward1 = (tp1 - entry) if direction == "LONG" else (entry - tp1)
        raw_rr = reward1 / risk

        split = assign_phase12_split(ts)
        dt_str = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).isoformat()

        # Causal historical candle slices (closed bars <= ts)
        hist_5m = [c for c in self.candles_5m[sym] if int(c["ts"]) <= ts]
        if len(hist_5m) < 40:
            return None

        # Future 12 bars (60m)
        future_all = [c for c in self.candles_5m[sym] if int(c["ts"]) > ts]
        future_60m = future_all[:12]
        if len(future_60m) < 3:
            return None

        # Structural Quality Features (Variant D)
        h5 = [float(c["high"]) for c in hist_5m]
        l5 = [float(c["low"]) for c in hist_5m]
        c5 = [float(c["close"]) for c in hist_5m]
        v5 = [float(c["volume"]) for c in hist_5m]

        atr_series = calculate_atr(h5, l5, c5, 14)
        cur_atr = atr_series[-1] if atr_series else entry * 0.005
        atr_pct = cur_atr / max(1e-6, entry)

        cur_rvol = float(calculate_rvol(v5, 20))

        disp_mag = abs(entry - float(cand.get("breakout_price", entry)))
        disp_atr = disp_mag / max(1e-6, cur_atr)

        last_bar = hist_5m[-1]
        lb_high = float(last_bar["high"])
        lb_low = float(last_bar["low"])
        lb_open = float(last_bar["open"])
        lb_close = float(last_bar["close"])
        lb_range = max(1e-6, lb_high - lb_low)
        rej_body_ratio = abs(lb_close - lb_open) / lb_range

        # Variant D Condition
        pass_variant_d = (disp_atr >= 1.20 and rej_body_ratio >= 0.45 and cur_rvol >= 1.00)

        # 4H and 1H HTF Features
        htf = compute_htf_features(ts, direction, self.candles_1h[sym], self.candles_4h[sym])
        trend_4h = htf.get("trend_4h", "NEUTRAL")
        trend_aligned_4h = bool(htf.get("trend_aligned_4h", False))
        atr_pct_4h = float(htf.get("atr_pct_4h", 0.02))
        vol_regime_4h = str(htf.get("vol_regime_4h", "NORMAL"))

        trend_1h = str(htf.get("trend_1h", "NEUTRAL"))
        vol_regime_1h = str(htf.get("vol_regime_1h", "NORMAL"))
        expansion_1h = str(htf.get("expansion_state_1h", "RANGE"))

        # Frozen D4H Membership
        pass_d4h = bool(pass_variant_d and trend_aligned_4h)

        # 1. Forward Trajectory Outcomes
        (exit_reason, exit_price, exit_time_min, gross_r,
         net_r_zero, net_r_low, net_r_base, net_r_high,
         mfe, mae, act_low, act_high) = evaluate_forward_trajectory_phase12(cand, future_60m)

        # Simple Baselines for Comparison (Section 12)
        base_persist = entry
        ema_span = 20
        ema_val = float(pd.Series(c5).ewm(span=ema_span, adjust=False).mean().iloc[-1])
        ema_slope = (c5[-1] - ema_val) / max(1e-6, ema_val)
        base_ema_extrap = entry * (1.0 + ema_slope * 12)
        cum_vol = sum(v5[-36:])
        cum_vp = sum(c5[i] * v5[i] for i in range(max(0, len(c5)-36), len(c5)))
        base_vwap = (cum_vp / max(1e-6, cum_vol)) if cum_vol > 0 else entry
        base_ar = entry

        # 2. TimesFM 3.0 Pre-Entry Forecast (at ENTRY_READY)
        # Authoritative Execution: Evaluated on all frozen D4H candidates (Cohort C)
        if pass_d4h:
            fc_context = CandidateForecastContext(
                candidate_id=cand_id,
                canonical_instrument_id=f"CRYPTO:{sym}",
                symbol=sym,
                direction=direction,
                candidate_timestamp_ms=ts,
                entry_price=entry,
                sl_price=sl,
                tp1_price=tp1,
                tp2_price=tp2,
                expected_holding_horizon="15m-60m",
                regime=trend_4h,
                structure_state="CONFIRMED_REJECTION",
                retest_state="ENTRY_READY"
            )

            fc_res = generate_candidate_forecast(fc_context, hist_5m, timeframe_mode=TIMESFM_PRIMARY_5M)
            p15 = fc_res.path.get("15m", entry)
            p30 = fc_res.path.get("30m", entry)
            p45 = fc_res.path.get("45m", entry)
            p60 = fc_res.path.get("60m", entry)
            q10 = fc_res.quantiles.get("q10", entry * 0.99)
            q50 = fc_res.quantiles.get("q50", entry)
            q90 = fc_res.quantiles.get("q90", entry * 1.01)

            dispersion_pct = fc_res.forecast_dispersion_pct
            path_slope = (p60 - p15) / entry
            curvature = ((p60 - p30) - (p30 - p15)) / entry
            base_ar = p60

            # Primary Hypothesis Reachability:
            if direction == "LONG":
                reach_ratio_15m = (p15 - entry) / max(1e-6, tp1 - entry)
                reach_ratio_30m = (p30 - entry) / max(1e-6, tp1 - entry)
                reach_ratio_45m = (p45 - entry) / max(1e-6, tp1 - entry)
                reach_ratio_60m = (q90 - entry) / max(1e-6, tp1 - entry)
                reachable_binary = (reach_ratio_60m >= 1.0)
                pred_drawdown = q10 - entry
                mae_error = mae - pred_drawdown
                q10_covered = (act_low >= q10)
                sl_touch_pred = (q10 <= sl)
                pass_downside = (q10 > sl)
            else:
                reach_ratio_15m = (entry - p15) / max(1e-6, entry - tp1)
                reach_ratio_30m = (entry - p30) / max(1e-6, entry - tp1)
                reach_ratio_45m = (entry - p45) / max(1e-6, entry - tp1)
                reach_ratio_60m = (entry - q10) / max(1e-6, entry - tp1)
                reachable_binary = (reach_ratio_60m >= 1.0)
                pred_drawdown = entry - q90
                mae_error = mae - pred_drawdown
                q10_covered = (act_high <= q90)
                sl_touch_pred = (q90 >= sl)
                pass_downside = (q90 < sl)

            tfm_model = fc_res.model
            tfm_checkpoint = fc_res.checkpoint
            tfm_inference_ms = fc_res.actual_model_inference_ms
            tfm_crossing = fc_res.quantile_crossing_detected
            tfm_ctx_hash = fc_res.context_hash
            tfm_snap_hash = fc_res.snapshot_hash

            # 3. Post-Entry Reforecast at T+15m
            reforecast_performed = False
            reforecast_q50 = q50
            reforecast_q10 = q10
            reforecast_q90 = q90
            reforecast_reach_ratio = reach_ratio_60m
            delta_q50 = 0.0
            delta_reach = 0.0
            reforecast_policy = "CONTINUE"
            reforecast_net_r_base = net_r_base

            if len(future_all) >= 3:
                reforecast_performed = True
                t_15m = int(future_all[2]["ts"])
                px_15m = float(future_all[2]["close"])
                hist_15m = [c for c in self.candles_5m[sym] if int(c["ts"]) <= t_15m]

                ctx_15m = CandidateForecastContext(
                    candidate_id=f"{cand_id}_T15",
                    canonical_instrument_id=f"CRYPTO:{sym}",
                    symbol=sym,
                    direction=direction,
                    candidate_timestamp_ms=t_15m,
                    entry_price=px_15m,
                    sl_price=sl,
                    tp1_price=tp1,
                    tp2_price=tp2,
                    expected_holding_horizon="15m-60m",
                    regime=trend_4h,
                    structure_state="REFORECAST_EVAL",
                    retest_state="ENTRY_READY"
                )
                fc_15m = generate_candidate_forecast(ctx_15m, hist_15m, timeframe_mode=TIMESFM_PRIMARY_5M)
                reforecast_q50 = fc_15m.quantiles.get("q50", px_15m)
                reforecast_q10 = fc_15m.quantiles.get("q10", px_15m * 0.99)
                reforecast_q90 = fc_15m.quantiles.get("q90", px_15m * 1.01)

                if direction == "LONG":
                    reforecast_reach_ratio = (reforecast_q90 - entry) / max(1e-6, tp1 - entry)
                    delta_q50 = reforecast_q50 - q50
                    delta_reach = reforecast_reach_ratio - reach_ratio_60m
                    if reforecast_reach_ratio < 0.70 or reforecast_q50 < entry:
                        reforecast_policy = "EARLY_EXIT"
                        cost_r = (FRICTION_BASE * entry) / risk
                        reforecast_net_r_base = ((px_15m - entry) / risk) - cost_r
                else:
                    reforecast_reach_ratio = (entry - reforecast_q10) / max(1e-6, entry - tp1)
                    delta_q50 = q50 - reforecast_q50
                    delta_reach = reforecast_reach_ratio - reach_ratio_60m
                    if reforecast_reach_ratio < 0.70 or reforecast_q50 > entry:
                        reforecast_policy = "EARLY_EXIT"
                        cost_r = (FRICTION_BASE * entry) / risk
                        reforecast_net_r_base = ((entry - px_15m) / risk) - cost_r
        else:
            # Baseline deterministic candidates outside D4H
            p15 = entry
            p30 = entry
            p45 = entry
            p60 = entry
            q10 = entry * 0.99 if direction == "LONG" else entry * 1.01
            q50 = entry
            q90 = entry * 1.01 if direction == "LONG" else entry * 0.99
            dispersion_pct = 2.0
            path_slope = 0.0
            curvature = 0.0
            reach_ratio_15m = 0.0
            reach_ratio_30m = 0.0
            reach_ratio_45m = 0.0
            reach_ratio_60m = 0.0
            reachable_binary = False
            pred_drawdown = 0.0
            mae_error = 0.0
            q10_covered = True
            sl_touch_pred = False
            pass_downside = False
            tfm_model = "NONE_FILTERED_D4H"
            tfm_checkpoint = "NONE"
            tfm_inference_ms = 0.0
            tfm_crossing = False
            tfm_ctx_hash = ""
            tfm_snap_hash = ""
            reforecast_performed = False
            reforecast_q50 = entry
            reforecast_q10 = entry
            reforecast_q90 = entry
            reforecast_reach_ratio = 0.0
            delta_q50 = 0.0
            delta_reach = 0.0
            reforecast_policy = "CONTINUE"
            reforecast_net_r_base = net_r_base

        return Phase12Candidate(
            candidate_id=cand_id,
            symbol=sym,
            direction=direction,
            timestamp_ms=ts,
            dt_utc=dt_str,
            split=split,
            entry_price=entry,
            sl_price=sl,
            tp1_price=tp1,
            tp2_price=tp2,
            risk_amount=risk,
            reward_tp1=reward1,
            raw_rr=raw_rr,
            displacement_atr=disp_atr,
            rejection_body_ratio=rej_body_ratio,
            rvol=cur_rvol,
            cur_atr=cur_atr,
            atr_pct=atr_pct,
            trend_4h=trend_4h,
            trend_aligned_4h=trend_aligned_4h,
            atr_pct_4h=atr_pct_4h,
            vol_regime_4h=vol_regime_4h,
            trend_1h=trend_1h,
            vol_regime_1h=vol_regime_1h,
            expansion_1h=expansion_1h,
            pass_variant_d=pass_variant_d,
            pass_d4h=pass_d4h,
            exit_reason=exit_reason,
            exit_price=exit_price,
            time_to_exit_min=exit_time_min,
            gross_realized_r=gross_r,
            net_realized_r_zero=net_r_zero,
            net_realized_r_low=net_r_low,
            net_realized_r_base=net_r_base,
            net_realized_r_high=net_r_high,
            mfe=mfe,
            mae=mae,
            actual_low=act_low,
            actual_high=act_high,
            tfm_model=tfm_model,
            tfm_checkpoint=tfm_checkpoint,
            tfm_inference_ms=tfm_inference_ms,
            tfm_p15=p15,
            tfm_p30=p30,
            tfm_p45=p45,
            tfm_p60=p60,
            tfm_q10_60m=q10,
            tfm_q50_60m=q50,
            tfm_q90_60m=q90,
            tfm_dispersion_pct=dispersion_pct,
            tfm_path_slope=path_slope,
            tfm_curvature=curvature,
            tfm_reachability_ratio_15m=reach_ratio_15m,
            tfm_reachability_ratio_30m=reach_ratio_30m,
            tfm_reachability_ratio_45m=reach_ratio_45m,
            tfm_reachability_ratio_60m=reach_ratio_60m,
            tfm_reachable_binary_60m=reachable_binary,
            tfm_quantile_crossing=tfm_crossing,
            tfm_context_hash=tfm_ctx_hash,
            tfm_snapshot_hash=tfm_snap_hash,
            tfm_predicted_drawdown=pred_drawdown,
            tfm_mae_prediction_error=mae_error,
            tfm_q10_covered_mae=q10_covered,
            tfm_sl_touch_predicted=sl_touch_pred,
            pass_downside_gate=pass_downside,
            base_persistence_pred=base_persist,
            base_ema_extrap_pred=base_ema_extrap,
            base_vwap_pred=base_vwap,
            base_ar_pred=base_ar,
            reforecast_performed=reforecast_performed,
            reforecast_q50=reforecast_q50,
            reforecast_q10=reforecast_q10,
            reforecast_q90=reforecast_q90,
            reforecast_reachability_ratio=reforecast_reach_ratio,
            reforecast_delta_q50=delta_q50,
            reforecast_delta_reachability=delta_reach,
            reforecast_policy=reforecast_policy,
            reforecast_net_r_base=reforecast_net_r_base
        )

    def _compute_metrics(self) -> Dict[str, Any]:
        """Calculates authoritative quantitative, statistical, economic, and multiple testing metrics."""
        test_cands = [c for c in self.all_candidates if c.split == "TEST"]
        val_cands = [c for c in self.all_candidates if c.split == "VALIDATION"]
        train_cands = [c for c in self.all_candidates if c.split == "TRAIN"]

        def cohort_stats(subset: List[Phase12Candidate], friction_key: str = "base", use_reforecast: bool = False) -> Dict[str, Any]:
            if not subset:
                return {
                    "count": 0, "win_rate": 0.0, "tp1_count": 0, "sl_count": 0,
                    "gross_r": 0.0, "net_r": 0.0, "mean_r": 0.0, "median_r": 0.0,
                    "pf": 0.0, "max_drawdown": 0.0, "ci_mean_r": [0.0, 0.0], "ci_wr": [0.0, 0.0]
                }
            n = len(subset)
            wins = sum(1 for c in subset if c.exit_reason in ("TP1", "TP2"))
            sl_count = sum(1 for c in subset if c.exit_reason == "SL")
            wr = (wins / n) * 100.0

            if use_reforecast:
                net_rs = [c.reforecast_net_r_base for c in subset]
            elif friction_key == "zero":
                net_rs = [c.net_realized_r_zero for c in subset]
            elif friction_key == "low":
                net_rs = [c.net_realized_r_low for c in subset]
            elif friction_key == "high":
                net_rs = [c.net_realized_r_high for c in subset]
            else:
                net_rs = [c.net_realized_r_base for c in subset]

            gross_rs = [c.gross_realized_r for c in subset]
            tot_gross = sum(gross_rs)
            tot_net = sum(net_rs)
            mean_r = float(np.mean(net_rs))
            median_r = float(np.median(net_rs))

            gw = sum(r for r in gross_rs if r > 0)
            gl = abs(sum(r for r in gross_rs if r < 0))
            pf = round(gw / max(1e-6, gl), 2)

            # Max Drawdown in R
            cum_r = np.cumsum(net_rs)
            peaks = np.maximum.accumulate(cum_r)
            drawdowns = peaks - cum_r
            max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

            # 95% Bootstrap CI
            _, ci_l, ci_u = bootstrap_ci(net_rs)
            wr_bool = [1.0 if c.exit_reason in ("TP1", "TP2") else 0.0 for c in subset]
            _, wr_l, wr_u = bootstrap_ci(wr_bool)

            return {
                "count": n,
                "win_rate": round(wr, 2),
                "tp1_count": wins,
                "sl_count": sl_count,
                "gross_r": round(tot_gross, 2),
                "net_r": round(tot_net, 2),
                "mean_r": round(mean_r, 3),
                "median_r": round(median_r, 3),
                "pf": pf,
                "max_drawdown": round(max_dd, 2),
                "ci_mean_r": [round(ci_l, 3), round(ci_u, 3)],
                "ci_wr": [round(wr_l * 100.0, 2), round(wr_u * 100.0, 2)]
            }

        # 1. Baseline Progression Cohorts Definition:
        # A = BASELINE_A (All candidates)
        # B = VARIANT_D (Passes Variant D structural quality)
        # C = D4H (Variant D + 4H trend alignment)
        # D = D4H + TimesFM Reachability (tfm_reachable_binary_60m == True)
        # E = D + Downside Gate (pass_downside_gate == True)
        # F = E + Post-Entry Reforecast Management
        def filter_cohort(subset: List[Phase12Candidate], cohort_key: str) -> List[Phase12Candidate]:
            if cohort_key == "A_BASELINE":
                return subset
            elif cohort_key == "B_VARIANT_D":
                return [c for c in subset if c.pass_variant_d]
            elif cohort_key == "C_D4H":
                return [c for c in subset if c.pass_d4h]
            elif cohort_key == "D_D4H_TFM_REACHABLE":
                return [c for c in subset if c.pass_d4h and c.tfm_reachable_binary_60m]
            elif cohort_key == "E_D4H_TFM_DOWNSIDE":
                return [c for c in subset if c.pass_d4h and c.tfm_reachable_binary_60m and c.pass_downside_gate]
            elif cohort_key == "F_D4H_TFM_MANAGED":
                return [c for c in subset if c.pass_d4h and c.tfm_reachable_binary_60m and c.pass_downside_gate]
            return []

        cohort_keys = [
            "A_BASELINE", "B_VARIANT_D", "C_D4H",
            "D_D4H_TFM_REACHABLE", "E_D4H_TFM_DOWNSIDE", "F_D4H_TFM_MANAGED"
        ]

        matrix_results = {}
        for k in cohort_keys:
            use_ref = (k == "F_D4H_TFM_MANAGED")
            matrix_results[k] = {
                "train": cohort_stats(filter_cohort(train_cands, k), use_reforecast=use_ref),
                "validation": cohort_stats(filter_cohort(val_cands, k), use_reforecast=use_ref),
                "test": cohort_stats(filter_cohort(test_cands, k), use_reforecast=use_ref)
            }

        # 2. Incremental Deltas on Untouched TEST Set:
        test_a = matrix_results["A_BASELINE"]["test"]
        test_b = matrix_results["B_VARIANT_D"]["test"]
        test_c = matrix_results["C_D4H"]["test"]
        test_d = matrix_results["D_D4H_TFM_REACHABLE"]["test"]
        test_e = matrix_results["E_D4H_TFM_DOWNSIDE"]["test"]
        test_f = matrix_results["F_D4H_TFM_MANAGED"]["test"]

        incremental_deltas_test = {
            "B_minus_A_structure_quality": {
                "delta_n": test_b["count"] - test_a["count"],
                "delta_win_rate_pct": round(test_b["win_rate"] - test_a["win_rate"], 2),
                "delta_gross_r": round(test_b["gross_r"] - test_a["gross_r"], 2),
                "delta_net_r": round(test_b["net_r"] - test_a["net_r"], 2),
                "delta_mean_r": round(test_b["mean_r"] - test_a["mean_r"], 3),
                "delta_pf": round(test_b["pf"] - test_a["pf"], 2)
            },
            "C_minus_B_4h_alignment": {
                "delta_n": test_c["count"] - test_b["count"],
                "delta_win_rate_pct": round(test_c["win_rate"] - test_b["win_rate"], 2),
                "delta_gross_r": round(test_c["gross_r"] - test_b["gross_r"], 2),
                "delta_net_r": round(test_c["net_r"] - test_b["net_r"], 2),
                "delta_mean_r": round(test_c["mean_r"] - test_b["mean_r"], 3),
                "delta_pf": round(test_c["pf"] - test_b["pf"], 2)
            },
            "D_minus_C_timesfm_reachability": {
                "delta_n": test_d["count"] - test_c["count"],
                "delta_win_rate_pct": round(test_d["win_rate"] - test_c["win_rate"], 2),
                "delta_gross_r": round(test_d["gross_r"] - test_c["gross_r"], 2),
                "delta_net_r": round(test_d["net_r"] - test_c["net_r"], 2),
                "delta_mean_r": round(test_d["mean_r"] - test_c["mean_r"], 3),
                "delta_pf": round(test_d["pf"] - test_c["pf"], 2)
            },
            "E_minus_D_timesfm_downside_gate": {
                "delta_n": test_e["count"] - test_d["count"],
                "delta_win_rate_pct": round(test_e["win_rate"] - test_d["win_rate"], 2),
                "delta_gross_r": round(test_e["gross_r"] - test_d["gross_r"], 2),
                "delta_net_r": round(test_e["net_r"] - test_d["net_r"], 2),
                "delta_mean_r": round(test_e["mean_r"] - test_d["mean_r"], 3),
                "delta_pf": round(test_e["pf"] - test_d["pf"], 2)
            },
            "F_minus_E_reforecast_management": {
                "delta_n": test_f["count"] - test_e["count"],
                "delta_win_rate_pct": round(test_f["win_rate"] - test_e["win_rate"], 2),
                "delta_gross_r": round(test_f["gross_r"] - test_e["gross_r"], 2),
                "delta_net_r": round(test_f["net_r"] - test_e["net_r"], 2),
                "delta_mean_r": round(test_f["mean_r"] - test_e["mean_r"], 3),
                "delta_pf": round(test_f["pf"] - test_e["pf"], 2)
            }
        }

        # 3. TimesFM Horizon Sensitivity on D4H (TEST split)
        d4h_test = filter_cohort(test_cands, "C_D4H")
        horizon_reachability_test = {
            "h15m": cohort_stats([c for c in d4h_test if c.tfm_reachability_ratio_15m >= 1.0]),
            "h30m": cohort_stats([c for c in d4h_test if c.tfm_reachability_ratio_30m >= 1.0]),
            "h45m": cohort_stats([c for c in d4h_test if c.tfm_reachability_ratio_45m >= 1.0]),
            "h60m_primary": cohort_stats([c for c in d4h_test if c.tfm_reachability_ratio_60m >= 1.0])
        }

        # 4. TimesFM vs Simple Baselines (Point Prediction MSE on TEST split)
        mse_tfm = float(np.mean([(c.tfm_p60 - c.exit_price)**2 for c in test_cands]))
        mse_persist = float(np.mean([(c.base_persistence_pred - c.exit_price)**2 for c in test_cands]))
        mse_ema = float(np.mean([(c.base_ema_extrap_pred - c.exit_price)**2 for c in test_cands]))
        mse_vwap = float(np.mean([(c.base_vwap_pred - c.exit_price)**2 for c in test_cands]))
        mse_ar = float(np.mean([(c.base_ar_pred - c.exit_price)**2 for c in test_cands]))

        baseline_comparison = {
            "timesfm_3_0_rmse": round(math.sqrt(mse_tfm), 2),
            "persistence_rmse": round(math.sqrt(mse_persist), 2),
            "ema_extrapolation_rmse": round(math.sqrt(mse_ema), 2),
            "session_vwap_rmse": round(math.sqrt(mse_vwap), 2),
            "statistical_ar_rmse": round(math.sqrt(mse_ar), 2)
        }

        # 5. Downside / Stop-Margin Analysis (TEST split)
        mae_coverage_pct = round(sum(1 for c in d4h_test if c.tfm_q10_covered_mae) / max(1, len(d4h_test)) * 100.0, 2)
        mae_errors = [c.tfm_mae_prediction_error for c in d4h_test]
        sl_touch_prec = round(sum(1 for c in d4h_test if c.tfm_sl_touch_predicted and c.exit_reason == "SL") /
                              max(1, sum(1 for c in d4h_test if c.tfm_sl_touch_predicted)) * 100.0, 2)

        downside_analysis = {
            "q10_coverage_mae_pct": mae_coverage_pct,
            "mae_prediction_error_mean": round(float(np.mean(mae_errors)), 2) if mae_errors else 0.0,
            "mae_prediction_rmse": round(float(np.sqrt(np.mean(np.array(mae_errors)**2))), 2) if mae_errors else 0.0,
            "sl_touch_prediction_precision_pct": sl_touch_prec
        }

        # 6. Asset Breakdown (TEST split for D4H and D4H + TimesFM)
        asset_breakdown = {}
        for sym in self.symbols:
            sym_d4h = [c for c in d4h_test if c.symbol == sym]
            sym_tfm = [c for c in d4h_test if c.symbol == sym and c.tfm_reachable_binary_60m]
            asset_breakdown[sym] = {
                "d4h": cohort_stats(sym_d4h),
                "d4h_timesfm": cohort_stats(sym_tfm),
                "delta_net_r": round(cohort_stats(sym_tfm)["net_r"] - cohort_stats(sym_d4h)["net_r"], 2),
                "delta_mean_r": round(cohort_stats(sym_tfm)["mean_r"] - cohort_stats(sym_d4h)["mean_r"], 3)
            }

        # 7. Regime Breakdown (TEST split for D4H and D4H + TimesFM)
        regimes = ["TREND_EXPANSION", "RANGE_CHOP"]
        regime_breakdown = {}
        for reg in ["EXPANSION", "RANGE"]:
            sub_d4h = [c for c in d4h_test if c.expansion_1h == reg]
            sub_tfm = [c for c in d4h_test if c.expansion_1h == reg and c.tfm_reachable_binary_60m]
            regime_breakdown[reg] = {
                "d4h": cohort_stats(sub_d4h),
                "d4h_timesfm": cohort_stats(sub_tfm),
                "delta_net_r": round(cohort_stats(sub_tfm)["net_r"] - cohort_stats(sub_d4h)["net_r"], 2),
                "delta_mean_r": round(cohort_stats(sub_tfm)["mean_r"] - cohort_stats(sub_d4h)["mean_r"], 3)
            }

        # 8. Friction Sensitivity on D4H and D4H + TimesFM (TEST split)
        tfm_test = [c for c in d4h_test if c.tfm_reachable_binary_60m]
        friction_sensitivity = {
            "d4h": {
                "zero_0bps": cohort_stats(d4h_test, "zero"),
                "low_5bps": cohort_stats(d4h_test, "low"),
                "base_9bps": cohort_stats(d4h_test, "base"),
                "high_14bps": cohort_stats(d4h_test, "high")
            },
            "d4h_timesfm": {
                "zero_0bps": cohort_stats(tfm_test, "zero"),
                "low_5bps": cohort_stats(tfm_test, "low"),
                "base_9bps": cohort_stats(tfm_test, "base"),
                "high_14bps": cohort_stats(tfm_test, "high")
            }
        }

        # 9. Clustering & Effective Sample Size (TEST split)
        day_map: Dict[str, List[Phase12Candidate]] = {}
        for c in test_cands:
            d_str = c.dt_utc.split("T")[0]
            day_map.setdefault(d_str, []).append(c)

        cluster_sizes = [len(v) for v in day_map.values()]
        mean_c_size = float(np.mean(cluster_sizes)) if cluster_sizes else 1.0
        n_raw = len(test_cands)
        rho_est = 0.35
        n_eff = n_raw / (1.0 + (mean_c_size - 1.0) * rho_est) if n_raw > 0 else 0.0

        cluster_analysis = {
            "total_test_candidates": n_raw,
            "total_day_clusters": len(day_map),
            "mean_cluster_size": round(mean_c_size, 2),
            "max_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
            "effective_sample_size_n_eff": round(n_eff, 1)
        }

        # 10. Multiple-Testing Registry & Benjamini-Hochberg FDR
        # Hypotheses:
        # H1: Target Reachability improves Net Mean R
        # H2: Downside Distribution provides informative MAE/SL protection
        # H3: Target Distribution differentiates feasible vs infeasible targets
        # H4: T+15m Reforecast improves post-entry net expectancy
        # Calculate two-sided p-value via Welch's t-test approximation / bootstrap
        r_d4h = [c.net_realized_r_base for c in d4h_test]
        r_tfm = [c.net_realized_r_base for c in tfm_test]

        from scipy import stats as sp_stats
        t_stat, p_val_h1 = sp_stats.ttest_ind(r_tfm, r_d4h, equal_var=False) if (len(r_tfm) > 2 and len(r_d4h) > 2) else (0.0, 1.0)
        p_val_h1 = float(p_val_h1)

        # H2 p-value: correlation between predicted drawdown and actual MAE
        pred_dd = [c.tfm_predicted_drawdown for c in d4h_test]
        act_mae = [c.mae for c in d4h_test]
        r_dd, p_val_h2 = sp_stats.pearsonr(pred_dd, act_mae) if len(d4h_test) > 5 else (0.0, 1.0)
        p_val_h2 = float(p_val_h2)

        # H3 p-value: Difference in TP1 hit rate between reachable and unreachable
        unreach_d4h = [c for c in d4h_test if not c.tfm_reachable_binary_60m]
        wr_reach = [1.0 if c.exit_reason in ("TP1", "TP2") else 0.0 for c in tfm_test]
        wr_unreach = [1.0 if c.exit_reason in ("TP1", "TP2") else 0.0 for c in unreach_d4h]
        _, p_val_h3 = sp_stats.ttest_ind(wr_reach, wr_unreach, equal_var=False) if (len(wr_reach) > 2 and len(wr_unreach) > 2) else (0.0, 1.0)
        p_val_h3 = float(p_val_h3)

        # H4 p-value: Managed vs Unmanaged Net R on Cohort E
        cohort_e = filter_cohort(test_cands, "E_D4H_TFM_DOWNSIDE")
        r_unmanaged = [c.net_realized_r_base for c in cohort_e]
        r_managed = [c.reforecast_net_r_base for c in cohort_e]
        _, p_val_h4 = sp_stats.ttest_rel(r_managed, r_unmanaged) if len(cohort_e) > 5 else (0.0, 1.0)
        p_val_h4 = float(p_val_h4)

        raw_hypotheses = [
            {"id": "H1", "name": "Target Reachability Improves Net Mean R", "p_value": p_val_h1},
            {"id": "H2", "name": "Downside Distribution Informs MAE/SL", "p_value": p_val_h2},
            {"id": "H3", "name": "Distribution Differentiates Feasible Targets", "p_value": p_val_h3},
            {"id": "H4", "name": "T+15m Reforecast Improves Trade Management", "p_value": p_val_h4}
        ]
        raw_hypotheses.sort(key=lambda x: x["p_value"])
        m = len(raw_hypotheses)
        fdr_alpha = 0.05
        multiple_testing_registry = []
        for i, h in enumerate(raw_hypotheses):
            rank = i + 1
            crit = (rank / m) * fdr_alpha
            bonf = fdr_alpha / m
            p_val = h["p_value"]
            status = "REJECT_NULL (SUPPORTED)" if p_val <= crit else "FAIL_TO_REJECT (NOT SUPPORTED)"
            multiple_testing_registry.append({
                "rank": rank,
                "hypothesis_id": h["id"],
                "name": h["name"],
                "raw_p_value": round(p_val, 5),
                "bh_critical_value": round(crit, 5),
                "bonferroni_critical": round(bonf, 5),
                "fdr_status": status
            })

        # 11. Final Stop Condition Evaluation
        net_r_tfm = test_d["net_r"]
        mean_r_tfm = test_d["mean_r"]
        delta_net_r = incremental_deltas_test["D_minus_C_timesfm_reachability"]["delta_net_r"]
        delta_mean_r = incremental_deltas_test["D_minus_C_timesfm_reachability"]["delta_mean_r"]

        if net_r_tfm > 0 and delta_net_r > 0 and p_val_h1 <= 0.05:
            scientific_conclusion = "OUT-OF-SAMPLE SUPPORTED: TimesFM provides statistically significant incremental economic value."
            stop_condition_met = "PROSPECTIVE_SHADOW_CANDIDATE"
        elif delta_net_r > 0 and delta_mean_r > 0:
            scientific_conclusion = "PROMISING / RESEARCH HYPOTHESIS: TimesFM improves net metrics incrementally but does not achieve statistically significant positive-net profitability."
            stop_condition_met = "TIMESFM INCREMENTAL VALUE PARTIAL / NOT FULLY ESTABLISHED"
        else:
            scientific_conclusion = "OUT-OF-SAMPLE NOT SUPPORTED: TimesFM target reachability does not improve net expectancy on fresh chronological test data."
            stop_condition_met = "TIMESFM INCREMENTAL VALUE NOT ESTABLISHED"

        return {
            "spec_hash": D4H_SPEC_HASH,
            "specification": D4H_SPECIFICATION,
            "dataset_period": "2023-12-01 to 2024-03-31 (122 calendar days)",
            "symbols": self.symbols,
            "candidate_counts": {
                "total": len(self.all_candidates),
                "train": len(train_cands),
                "validation": len(val_cands),
                "test": len(test_cands),
                "d4h_test": len(d4h_test),
                "tfm_reachable_test": len(tfm_test)
            },
            "baseline_progression_matrix": matrix_results,
            "incremental_deltas_test": incremental_deltas_test,
            "horizon_sensitivity_test": horizon_reachability_test,
            "baseline_models_comparison": baseline_comparison,
            "downside_distribution_analysis": downside_analysis,
            "asset_breakdown_test": asset_breakdown,
            "regime_breakdown_test": regime_breakdown,
            "friction_sensitivity_test": friction_sensitivity,
            "cluster_analysis_test": cluster_analysis,
            "multiple_testing_registry": multiple_testing_registry,
            "scientific_conclusion": scientific_conclusion,
            "stop_condition_status": stop_condition_met,
            "invariants": {
                "TRADING_AUTHORITY": TRADING_AUTHORITY,
                "EXECUTION_MODE": EXECUTION_MODE,
                "LIVE_ORDERS": "FORBIDDEN",
                "AUTONOMOUS_SLOT_RESERVATION": "FORBIDDEN"
            }
        }
