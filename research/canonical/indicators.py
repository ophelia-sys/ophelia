"""Canonical indicators — the ONE implementation (spec §3).

All functions are causal: values at bar i use bars <= i only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def session_vwap(df: pd.DataFrame) -> np.ndarray:
    """Session VWAP: typical price * volume, cumsum within UTC calendar date (spec §3.1).

    Volume==0 bars are excluded from both cumsums; a session with zero total volume
    yields NaN for that session.
    """
    o_time = df["candle_open_time"].to_numpy()
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    v = df["volume"].to_numpy(dtype=float)
    tp = (h + l + c) / 3.0
    pv = tp * v
    valid = np.isfinite(v) & (v > 0)
    # per-day reset via segment boundaries:
    day_index = (o_time // 86_400_000).astype(np.int64)
    new_day = np.empty_like(day_index, dtype=bool)
    new_day[0] = True
    new_day[1:] = day_index[1:] != day_index[:-1]
    seg = np.cumsum(new_day) - 1                      # session segment id per row
    out = np.full(len(df), np.nan)
    run_pv = run_v = 0.0
    prev_seg = -1
    for i in range(len(df)):
        if seg[i] != prev_seg:
            prev_seg = seg[i]
            run_pv = 0.0
            run_v = 0.0
        if valid[i]:
            run_pv += pv[i]
            run_v += v[i]
        out[i] = run_pv / run_v if run_v > 0 else np.nan
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    tr = np.empty(len(close))
    tr[0] = high[0] - low[0]
    pc = close[:-1]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                np.abs(high[1:] - pc),
                                np.abs(low[1:] - pc)])
    return tr


def atr_rma(tr: np.ndarray, length: int) -> np.ndarray:
    """Wilder RMA ATR seeded with SMA of first `length` TRs (spec §3.2)."""
    rma = np.full(len(tr), np.nan)
    if len(tr) < length:
        return rma
    alpha = 1.0 / length
    rma[length - 1] = tr[:length].mean()
    for i in range(length, len(tr)):
        rma[i] = alpha * tr[i] + (1 - alpha) * rma[i - 1]
    return rma


def supertrend(df: pd.DataFrame, length: int = 10, factor: float = 4.0):
    """TradingView-equivalent Supertrend (spec §3.3).

    Returns (direction int8 array, active_line float array, final_lower, final_upper).
    direction +1 bullish (active line = finalLower), -1 bearish (= finalUpper).
    """
    high = df["high"].to_numpy(); low = df["low"].to_numpy(); close = df["close"].to_numpy()
    atr = atr_rma(true_range(high, low, close), length)
    hl2 = (high + low) / 2.0
    n = len(close)
    bu = hl2 + factor * atr
    bl = hl2 - factor * atr
    fu = np.full(n, np.nan); fl = np.full(n, np.nan)
    direction = np.ones(n, dtype=np.int8)
    start = None
    for i in range(n):
        if not np.isnan(bu[i]):
            fu[i] = bu[i]; fl[i] = bl[i]; direction[i] = 1
            start = i + 1
            break
    if start is None:
        return direction, np.full(n, np.nan), fl, fu
    for i in range(start, n):
        fu[i] = bu[i] if (bu[i] < fu[i-1] or close[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = bl[i] if (bl[i] > fl[i-1] or close[i-1] < fl[i-1]) else fl[i-1]
        if direction[i-1] == 1 and close[i] < fl[i]:
            direction[i] = -1
        elif direction[i-1] == -1 and close[i] > fu[i]:
            direction[i] = 1
        else:
            direction[i] = direction[i-1]
    active = np.where(direction == 1, fl, fu)
    return direction, active, fl, fu


def atr_pct(df: pd.DataFrame, length: int = 14) -> np.ndarray:
    """ATR(length)/close — used by regime buckets (§17). Causal."""
    high = df["high"].to_numpy(); low = df["low"].to_numpy(); close = df["close"].to_numpy()
    a = atr_rma(true_range(high, low, close), length)
    return a / close
