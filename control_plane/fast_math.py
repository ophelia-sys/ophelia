"""Fast Mathematical Kernel Dispatcher for Ophelia.

Provides unified interface for high-performance deterministic market mathematics.
Dispatches directly to the compiled Rust kernel (ophelia_math) when available,
with a mathematically identical Python fallback for development and zero-downtime rollback.
"""
from __future__ import annotations

import math
from typing import List, Tuple, Optional, Any, Dict
import numpy as np

_RUST_AVAILABLE = False
try:
    import ophelia_math
    _RUST_AVAILABLE = True
except ImportError:
    ophelia_math = None


def is_rust_accelerated() -> bool:
    """Return True if the native compiled Rust ophelia_math extension is active."""
    return _RUST_AVAILABLE


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Causal ATR series calculated on confirmed closed candles."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_atr(highs, lows, closes, period)
        except Exception:
            pass

    n = len(closes)
    if n < 2 or period == 0 or len(highs) != n or len(lows) != n:
        return [0.0] * n
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    atr = [0.0] * n
    if n < period:
        mean_tr = sum(tr) / n
        return [mean_tr] * n
    first_sum = sum(tr[:period])
    initial_atr = first_sum / period
    atr[period - 1] = initial_atr
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    for i in range(period - 1):
        atr[i] = initial_atr
    return atr


def calculate_ema(closes: List[float], period: int = 9) -> List[float]:
    """Causal EMA series with SMA seed."""
    if not closes or period <= 0:
        return []
    n = len(closes)
    if n < period:
        return [float(closes[i]) for i in range(n)]
    out = [0.0] * n
    k = 2.0 / (period + 1.0)
    sma = sum(closes[:period]) / period
    for i in range(period - 1):
        out[i] = sma
    out[period - 1] = sma
    for i in range(period, n):
        out[i] = (closes[i] * k) + (out[i - 1] * (1.0 - k))
    return out


def calculate_rvol(volumes: List[float], period: int = 20) -> float:
    """Causal RVOL of latest candle compared to rolling baseline."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return float(ophelia_math.calculate_rvol(volumes, period))
        except Exception:
            pass

    n = len(volumes)
    if n < period + 1 or period == 0:
        return 1.0
    baseline = np.mean(volumes[-period - 1 : -1])
    if baseline <= 1e-9:
        return 1.0
    return round(float(volumes[-1] / baseline), 2)


def calculate_cvd_series(
    volumes: List[float],
    taker_buys: List[float],
    opens: List[float],
    closes: List[float]
) -> List[float]:
    """Causal CVD series."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_cvd_series(volumes, taker_buys, opens, closes)
        except Exception:
            pass

    cvd = 0.0
    series = []
    n = len(volumes)
    for i in range(n):
        vol = float(volumes[i] if i < len(volumes) else 0.0)
        tb = float(taker_buys[i] if i < len(taker_buys) else 0.0)
        if tb > 0.0:
            ts = max(0.0, vol - tb)
            delta = tb - ts
        else:
            c = closes[i] if i < len(closes) else 0.0
            o = opens[i] if i < len(opens) else 0.0
            delta = vol if c >= o else -vol
        cvd += delta
        series.append(cvd)
    return series


def calculate_vwap_series(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float]
) -> List[float]:
    """Causal VWAP series."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_vwap_series(highs, lows, closes, volumes)
        except Exception:
            pass

    n = len(closes)
    cum_tp_vol = 0.0
    cum_vol = 0.0
    result = []
    for i in range(n):
        h = highs[i]
        l = lows[i]
        c = closes[i]
        v = volumes[i] if i < len(volumes) else 0.0
        tp = (h + l + c) / 3.0
        cum_tp_vol += tp * v
        cum_vol += v
        vwap = (cum_tp_vol / cum_vol) if cum_vol > 1e-9 else c
        result.append(vwap)
    return result


def detect_swings(
    highs: List[float],
    lows: List[float],
    lookback: int = 5
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Causal swing detection."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.detect_swings(highs, lows, lookback)
        except Exception:
            pass

    swing_highs = []
    swing_lows = []
    n = len(highs)
    if n < lookback * 2 + 1 or len(lows) != n or lookback == 0:
        return swing_highs, swing_lows

    for i in range(lookback, n - lookback):
        is_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and highs[j] >= highs[i]:
                is_high = False
                break
        if is_high:
            swing_highs.push((i, highs[i])) if hasattr(swing_highs, 'push') else swing_highs.append((i, highs[i]))

        is_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and lows[j] <= lows[i]:
                is_low = False
                break
        if is_low:
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def detect_fvg(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    threshold_pct: float = 0.001
) -> List[Tuple[int, str, float, float, float]]:
    """Causal FVG detection."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.detect_fvg(highs, lows, closes, threshold_pct)
        except Exception:
            pass

    fvgs = []
    n = len(closes)
    for i in range(2, n):
        px = closes[i]
        if px <= 0:
            continue
        if lows[i] > highs[i - 2]:
            gap = lows[i] - highs[i - 2]
            size_pct = gap / px
            if size_pct >= threshold_pct:
                fvgs.append((i, "BULLISH_FVG", highs[i - 2], lows[i], size_pct))
        elif highs[i] < lows[i - 2]:
            gap = lows[i - 2] - highs[i]
            size_pct = gap / px
            if size_pct >= threshold_pct:
                fvgs.append((i, "BEARISH_FVG", highs[i], lows[i - 2], size_pct))
    return fvgs


def calculate_structural_stops(
    direction: str,
    entry_price: float,
    swing_level: float,
    atr: float,
    buffer_mult: float = 0.5,
    min_dist_pct: float = 0.003,
    max_dist_pct: float = 0.04
) -> Tuple[float, float, str]:
    """Causal structural stop derivation."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_structural_stops(
                direction, entry_price, swing_level, atr, buffer_mult, min_dist_pct, max_dist_pct
            )
        except Exception:
            pass

    if entry_price <= 0.0:
        return 0.0, 0.0, "INVALID_ENTRY"

    buffer = atr * buffer_mult
    if direction == "LONG":
        base = swing_level if (0.0 < swing_level < entry_price) else (entry_price - atr * 1.5)
        raw_sl = base - buffer
        reason = "STRUCTURAL_SWING_LOW_BUFFERED"
    else:
        base = swing_level if (swing_level > entry_price) else (entry_price + atr * 1.5)
        raw_sl = base + buffer
        reason = "STRUCTURAL_SWING_HIGH_BUFFERED"

    min_dist = entry_price * min_dist_pct
    max_dist = entry_price * max_dist_pct

    if direction == "LONG":
        dist = max(min_dist, min(max_dist, entry_price - raw_sl))
        clamped_sl = entry_price - dist
    else:
        dist = max(min_dist, min(max_dist, raw_sl - entry_price))
        clamped_sl = entry_price + dist

    dist_pct = round(abs(entry_price - clamped_sl) / entry_price * 100.0, 2)
    return clamped_sl, dist_pct, reason


def calculate_structural_targets(
    direction: str,
    entry_price: float,
    sl_price: float,
    rr_targets: Optional[List[float]] = None
) -> List[Tuple[float, float, float]]:
    """Causal structural target derivation."""
    targets = rr_targets or [1.5, 2.5, 4.0]
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_structural_targets(direction, entry_price, sl_price, targets)
        except Exception:
            pass

    risk = abs(entry_price - sl_price)
    if entry_price <= 0.0 or risk <= 0.0:
        return []

    res = []
    for rr in targets:
        tp = (entry_price + risk * rr) if direction == "LONG" else (entry_price - risk * rr)
        dist_pct = round(abs(tp - entry_price) / entry_price * 100.0, 2)
        res.append((tp, dist_pct, rr))
    return res


def calculate_position_sizing(
    equity_usdt: float,
    risk_pct: float,
    entry_price: float,
    sl_price: float,
    max_leverage: float = 20.0
) -> Tuple[float, float, float, float]:
    """Calculate position size: (quantity, notional, margin, effective_leverage)."""
    if _RUST_AVAILABLE and ophelia_math is not None:
        try:
            return ophelia_math.calculate_position_sizing(equity_usdt, risk_pct, entry_price, sl_price, max_leverage)
        except Exception:
            pass

    if equity_usdt <= 0.0 or entry_price <= 0.0 or sl_price <= 0.0 or entry_price == sl_price:
        return 0.0, 0.0, 0.0, 0.0

    risk_usdt = equity_usdt * (risk_pct / 100.0)
    sl_pct = abs(entry_price - sl_price) / entry_price
    if sl_pct <= 0.0:
        return 0.0, 0.0, 0.0, 0.0

    notional = min(risk_usdt / sl_pct, equity_usdt * max_leverage)
    quantity = notional / entry_price
    effective_leverage = notional / equity_usdt
    margin = notional / max(1.0, effective_leverage)

    return round(quantity, 4), round(notional, 2), round(margin, 2), round(effective_leverage, 1)
