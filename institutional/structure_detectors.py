"""
Deterministic Market Structure and Microstructure Detectors for Ophelia.
Layer: institutional/structure_detectors
Contract: Outputs analytical research detections without execution authority.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np


@dataclass(frozen=True)
class StructureDetection:
    """Standardized output container for all structure detectors."""
    detector_name: str
    detected: bool
    symbol: str
    timeframe: str
    timestamp: int
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    strength: float  # 0.0 to 1.0
    measurements: Dict[str, Any] = field(default_factory=dict)
    data_quality: str = "VALID"


def detect_fvg(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    timestamp: int,
    symbol: str,
    timeframe: str = "1m",
    min_gap_pct: float = 0.0005
) -> StructureDetection:
    """
    Detect Fair Value Gap (FVG) across 3 consecutive closed candles.
    Bullish FVG: Candle[i-2].high < Candle[i].low (gap between high of candle 1 and low of candle 3).
    Bearish FVG: Candle[i-2].low > Candle[i].high (gap between low of candle 1 and high of candle 3).
    """
    if len(highs) < 3 or len(lows) < 3:
        return StructureDetection(
            detector_name="FAIR_VALUE_GAP",
            detected=False,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="NEUTRAL",
            strength=0.0,
            measurements={"reason": "insufficient_candles"},
            data_quality="INSUFFICIENT_DATA"
        )

    c1_high, c1_low = highs[-3], lows[-3]
    c3_high, c3_low = highs[-1], lows[-1]
    ref_price = closes[-1] if closes[-1] > 0 else 1.0

    # Check Bullish FVG
    if c3_low > c1_high:
        gap_size = c3_low - c1_high
        gap_pct = gap_size / ref_price
        if gap_pct >= min_gap_pct:
            return StructureDetection(
                detector_name="FAIR_VALUE_GAP",
                detected=True,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                direction="BULLISH",
                strength=min(1.0, gap_pct * 1000),
                measurements={
                    "gap_low": round(c1_high, 4),
                    "gap_high": round(c3_low, 4),
                    "gap_size": round(gap_size, 4),
                    "gap_pct": round(gap_pct * 100, 4)
                }
            )

    # Check Bearish FVG
    if c1_low > c3_high:
        gap_size = c1_low - c3_high
        gap_pct = gap_size / ref_price
        if gap_pct >= min_gap_pct:
            return StructureDetection(
                detector_name="FAIR_VALUE_GAP",
                detected=True,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                direction="BEARISH",
                strength=min(1.0, gap_pct * 1000),
                measurements={
                    "gap_low": round(c3_high, 4),
                    "gap_high": round(c1_low, 4),
                    "gap_size": round(gap_size, 4),
                    "gap_pct": round(gap_pct * 100, 4)
                }
            )

    return StructureDetection(
        detector_name="FAIR_VALUE_GAP",
        detected=False,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction="NEUTRAL",
        strength=0.0
    )


def detect_liquidity_sweep(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    timestamp: int,
    symbol: str,
    timeframe: str = "1m",
    lookback: int = 20
) -> StructureDetection:
    """
    Detect liquidity sweeps:
    Price breaches a prior swing high/low with its wick but closes back within the prior range.
    """
    if len(highs) < lookback + 1 or len(lows) < lookback + 1 or len(closes) < lookback + 1:
        return StructureDetection(
            detector_name="LIQUIDITY_SWEEP",
            detected=False,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="NEUTRAL",
            strength=0.0,
            data_quality="INSUFFICIENT_DATA"
        )

    prior_highs = highs[-lookback - 1 : -1]
    prior_lows = lows[-lookback - 1 : -1]

    swing_high = max(prior_highs)
    swing_low = min(prior_lows)

    cur_high = highs[-1]
    cur_low = lows[-1]
    cur_close = closes[-1]

    # Bearish Sweep: Sweeps above swing high, closes below it
    if cur_high > swing_high and cur_close < swing_high:
        wick_excess = cur_high - swing_high
        strength = min(1.0, (wick_excess / cur_close) * 1000)
        return StructureDetection(
            detector_name="LIQUIDITY_SWEEP",
            detected=True,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="BEARISH",
            strength=strength,
            measurements={
                "swept_level": swing_high,
                "sweep_high": cur_high,
                "close": cur_close,
                "wick_excess": round(wick_excess, 4),
                "type": "BUY_SIDE_LIQUIDITY_SWEPT"
            }
        )

    # Bullish Sweep: Sweeps below swing low, closes above it
    if cur_low < swing_low and cur_close > swing_low:
        wick_excess = swing_low - cur_low
        strength = min(1.0, (wick_excess / cur_close) * 1000)
        return StructureDetection(
            detector_name="LIQUIDITY_SWEEP",
            detected=True,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="BULLISH",
            strength=strength,
            measurements={
                "swept_level": swing_low,
                "sweep_low": cur_low,
                "close": cur_close,
                "wick_excess": round(wick_excess, 4),
                "type": "SELL_SIDE_LIQUIDITY_SWEPT"
            }
        )

    return StructureDetection(
        detector_name="LIQUIDITY_SWEEP",
        detected=False,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction="NEUTRAL",
        strength=0.0
    )


def detect_equal_highs_lows(
    highs: List[float],
    lows: List[float],
    timestamp: int,
    symbol: str,
    timeframe: str = "1m",
    lookback: int = 30,
    tolerance_pct: float = 0.0008  # 0.08%
) -> StructureDetection:
    """
    Detect Equal Highs (EQH) or Equal Lows (EQL) representing resting liquidity pools.
    """
    if len(highs) < 10 or len(lows) < 10:
        return StructureDetection(
            detector_name="EQUAL_HIGHS_LOWS",
            detected=False,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="NEUTRAL",
            strength=0.0,
            data_quality="INSUFFICIENT_DATA"
        )

    window_h = highs[-min(len(highs), lookback):]
    window_l = lows[-min(len(lows), lookback):]

    # Find swing peaks (higher than immediate neighbors)
    peaks = []
    for i in range(1, len(window_h) - 1):
        if window_h[i] >= window_h[i - 1] and window_h[i] >= window_h[i + 1]:
            peaks.append(window_h[i])

    # Find swing valleys (lower than immediate neighbors)
    valleys = []
    for i in range(1, len(window_l) - 1):
        if window_l[i] <= window_l[i - 1] and window_l[i] <= window_l[i + 1]:
            valleys.append(window_l[i])

    # Check for EQH
    if len(peaks) >= 2:
        for i in range(len(peaks)):
            for j in range(i + 1, len(peaks)):
                p1, p2 = peaks[i], peaks[j]
                diff_pct = abs(p1 - p2) / max(p1, 1e-9)
                if diff_pct <= tolerance_pct:
                    return StructureDetection(
                        detector_name="EQUAL_HIGHS_LOWS",
                        detected=True,
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=timestamp,
                        direction="BEARISH",  # Resistance liquidity pool
                        strength=round(1.0 - (diff_pct / tolerance_pct), 3),
                        measurements={
                            "structure": "EQUAL_HIGHS",
                            "level_1": p1,
                            "level_2": p2,
                            "diff_pct": round(diff_pct * 100, 4)
                        }
                    )

    # Check for EQL
    if len(valleys) >= 2:
        for i in range(len(valleys)):
            for j in range(i + 1, len(valleys)):
                v1, v2 = valleys[i], valleys[j]
                diff_pct = abs(v1 - v2) / max(v1, 1e-9)
                if diff_pct <= tolerance_pct:
                    return StructureDetection(
                        detector_name="EQUAL_HIGHS_LOWS",
                        detected=True,
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=timestamp,
                        direction="BULLISH",  # Support liquidity pool
                        strength=round(1.0 - (diff_pct / tolerance_pct), 3),
                        measurements={
                            "structure": "EQUAL_LOWS",
                            "level_1": v1,
                            "level_2": v2,
                            "diff_pct": round(diff_pct * 100, 4)
                        }
                    )

    return StructureDetection(
        detector_name="EQUAL_HIGHS_LOWS",
        detected=False,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction="NEUTRAL",
        strength=0.0
    )


def detect_displacement(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    timestamp: int,
    symbol: str,
    timeframe: str = "1m",
    atr_lookback: int = 14,
    atr_multiplier: float = 2.0
) -> StructureDetection:
    """
    Detect displacement / impulse candles (strong momentum expanding beyond typical ATR).
    """
    if len(closes) < atr_lookback + 1:
        return StructureDetection(
            detector_name="DISPLACEMENT",
            detected=False,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="NEUTRAL",
            strength=0.0,
            data_quality="INSUFFICIENT_DATA"
        )

    # Simple ATR calculation
    tr_list = []
    for i in range(1, atr_lookback + 1):
        idx = -1 - i
        h, l, prev_c = highs[idx], lows[idx], closes[idx - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)
    atr = sum(tr_list) / len(tr_list) if tr_list else 1.0

    cur_open = opens[-1]
    cur_close = closes[-1]
    cur_high = highs[-1]
    cur_low = lows[-1]

    body = abs(cur_close - cur_open)
    candle_range = cur_high - cur_low

    is_impulse = body >= (atr * atr_multiplier)
    direction = "BULLISH" if cur_close > cur_open else ("BEARISH" if cur_close < cur_open else "NEUTRAL")

    return StructureDetection(
        detector_name="DISPLACEMENT",
        detected=is_impulse,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction=direction if is_impulse else "NEUTRAL",
        strength=min(1.0, body / (atr * 3.0)) if is_impulse else 0.0,
        measurements={
            "body": round(body, 4),
            "range": round(candle_range, 4),
            "atr": round(atr, 4),
            "body_to_atr": round(body / max(atr, 1e-9), 2),
            "is_impulse": is_impulse
        }
    )


def detect_cvd_divergence(
    prices: List[float],
    cvd_deltas: List[float],
    timestamp: int,
    symbol: str,
    timeframe: str = "1m",
    lookback: int = 10
) -> StructureDetection:
    """
    Detect divergence between price trend and cumulative volume delta trend.
    Bearish Divergence: Price makes higher high while CVD makes lower high or declines.
    Bullish Divergence: Price makes lower low while CVD makes higher low or advances.
    """
    if len(prices) < lookback or len(cvd_deltas) < lookback:
        return StructureDetection(
            detector_name="CVD_DIVERGENCE",
            detected=False,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="NEUTRAL",
            strength=0.0,
            data_quality="INSUFFICIENT_DATA"
        )

    p_recent = prices[-lookback:]
    c_recent = cvd_deltas[-lookback:]

    # Compare first half vs second half
    mid = lookback // 2
    p_half1_max = max(p_recent[:mid])
    p_half2_max = max(p_recent[mid:])
    c_half1_max = max(c_recent[:mid])
    c_half2_max = max(c_recent[mid:])

    p_half1_min = min(p_recent[:mid])
    p_half2_min = min(p_recent[mid:])
    c_half1_min = min(c_recent[:mid])
    c_half2_min = min(c_recent[mid:])

    # Regular Bearish Divergence: Higher high in price, lower high in CVD
    if p_half2_max > p_half1_max and c_half2_max < c_half1_max:
        return StructureDetection(
            detector_name="CVD_DIVERGENCE",
            detected=True,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="BEARISH",
            strength=0.75,
            measurements={
                "type": "REGULAR_BEARISH_DIVERGENCE",
                "price_delta": round(p_half2_max - p_half1_max, 4),
                "cvd_delta": round(c_half2_max - c_half1_max, 2)
            }
        )

    # Regular Bullish Divergence: Lower low in price, higher low in CVD
    if p_half2_min < p_half1_min and c_half2_min > c_half1_min:
        return StructureDetection(
            detector_name="CVD_DIVERGENCE",
            detected=True,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            direction="BULLISH",
            strength=0.75,
            measurements={
                "type": "REGULAR_BULLISH_DIVERGENCE",
                "price_delta": round(p_half2_min - p_half1_min, 4),
                "cvd_delta": round(c_half2_min - c_half1_min, 2)
            }
        )

    return StructureDetection(
        detector_name="CVD_DIVERGENCE",
        detected=False,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        direction="NEUTRAL",
        strength=0.0
    )
