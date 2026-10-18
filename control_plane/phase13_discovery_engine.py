"""Ophelia Phase 13: Alpha Discovery Reset & Structural Stop-Room Research Engine.

Layer: control_plane/phase13_discovery_engine.py
Contract:
- Authoritative execution of Phase 13: Alpha Discovery Reset & Structural Stop-Room Research.
- Absolute Safety Invariants:
    TRADING_AUTHORITY = FALSE
    EXECUTION_MODE = SHADOW
    LIVE_ORDERS = FORBIDDEN
    AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN
- Research Scope:
    Discovers where, when, and under what conditions Binance market microstructure
    contains repeatable forward relationships surviving chronological OOS and verified BingX costs.
    Investigates structural invalidation hierarchy: ENTRY TIMEFRAME != STOP TIMEFRAME.
    Investigates "Stop Hit -> Thesis Resumption" study (Classes A through F).
    Audits empirical stop-distance regimes and minimum viable breathing room.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("ophelia.phase13_discovery")

# Absolute Safety Invariants
TRADING_AUTHORITY = False
EXECUTION_MODE = "SHADOW"
LIVE_ORDERS_FORBIDDEN = True
AUTONOMOUS_SLOT_RESERVATION_FORBIDDEN = True

# Chronological Partitions (UTC ms) - 12 Months 2023
TS_JAN_01_2023 = int(datetime.datetime(2023, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_JUL_31_2023 = int(datetime.datetime(2023, 7, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_AUG_01_2023_END = int(datetime.datetime(2023, 8, 1, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_AUG_02_2023 = int(datetime.datetime(2023, 8, 2, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_OCT_14_2023 = int(datetime.datetime(2023, 10, 14, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_OCT_15_2023_END = int(datetime.datetime(2023, 10, 15, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_OCT_16_2023 = int(datetime.datetime(2023, 10, 16, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
TS_DEC_31_2023 = int(datetime.datetime(2023, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)

# Verified BingX Friction Regimes (from Phase 12 Forensic Audit)
# Maker = 0.020% (2.0 bps), Taker = 0.050% (5.0 bps)
FRICTION_ZERO = 0.00000        # 0.0 bps (Gross baseline)
FRICTION_FEE_ONLY = 0.00070    # 7.0 bps (Maker 2.0 bps + Taker 5.0 bps round-trip)
FRICTION_FEE_SLIP = 0.00091    # 9.1 bps (7.0 bps fee + 2.1 bps empirical slippage)
FRICTION_CONSERVATIVE = 0.00141 # 14.1 bps (10.0 bps taker fee + 4.1 bps slippage)

# Stop Distance Regimes (Buckets)
# Rationale: Added ("SUB_02", 0.0000, 0.0020) at index 0 so that the empirical regime mapping
# partitions [0.0, 1.0] exhaustively. Previously, distances < 20 bps were mapped in classify_stop_regime
# but missing from STOP_REGIMES enumeration, causing silent omission from regime-level aggregations.
STOP_REGIMES = [
    ("SUB_02", 0.0000, 0.0020),
    ("TIGHT_02_03", 0.0020, 0.0030),
    ("MOD_03_05", 0.0030, 0.0050),
    ("BALANCED_05_075", 0.0050, 0.0075),
    ("ROOM_075_10", 0.0075, 0.0100),
    ("WIDE_10_15", 0.0100, 0.0150),
    ("VERY_WIDE_GT15", 0.0150, 1.0000),
]

# ==============================================================================
# PHASE 13 TIMESTAMP CONVENTION & SEMANTICS AUDIT
# ==============================================================================
# 1. 'timestamp' / 'timestamp_ms':
#    Represents the bar OPEN timestamp (UTC milliseconds).
#    A 5m bar with timestamp_ms = 1672531200000 opens at 00:00:00.000 UTC.
#
# 2. 'decision_timestamp_ms' / 'ts_close':
#    Represents the bar CLOSE timestamp (UTC milliseconds), calculated strictly as:
#        decision_timestamp_ms = timestamp_ms + (5 * 60 * 1000)
#    This is the exact timestamp at which the 5m interval is complete, the bar's
#    close is known, features are causal, and the signal decision becomes knowable.
#
# 3. 'dt_utc':
#    ISO 8601 string representation of the decision timestamp (candle close),
#    e.g. "2023-01-01 00:05:00+00:00".
#
# 4. Chronological Split Assignment:
#    Evaluated on 'decision_timestamp_ms' (NOT candle open). This guarantees that
#    decisions occurring at the exact embargo boundary are assigned to EMBARGO,
#    preventing forward leakage into TRAIN.
#
# 5. Forward Excursion & Outcome Evaluation:
#    1m forward bars are sliced starting at exactly 'ts_close' ('decision_timestamp_ms').
#    Minute 0 of the forward trajectory corresponds to [decision_timestamp_ms, decision_timestamp_ms + 60s).
#    No future data prior to decision_timestamp_ms is ever accessed.
#
# 6. Higher-Timeframe Feature Availability:
#    HTF bars are available ONLY after their completion timestamp:
#        available_15m_ts = ts_15m_open + 15m
#        available_1h_ts = ts_1h_open + 60m
#        available_4h_ts = ts_4h_open + 240m
#    Joined via backward merge_asof on: decision_timestamp_ms >= available_ts.
#
# 7. F-03 Order Flow, CVD & Session VWAP Correctness:
#    - Strict 5m flow aggregation requiring all constituent 1m bars to have valid finite flow.
#    - Causal 1h rolling CVD acceleration with explicit statuses ('AVAILABLE', 'MISSING_FLOW',
#      'INSUFFICIENT_HISTORY', 'ZERO_VARIANCE'). Never substitutes neutral zero for missing CVD.
#    - Volume-weighted causal session VWAP dispersion: variance = cumsum(V*P^2)/cumsum(V) - VWAP^2.
#    - CVD & VWAP signal families strictly gated on valid data status and finite dispersion.
# ==============================================================================

# Forward Evaluation Horizons (minutes)
FORWARD_HORIZONS = [1, 3, 5, 10, 15, 30, 60, 120]


def assign_phase13_split(ts: int) -> str:
    """Assigns timestamp to Phase 13 chronological partition with 24h purge embargos."""
    if TS_JAN_01_2023 <= ts <= TS_JUL_31_2023:
        return "TRAIN"
    elif TS_JUL_31_2023 < ts <= TS_AUG_01_2023_END:
        return "EMBARGO_1"
    elif TS_AUG_02_2023 <= ts <= TS_OCT_14_2023:
        return "VALIDATION"
    elif TS_OCT_14_2023 < ts <= TS_OCT_15_2023_END:
        return "EMBARGO_2"
    elif TS_OCT_16_2023 <= ts <= TS_DEC_31_2023:
        return "TEST"
    return "OUT_OF_BOUNDS"


def classify_stop_regime(sl_distance_pct: float) -> str:
    """Maps stop distance percentage to empirical regime bucket."""
    for name, low, high in STOP_REGIMES:
        if low <= sl_distance_pct < high:
            return name
    if sl_distance_pct < 0.0020:
        return "SUB_02"
    return "VERY_WIDE_GT15"


@dataclass(slots=True)
class Phase13Event:
    """Broad Market Microstructure Event Record."""
    event_id: str
    symbol: str
    timestamp_ms: int
    dt_utc: str
    split: str
    event_class: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    atr_5m: float
    atr_15m: float
    atr_1h: float
    volume_5m: float
    rvol_5m: float
    cvd_zscore: float
    vwap_deviation_sigma: float
    htf_trend_4h: str
    htf_aligned: bool
    volatility_regime: str
    cvd_data_status: str = "AVAILABLE"
    decision_timestamp_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ForwardOutcome:
    """Forward trajectory outcome across 8 evaluation horizons."""
    event_id: str
    horizon_min: int
    return_pct: float
    directional_return_pct: float
    mfe_pct: float
    mae_pct: float
    mfe_mae_ratio: float
    time_to_mfe_min: int
    time_to_mae_min: int
    reached_plus_1atr: bool
    reached_minus_1atr: bool
    time_to_plus_1atr_min: Optional[int]
    time_to_minus_1atr_min: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StopRoomEvaluation:
    """Detailed structural stop evaluation & thesis-resumption classification."""
    event_id: str
    symbol: str
    direction: str
    split: str
    stop_model: str  # "STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"
    entry_price: float
    sl_price: float
    tp1_price: float
    sl_distance_price: float
    sl_distance_pct: float
    sl_distance_atr_5m: float
    sl_distance_atr_15m: float
    sl_distance_atr_1h: float
    stop_regime: str
    rr: float

    # Outcome Classification
    resumption_class: str  # "CLASS_A", "CLASS_B", "CLASS_C", "CLASS_D", "CLASS_E", "CLASS_F"
    sl_hit: bool
    tp1_hit: bool
    time_to_sl_min: Optional[int]
    time_to_tp1_min: Optional[int]
    exit_price: float
    exit_reason: str

    # Adverse Excursion Metrics
    mae_pct: float
    mfe_pct: float
    mae_to_sl_ratio: float
    mae_to_atr_ratio: float

    # Realized Return & Economics across 4 Scenarios
    gross_realized_r: float
    friction_r_fee_only: float
    friction_r_fee_slip: float
    friction_r_conservative: float

    net_r_zero: float
    net_r_fee_only: float
    net_r_fee_slip: float
    net_r_conservative: float

    # Standardized Notional PnL ($10,000 notional)
    gross_pnl_usd: float
    net_pnl_usd_fee_only: float
    net_pnl_usd_fee_slip: float
    net_pnl_usd_conservative: float

    # Extended Excursion & Ambiguity Metrics (Defaults for backward compatibility)
    full_window_mae_pct: float = 0.0
    full_window_mfe_pct: float = 0.0
    post_exit_mfe_pct: float = 0.0
    post_exit_mae_pct: float = 0.0
    same_candle_ambiguity: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResumptionResult(tuple):
    """Result tuple for thesis-resumption classification.

    Subclasses tuple for 100% backward compatibility with 9-element unpacking:
        res_class, sl_hit, tp1_hit, t_sl, t_tp, exit_p, exit_reason, mae, mfe = result

    Exposes explicit attributes separating realized-trade metrics from full-horizon excursions:
        .realized_mae / .mae: Adverse excursion strictly until trade exit
        .realized_mfe / .mfe: Favorable excursion strictly until trade exit
        .full_window_mae: Adverse excursion across entire observation window
        .full_window_mfe: Favorable excursion across entire observation window
        .post_exit_mae: Adverse excursion after trade exit
        .post_exit_mfe: Favorable excursion after trade exit
        .same_candle_ambiguity: Boolean indicating whether SL and TP1 were touched in same 1m candle
    """
    def __new__(
        cls,
        resumption_class: str,
        sl_hit: bool,
        tp1_hit: bool,
        time_to_sl: Optional[int],
        time_to_tp1: Optional[int],
        exit_price: float,
        exit_reason: str,
        mae: float,
        mfe: float,
        full_window_mae: float = 0.0,
        full_window_mfe: float = 0.0,
        post_exit_mae: float = 0.0,
        post_exit_mfe: float = 0.0,
        same_candle_ambiguity: bool = False,
    ):
        instance = super().__new__(
            cls,
            (resumption_class, sl_hit, tp1_hit, time_to_sl, time_to_tp1, exit_price, exit_reason, mae, mfe)
        )
        instance.resumption_class = resumption_class
        instance.sl_hit = sl_hit
        instance.tp1_hit = tp1_hit
        instance.time_to_sl = time_to_sl
        instance.time_to_tp1 = time_to_tp1
        instance.exit_price = exit_price
        instance.exit_reason = exit_reason
        instance.mae = mae
        instance.realized_mae = mae
        instance.mfe = mfe
        instance.realized_mfe = mfe
        instance.full_window_mae = full_window_mae
        instance.full_window_mfe = full_window_mfe
        instance.post_exit_mae = post_exit_mae
        instance.post_exit_mfe = post_exit_mfe
        instance.same_candle_ambiguity = same_candle_ambiguity
        return instance


def classify_thesis_resumption(
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    future_1m_bars: List[Dict[str, float]]
) -> ResumptionResult:
    """Evaluates causal forward 1m path for thesis resumption and first-passage exit.

    Deterministic First-Passage Semantics:
    1. If TP1 is reached strictly before the stop:
       - Trade exits at TP1 (CLASS_C, exit_reason="TP1").
       - Realized MAE/MFE are computed strictly up to the exit candle.
       - Any subsequent stop touch or adverse excursion after exit cannot alter the realized trade outcome.
    2. If the stop is reached strictly before TP1:
       - Trade exits at the stop (exit_price=sl).
       - If price subsequently reaches TP1 within the observation window: CLASS_B (Premature Stop-Out / Resumed).
       - If price never reaches TP1: CLASS_A (True Invalidation).
       - Realized MAE/MFE are computed strictly up to the stop exit.
    3. If both barriers are touched in the same 1-minute candle:
       - Conservative stop-first policy applies: trade is assumed stopped out at sl.
       - same_candle_ambiguity flag is set to True.
       - If price reaches TP1 in a strictly later candle (minute > stop_candle): CLASS_B (SL_RESUMED).
       - Otherwise: CLASS_A (SL).
    4. If neither barrier is touched:
       - Trade held until observation horizon expires (CLASS_D / CLASS_E).
       - Realized MAE/MFE cover all available bars.
    """
    if not future_1m_bars:
        return ResumptionResult(
            resumption_class="CLASS_F",
            sl_hit=False,
            tp1_hit=False,
            time_to_sl=None,
            time_to_tp1=None,
            exit_price=entry,
            exit_reason="NO_DATA",
            mae=0.0,
            mfe=0.0,
            full_window_mae=0.0,
            full_window_mfe=0.0,
            post_exit_mae=0.0,
            post_exit_mfe=0.0,
            same_candle_ambiguity=False,
        )

    is_long = (direction == "LONG")
    risk_pct = abs(entry - sl) / max(1e-6, entry)

    # Full window series
    all_highs = [float(b["high"]) for b in future_1m_bars]
    all_lows = [float(b["low"]) for b in future_1m_bars]
    closes = [float(b["close"]) for b in future_1m_bars]

    if is_long:
        full_window_mfe = max(0.0, (max(all_highs) - entry) / entry)
        full_window_mae = max(0.0, (entry - min(all_lows)) / entry)
    else:
        full_window_mfe = max(0.0, (entry - min(all_lows)) / entry)
        full_window_mae = max(0.0, (max(all_highs) - entry) / entry)

    first_sl_bar: Optional[int] = None
    first_tp1_bar: Optional[int] = None

    for minute_idx, b in enumerate(future_1m_bars):
        h, l = float(b["high"]), float(b["low"])
        candle_num = minute_idx + 1

        candle_touches_sl = (l <= sl) if is_long else (h >= sl)
        candle_touches_tp = (h >= tp1) if is_long else (l <= tp1)

        if candle_touches_sl and first_sl_bar is None:
            first_sl_bar = candle_num
        if candle_touches_tp and first_tp1_bar is None:
            first_tp1_bar = candle_num

    same_candle_ambiguity = (
        first_sl_bar is not None
        and first_tp1_bar is not None
        and first_sl_bar == first_tp1_bar
    )

    # Determine first-passage classification and actual trade exit
    if first_tp1_bar is not None and (first_sl_bar is None or first_tp1_bar < first_sl_bar):
        # Case 1: TP1 reached strictly before SL -> Clean Winner (CLASS_C)
        resumption_class = "CLASS_C"
        exit_price = tp1
        exit_reason = "TP1"
        sl_hit = False
        tp1_hit = True
        time_to_sl = None
        time_to_tp1 = first_tp1_bar
        t_exit = first_tp1_bar

    elif first_sl_bar is not None:
        # Case 2: Stop reached first, or both barriers touched on same candle (conservative stop-first)
        sl_hit = True
        time_to_sl = first_sl_bar
        exit_price = sl
        t_exit = first_sl_bar

        # Check if TP1 was reached strictly after the stop exit (thesis resumption)
        resumed_tp1_bar: Optional[int] = None
        for m_idx in range(first_sl_bar, len(future_1m_bars)):
            b = future_1m_bars[m_idx]
            h, l = float(b["high"]), float(b["low"])
            touches_tp = (h >= tp1) if is_long else (l <= tp1)
            if touches_tp:
                resumed_tp1_bar = m_idx + 1
                break

        if resumed_tp1_bar is not None:
            resumption_class = "CLASS_B"
            exit_reason = "SL_RESUMED"
            tp1_hit = True
            time_to_tp1 = resumed_tp1_bar
        else:
            resumption_class = "CLASS_A"
            exit_reason = "SL"
            tp1_hit = False
            time_to_tp1 = None

    else:
        # Case 3: Neither barrier reached within observation horizon
        sl_hit = False
        tp1_hit = False
        time_to_sl = None
        time_to_tp1 = None
        exit_price = closes[-1]
        t_exit = len(future_1m_bars)

        # Realized MAE for the full hold
        if full_window_mae > 0.75 * risk_pct:
            resumption_class = "CLASS_E"
            exit_reason = "STRUCTURAL_DRIFT"
        else:
            resumption_class = "CLASS_D"
            exit_reason = "CHOP_FLAT"

    # Compute realized MAE and MFE strictly up to t_exit
    realized_bars = future_1m_bars[:t_exit]
    r_highs = [float(b["high"]) for b in realized_bars]
    r_lows = [float(b["low"]) for b in realized_bars]

    if is_long:
        realized_mfe = max(0.0, (max(r_highs) - entry) / entry)
        realized_mae = max(0.0, (entry - min(r_lows)) / entry)
    else:
        realized_mfe = max(0.0, (entry - min(r_lows)) / entry)
        realized_mae = max(0.0, (max(r_highs) - entry) / entry)

    # Post-exit excursions (strictly from t_exit onward)
    post_bars = future_1m_bars[t_exit:]
    if post_bars:
        p_highs = [float(b["high"]) for b in post_bars]
        p_lows = [float(b["low"]) for b in post_bars]
        if is_long:
            post_exit_mfe = max(0.0, (max(p_highs) - entry) / entry)
            post_exit_mae = max(0.0, (entry - min(p_lows)) / entry)
        else:
            post_exit_mfe = max(0.0, (entry - min(p_lows)) / entry)
            post_exit_mae = max(0.0, (max(p_highs) - entry) / entry)
    else:
        post_exit_mfe = 0.0
        post_exit_mae = 0.0

    return ResumptionResult(
        resumption_class=resumption_class,
        sl_hit=sl_hit,
        tp1_hit=tp1_hit,
        time_to_sl=time_to_sl,
        time_to_tp1=time_to_tp1,
        exit_price=exit_price,
        exit_reason=exit_reason,
        mae=realized_mae,
        mfe=realized_mfe,
        full_window_mae=full_window_mae,
        full_window_mfe=full_window_mfe,
        post_exit_mae=post_exit_mae,
        post_exit_mfe=post_exit_mfe,
        same_candle_ambiguity=same_candle_ambiguity,
    )


def compute_vwap(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """Computes daily rolling session VWAP and volume-weighted standard deviation causally.

    Formulation & Output Contract:
    1. Session Anchoring & Provenance:
       - Anchored strictly at 00:00:00 UTC of each calendar day.
       - If 'quote_volume' is present and valid, cumulative session VWAP is computed as
         cumulative(quote_volume) / cumulative(volume), which is exact transaction VWAP.
       - If 'quote_volume' is unavailable or incomplete, representative-price turnover
         cumulative(close * volume) / cumulative(volume) is computed as an approximation.
    2. Session Gap Invalidation:
       - If an unaccounted-for data gap or invalid bar occurs within a UTC session,
         session VWAP and dispersion are marked invalid (NaN) for the remainder of that
         UTC session because cumulative turnover can no longer be reconstructed.
       - The calculation resets cleanly at 00:00 UTC of the subsequent day.
    3. Numerically Stable Dispersion:
       - Exact transaction-level price variance cannot be reconstructed from aggregate OHLCV totals alone.
         Dispersion is defined as between-bar representative-price volume-weighted standard deviation.
       - Uses numerically stable weighted Welford accumulation, avoiding catastrophic cancellation
         from E[P^2] - E[P]^2.
       - Single-bar dispersion (N=1) is undefined (NaN).
       - Constant prices across multiple bars (N >= 2) produce exact zero variance (0.0).
       - No arbitrary epsilon clamping is applied, preserving small valid dispersions on low-priced instruments.
    """
    if "volume" not in df.columns or "close" not in df.columns or len(df) == 0:
        empty = pd.Series(np.nan, index=df.index, dtype=float)
        return empty, empty

    s_vwap = pd.Series(np.nan, index=df.index, dtype=float)
    s_std = pd.Series(np.nan, index=df.index, dtype=float)

    if isinstance(df.index, pd.DatetimeIndex):
        groups = df.groupby(df.index.floor("1D"))
    else:
        groups = [(None, df)]

    for _, group in groups:
        n = len(group)
        if n == 0:
            continue
        g_idx = group.index
        vol = group["volume"].astype(float).values
        close = group["close"].astype(float).values

        # Determine quote turnover provenance
        has_qv = "quote_volume" in group.columns and group["quote_volume"].notna().all()
        if has_qv:
            turnover = group["quote_volume"].astype(float).values
        else:
            turnover = close * vol

        # Validity mask
        is_valid = (vol > 0) & np.isfinite(vol) & (close > 0) & np.isfinite(close)
        if has_qv:
            is_valid = is_valid & (turnover > 0) & np.isfinite(turnover)
        if "is_valid_interval" in group.columns:
            is_valid = is_valid & group["is_valid_interval"].astype(bool).values

        # Anchored session VWAP invalidation across data gaps
        has_gap = np.logical_not(is_valid)
        has_gap_cum = np.maximum.accumulate(has_gap)

        cum_turnover = np.cumsum(turnover)
        cum_vol = np.cumsum(vol)

        v_out = np.full(n, np.nan, dtype=float)
        valid_vwap_mask = (cum_vol > 0) & (~has_gap_cum)
        v_out[valid_vwap_mask] = cum_turnover[valid_vwap_mask] / cum_vol[valid_vwap_mask]
        s_vwap.loc[g_idx] = v_out

        # Weighted Welford accumulation for between-bar representative-price dispersion
        std_out = np.full(n, np.nan, dtype=float)
        W = 0.0
        mean = 0.0
        M2 = 0.0
        for k in range(n):
            if has_gap_cum[k]:
                break
            w_k = vol[k]
            p_k = close[k]
            if k == 0:
                W = w_k
                mean = p_k
                M2 = 0.0
                std_out[k] = np.nan
            else:
                W_prev = W
                W = W_prev + w_k
                delta = p_k - mean
                mean = mean + (w_k / W) * delta
                M2 = M2 + (w_k * W_prev / W) * (delta ** 2)
                if M2 <= 0.0 or W <= 0.0:
                    std_out[k] = 0.0
                else:
                    std_out[k] = np.sqrt(M2 / W)
        s_std.loc[g_idx] = std_out

    return s_vwap, s_std


def compute_cvd(df_5m: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """Computes causal rolling CVD net imbalance z-score and explicit data status.

    Semantic & Methodological Specification:
    - Statistic: 1-hour rolling net signed order-flow imbalance z-score:
        CVD_1h = sum(delta_v over trailing 12 5m bars)
        cvd_zscore = (CVD_1h - mean_24h) / std_24h
      Note: While retained under the legacy event label 'CVD_ACCELERATION' for serialized
      schema compatibility, this statistic is mathematically a rolling standardized
      one-hour net order-flow imbalance (first difference / cumulative volume delta),
      not a second-order rate of acceleration.
    - Windows & Warm-up:
      - 1-hour window: exactly 12 5m bars (min_periods=12).
      - 24-hour baseline: trailing 288 5m bars, requiring at least 24 valid 1h CVD observations (min_periods=24).
      - The current 1h observation participates in its own 288-bar trailing baseline.
    - Explicit Status Precedence:
      1. MISSING_FLOW: If any constituent 5m bar in the 12-bar window contains NaN/missing/non-finite flow.
         For early bars (i < 11), status is MISSING_FLOW unless ALL constituent bars from 0 to i have valid flow.
      2. INSUFFICIENT_HISTORY: Complete valid 12-bar flow is present, but fewer than 24 valid 1h CVD
         observations exist in the 288-bar baseline lookback.
      3. ZERO_VARIANCE: Baseline has >= 24 valid observations, but standard deviation is zero (<= 1e-12) or undefined.
      4. AVAILABLE: Valid 1h flow, valid baseline with >= 24 observations, and positive standard deviation.
    - When status != 'AVAILABLE', cvd_zscore is float NaN (never substituted with neutral 0.0).
    """
    if "delta_v" not in df_5m.columns or len(df_5m) == 0:
        return (
            pd.Series(np.nan, index=df_5m.index, dtype=float),
            pd.Series("MISSING_FLOW", index=df_5m.index, dtype=object),
        )

    n = len(df_5m)
    s_flow = df_5m["delta_v"].astype(float)
    clean_flow = s_flow.where(np.isfinite(s_flow), np.nan)
    flow_valid = clean_flow.notna()

    # Track valid consecutive prefix for early bars (i < 11)
    valid_prefix = flow_valid.astype(int).groupby((~flow_valid).cumsum()).cumsum()

    cvd_1h = clean_flow.rolling(12, min_periods=12).sum()
    valid_count = cvd_1h.rolling(288, min_periods=1).count()
    cvd_mean = cvd_1h.rolling(288, min_periods=24).mean()
    cvd_std = cvd_1h.rolling(288, min_periods=24).std()

    status = pd.Series("MISSING_FLOW", index=df_5m.index, dtype=object)

    # 1. Early bars i < 11 only qualify for INSUFFICIENT_HISTORY if all constituents 0..i are valid
    early_valid = (np.arange(n) < 11) & (valid_prefix == (np.arange(n) + 1))
    status[early_valid] = "INSUFFICIENT_HISTORY"

    # 2. Complete 12-bar window valid, but fewer than 24 1h baseline observations
    valid_1h = cvd_1h.notna()
    status[valid_1h & (valid_count < 24)] = "INSUFFICIENT_HISTORY"

    # 3. Sufficient history but zero / undefined variance
    has_history = valid_1h & (valid_count >= 24)
    zero_var = has_history & (cvd_std.isna() | (cvd_std <= 1e-12))
    status[zero_var] = "ZERO_VARIANCE"

    # 4. Available with finite z-score
    avail = has_history & (~zero_var) & cvd_mean.notna() & cvd_std.notna()
    status[avail] = "AVAILABLE"

    cvd_z = pd.Series(np.nan, index=df_5m.index, dtype=float)
    cvd_z[avail] = (cvd_1h[avail] - cvd_mean[avail]) / cvd_std[avail]
    return cvd_z, status


def compute_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> pd.Series:
    """Causal ATR using Wilder's smoothing with strict gap-handling.

    Integrity & Gap Rules:
    - If any input bar in the window is invalid/NaN, true range across the missing interval
      cannot be measured because prev_close is unknown or current bar is missing.
    - True range across an invalid interval is marked NaN.
    - Wilder's smoothing state is invalidated across data gaps: it does not carry forward
      stale ATR across missing elapsed time.
    - Contiguous valid segments require a complete warm-up of `period` consecutive bars
      (min_periods=period) before reporting a valid ATR.
    """
    if len(closes) == 0:
        return pd.Series(dtype=float, index=closes.index)

    prev_close = closes.shift(1)
    # Check consecutive timestamps if DatetimeIndex
    if isinstance(closes.index, pd.DatetimeIndex) and len(closes) > 1:
        dt_diff = closes.index.to_series().diff()
        expected_diff = closes.index.to_series().diff().median()
        is_consec = (dt_diff == expected_diff) | dt_diff.isna()
    else:
        is_consec = pd.Series(True, index=closes.index)

    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    # At bar 0, prev_close is NaN by construction; for bar > 0, missing prev_close is a data gap
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1, skipna=False)
    if len(tr) > 0 and pd.isna(tr.iloc[0]) and pd.notna(tr1.iloc[0]):
        tr.iloc[0] = tr1.iloc[0]
    tr = tr.where(is_consec, np.nan)

    # Invalidate smoothing across gaps by grouping by contiguous valid blocks
    is_gap = tr.isna()
    gap_group = is_gap.cumsum()

    # Reset Wilder's smoothing state across data gaps per contiguous block
    atr = tr.groupby(gap_group).transform(
        lambda g: g.ewm(alpha=1.0 / period, adjust=False).mean()
    )
    return atr


def compute_benjamini_hochberg(p_values: List[float], alpha: float = 0.05) -> Tuple[List[bool], List[float]]:
    """Calculates Benjamini-Hochberg FDR control.

    Returns:
        rejected (List[bool]): True if null hypothesis is rejected at FDR alpha.
        q_values (List[float]): Adjusted FDR q-values.
    """
    m = len(p_values)
    if m == 0:
        return [], []

    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]

    # Calculate q-values causally
    q_values = np.zeros(m)
    min_q = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        q = (sorted_p[i] * m) / rank
        min_q = min(min_q, q)
        q_values[i] = min_q

    # Map back to original order
    original_q = np.zeros(m)
    original_q[sorted_indices] = q_values

    # Determine rejection threshold
    rejected = [q <= alpha for q in original_q]
    return rejected, original_q.tolist()


def bootstrap_mean_ci(
    values: List[float],
    n_boot: int = 2000,
    alpha: float = 0.05,
    block_size: int = 12,
) -> Tuple[float, float, float]:
    """Dependence-aware circular block bootstrap confidence interval for overlapping outcomes.

    Methodological Specification:
    - IID row resampling underestimates standard errors when forward return horizons overlap.
    - Uses circular block bootstrap with block_size corresponding to the forward horizon
      (e.g., 12 5m bars for 60m forward outcomes), preserving chronological serial correlation.
    - If block_size <= 1, defaults to standard IID bootstrap.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = len(arr)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean_val = float(np.mean(arr))
    if n < 5 or np.all(arr == arr[0]):
        return mean_val, mean_val, mean_val

    b = max(1, min(int(block_size), n))
    k_blocks = int(np.ceil(n / b))
    ext = np.concatenate([arr, arr[:b]])
    rng = np.random.default_rng(42)

    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        starts = rng.integers(0, n, size=k_blocks)
        sample = np.concatenate([ext[s : s + b] for s in starts])[:n]
        boot_means[i] = np.mean(sample)

    ci_low = float(np.percentile(boot_means, 100 * (alpha / 2)))
    ci_high = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return mean_val, ci_low, ci_high


def resample_phase13_bars(df_1m: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Resample 1m data to complete 5m, 15m, 1h, and 4h OHLCV bars.

    Causality & Data Integrity Rules:
    - Requires DatetimeIndex with zero duplicates, agreeing with 'timestamp' column.
    - Rejects non-finite required market data (NaN, Inf), negative prices/volume, and high < low.
    - Rejects off-grid, sub-minute timestamps from constituent intervals.
    - An interval is valid only if ALL constituent 1m bars form the exact expected
      timestamp grid {T_open + k*60_000 for k in 0..M-1}.
      (5 for 5m, 15 for 15m, 60 for 1h, 240 for 4h).
    - Incomplete, shifted, or off-grid intervals are dropped. No interpolation or gap-filling.
    - If order-flow columns (delta_v, aggressive_buy_volume, aggressive_sell_volume)
      are present, they are aggregated only if all constituent 1m rows have valid flow.
      If any constituent minute is NaN, the aggregated flow is set to np.nan.
      If absent from df_1m, columns are initialized as np.nan.
    """
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in df_1m.columns]
    if missing:
        raise ValueError(f"Phase 13 requires source columns {missing}; refusing to infer missing market data")

    # Reject non-finite market data
    vals = df_1m[required].to_numpy(dtype=float)
    if not np.isfinite(vals).all():
        raise ValueError("Phase 13 source contains non-finite required market data (NaN or Inf)")
    if (df_1m["open"] <= 0).any() or (df_1m["high"] <= 0).any() or (df_1m["low"] <= 0).any() or (df_1m["close"] <= 0).any():
        raise ValueError("Phase 13 source prices must be strictly positive")
    if (df_1m["high"] < df_1m["low"]).any():
        raise ValueError("Phase 13 source high price cannot be lower than low price")
    if (df_1m["volume"] < 0).any():
        raise ValueError("Phase 13 source volume cannot be negative")

    # Timestamp and DatetimeIndex validation
    if isinstance(df_1m.index, pd.DatetimeIndex):
        epoch = pd.Timestamp("1970-01-01", tz="UTC") if df_1m.index.tz is not None else pd.Timestamp("1970-01-01")
        dt_ms = (df_1m.index - epoch) // pd.Timedelta(milliseconds=1)
        ts_col = df_1m["timestamp"].to_numpy(dtype=np.int64)
        if not np.array_equal(dt_ms.to_numpy(), ts_col):
            raise ValueError("Phase 13 source index dt and timestamp column disagree")
        if df_1m.index.has_duplicates or df_1m["timestamp"].duplicated().any():
            raise ValueError("Phase 13 source has duplicate 1m timestamps; de-duplicate and audit upstream")
        df = df_1m.copy()
    else:
        if "timestamp" in df_1m.columns:
            if df_1m["timestamp"].duplicated().any():
                raise ValueError("Phase 13 source has duplicate 1m timestamps; de-duplicate and audit upstream")
            df = df_1m.copy()
            df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("dt")
        else:
            raise ValueError("Phase 13 resampling requires a DatetimeIndex or timestamp column")

    df.index.name = "dt"
    df = df.sort_index()

    def _resample_strict_interval(rule: str, expected_minutes: int, include_volume: bool = True) -> pd.DataFrame:
        agg = {
            "timestamp": "first",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
        if include_volume:
            agg["volume"] = "sum"

        start_bucket = df.index.min().floor(rule)
        end_bucket = df.index.max().floor(rule)
        full_grid = pd.date_range(start_bucket, end_bucket, freq=rule, tz=df.index.tz)
        full_grid.name = "dt"

        bucket_starts = df.index.floor(rule)
        rem = (df.index - bucket_starts) % pd.Timedelta(minutes=1)
        offsets = (df.index - bucket_starts) // pd.Timedelta(minutes=1)
        # Row is on-grid iff exactly at minute boundary and within interval range
        on_grid = (rem == pd.Timedelta(0)) & (offsets >= 0) & (offsets < expected_minutes)

        s_valid = pd.Series(on_grid.astype(int), index=df.index)
        s_offset = pd.Series(offsets, index=df.index)

        gtot = s_valid.groupby(bucket_starts).count()
        gval = s_valid.groupby(bucket_starts).sum()
        gunq = s_offset.where(s_valid == 1).groupby(bucket_starts).nunique()
        gmin = s_offset.where(s_valid == 1).groupby(bucket_starts).min()
        gmax = s_offset.where(s_valid == 1).groupby(bucket_starts).max()

        is_valid_bucket = (
            (gtot == expected_minutes) &
            (gval == expected_minutes) &
            (gunq == expected_minutes) &
            (gmin == 0) &
            (gmax == expected_minutes - 1)
        )

        resampled = df.resample(rule, label="left", closed="left").agg(agg)
        resampled = resampled.reindex(full_grid)
        resampled.index.name = "dt"
        valid_mask = is_valid_bucket.reindex(full_grid, fill_value=False)

        # Ensure exact epoch ms timestamp for all grid points
        if df.index.tz is not None:
            epoch = pd.Timestamp("1970-01-01", tz="UTC")
            resampled["timestamp"] = ((full_grid - epoch) // pd.Timedelta(milliseconds=1)).astype(np.int64)
        else:
            epoch = pd.Timestamp("1970-01-01")
            resampled["timestamp"] = ((full_grid - epoch) // pd.Timedelta(milliseconds=1)).astype(np.int64)

        # Incomplete intervals must remain identifiable as invalid; never fabricated OHLCV
        invalid_mask = ~valid_mask
        resampled.loc[invalid_mask, ["open", "high", "low", "close"]] = np.nan
        if include_volume:
            resampled.loc[invalid_mask, "volume"] = np.nan

        # Quote volume aggregation if present in source
        if "quote_volume" in df.columns:
            clean_qv = df["quote_volume"].where(np.isfinite(df["quote_volume"]), np.nan)
            qv_res = clean_qv.resample(rule, label="left", closed="left").sum(min_count=expected_minutes)
            resampled["quote_volume"] = qv_res.reindex(full_grid)
            resampled.loc[invalid_mask, "quote_volume"] = np.nan
        elif include_volume:
            resampled["quote_volume"] = np.nan

        # Flow aggregation: require all constituent minutes in interval to have valid finite flow
        if include_volume:
            for flow_col in ("delta_v", "aggressive_buy_volume", "aggressive_sell_volume", "taker_buy_volume"):
                if flow_col in df.columns:
                    clean_flow = df[flow_col].where(np.isfinite(df[flow_col]), np.nan)
                    flow_res = clean_flow.resample(rule, label="left", closed="left").sum(min_count=expected_minutes)
                    resampled[flow_col] = flow_res.reindex(full_grid)
                    resampled.loc[invalid_mask, flow_col] = np.nan
                else:
                    resampled[flow_col] = np.nan

        resampled["is_valid_interval"] = valid_mask
        return resampled

    df_5m = _resample_strict_interval("5min", 5, include_volume=True)
    df_15m = _resample_strict_interval("15min", 15, include_volume=True)
    df_1h = _resample_strict_interval("1h", 60, include_volume=True)
    df_4h = _resample_strict_interval("4h", 240, include_volume=False)

    return df_5m, df_15m, df_1h, df_4h


def merge_completed_htf_features(
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame,
) -> pd.DataFrame:
    """Join HTF indicators only when the source candle has fully closed.

    Causality & Timing Convention:
    1. 5m signals are decided at candle close: decision_ts = dt_open + 5 minutes.
    2. 15m candle opened at T completes at available_15m_ts = T + 15 minutes.
    3. 1h candle opened at T completes at available_1h_ts = T + 1 hour.
    4. 4h candle opened at T completes at available_4h_ts = T + 4 hours.
    5. Features are joined via backward merge_asof on decision_ts >= available_ts.
    6. Freshness contract:
       A completed HTF feature remains valid for decisions occurring within its
       expected interval period [available_ts, available_ts + interval_length).
       If the next HTF candle fails to complete (due to data gaps or dropped incomplete
       intervals), decision_ts - available_ts >= interval_length, and the feature is
       marked STALE (set to np.nan). Stale features never fall back to lower timeframes.
    """
    left = df_5m.copy()
    left.index.name = "dt"
    left = left.reset_index().rename(columns={"dt": "dt_open"})
    left["decision_ts"] = left["dt_open"] + pd.Timedelta(minutes=5)
    left = left.sort_values("decision_ts")

    # 15m features
    right_15m = pd.DataFrame(index=df_15m.index)
    if len(df_15m) > 0:
        if "close" in df_15m.columns:
            right_15m["close_15m"] = df_15m["close"]
            right_15m["high_15m"] = df_15m["high"]
            right_15m["low_15m"] = df_15m["low"]
        if "atr_14" in df_15m.columns:
            right_15m["atr_15m"] = df_15m["atr_14"]
        else:
            right_15m["atr_15m"] = np.nan
        right_15m["swing_low_15m"] = df_15m["low"].rolling(8, min_periods=8).min()
        right_15m["swing_high_15m"] = df_15m["high"].rolling(8, min_periods=8).max()
    else:
        for col in ["close_15m", "high_15m", "low_15m", "atr_15m", "swing_low_15m", "swing_high_15m"]:
            right_15m[col] = pd.Series(dtype=float)
    right_15m["available_15m_ts"] = right_15m.index + pd.Timedelta(minutes=15)
    right_15m = right_15m[right_15m["close_15m"].notna()].reset_index(drop=True).sort_values("available_15m_ts")

    # 1h features
    right_1h = pd.DataFrame(index=df_1h.index)
    if len(df_1h) > 0:
        if "close" in df_1h.columns:
            right_1h["close_1h"] = df_1h["close"]
            right_1h["high_1h"] = df_1h["high"]
            right_1h["low_1h"] = df_1h["low"]
        if "atr_14" in df_1h.columns:
            right_1h["atr_1h"] = df_1h["atr_14"]
        else:
            right_1h["atr_1h"] = np.nan
        right_1h["swing_low_1h"] = df_1h["low"].rolling(6, min_periods=6).min()
        right_1h["swing_high_1h"] = df_1h["high"].rolling(6, min_periods=6).max()
    else:
        for col in ["close_1h", "high_1h", "low_1h", "atr_1h", "swing_low_1h", "swing_high_1h"]:
            right_1h[col] = pd.Series(dtype=float)
    right_1h["available_1h_ts"] = right_1h.index + pd.Timedelta(hours=1)
    right_1h = right_1h[right_1h["close_1h"].notna()].reset_index(drop=True).sort_values("available_1h_ts")

    # 4h features
    right_4h = pd.DataFrame(index=df_4h.index)
    if len(df_4h) > 0:
        if "close" in df_4h.columns:
            right_4h["close_4h"] = df_4h["close"]
            right_4h["high_4h"] = df_4h["high"]
            right_4h["low_4h"] = df_4h["low"]
        if "trend_4h" in df_4h.columns:
            right_4h["trend_4h"] = df_4h["trend_4h"]
        else:
            right_4h["trend_4h"] = np.nan
    else:
        for col in ["close_4h", "high_4h", "low_4h"]:
            right_4h[col] = pd.Series(dtype=float)
        right_4h["trend_4h"] = pd.Series(dtype=object)
    right_4h["available_4h_ts"] = right_4h.index + pd.Timedelta(hours=4)
    right_4h = right_4h[right_4h["close_4h"].notna()].reset_index(drop=True).sort_values("available_4h_ts")

    # As-of joins
    if len(right_15m) > 0:
        merged = pd.merge_asof(
            left, right_15m, left_on="decision_ts", right_on="available_15m_ts", direction="backward"
        )
    else:
        merged = left.copy()
        for col in ["close_15m", "high_15m", "low_15m", "atr_15m", "swing_low_15m", "swing_high_15m"]:
            merged[col] = np.nan
        merged["available_15m_ts"] = pd.NaT

    if len(right_1h) > 0:
        merged = pd.merge_asof(
            merged.sort_values("decision_ts"), right_1h,
            left_on="decision_ts", right_on="available_1h_ts", direction="backward"
        )
    else:
        for col in ["close_1h", "high_1h", "low_1h", "atr_1h", "swing_low_1h", "swing_high_1h"]:
            merged[col] = np.nan
        merged["available_1h_ts"] = pd.NaT

    if len(right_4h) > 0:
        merged = pd.merge_asof(
            merged.sort_values("decision_ts"), right_4h,
            left_on="decision_ts", right_on="available_4h_ts", direction="backward"
        )
    else:
        for col in ["close_4h", "high_4h", "low_4h", "trend_4h"]:
            merged[col] = np.nan
        merged["available_4h_ts"] = pd.NaT

    # Freshness contract: mark stale if gap exceeds interval
    for key, maximum_age, feature_cols in (
        ("available_15m_ts", pd.Timedelta(minutes=15), ["close_15m", "high_15m", "low_15m", "atr_15m", "swing_low_15m", "swing_high_15m"]),
        ("available_1h_ts", pd.Timedelta(hours=1), ["close_1h", "high_1h", "low_1h", "atr_1h", "swing_low_1h", "swing_high_1h"]),
        ("available_4h_ts", pd.Timedelta(hours=4), ["close_4h", "high_4h", "low_4h", "trend_4h"]),
    ):
        present_cols = [c for c in feature_cols if c in merged.columns]
        avail_ts = pd.to_datetime(merged[key])
        stale = avail_ts.isna() | ((merged["decision_ts"] - avail_ts) >= maximum_age)
        merged.loc[stale, present_cols] = np.nan

    return merged.set_index("dt_open").sort_index()


class Phase13DiscoveryEngine:
    """Core Alpha Discovery Reset & Structural Stop-Room Research Engine."""

    def __init__(self, data_path: str = "data/processed/binance_um_universe_1m_v2.parquet"):
        self.data_path = data_path
        self.events: List[Phase13Event] = []
        self.forward_outcomes: List[ForwardOutcome] = []
        self.stop_evaluations: List[StopRoomEvaluation] = []
        self.stop_diagnostics: Dict[str, Any] = {
            "included": {m: 0 for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]},
            "excluded": {
                "MISSING_SWING_DATA": {m: 0 for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]},
                "NON_FINITE_PRICE": {m: 0 for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]},
                "WRONG_SIDE_OF_ENTRY": {m: 0 for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]},
                "INADMISSIBLE_DISTANCE": {m: 0 for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]},
            }
        }

    def extract_events_for_symbol(self, symbol: str, df_1m: pd.DataFrame) -> Tuple[List[Phase13Event], List[ForwardOutcome], List[StopRoomEvaluation]]:
        """Processes a single symbol's 1m data to extract broad microstructure events,

        computes forward outcomes, and evaluates structural stop models.
        """
        logger.info("Extracting broad event universe for %s (%d 1m rows)...", symbol, len(df_1m))
        events: List[Phase13Event] = []
        outcomes: List[ForwardOutcome] = []
        evals: List[StopRoomEvaluation] = []

        # Ensure datetime index
        if not isinstance(df_1m.index, pd.DatetimeIndex):
            df_1m["dt"] = pd.to_datetime(df_1m["timestamp"], unit="ms")
            df_1m = df_1m.set_index("dt")

        df_1m.index.name = "dt"
        df_1m = df_1m.sort_index()

        # Resample only complete bars; optional order-flow columns remain explicitly unavailable.
        df_5m, df_15m, df_1h, df_4h = resample_phase13_bars(df_1m)

        # Compute indicators
        df_5m["atr_14"] = compute_atr(df_5m["high"], df_5m["low"], df_5m["close"], 14)
        df_5m["atr_50"] = compute_atr(df_5m["high"], df_5m["low"], df_5m["close"], 50)
        df_5m["vol_sma20"] = df_5m["volume"].rolling(20).mean().replace(0, 1e-6)
        df_5m["rvol"] = df_5m["volume"] / df_5m["vol_sma20"]

        # 5m VWAP & deviation
        df_5m["vwap"], df_5m["std_vwap"] = compute_vwap(df_5m)
        df_5m["vwap_zscore"] = (df_5m["close"] - df_5m["vwap"]) / df_5m["std_vwap"]

        # 5m CVD acceleration & explicit data status
        df_5m["cvd_zscore"], df_5m["cvd_status"] = compute_cvd(df_5m)

        # 15m & 1H ATR on completed HTF bars
        df_15m["atr_14"] = compute_atr(df_15m["high"], df_15m["low"], df_15m["close"], 14)
        df_1h["atr_14"] = compute_atr(df_1h["high"], df_1h["low"], df_1h["close"], 14)

        # 4H EMA Trend on completed 4H bars
        df_4h["ema20"] = df_4h["close"].ewm(span=20, adjust=False).mean()
        df_4h["ema50"] = df_4h["close"].ewm(span=50, adjust=False).mean()
        df_4h["trend_4h"] = np.where(df_4h["ema20"] > df_4h["ema50"] * 1.001, "BULL",
                            np.where(df_4h["ema20"] < df_4h["ema50"] * 0.999, "BEAR", "NEUTRAL"))

        # Join higher-timeframe values only at their completion timestamps.
        df_5m = merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)

        # Fast arrays for 1m lookups
        timestamps_1m = df_1m["timestamp"].values
        closes_1m = df_1m["close"].values
        highs_1m = df_1m["high"].values
        lows_1m = df_1m["low"].values

        n_5m = len(df_5m)
        logger.info("Iterating across %d 5m bars for %s...", n_5m, symbol)

        # Precompute swing arrays for speed (min_periods=12 prevents gap compression)
        lows_5m_rolling = df_5m["low"].rolling(12, min_periods=12).min().values
        highs_5m_rolling = df_5m["high"].rolling(12, min_periods=12).max().values
        swing_low_15m_arr = df_5m["swing_low_15m"].values
        swing_high_15m_arr = df_5m["swing_high_15m"].values
        swing_low_1h_arr = df_5m["swing_low_1h"].values
        swing_high_1h_arr = df_5m["swing_high_1h"].values

        # Rolling close-price quantile levels, not true volume-at-price value area.
        # Shift one completed 5m bar so the tested candle cannot define its own level.
        rolling_close_p30 = df_5m["close"].rolling(288, min_periods=50).quantile(0.30).shift(1).values
        rolling_close_p70 = df_5m["close"].rolling(288, min_periods=50).quantile(0.70).shift(1).values

        # Scan each 5m bar causally
        for i in range(50, n_5m - 25):  # Leave room for lookback and forward 120m
            if "is_valid_interval" in df_5m.columns and not bool(df_5m["is_valid_interval"].iloc[i]):
                continue

            ts_bar = int(df_5m["timestamp"].iloc[i])
            decision_ts_ms = ts_bar + 5 * 60 * 1000
            split = assign_phase13_split(decision_ts_ms)
            if split.startswith("EMBARGO") or split == "OUT_OF_BOUNDS":
                continue

            close_p = float(df_5m["close"].iloc[i])
            open_p = float(df_5m["open"].iloc[i])
            high_p = float(df_5m["high"].iloc[i])
            low_p = float(df_5m["low"].iloc[i])
            atr_5m = float(df_5m["atr_14"].iloc[i])
            atr_50 = float(df_5m["atr_50"].iloc[i])
            atr_15m_value = df_5m["atr_15m"].iloc[i]
            atr_1h_value = df_5m["atr_1h"].iloc[i]
            atr_15m = float(atr_15m_value) if pd.notna(atr_15m_value) and float(atr_15m_value) > 0 else float("nan")
            atr_1h = float(atr_1h_value) if pd.notna(atr_1h_value) and float(atr_1h_value) > 0 else float("nan")
            rvol = float(df_5m["rvol"].iloc[i])
            cvd_z = float(df_5m["cvd_zscore"].iloc[i])
            cvd_status = str(df_5m["cvd_status"].iloc[i])
            vwap_z = float(df_5m["vwap_zscore"].iloc[i])
            trend_value = df_5m["trend_4h"].iloc[i]
            trend_4h = str(trend_value) if pd.notna(trend_value) else "NOT_AVAILABLE"

            if atr_5m <= 0:
                continue

            vol_ratio = atr_5m / max(1e-6, atr_50)
            vol_regime = "COMPRESSED" if vol_ratio < 0.75 else ("EXPANDED" if vol_ratio > 1.25 else "NORMAL")

            # Check Event Families
            detected_events: List[Tuple[str, str]] = []  # (event_class, direction)

            # 1. Momentum Displacement (>= 1.5 ATR)
            body = close_p - open_p
            if body >= 1.5 * atr_5m:
                detected_events.append(("MOMENTUM_DISPLACEMENT", "LONG"))
            elif body <= -1.5 * atr_5m:
                detected_events.append(("MOMENTUM_DISPLACEMENT", "SHORT"))

            # 2. RVOL Expansion (RVOL >= 2.0)
            if rvol >= 2.0:
                dir_rvol = "LONG" if close_p > open_p else "SHORT"
                detected_events.append(("RVOL_EXPANSION", dir_rvol))

            # 3. CVD Acceleration (|cvd_z| >= 2.0, gated strictly on AVAILABLE status)
            if cvd_status == "AVAILABLE" and np.isfinite(cvd_z):
                if cvd_z >= 2.0:
                    detected_events.append(("CVD_ACCELERATION", "LONG"))
                elif cvd_z <= -2.0:
                    detected_events.append(("CVD_ACCELERATION", "SHORT"))

            # 4. VWAP Deviation Mean Reversion (|vwap_z| >= 1.5, gated on finite dispersion)
            if np.isfinite(vwap_z):
                if vwap_z <= -1.5:
                    detected_events.append(("VWAP_DEVIATION", "LONG"))
                elif vwap_z >= 1.5:
                    detected_events.append(("VWAP_DEVIATION", "SHORT"))

            # 5. VWAP Reclaim (gated on finite prior & current VWAP, consecutive 5m timestamps, and valid intervals)
            is_prev_valid = bool(df_5m["is_valid_interval"].iloc[i - 1]) if "is_valid_interval" in df_5m.columns else True
            is_consec_time = (df_5m.index[i] - df_5m.index[i - 1]) == pd.Timedelta(minutes=5)
            prev_close = float(df_5m["close"].iloc[i - 1])
            prev_vwap = float(df_5m["vwap"].iloc[i - 1])
            cur_vwap = float(df_5m["vwap"].iloc[i])

            if i > 0 and is_prev_valid and is_consec_time and np.isfinite(prev_close) and np.isfinite(prev_vwap) and np.isfinite(cur_vwap):
                if prev_close < prev_vwap and close_p > cur_vwap:
                    detected_events.append(("VWAP_RECLAIM", "LONG"))
                elif prev_close > prev_vwap and close_p < cur_vwap:
                    detected_events.append(("VWAP_RECLAIM", "SHORT"))

            # 6. Liquidity Sweep SFP (15m swing breach + reclaim)
            prior_15m_low = swing_low_15m_arr[i - 1]
            prior_15m_high = swing_high_15m_arr[i - 1]
            if not np.isnan(prior_15m_low) and low_p < prior_15m_low * 0.999 and close_p > prior_15m_low:
                detected_events.append(("LIQUIDITY_SWEEP_SFP", "LONG"))
            elif not np.isnan(prior_15m_high) and high_p > prior_15m_high * 1.001 and close_p < prior_15m_high:
                detected_events.append(("LIQUIDITY_SWEEP_SFP", "SHORT"))

            # 7. Value Area Boundary Rejection
            val = rolling_close_p30[i]
            vah = rolling_close_p70[i]
            if not np.isnan(val) and low_p <= val and close_p > val:
                detected_events.append(("VALUE_AREA_BOUNDARY", "LONG"))
            elif not np.isnan(vah) and high_p >= vah and close_p < vah:
                detected_events.append(("VALUE_AREA_BOUNDARY", "SHORT"))

            # 8. Volatility Compression -> Expansion Breakout
            if vol_regime == "COMPRESSED":
                if body >= 1.2 * atr_5m:
                    detected_events.append(("RANGE_EXPANSION", "LONG"))
                elif body <= -1.2 * atr_5m:
                    detected_events.append(("RANGE_EXPANSION", "SHORT"))

            # 9. HTF Aligned Displacement Interaction
            if abs(body) >= 1.5 * atr_5m:
                if body > 0 and trend_4h == "BULL":
                    detected_events.append(("HTF_ALIGNED_DISPLACEMENT", "LONG"))
                elif body < 0 and trend_4h == "BEAR":
                    detected_events.append(("HTF_ALIGNED_DISPLACEMENT", "SHORT"))

            # 10. Order Flow x VWAP Confluence Interaction (gated on AVAILABLE flow, valid VWAP, and consecutive bars)
            if (
                cvd_status == "AVAILABLE"
                and np.isfinite(cvd_z)
                and i > 0
                and is_prev_valid
                and is_consec_time
                and np.isfinite(prev_close)
                and np.isfinite(prev_vwap)
                and np.isfinite(cur_vwap)
            ):
                if prev_close < prev_vwap and close_p > cur_vwap and cvd_z >= 1.5:
                    detected_events.append(("ORDER_FLOW_VWAP_CONFLUENCE", "LONG"))
                elif prev_close > prev_vwap and close_p < cur_vwap and cvd_z <= -1.5:
                    detected_events.append(("ORDER_FLOW_VWAP_CONFLUENCE", "SHORT"))

            if not detected_events:
                continue

            # Find matching 1m index for forward outcome extraction
            # Timestamp of 5m bar close is ts_bar + 5*60*1000
            ts_close = decision_ts_ms
            idx_1m = np.searchsorted(timestamps_1m, ts_close)

            # Do not shift a missing timestamp forward or treat gaps as continuous 1m outcomes.
            if idx_1m + 120 > len(timestamps_1m) or idx_1m >= len(timestamps_1m):
                continue
            if int(timestamps_1m[idx_1m]) != ts_close:
                continue
            future_timestamps = np.asarray(timestamps_1m[idx_1m:idx_1m + 120], dtype=np.int64)
            if len(future_timestamps) != 120 or not np.all(np.diff(future_timestamps) == 60_000):
                continue

            # Slice forward 120 1m bars
            forward_bars = [
                {"open": closes_1m[idx_1m + k - 1] if k > 0 else close_p,
                 "high": highs_1m[idx_1m + k],
                 "low": lows_1m[idx_1m + k],
                 "close": closes_1m[idx_1m + k]}
                for k in range(120)
            ]

            # Structural Invalidation Reference Levels
            # 5m swing: lowest/highest of last 12 5m bars (no fallback to ATR)
            sl_5m_long = float(lows_5m_rolling[i - 1]) if (pd.notna(lows_5m_rolling[i - 1]) and np.isfinite(lows_5m_rolling[i - 1])) else None
            sl_5m_short = float(highs_5m_rolling[i - 1]) if (pd.notna(highs_5m_rolling[i - 1]) and np.isfinite(highs_5m_rolling[i - 1])) else None

            # HTF swing stops are unavailable until enough fully closed HTF bars exist.
            sl_15m_low = swing_low_15m_arr[i - 1]
            sl_15m_high = swing_high_15m_arr[i - 1]
            sl_15m_long = float(sl_15m_low) if pd.notna(sl_15m_low) and np.isfinite(sl_15m_low) else None
            sl_15m_short = float(sl_15m_high) if pd.notna(sl_15m_high) and np.isfinite(sl_15m_high) else None

            sl_1h_low = swing_low_1h_arr[i - 1]
            sl_1h_high = swing_high_1h_arr[i - 1]
            sl_1h_long = float(sl_1h_low) if pd.notna(sl_1h_low) and np.isfinite(sl_1h_low) else None
            sl_1h_short = float(sl_1h_high) if pd.notna(sl_1h_high) and np.isfinite(sl_1h_high) else None

            # ATR envelope (requires valid positive ATR)
            sl_atr_long = close_p - 1.5 * atr_5m if (np.isfinite(atr_5m) and atr_5m > 0) else None
            sl_atr_short = close_p + 1.5 * atr_5m if (np.isfinite(atr_5m) and atr_5m > 0) else None

            dt_utc_str = str(df_5m.index[i] + pd.Timedelta(minutes=5))

            for event_class, direction in detected_events:
                ev_id = f"{symbol}_{ts_bar}_{event_class}_{direction}"
                is_long = (direction == "LONG")
                htf_aligned = (is_long and trend_4h == "BULL") or (not is_long and trend_4h == "BEAR")

                event_obj = Phase13Event(
                    event_id=ev_id,
                    symbol=symbol,
                    timestamp_ms=ts_bar,
                    dt_utc=dt_utc_str,
                    split=split,
                    event_class=event_class,
                    direction=direction,
                    entry_price=close_p,
                    atr_5m=atr_5m,
                    atr_15m=atr_15m,
                    atr_1h=atr_1h,
                    volume_5m=float(df_5m["volume"].iloc[i]),
                    rvol_5m=rvol,
                    cvd_zscore=cvd_z if cvd_status == "AVAILABLE" else float("nan"),
                    cvd_data_status=cvd_status,
                    vwap_deviation_sigma=vwap_z if np.isfinite(vwap_z) else float("nan"),
                    htf_trend_4h=trend_4h,
                    htf_aligned=htf_aligned,
                    volatility_regime=vol_regime,
                    decision_timestamp_ms=decision_ts_ms,
                )
                events.append(event_obj)

                # Compute Forward Outcomes across 8 horizons
                for hz in FORWARD_HORIZONS:
                    sub_bars = forward_bars[:hz]
                    sub_closes = [b["close"] for b in sub_bars]
                    sub_highs = [b["high"] for b in sub_bars]
                    sub_lows = [b["low"] for b in sub_bars]

                    ret = (sub_closes[-1] - close_p) / close_p
                    dir_ret = ret if is_long else -ret

                    if is_long:
                        mfe = (max(sub_highs) - close_p) / close_p
                        mae = (close_p - min(sub_lows)) / close_p
                        time_mfe = int(np.argmax(sub_highs)) + 1
                        time_mae = int(np.argmin(sub_lows)) + 1
                    else:
                        mfe = (close_p - min(sub_lows)) / close_p
                        mae = (max(sub_highs) - close_p) / close_p
                        time_mfe = int(np.argmin(sub_lows)) + 1
                        time_mae = int(np.argmax(sub_highs)) + 1

                    mae = max(0.0, mae)
                    mfe = max(0.0, mfe)
                    mfe_mae_r = mfe / max(1e-6, mae)

                    # Time to +/- 1 ATR
                    atr_pct = atr_5m / close_p
                    hit_plus = False
                    hit_minus = False
                    t_plus: Optional[int] = None
                    t_minus: Optional[int] = None

                    for idx_b, b in enumerate(sub_bars):
                        bh, bl = b["high"], b["low"]
                        if is_long:
                            if not hit_plus and (bh - close_p) / close_p >= atr_pct:
                                hit_plus = True
                                t_plus = idx_b + 1
                            if not hit_minus and (close_p - bl) / close_p >= atr_pct:
                                hit_minus = True
                                t_minus = idx_b + 1
                        else:
                            if not hit_plus and (close_p - bl) / close_p >= atr_pct:
                                hit_plus = True
                                t_plus = idx_b + 1
                            if not hit_minus and (bh - close_p) / close_p >= atr_pct:
                                hit_minus = True
                                t_minus = idx_b + 1

                    outcomes.append(ForwardOutcome(
                        event_id=ev_id,
                        horizon_min=hz,
                        return_pct=ret,
                        directional_return_pct=dir_ret,
                        mfe_pct=mfe,
                        mae_pct=mae,
                        mfe_mae_ratio=mfe_mae_r,
                        time_to_mfe_min=time_mfe,
                        time_to_mae_min=time_mae,
                        reached_plus_1atr=hit_plus,
                        reached_minus_1atr=hit_minus,
                        time_to_plus_1atr_min=t_plus,
                        time_to_minus_1atr_min=t_minus,
                    ))

                # Structural Stop Models
                stop_candidates = [
                    ("STOP_5M_SWING", sl_5m_long if is_long else sl_5m_short),
                    ("STOP_15M_SWING", sl_15m_long if is_long else sl_15m_short),
                    ("STOP_1H_SWING", sl_1h_long if is_long else sl_1h_short),
                    ("STOP_ATR_ENVELOPE", sl_atr_long if is_long else sl_atr_short),
                ]

                for stop_model_name, sl_price in stop_candidates:
                    # 1. Missing swing or ATR level -> exclude evaluation
                    if sl_price is None or pd.isna(sl_price):
                        self.stop_diagnostics["excluded"]["MISSING_SWING_DATA"][stop_model_name] += 1
                        continue

                    # 2. Non-finite price
                    try:
                        sl_val = float(sl_price)
                    except (ValueError, TypeError):
                        self.stop_diagnostics["excluded"]["NON_FINITE_PRICE"][stop_model_name] += 1
                        continue

                    if not np.isfinite(sl_val):
                        self.stop_diagnostics["excluded"]["NON_FINITE_PRICE"][stop_model_name] += 1
                        continue

                    # 3. Wrong side of entry -> strictly reject without manufactured ATR replacement
                    if is_long and sl_val >= close_p:
                        self.stop_diagnostics["excluded"]["WRONG_SIDE_OF_ENTRY"][stop_model_name] += 1
                        continue
                    elif not is_long and sl_val <= close_p:
                        self.stop_diagnostics["excluded"]["WRONG_SIDE_OF_ENTRY"][stop_model_name] += 1
                        continue

                    # 4. Inadmissible distance -> exclude without artificial price clamping
                    sl_dist_price = abs(close_p - sl_val)
                    sl_dist_pct = sl_dist_price / close_p
                    if sl_dist_pct < 1e-4 or not np.isfinite(sl_dist_pct):
                        self.stop_diagnostics["excluded"]["INADMISSIBLE_DISTANCE"][stop_model_name] += 1
                        continue

                    # 5. Passed all eligibility rules -> record inclusion
                    self.stop_diagnostics["included"][stop_model_name] += 1
                    sl_price = sl_val

                    tp1_price = close_p + 1.5 * sl_dist_price if is_long else close_p - 1.5 * sl_dist_price
                    stop_regime = classify_stop_regime(sl_dist_pct)

                    res = classify_thesis_resumption(
                        direction=direction,
                        entry=close_p,
                        sl=sl_price,
                        tp1=tp1_price,
                        future_1m_bars=forward_bars
                    )
                    res_class, sl_hit, tp1_hit, t_sl, t_tp, exit_p, exit_reason, mae_eval, mfe_eval = res

                    # Realized Gross R
                    if is_long:
                        gross_r = (exit_p - close_p) / sl_dist_price
                        gross_pnl_pct = (exit_p - close_p) / close_p
                    else:
                        gross_r = (close_p - exit_p) / sl_dist_price
                        gross_pnl_pct = (close_p - exit_p) / close_p

                    # Friction in R scaling law: Friction_R = friction_rate / stop_distance_%
                    fric_r_fee = FRICTION_FEE_ONLY / sl_dist_pct
                    fric_r_slip = FRICTION_FEE_SLIP / sl_dist_pct
                    fric_r_cons = FRICTION_CONSERVATIVE / sl_dist_pct

                    net_r_zero = gross_r
                    net_r_fee = gross_r - fric_r_fee
                    net_r_slip = gross_r - fric_r_slip
                    net_r_cons = gross_r - fric_r_cons

                    # Standardized Notional PnL ($10,000 position)
                    notional = 10000.0
                    gross_usd = notional * gross_pnl_pct
                    net_usd_fee = gross_usd - (notional * FRICTION_FEE_ONLY)
                    net_usd_slip = gross_usd - (notional * FRICTION_FEE_SLIP)
                    net_usd_cons = gross_usd - (notional * FRICTION_CONSERVATIVE)

                    mae_to_sl = mae_eval / max(1e-6, sl_dist_pct)
                    mae_to_atr = (mae_eval * close_p) / max(1e-6, atr_5m)

                    eval_obj = StopRoomEvaluation(
                        event_id=ev_id,
                        symbol=symbol,
                        direction=direction,
                        split=split,
                        stop_model=stop_model_name,
                        entry_price=close_p,
                        sl_price=sl_price,
                        tp1_price=tp1_price,
                        sl_distance_price=sl_dist_price,
                        sl_distance_pct=sl_dist_pct,
                        sl_distance_atr_5m=sl_dist_price / max(1e-6, atr_5m),
                        sl_distance_atr_15m=(sl_dist_price / atr_15m) if np.isfinite(atr_15m) and atr_15m > 0 else float("nan"),
                        sl_distance_atr_1h=(sl_dist_price / atr_1h) if np.isfinite(atr_1h) and atr_1h > 0 else float("nan"),
                        stop_regime=stop_regime,
                        rr=1.5,
                        resumption_class=res_class,
                        sl_hit=sl_hit,
                        tp1_hit=tp1_hit,
                        time_to_sl_min=t_sl,
                        time_to_tp1_min=t_tp,
                        exit_price=exit_p,
                        exit_reason=exit_reason,
                        mae_pct=mae_eval,
                        mfe_pct=mfe_eval,
                        mae_to_sl_ratio=mae_to_sl,
                        mae_to_atr_ratio=mae_to_atr,
                        gross_realized_r=gross_r,
                        friction_r_fee_only=fric_r_fee,
                        friction_r_fee_slip=fric_r_slip,
                        friction_r_conservative=fric_r_cons,
                        net_r_zero=net_r_zero,
                        net_r_fee_only=net_r_fee,
                        net_r_fee_slip=net_r_slip,
                        net_r_conservative=net_r_cons,
                        gross_pnl_usd=gross_usd,
                        net_pnl_usd_fee_only=net_usd_fee,
                        net_pnl_usd_fee_slip=net_usd_slip,
                        net_pnl_usd_conservative=net_usd_cons,
                        full_window_mae_pct=res.full_window_mae,
                        full_window_mfe_pct=res.full_window_mfe,
                        post_exit_mfe_pct=res.post_exit_mfe,
                        post_exit_mae_pct=res.post_exit_mae,
                        same_candle_ambiguity=res.same_candle_ambiguity,
                    )
                    evals.append(eval_obj)

        logger.info("Symbol %s completed: %d events, %d outcomes, %d stop evaluations.",
                    symbol, len(events), len(outcomes), len(evals))
        return events, outcomes, evals


def run_alpha_discovery(
    parquet_path: str = "data/processed/binance_um_universe_1m_v2.parquet",
    symbols: Optional[List[str]] = None,
    output_dir: str = "data",
) -> Dict[str, Any]:
    """Executes the complete Phase 13 Alpha Discovery Reset & Stop-Room Research."""
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    engine = Phase13DiscoveryEngine(data_path=parquet_path)
    all_events: List[Phase13Event] = []
    all_outcomes: List[ForwardOutcome] = []
    all_evals: List[StopRoomEvaluation] = []

    ts_start = TS_JAN_01_2023
    ts_end = TS_DEC_31_2023

    for sym in symbols:
        logger.info("Loading 1m data for %s from %s...", sym, parquet_path)
        filters = [("symbol", "=", sym), ("timestamp", ">=", ts_start), ("timestamp", "<=", ts_end)]
        cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "delta_v", "aggressive_buy_volume", "aggressive_sell_volume"]
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(parquet_path, columns=cols, filters=filters)
            df_sym = table.to_pandas()
        except Exception as e:
            logger.error("Failed to read parquet for %s: %s", sym, e)
            continue

        evs, outs, evals = engine.extract_events_for_symbol(sym, df_sym)
        all_events.extend(evs)
        all_outcomes.extend(outs)
        all_evals.extend(evals)

    logger.info("Total extracted: %d events, %d outcomes, %d stop evaluations across %d symbols.",
                len(all_events), len(all_outcomes), len(all_evals), len(symbols))

    # Convert to DataFrames for rigorous statistical aggregation
    df_evs = pd.DataFrame([e.to_dict() for e in all_events])
    df_outs = pd.DataFrame([o.to_dict() for o in all_outcomes])
    df_evals = pd.DataFrame([ev.to_dict() for ev in all_evals])

    # Save parquets
    os.makedirs(output_dir, exist_ok=True)
    events_path = os.path.join(output_dir, "phase13_events.parquet")
    outcomes_path = os.path.join(output_dir, "phase13_forward_outcomes.parquet")
    df_evs.to_parquet(events_path, index=False)
    df_outs.to_parquet(outcomes_path, index=False)
    logger.info("Saved events to %s and outcomes to %s", events_path, outcomes_path)

    # 1. Statistical Hypothesis Testing across Event Classes
    # Evaluate 4 Core Questions:
    # A. Directional Edge: Win rate, t-test on 60m directional return
    # B. Magnitude Edge: Mean MFE vs Mean MAE
    # C. Timing Edge: Time to MFE vs Time to MAE
    # D. Stop Room / Path Edge: MAE distribution of Winners vs Losers
    hypothesis_results: List[Dict[str, Any]] = []

    # Filter to 60m outcomes merged with event metadata
    df_60m = df_outs[df_outs["horizon_min"] == 60].merge(df_evs, on="event_id")

    unique_classes = df_evs["event_class"].unique()
    for ev_cls in sorted(unique_classes):
        sub = df_60m[df_60m["event_class"] == ev_cls]
        n_total = len(sub)
        if n_total < 30:
            continue

        sub_train = sub[sub["split"] == "TRAIN"]
        sub_val = sub[sub["split"] == "VALIDATION"]
        sub_test = sub[sub["split"] == "TEST"]

        n_train = len(sub_train)
        n_val = len(sub_val)
        n_test = len(sub_test)

        dir_rets_all = sub["directional_return_pct"].dropna().values
        win_rate_all = float(np.mean(dir_rets_all > 0)) * 100 if len(dir_rets_all) > 0 else 0.0
        mean_dir_ret_all = float(np.mean(dir_rets_all)) * 100 if len(dir_rets_all) > 0 else 0.0

        mean_mfe = float(np.mean(sub["mfe_pct"].dropna().values)) * 100 if len(sub["mfe_pct"].dropna()) > 0 else 0.0
        mean_mae = float(np.mean(sub["mae_pct"].dropna().values)) * 100 if len(sub["mae_pct"].dropna()) > 0 else 0.0
        median_t_mfe = float(np.median(sub["time_to_mfe_min"].dropna().values)) if len(sub["time_to_mfe_min"].dropna()) > 0 else 0.0
        median_t_mae = float(np.median(sub["time_to_mae_min"].dropna().values)) if len(sub["time_to_mae_min"].dropna()) > 0 else 0.0

        # Confirmatory evaluation: strictly on held-out TEST split
        dir_rets_test = sub_test["directional_return_pct"].dropna().values
        if n_test >= 10 and len(dir_rets_test) >= 10:
            win_rate_test = float(np.mean(dir_rets_test > 0)) * 100
            mean_dir_ret_test = float(np.mean(dir_rets_test)) * 100
            t_stat_val, p_val = stats.ttest_1samp(dir_rets_test, 0.0)
            t_stat = round(float(t_stat_val), 3) if not np.isnan(t_stat_val) else 0.0
            raw_p = float(p_val) if not np.isnan(p_val) else 1.0
            # Dependence-aware circular block bootstrap on test split (block_size=12 for 60m horizon)
            _, test_ci_low, test_ci_high = bootstrap_mean_ci(list(dir_rets_test * 100.0), block_size=12)
            test_status = "EVALUATED"
        else:
            win_rate_test = float(np.mean(dir_rets_test > 0)) * 100 if len(dir_rets_test) > 0 else None
            mean_dir_ret_test = float(np.mean(dir_rets_test)) * 100 if len(dir_rets_test) > 0 else None
            t_stat = None
            raw_p = None
            test_ci_low = None
            test_ci_high = None
            test_status = "INCONCLUSIVE_INSUFFICIENT_TEST_SAMPLE"

        hypothesis_results.append({
            "event_class": ev_cls,
            "n_total": n_total,
            "n_train": n_train,
            "n_val": n_val,
            "n_test": n_test,
            "exploratory_pooled": {
                "scope": "POOLED_ALL_SPLITS_EXPLORATORY_ONLY",
                "win_rate_pct": round(win_rate_all, 2),
                "mean_directional_return_pct": round(mean_dir_ret_all, 4),
                "mean_mfe_pct": round(mean_mfe, 4),
                "mean_mae_pct": round(mean_mae, 4),
                "mfe_mae_ratio": round(mean_mfe / max(1e-4, mean_mae), 2),
                "median_time_to_mfe_min": median_t_mfe,
                "median_time_to_mae_min": median_t_mae,
            },
            "confirmatory_test": {
                "split": "TEST",
                "status": test_status,
                "sample_size": n_test,
                "win_rate_test_pct": round(win_rate_test, 2) if win_rate_test is not None else None,
                "mean_directional_return_test_pct": round(mean_dir_ret_test, 4) if mean_dir_ret_test is not None else None,
                "ci_95_low": round(test_ci_low, 4) if test_ci_low is not None else None,
                "ci_95_high": round(test_ci_high, 4) if test_ci_high is not None else None,
                "t_stat": t_stat,
                "raw_p": raw_p,
                "bootstrap_method": "CIRCULAR_BLOCK_BOOTSTRAP_BLOCK_12",
            },
            # Flat compatibility keys
            "win_rate_all_pct": round(win_rate_all, 2),
            "win_rate_test_pct": round(win_rate_test, 2) if win_rate_test is not None else 0.0,
            "mean_directional_return_pct": round(mean_dir_ret_all, 4),
            "mean_directional_return_test_pct": round(mean_dir_ret_test, 4) if mean_dir_ret_test is not None else 0.0,
            "t_stat": t_stat if t_stat is not None else 0.0,
            "raw_p": raw_p if raw_p is not None else 1.0,
            "test_status": test_status,
        })

    # Apply Benjamini-Hochberg FDR on confirmatory TEST p-values
    evaluated_indices = [i for i, h in enumerate(hypothesis_results) if h["confirmatory_test"]["raw_p"] is not None]
    if len(evaluated_indices) > 0:
        test_p_list = [hypothesis_results[i]["confirmatory_test"]["raw_p"] for i in evaluated_indices]
        fdr_rejected, adj_q_list = compute_benjamini_hochberg(test_p_list, alpha=0.05)
        for idx_ev, orig_idx in enumerate(evaluated_indices):
            h = hypothesis_results[orig_idx]
            q_val = round(adj_q_list[idx_ev], 5)
            sig = bool(fdr_rejected[idx_ev])
            h["confirmatory_test"]["fdr_q"] = q_val
            h["confirmatory_test"]["fdr_significant"] = sig
            h["fdr_q"] = q_val
            h["fdr_significant"] = sig

    for h in hypothesis_results:
        if "fdr_q" not in h:
            h["fdr_q"] = 1.0
            h["fdr_significant"] = False
            h["confirmatory_test"]["fdr_q"] = 1.0
            h["confirmatory_test"]["fdr_significant"] = False

    # 2. Stop-Room & Thesis Resumption Analysis
    stop_room_analysis: Dict[str, Any] = {}

    # Multi-timeframe stop models comparison
    stop_models_summary: List[Dict[str, Any]] = []
    for model_name in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]:
        sub_m = df_evals[df_evals["stop_model"] == model_name]
        n_m = len(sub_m)
        if n_m == 0:
            continue

        class_counts = sub_m["resumption_class"].value_counts().to_dict()
        class_a_rate = round((class_counts.get("CLASS_A", 0) / n_m) * 100, 2)
        class_b_rate = round((class_counts.get("CLASS_B", 0) / n_m) * 100, 2)  # Premature stop-out
        class_c_rate = round((class_counts.get("CLASS_C", 0) / n_m) * 100, 2)  # Clean winner
        class_d_rate = round((class_counts.get("CLASS_D", 0) / n_m) * 100, 2)  # Flat
        class_e_rate = round((class_counts.get("CLASS_E", 0) / n_m) * 100, 2)

        median_sl_pct = float(np.median(sub_m["sl_distance_pct"].values)) * 100
        mean_sl_pct = float(np.mean(sub_m["sl_distance_pct"].values)) * 100

        # Economics across 4 scenarios
        mean_gross_r = float(np.mean(sub_m["gross_realized_r"].values))
        mean_net_r_fee = float(np.mean(sub_m["net_r_fee_only"].values))
        mean_net_r_slip = float(np.mean(sub_m["net_r_fee_slip"].values))
        mean_net_r_cons = float(np.mean(sub_m["net_r_conservative"].values))

        fric_r_fee = float(np.mean(sub_m["friction_r_fee_only"].values))
        fric_r_slip = float(np.mean(sub_m["friction_r_fee_slip"].values))

        stop_models_summary.append({
            "stop_model": model_name,
            "sample_size": n_m,
            "median_sl_pct": round(median_sl_pct, 3),
            "mean_sl_pct": round(mean_sl_pct, 3),
            "class_a_pct": class_a_rate,
            "class_b_resumed_pct": class_b_rate,
            "class_c_winner_pct": class_c_rate,
            "class_d_flat_pct": class_d_rate,
            "class_e_drift_pct": class_e_rate,
            "mean_gross_r": round(mean_gross_r, 4),
            "mean_friction_r_fee": round(fric_r_fee, 4),
            "mean_friction_r_slip": round(fric_r_slip, 4),
            "mean_net_r_zero": round(mean_gross_r, 4),
            "mean_net_r_fee_only": round(mean_net_r_fee, 4),
            "mean_net_r_fee_slip": round(mean_net_r_slip, 4),
            "mean_net_r_conservative": round(mean_net_r_cons, 4),
        })

    # Stop-distance regimes comparison (across all models)
    regimes_summary: List[Dict[str, Any]] = []
    for regime_name, low_p, high_p in STOP_REGIMES:
        sub_r = df_evals[df_evals["stop_regime"] == regime_name]
        n_r = len(sub_r)
        if n_r == 0:
            continue

        class_counts = sub_r["resumption_class"].value_counts().to_dict()
        class_b_rate = round((class_counts.get("CLASS_B", 0) / n_r) * 100, 2)
        class_c_rate = round((class_counts.get("CLASS_C", 0) / n_r) * 100, 2)

        mean_gross_r = float(np.mean(sub_r["gross_realized_r"].values))
        mean_net_r_slip = float(np.mean(sub_r["net_r_fee_slip"].values))
        fric_r_slip = float(np.mean(sub_r["friction_r_fee_slip"].values))

        # Dependence-aware circular block bootstrap CI on Net R (block_size=12)
        _, ci_low, ci_high = bootstrap_mean_ci(sub_r["net_r_fee_slip"].values, block_size=12)

        regimes_summary.append({
            "stop_regime": regime_name,
            "range_pct": f"{low_p*100:.2f}% - {high_p*100:.2f}%",
            "sample_size": n_r,
            "class_b_resumed_pct": class_b_rate,
            "class_c_winner_pct": class_c_rate,
            "mean_gross_r": round(mean_gross_r, 4),
            "mean_friction_r_slip": round(fric_r_slip, 4),
            "mean_net_r_fee_slip": round(mean_net_r_slip, 4),
            "ci_95_low": round(ci_low, 4),
            "ci_95_high": round(ci_high, 4),
        })

    # MAE of Eventual Winners vs Eventual Losers
    winners = df_evals[df_evals["resumption_class"].isin(["CLASS_C", "CLASS_B"])]
    clean_winners = df_evals[df_evals["resumption_class"] == "CLASS_C"]
    resumed_b = df_evals[df_evals["resumption_class"] == "CLASS_B"]
    losers = df_evals[df_evals["resumption_class"] == "CLASS_A"]

    mae_stats = {
        "winners_median_mae_pct": round(float(np.median(winners["mae_pct"].values)) * 100, 3) if len(winners) > 0 else 0.0,
        "winners_mean_mae_pct": round(float(np.mean(winners["mae_pct"].values)) * 100, 3) if len(winners) > 0 else 0.0,
        "winners_p75_mae_pct": round(float(np.percentile(winners["mae_pct"].values, 75)) * 100, 3) if len(winners) > 0 else 0.0,
        "winners_p90_mae_pct": round(float(np.percentile(winners["mae_pct"].values, 90)) * 100, 3) if len(winners) > 0 else 0.0,
        "clean_winners_median_mae_pct": round(float(np.median(clean_winners["mae_pct"].values)) * 100, 3) if len(clean_winners) > 0 else 0.0,
        "clean_winners_mean_mae_pct": round(float(np.mean(clean_winners["mae_pct"].values)) * 100, 3) if len(clean_winners) > 0 else 0.0,
        "resumed_b_median_full_window_mae_pct": round(float(np.median(resumed_b["full_window_mae_pct"].values)) * 100, 3) if len(resumed_b) > 0 else 0.0,
        "losers_median_mae_pct": round(float(np.median(losers["mae_pct"].values)) * 100, 3) if len(losers) > 0 else 0.0,
        "losers_mean_mae_pct": round(float(np.mean(losers["mae_pct"].values)) * 100, 3) if len(losers) > 0 else 0.0,
    }

    stop_room_analysis = {
        "stop_models_summary": stop_models_summary,
        "regimes_summary": regimes_summary,
        "mae_stats": mae_stats,
    }

    # Save stop-room JSON
    stop_room_path = os.path.join(output_dir, "phase13_stop_room.json")
    with open(stop_room_path, "w") as f:
        json.dump(stop_room_analysis, f, indent=2)
    logger.info("Saved stop-room analysis to %s", stop_room_path)

    # 3. Overall Economic Evaluation & Results Compilation
    total_events = len(all_events)
    total_outcomes = len(all_outcomes)
    total_evals = len(all_evals)

    results_summary = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_events": total_events,
        "total_forward_outcomes": total_outcomes,
        "total_stop_evaluations": total_evals,
        "symbols_evaluated": symbols,
        "date_range": "2023-01-01 to 2023-12-31 UTC",
        "partitions": {
            "train": "2023-01-01 to 2023-07-31 UTC",
            "validation": "2023-08-02 to 2023-10-14 UTC",
            "test": "2023-10-16 to 2023-12-31 UTC",
        },
        "hypothesis_results": hypothesis_results,
        "stop_models_summary": stop_models_summary,
        "regimes_summary": regimes_summary,
        "mae_stats": mae_stats,
    }

    results_path = os.path.join(output_dir, "phase13_results.json")
    with open(results_path, "w") as f:
        json.dump(results_summary, f, indent=2)
    logger.info("Saved phase13 results summary to %s", results_path)

    return results_summary
