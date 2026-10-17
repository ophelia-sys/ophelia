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
STOP_REGIMES = [
    ("SUB_02", 0.0000, 0.0020),
    ("TIGHT_02_03", 0.0020, 0.0030),
    ("MOD_03_05", 0.0030, 0.0050),
    ("BALANCED_05_075", 0.0050, 0.0075),
    ("ROOM_075_10", 0.0075, 0.0100),
    ("WIDE_10_15", 0.0100, 0.0150),
    ("VERY_WIDE_GT15", 0.0150, 1.0000),
]

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
    """Computes daily rolling session VWAP and 1-sigma dispersion causally."""
    pv = df["close"] * df["volume"]
    cum_pv = pv.groupby(df.index.date).cumsum()
    cum_v = df["volume"].groupby(df.index.date).cumsum().replace(0, np.nan)
    vwap = cum_pv / cum_v

    # Rolling standard deviation from VWAP
    dev = (df["close"] - vwap) ** 2
    cum_dev = dev.groupby(df.index.date).cumsum()
    variance = cum_dev / cum_v
    std_vwap = np.sqrt(variance.fillna(0)).replace(0, 1e-6)
    return vwap.fillna(df["close"]), std_vwap


def compute_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> pd.Series:
    """Causal ATR using Wilder's smoothing."""
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
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


def bootstrap_mean_ci(values: List[float], n_boot: int = 2000, alpha: float = 0.05) -> Tuple[float, float, float]:
    """Bootstrap 95% confidence interval for the mean."""
    arr = np.array(values)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0
    mean_val = float(np.mean(arr))
    if len(arr) < 5 or np.all(arr == arr[0]):
        return mean_val, mean_val, mean_val

    rng = np.random.default_rng(42)
    boot_means = np.array([np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(n_boot)])
    ci_low = float(np.percentile(boot_means, 100 * (alpha / 2)))
    ci_high = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return mean_val, ci_low, ci_high


def resample_phase13_bars(df_1m: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Resample 1m data to complete 5m, 15m, 1h, and 4h OHLCV bars.

    Causality & Data Integrity Rules:
    - Requires DatetimeIndex with zero duplicates.
    - An interval is valid only if ALL constituent 1m bars are present and valid (notna).
      (5 for 5m, 15 for 15m, 60 for 1h, 240 for 4h).
    - Incomplete intervals are dropped. No interpolation or gap-filling.
    - If order-flow columns (delta_v, aggressive_buy_volume, aggressive_sell_volume)
      are present, they are aggregated only if all constituent 1m rows have valid flow.
      If any constituent minute is NaN, the aggregated flow is set to np.nan.
      If absent from df_1m, columns are initialized as np.nan.
    """
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in df_1m.columns]
    if missing:
        raise ValueError(f"Phase 13 requires source columns {missing}; refusing to infer missing market data")

    if not isinstance(df_1m.index, pd.DatetimeIndex):
        if "timestamp" in df_1m.columns:
            df = df_1m.copy()
            df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("dt")
        else:
            raise ValueError("Phase 13 resampling requires a DatetimeIndex or timestamp column")
    else:
        df = df_1m.copy()

    if df.index.has_duplicates:
        raise ValueError("Phase 13 source has duplicate 1m timestamps; de-duplicate and audit upstream")

    df.index.name = "dt"
    df = df.sort_index()
    valid_1m = df[required].notna().all(axis=1).astype("int8")

    # 5m aggregation
    agg_5m = {
        "timestamp": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    flow_columns = ("delta_v", "aggressive_buy_volume", "aggressive_sell_volume")
    for flow_col in flow_columns:
        if flow_col in df.columns:
            agg_5m[flow_col] = "sum"

    df_5m = df.resample("5min", label="left", closed="left").agg(agg_5m)
    valid_5m_count = valid_1m.resample("5min", label="left", closed="left").sum()
    df_5m = df_5m.loc[valid_5m_count[valid_5m_count == 5].index].dropna(
        subset=["timestamp", "open", "high", "low", "close", "volume"]
    ).copy()

    for flow_col in flow_columns:
        if flow_col not in df_5m.columns:
            df_5m[flow_col] = np.nan
        elif flow_col in df.columns:
            flow_count = df[flow_col].notna().astype("int8").resample("5min", label="left", closed="left").sum()
            df_5m.loc[flow_count.reindex(df_5m.index).fillna(0).astype(int) != 5, flow_col] = np.nan

    def _complete_htf(rule: str, expected_minutes: int, include_volume: bool = True) -> pd.DataFrame:
        agg = {
            "timestamp": "first",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
        if include_volume:
            agg["volume"] = "sum"
        resampled = df.resample(rule, label="left", closed="left").agg(agg)
        valid_count = valid_1m.resample(rule, label="left", closed="left").sum()
        resampled = resampled.loc[valid_count[valid_count == expected_minutes].index]
        return resampled.dropna(subset=["open", "high", "low", "close"]).copy()

    df_15m = _complete_htf("15min", 15, include_volume=True)
    df_1h = _complete_htf("1h", 60, include_volume=True)
    df_4h = _complete_htf("4h", 240, include_volume=False)

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
    right_15m = right_15m.reset_index(drop=True).sort_values("available_15m_ts")

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
    right_1h = right_1h.reset_index(drop=True).sort_values("available_1h_ts")

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
    right_4h = right_4h.reset_index(drop=True).sort_values("available_4h_ts")

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

        # 5m CVD acceleration
        if "delta_v" in df_5m.columns and df_5m["delta_v"].notna().any():
            cvd_1h = df_5m["delta_v"].rolling(12, min_periods=12).sum()
            cvd_mean = cvd_1h.rolling(288, min_periods=24).mean()
            cvd_std = cvd_1h.rolling(288, min_periods=24).std().replace(0, 1e-6)
            df_5m["cvd_zscore"] = ((cvd_1h - cvd_mean) / cvd_std).fillna(0.0)
        else:
            df_5m["cvd_zscore"] = float("nan")

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

        # Precompute swing arrays for speed
        # 5m swing high/low over 12 bars (1 hour)
        lows_5m_rolling = df_5m["low"].rolling(12).min().values
        highs_5m_rolling = df_5m["high"].rolling(12).max().values
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

            # 3. CVD Acceleration (abs(cvd_z) >= 2.0)
            if cvd_z >= 2.0:
                detected_events.append(("CVD_ACCELERATION", "LONG"))
            elif cvd_z <= -2.0:
                detected_events.append(("CVD_ACCELERATION", "SHORT"))

            # 4. VWAP Deviation Mean Reversion (|vwap_z| >= 1.5)
            if vwap_z <= -1.5:
                detected_events.append(("VWAP_DEVIATION", "LONG"))
            elif vwap_z >= 1.5:
                detected_events.append(("VWAP_DEVIATION", "SHORT"))

            # 5. VWAP Reclaim
            prev_close = float(df_5m["close"].iloc[i - 1])
            prev_vwap = float(df_5m["vwap"].iloc[i - 1])
            cur_vwap = float(df_5m["vwap"].iloc[i])
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

            # 10. Order Flow x VWAP Confluence Interaction
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
            # 5m swing: lowest/highest of last 12 5m bars
            sl_5m_long = float(lows_5m_rolling[i - 1]) if not np.isnan(lows_5m_rolling[i - 1]) else close_p - 1.5 * atr_5m
            sl_5m_short = float(highs_5m_rolling[i - 1]) if not np.isnan(highs_5m_rolling[i - 1]) else close_p + 1.5 * atr_5m

            # HTF swing stops are unavailable until enough fully closed HTF bars exist.
            sl_15m_low = swing_low_15m_arr[i - 1]
            sl_15m_high = swing_high_15m_arr[i - 1]
            sl_15m_long = float(sl_15m_low) if pd.notna(sl_15m_low) and np.isfinite(sl_15m_low) else None
            sl_15m_short = float(sl_15m_high) if pd.notna(sl_15m_high) and np.isfinite(sl_15m_high) else None

            sl_1h_low = swing_low_1h_arr[i - 1]
            sl_1h_high = swing_high_1h_arr[i - 1]
            sl_1h_long = float(sl_1h_low) if pd.notna(sl_1h_low) and np.isfinite(sl_1h_low) else None
            sl_1h_short = float(sl_1h_high) if pd.notna(sl_1h_high) and np.isfinite(sl_1h_high) else None

            # ATR envelope
            sl_atr_long = close_p - 1.5 * atr_5m
            sl_atr_short = close_p + 1.5 * atr_5m

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
                    cvd_zscore=cvd_z if np.isfinite(cvd_z) else 0.0,
                    cvd_data_status="AVAILABLE" if np.isfinite(cvd_z) else "NOT_AVAILABLE",
                    vwap_deviation_sigma=vwap_z,
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
                    # Do not substitute a lower-timeframe ATR stop for a missing HTF swing.
                    if sl_price is None or not np.isfinite(float(sl_price)):
                        continue
                    # Enforce directional sanity
                    if is_long and sl_price >= close_p:
                        sl_price = close_p - 1.0 * atr_5m
                    elif not is_long and sl_price <= close_p:
                        sl_price = close_p + 1.0 * atr_5m

                    sl_dist_price = abs(close_p - sl_price)
                    sl_dist_pct = sl_dist_price / close_p
                    if sl_dist_pct < 1e-4:
                        sl_dist_pct = 1e-4
                        sl_dist_price = close_p * sl_dist_pct
                        sl_price = close_p - sl_dist_price if is_long else close_p + sl_dist_price

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

        dir_rets_all = sub["directional_return_pct"].values
        dir_rets_test = sub_test["directional_return_pct"].values if len(sub_test) > 0 else np.array([0.0])

        win_rate_all = float(np.mean(dir_rets_all > 0)) * 100
        win_rate_test = float(np.mean(dir_rets_test > 0)) * 100 if len(sub_test) > 0 else 0.0

        mean_dir_ret = float(np.mean(dir_rets_all)) * 100
        mean_dir_ret_test = float(np.mean(dir_rets_test)) * 100 if len(sub_test) > 0 else 0.0

        # One-sample t-test against 0 directional return
        t_stat, p_val = stats.ttest_1samp(dir_rets_all, 0.0)
        p_val_clean = float(p_val) if not np.isnan(p_val) else 1.0

        mean_mfe = float(np.mean(sub["mfe_pct"].values)) * 100
        mean_mae = float(np.mean(sub["mae_pct"].values)) * 100
        median_t_mfe = float(np.median(sub["time_to_mfe_min"].values))
        median_t_mae = float(np.median(sub["time_to_mae_min"].values))

        hypothesis_results.append({
            "event_class": ev_cls,
            "n_total": n_total,
            "n_train": len(sub_train),
            "n_val": len(sub_val),
            "n_test": len(sub_test),
            "win_rate_all_pct": round(win_rate_all, 2),
            "win_rate_test_pct": round(win_rate_test, 2),
            "mean_directional_return_pct": round(mean_dir_ret, 4),
            "mean_directional_return_test_pct": round(mean_dir_ret_test, 4),
            "t_stat": round(float(t_stat), 3),
            "raw_p": p_val_clean,
            "mean_mfe_pct": round(mean_mfe, 4),
            "mean_mae_pct": round(mean_mae, 4),
            "mfe_mae_ratio": round(mean_mfe / max(1e-4, mean_mae), 2),
            "median_time_to_mfe_min": median_t_mfe,
            "median_time_to_mae_min": median_t_mae,
        })

    # Apply Benjamini-Hochberg FDR
    raw_p_list = [h["raw_p"] for h in hypothesis_results]
    fdr_rejected, adj_q_list = compute_benjamini_hochberg(raw_p_list, alpha=0.05)
    for i, h in enumerate(hypothesis_results):
        h["fdr_q"] = round(adj_q_list[i], 5)
        h["fdr_significant"] = bool(fdr_rejected[i])

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

        # Bootstrap CI on Net R
        _, ci_low, ci_high = bootstrap_mean_ci(sub_r["net_r_fee_slip"].values)

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
