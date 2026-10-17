"""Forecast Trade Compatibility Engine.

Layer: control_plane/trade_compatibility.py
Contract:
- Authoritative multi-metric evaluation of TimesFM forecast distribution and path against structural trade geometry.
- Strictly advisory (zero order placement, zero risk mutation, zero slot reservation).
- Exposes three distinct transparent evidence dimensions:
  1. FORECAST_DIRECTION (BULLISH, BEARISH, NEUTRAL)
  2. FORECAST_DISPERSION (DISPERSION_BUCKET_UNCALIBRATED)
  3. TRADE_COMPATIBILITY (SUPPORTIVE, MIXED, UNSUPPORTIVE, NOT_AVAILABLE)
- Zero single opaque AI score. Zero uncalibrated pseudo-confidence.
- Multi-dimensional path and distribution metrics:
  - forecast_median_return, return_15m, return_30m, return_45m, return_60m
  - quantile returns (q10, q50, q90)
  - distances: entry_to_q*, SL_to_q*, TP1_to_q*
  - path slope and path direction
  - DOES NOT require q10 > SL or q90 > TP2.
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .timesfm_candidate import CandidateForecastContext, CandidateForecastResult

logger = logging.getLogger("ophelia.trade_compatibility")

COMPATIBILITY_ENGINE_VERSION = "TRADE_COMPATIBILITY_V2"


@dataclass(slots=True)
class ForecastCompatibilityResult:
    candidate_id: str
    symbol: str
    direction: str
    entry_price: float
    sl_price: float
    tp1_price: float
    tp2_price: Optional[float]

    # Three Distinct Evidence Dimensions
    forecast_direction: str          # "BULLISH", "BEARISH", "NEUTRAL"
    forecast_dispersion: str         # "DISPERSION_BUCKET_UNCALIBRATED"
    trade_compatibility: str         # "COMPATIBLE", "INCOMPATIBLE", "NEUTRAL", "NOT_AVAILABLE"
    compatibility_category: str      # "SUPPORTIVE", "MIXED", "UNSUPPORTIVE", "NOT_AVAILABLE"
    compatibility_mode: str          # "MULTI_METRIC_GEOMETRY"

    # Multi-Horizon Returns (Direction-Aligned / Signed)
    forecast_median_return: float
    forecast_return_to_15m: float
    forecast_return_to_30m: float
    forecast_return_to_45m: float
    forecast_return_to_60m: float
    forecast_median_vs_entry: float

    # Quantile Returns (Absolute price return vs entry)
    forecast_q10_return: float
    forecast_q50_return: float
    forecast_q90_return: float

    # Quantile Distances to Entry
    dist_q10_to_entry: float
    dist_q50_to_entry: float
    dist_q90_to_entry: float

    # Quantile Distances to Stop Loss
    dist_q10_to_sl: float
    dist_q50_to_sl: float
    dist_q90_to_sl: float

    # Quantile Distances to Take Profit 1
    dist_q10_to_tp1: float
    dist_q50_to_tp1: float
    dist_q90_to_tp1: float

    # Path Trajectory Geometry
    forecast_path_direction: str     # "UPWARD", "DOWNWARD", "FLAT"
    forecast_path_slope: float
    forecast_expected_range: float
    forecast_dispersion_pct: float
    forecast_vs_trade_geometry: str

    # Alignments
    forecast_directional_alignment: bool
    forecast_horizon_alignment: bool
    tail_risk_warning: bool

    # Metadata & Calibration
    model_version: str
    data_freshness: str
    compatibility_calculation_ms: float = 0.0
    calibration_status: str = "NOT CALIBRATED"
    status: str = "SHADOW"
    version: str = COMPATIBILITY_ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForecastTradeCompatibilityEngine:
    """Evaluates TimesFM forecast distribution path against structural trade setup geometry."""

    @classmethod
    def evaluate(
        cls,
        context: CandidateForecastContext,
        forecast: CandidateForecastResult
    ) -> ForecastCompatibilityResult:
        import time
        t_comp_start = time.perf_counter()
        entry = context.entry_price
        sl = context.sl_price
        tp1 = context.tp1_price
        tp2 = context.tp2_price
        direction = context.direction.upper()

        p15 = forecast.path.get("15m", entry)
        p30 = forecast.path.get("30m", entry)
        p45 = forecast.path.get("45m", entry)
        p60 = forecast.path.get("60m", entry)

        q10 = forecast.quantiles.get("q10", entry * 0.99)
        q50 = forecast.quantiles.get("q50", entry)
        q90 = forecast.quantiles.get("q90", entry * 1.01)

        # 1. Multi-Horizon Returns (Raw price change vs entry)
        raw_ret_15m = ((p15 - entry) / entry) * 100.0
        raw_ret_30m = ((p30 - entry) / entry) * 100.0
        raw_ret_45m = ((p45 - entry) / entry) * 100.0
        raw_ret_60m = ((p60 - entry) / entry) * 100.0

        # Direction-aligned returns (positive means favorable to trade)
        dir_mult = 1.0 if direction == "LONG" else -1.0
        ret_15m = round(raw_ret_15m * dir_mult, 4)
        ret_30m = round(raw_ret_30m * dir_mult, 4)
        ret_45m = round(raw_ret_45m * dir_mult, 4)
        ret_60m = round(raw_ret_60m * dir_mult, 4)

        med_vs_entry = round(q50 - entry, 4)
        med_return = round(((q50 - entry) / entry) * 100.0 * dir_mult, 4)

        # Quantile returns vs entry
        q10_ret = round(((q10 - entry) / entry) * 100.0, 4)
        q50_ret = round(((q50 - entry) / entry) * 100.0, 4)
        q90_ret = round(((q90 - entry) / entry) * 100.0, 4)

        dispersion_pct = forecast.forecast_dispersion_pct
        expected_range = round(abs(max(p15, p30, p45, p60) - min(p15, p30, p45, p60)), 4)

        # 2. Quantile Distances to Structural Levels
        dist_q10_entry = round(q10 - entry, 4)
        dist_q50_entry = round(q50 - entry, 4)
        dist_q90_entry = round(q90 - entry, 4)

        dist_q10_sl = round(q10 - sl, 4)
        dist_q50_sl = round(q50 - sl, 4)
        dist_q90_sl = round(q90 - sl, 4)

        dist_q10_tp1 = round(tp1 - q10, 4)
        dist_q50_tp1 = round(tp1 - q50, 4)
        dist_q90_tp1 = round(tp1 - q90, 4)

        # 3. Path Slope and Direction
        # Linear regression slope across path points [entry, p15, p30, p45, p60]
        path_points = np.array([entry, p15, p30, p45, p60], dtype=np.float64)
        x_steps = np.arange(5)
        slope, _ = np.polyfit(x_steps, path_points, 1)
        norm_slope = round((slope / entry) * 100.0, 4)  # % per step

        if norm_slope > 0.03:
            path_dir = "UPWARD"
        elif norm_slope < -0.03:
            path_dir = "DOWNWARD"
        else:
            path_dir = "FLAT"

        # 4. Dimension 1: FORECAST_DIRECTION
        if raw_ret_60m > 0.10:
            f_dir = "BULLISH"
        elif raw_ret_60m < -0.10:
            f_dir = "BEARISH"
        else:
            f_dir = "NEUTRAL"

        # 5. Dimension 2: FORECAST_DISPERSION
        f_disp = "DISPERSION_BUCKET_UNCALIBRATED"

        # 6. Directional and Horizon Alignment
        if direction == "LONG":
            dir_aligned = bool(norm_slope > 0.0 or raw_ret_60m > 0.0)
            horizon_aligned = bool(p30 > entry or p60 > entry)
            tail_risk = bool(q10 <= sl)  # Advisory warning only; does NOT disqualify compatibility
        else:
            dir_aligned = bool(norm_slope < 0.0 or raw_ret_60m < 0.0)
            horizon_aligned = bool(p30 < entry or p60 < entry)
            tail_risk = bool(q90 >= sl)

        # 7. Dimension 3: TRADE_COMPATIBILITY (Multi-metric classification)
        # Does NOT require q10 > sl or q50 > entry binary gate.
        # Combines slope, multi-horizon returns, and median direction.
        if forecast.data_freshness == "INSUFFICIENT_SAMPLE":
            category = "NOT_AVAILABLE"
            compatibility = "NOT_AVAILABLE"
            geom_summary = "INSUFFICIENT_DATA"
        else:
            favorable_steps = sum(1 for r in [ret_15m, ret_30m, ret_45m, ret_60m] if r > 0.0)
            avg_return = (ret_15m + ret_30m + ret_45m + ret_60m) / 4.0

            if direction == "LONG":
                is_favorable_slope = (norm_slope > 0.0)
                is_unfavorable_slope = (norm_slope < -0.08)
            else:
                is_favorable_slope = (norm_slope < 0.0)
                is_unfavorable_slope = (norm_slope > 0.08)

            if favorable_steps >= 3 and avg_return > 0.05 and is_favorable_slope:
                category = "SUPPORTIVE"
                compatibility = "COMPATIBLE"
                geom_summary = "PATH_ALIGNED_EXPANSIVE"
            elif favorable_steps <= 1 and avg_return < -0.08 and is_unfavorable_slope:
                category = "UNSUPPORTIVE"
                compatibility = "INCOMPATIBLE"
                geom_summary = "PATH_ADVERSE_REVERSAL"
            else:
                category = "MIXED"
                compatibility = "NEUTRAL"
                geom_summary = "PATH_CONSOLIDATING_OR_PULLBACK"

        return ForecastCompatibilityResult(
            candidate_id=context.candidate_id,
            symbol=context.symbol,
            direction=direction,
            entry_price=entry,
            sl_price=sl,
            tp1_price=tp1,
            tp2_price=tp2,
            forecast_direction=f_dir,
            forecast_dispersion=f_disp,
            trade_compatibility=compatibility,
            compatibility_category=category,
            compatibility_mode="MULTI_METRIC_GEOMETRY",
            forecast_median_return=med_return,
            forecast_return_to_15m=ret_15m,
            forecast_return_to_30m=ret_30m,
            forecast_return_to_45m=ret_45m,
            forecast_return_to_60m=ret_60m,
            forecast_median_vs_entry=med_vs_entry,
            forecast_q10_return=q10_ret,
            forecast_q50_return=q50_ret,
            forecast_q90_return=q90_ret,
            dist_q10_to_entry=dist_q10_entry,
            dist_q50_to_entry=dist_q50_entry,
            dist_q90_to_entry=dist_q90_entry,
            dist_q10_to_sl=dist_q10_sl,
            dist_q50_to_sl=dist_q50_sl,
            dist_q90_to_sl=dist_q90_sl,
            dist_q10_to_tp1=dist_q10_tp1,
            dist_q50_to_tp1=dist_q50_tp1,
            dist_q90_to_tp1=dist_q90_tp1,
            forecast_path_direction=path_dir,
            forecast_path_slope=norm_slope,
            forecast_expected_range=expected_range,
            forecast_dispersion_pct=dispersion_pct,
            forecast_vs_trade_geometry=geom_summary,
            forecast_directional_alignment=dir_aligned,
            forecast_horizon_alignment=horizon_aligned,
            tail_risk_warning=tail_risk,
            model_version=forecast.model_version,
            data_freshness=forecast.data_freshness,
            compatibility_calculation_ms=round((time.perf_counter() - t_comp_start) * 1000.0, 3),
            calibration_status="NOT CALIBRATED",
            status="SHADOW"
        )


def evaluate_compatibility(
    context: CandidateForecastContext,
    forecast: CandidateForecastResult
) -> ForecastCompatibilityResult:
    """Convenience helper to evaluate multi-metric forecast compatibility."""
    return ForecastTradeCompatibilityEngine.evaluate(context, forecast)
