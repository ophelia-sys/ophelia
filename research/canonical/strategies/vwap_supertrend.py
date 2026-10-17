"""VWAP/Supertrend active-line-cross strategy (spec §4) — DS-A acceptance anchor D2.

Two variants:
  * VwapSupertrendVendorStrategy : consumes TradingView-provided Up/Down Trend + VWAP
    columns (indicator_source=VENDOR_PROVIDED). Required for DS-A because the export
    contains no pre-window history for engine warm-up (SPEC-GAP S1).
  * VwapSupertrendEngineStrategy : computes indicators via canonical.indicators
    (ENGINE_COMPUTED); for datasets with sufficient pre-history.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseStrategy, SignalIntent, TargetSpec


def detect_active_line_crosses(
    up: np.ndarray, down: np.ndarray, vwap: np.ndarray, close: np.ndarray,
):
    """Pure §4 signal logic on indicator series. Returns (long_idx, short_idx).

    LONG : up[i-1] < vwap[i-1] and up[i] >= vwap[i] and close[i] > vwap[i]
    SHORT: down[i-1] > vwap[i-1] and down[i] <= vwap[i] and close[i] < vwap[i]
    NaN inputs suppress the bar. Inclusive-at-touch semantics (spec D8).
    """
    n = len(close)
    longs, shorts = [], []
    for i in range(1, n):
        u0, u1 = up[i - 1], up[i]
        d0, d1 = down[i - 1], down[i]
        v0, v1 = vwap[i - 1], vwap[i]
        c1 = close[i]
        if np.isfinite(u0) and np.isfinite(u1) and np.isfinite(v0) and np.isfinite(v1):
            if u0 < v0 and u1 >= v1 and c1 > v1:
                longs.append(i)
                continue
        if np.isfinite(d0) and np.isfinite(d1) and np.isfinite(v0) and np.isfinite(v1):
            if d0 > v0 and d1 <= v1 and c1 < v1:
                shorts.append(i)
    return longs, shorts


class _VwapStBase(BaseStrategy):
    stop_buffer_bps: float = 1.0
    indicator_source: str = "ENGINE_COMPUTED"

    def _series(self, candles: pd.DataFrame):
        raise NotImplementedError

    def generate(self, candles: pd.DataFrame, dataset_id: str, dataset_version: str,
                 timeframe_minutes: int):
        up, down, vwap = self._series(candles)
        close = candles["close"].to_numpy()
        opens = candles["open"].to_numpy()
        otime = candles["candle_open_time"].to_numpy().astype(np.int64)
        tf_ms = timeframe_minutes * 60_000
        longs, shorts = detect_active_line_crosses(up, down, vwap, close)
        buf = self.stop_buffer_bps * 1e-4
        intents = []
        for i in sorted(longs + shorts):
            direction = 1 if i in set(longs) else -1   # a bar cannot be both (§4 S1)
            if i + 1 >= len(candles):
                continue                                # UNFILLED_EOD handled by engine audit
            line = up[i] if direction == 1 else down[i]
            entry_ref = int(otime[i] + tf_ms)
            sid = (f"{self.symbol_default}_{timeframe_minutes}M_{dataset_version}_"
                   f"{pd.Timestamp(int(otime[i]), unit='ms').strftime('%Y%m%d_%H%M')}_"
                   f"{'LONG' if direction == 1 else 'SHORT'}")
            intents.append(SignalIntent(
                signal_id=sid,
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                symbol=self.symbol_default,
                timeframe_minutes=timeframe_minutes,
                signal_timeframe_minutes=timeframe_minutes,
                signal_candle_open_time_ms=int(otime[i]),
                signal_time_ms=int(otime[i] + tf_ms),
                entry_reference_open_time_ms=entry_ref,
                direction=direction,
                theoretical_entry_price=None,       # Model A: engine fills at next open
                stop_price=float(line * (1 - buf)) if direction == 1
                            else float(line * (1 + buf)),
                target_spec=TargetSpec(use_standard_policies=True),
                entry_model="NEXT_OPEN",
                trigger=None,
                indicator_source=self.indicator_source,
                metadata={
                    "vwap_at_signal": float(vwap[i]),
                    "supertrend_line_at_signal": float(line),
                    "signal_price": float(close[i]),
                },
            ))
        return intents

    symbol_default: str = "SOLUSDT"


class VwapSupertrendVendorStrategy(_VwapStBase):
    """Uses vendor VWAP / Up Trend / Down Trend columns (DS-A). SPEC-GAP S1."""

    strategy_id = "VWAP_SUPERTREND_ACTIVE_LINE_CROSS"
    strategy_version = "1.0.0"
    indicator_source = "VENDOR_PROVIDED"

    def __init__(self, st_factor: float = 4.0, st_length: int = 10,
                 stop_buffer_bps: float = 1.0):
        self.st_factor = st_factor
        self.st_length = st_length
        self.stop_buffer_bps = stop_buffer_bps

    def _series(self, candles: pd.DataFrame):
        need = {"vwap_vendor", "up_trend_vendor", "down_trend_vendor"}
        missing = need - set(candles.columns)
        if missing:
            raise ValueError(f"Vendor strategy requires columns {sorted(missing)} (S1)")
        return (candles["up_trend_vendor"].to_numpy(dtype=float),
                candles["down_trend_vendor"].to_numpy(dtype=float),
                candles["vwap_vendor"].to_numpy(dtype=float))


class VwapSupertrendEngineStrategy(_VwapStBase):
    """Computes VWAP + Supertrend via canonical.indicators (history-rich datasets)."""

    strategy_id = "VWAP_SUPERTREND_ACTIVE_LINE_CROSS_ENGINE"
    strategy_version = "1.0.0"
    indicator_source = "ENGINE_COMPUTED"

    def __init__(self, st_factor: float = 4.0, st_length: int = 10,
                 stop_buffer_bps: float = 1.0, warmup_bars: int = 300):
        from .. import config as cfg
        self.st_factor = st_factor
        self.st_length = st_length
        self.stop_buffer_bps = stop_buffer_bps
        self.warmup_bars = warmup_bars or cfg.WARMUP_BARS

    def _series(self, candles: pd.DataFrame):
        from ..indicators import session_vwap, supertrend
        vwap = session_vwap(candles)
        direction, active, fl, fu = supertrend(candles, self.st_length, self.st_factor)
        up = np.where(direction == 1, active, np.nan)
        down = np.where(direction == -1, active, np.nan)
        if self.warmup_bars and self.warmup_bars > 0:
            w = min(self.warmup_bars, len(candles))
            up[:w] = np.nan
            down[:w] = np.nan
        return up, down, vwap
