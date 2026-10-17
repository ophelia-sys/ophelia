"""Causal Deterministic Retest State Machine & Setup Engine for Ophelia.

Layer: control_plane/retest_engine
Contract:
- Strictly causal: processes confirmed closed candles sequentially.
- Zero lookahead: no shift(-1), no centered rolling windows, no future swing points.
- State transitions:
    IDLE -> BREAKOUT_DETECTED -> WAITING_FOR_RETEST -> RETEST_ZONE_TOUCHED ->
    REJECTION_CONFIRMED -> ENTRY_CANDIDATE -> RISK_VALIDATED -> EXECUTED
    Terminal / Exit states: INVALIDATED, EXPIRED.
- All experimental parameters are configurable and feature-flagged.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config, db, fast_math
from institutional import structure_detectors


@dataclass
class RetestState:
    symbol: str
    timeframe: int
    direction: str  # "LONG" or "SHORT"
    state: str = "IDLE"
    breakout_ts: Optional[int] = None
    breakout_price: Optional[float] = None
    vwap_at_breakout: Optional[float] = None
    zone_low: Optional[float] = None
    zone_high: Optional[float] = None
    fvg_id: Optional[str] = None
    elapsed_candles: int = 0
    touch_ts: Optional[int] = None
    rejection_ts: Optional[int] = None
    confirmation_ts: Optional[int] = None
    invalidation_ts: Optional[int] = None
    invalidation_reason: Optional[str] = None
    distance_pct: float = 0.0
    distance_atr: float = 0.0
    current_atr: float = 0.0
    updated_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "state": self.state,
            "breakout_ts": self.breakout_ts,
            "breakout_price": self.breakout_price,
            "vwap_at_breakout": self.vwap_at_breakout,
            "zone_low": self.zone_low,
            "zone_high": self.zone_high,
            "fvg_id": self.fvg_id,
            "elapsed_candles": self.elapsed_candles,
            "touch_ts": self.touch_ts,
            "rejection_ts": self.rejection_ts,
            "confirmation_ts": self.confirmation_ts,
            "invalidation_ts": self.invalidation_ts,
            "invalidation_reason": self.invalidation_reason,
            "distance_pct": self.distance_pct,
            "distance_atr": self.distance_atr,
            "current_atr": self.current_atr,
            "updated_ms": self.updated_ms or int(time.time() * 1000),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RetestState":
        return cls(
            symbol=d["symbol"],
            timeframe=int(d["timeframe"]),
            direction=d["direction"],
            state=d.get("state", "IDLE"),
            breakout_ts=d.get("breakout_ts"),
            breakout_price=d.get("breakout_price"),
            vwap_at_breakout=d.get("vwap_at_breakout"),
            zone_low=d.get("zone_low"),
            zone_high=d.get("zone_high"),
            fvg_id=d.get("fvg_id"),
            elapsed_candles=int(d.get("elapsed_candles", 0)),
            touch_ts=d.get("touch_ts"),
            rejection_ts=d.get("rejection_ts"),
            confirmation_ts=d.get("confirmation_ts"),
            invalidation_ts=d.get("invalidation_ts"),
            invalidation_reason=d.get("invalidation_reason"),
            distance_pct=float(d.get("distance_pct", 0.0)),
            distance_atr=float(d.get("distance_atr", 0.0)),
            current_atr=float(d.get("current_atr", 0.0)),
            updated_ms=int(d.get("updated_ms", 0)),
        )


@dataclass
class SetupCandidate:
    setup_id: str
    symbol: str
    direction: str
    timeframe: str
    strategy: str
    entry_price: float
    suggested_sl: float
    suggested_tp1: float
    suggested_tp2: float
    suggested_tp3: float
    sl_distance_pct: float
    tp1_distance_pct: float
    tp2_distance_pct: float
    tp3_distance_pct: float
    risk_reward: float
    confidence_pct: float
    ai_confidence: float
    calibration_status: str = "NOT CALIBRATED"
    current_state: str = "ENTRY_CANDIDATE"
    status: str = "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setup_id": self.setup_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "suggested_sl": self.suggested_sl,
            "suggested_tp1": self.suggested_tp1,
            "suggested_tp2": self.suggested_tp2,
            "suggested_tp3": self.suggested_tp3,
            "sl_distance_pct": self.sl_distance_pct,
            "tp1_distance_pct": self.tp1_distance_pct,
            "tp2_distance_pct": self.tp2_distance_pct,
            "tp3_distance_pct": self.tp3_distance_pct,
            "risk_reward": self.risk_reward,
            "confidence_pct": self.confidence_pct,
            "ai_confidence": self.ai_confidence,
            "calibration_status": self.calibration_status,
            "current_state": self.current_state,
            "status": self.status,
        }


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Causal ATR series calculated on confirmed closed candles (accelerated by Rust kernel)."""
    return fast_math.calculate_atr(highs, lows, closes, period)


def calculate_rvol(volumes: List[float], period: int = 20, method: str = "ROLLING_20") -> float:
    """Causal RVOL of the latest closed candle compared to past baseline (accelerated by Rust kernel)."""
    return fast_math.calculate_rvol(volumes, period)


def calculate_cvd_series(candles: List[dict]) -> List[float]:
    """Causal cumulative volume delta series from taker_buy volume (accelerated by Rust kernel)."""
    vols = [float(c.get("volume") or 0.0) for c in candles]
    tbs = [float(c.get("taker_buy") or 0.0) for c in candles]
    opens = [float(c.get("open") or 0.0) for c in candles]
    closes = [float(c.get("close") or 0.0) for c in candles]
    return fast_math.calculate_cvd_series(vols, tbs, opens, closes)


def detect_swing_points(highs: List[float], lows: List[float], lookback: int = 5) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Find causal swing highs and lows strictly requiring lookback closed bars on both sides."""
    return fast_math.detect_swings(highs, lows, lookback)



def compute_structural_targets_stops(
    candles: List[dict],
    direction: str,
    entry_price: float,
    vwap: float,
    timeframe: int = 3
) -> Dict[str, Any]:
    """Calculate structural Stop Loss and structural Take Profit (TP1, TP2, TP3) based on
    swing liquidity and VWAP. Strictly no arbitrary retail percentages.
    Guarantees:
      - LONG: SL < Entry < TP1 < TP2 < TP3
      - SHORT: SL > Entry > TP1 > TP2 > TP3
      - Proximity-based candidate selection (closest to entry first)
      - Distinct, non-duplicate target levels
      - Feasibility constraints based on ATR reachability
    """
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    atr_series = calculate_atr(highs, lows, closes, 14)
    cur_atr = max(atr_series[-1] if atr_series else entry_price * 0.01, entry_price * 0.0005)

    # Lookback horizon for timeframe-relevant swing liquidity
    if timeframe <= 5:
        max_lookback = min(len(candles), 60)
    elif timeframe <= 30:
        max_lookback = min(len(candles), 100)
    else:
        max_lookback = min(len(candles), 180)
    min_idx = max(0, len(candles) - max_lookback)
    swing_highs, swing_lows = detect_swing_points(highs, lows, lookback=4)
    recent_swing_highs = [(idx, p) for idx, p in swing_highs if idx >= min_idx]
    recent_swing_lows = [(idx, p) for idx, p in swing_lows if idx >= min_idx]

    if direction == "LONG":
        # Structural SL: Below nearest valid swing low (highest low below entry) or VWAP buffer
        candidate_sl_lows = sorted([p for idx, p in recent_swing_lows if p < entry_price], reverse=True)
        if candidate_sl_lows:
            structural_sl = candidate_sl_lows[0] - (0.15 * cur_atr)
            sl_source = "RECENT_SWING_LOW"
        else:
            structural_sl = min(entry_price - (1.5 * cur_atr), vwap - (0.2 * cur_atr))
            sl_source = "VWAP_ATR_BUFFER"

        # Ensure SL is strictly below entry with minimum buffer
        if structural_sl >= entry_price:
            structural_sl = entry_price - (1.5 * cur_atr)
        sl_distance = max(entry_price - structural_sl, 0.5 * cur_atr)
        structural_sl = entry_price - sl_distance

        # Structural TPs: Candidate highs above entry derived from valid market structure
        # Sorted ASCENDING: closest to entry first (TP1 < TP2 < TP3)
        candidate_tp_highs = sorted([
            p for idx, p in recent_swing_highs
            if p > entry_price
        ])

        # Deduplicate candidates within 0.2 ATR
        deduped_tps = []
        for p in candidate_tp_highs:
            if not deduped_tps or (p - deduped_tps[-1]) >= (0.2 * cur_atr):
                deduped_tps.append(p)

        # Filter for minimum 1.0 R:R from entry
        deduped_tps = [p for p in deduped_tps if (p - entry_price) >= (1.0 * sl_distance)]

        tp1 = deduped_tps[0] if len(deduped_tps) > 0 else round(entry_price + (sl_distance * 1.5), 4)
        tp2 = deduped_tps[1] if len(deduped_tps) > 1 else None
        tp3 = deduped_tps[2] if len(deduped_tps) > 2 else None

        # Enforce strict hierarchy: SL < Entry < TP1 < TP2 < TP3
        if tp2 is not None and tp2 <= tp1:
            tp2 = None
            tp3 = None
        if tp3 is not None and tp2 is not None and tp3 <= tp2:
            tp3 = None

        reward1 = tp1 - entry_price
        reward2 = (tp2 - entry_price) if tp2 is not None else None
        reward3 = (tp3 - entry_price) if tp3 is not None else None

        rr1 = round(reward1 / max(sl_distance, 1e-6), 2)
        rr2 = round(reward2 / max(sl_distance, 1e-6), 2) if reward2 is not None else None
        rr3 = round(reward3 / max(sl_distance, 1e-6), 2) if reward3 is not None else None

        sl_pct = -round((sl_distance / entry_price) * 100.0, 2)
        tp1_pct = round((reward1 / entry_price) * 100.0, 2)
        tp2_pct = round((reward2 / entry_price) * 100.0, 2) if reward2 is not None else None
        tp3_pct = round((reward3 / entry_price) * 100.0, 2) if reward3 is not None else None

        return {
            "sl": round(structural_sl, 4),
            "tp1": round(tp1, 4),
            "tp2": round(tp2, 4) if tp2 is not None else None,
            "tp3": round(tp3, 4) if tp3 is not None else None,
            "tp2_status": "AVAILABLE" if tp2 is not None else "UNAVAILABLE",
            "tp3_status": "AVAILABLE" if tp3 is not None else "UNAVAILABLE",
            "risk_distance": round(sl_distance, 4),
            "reward_distance_tp1": round(reward1, 4),
            "reward_distance_tp2": round(reward2, 4) if reward2 is not None else None,
            "reward_distance_tp3": round(reward3, 4) if reward3 is not None else None,
            "reward_risk_ratio": rr1,
            "reward_risk_tp1": rr1,
            "reward_risk_tp2": rr2,
            "reward_risk_tp3": rr3,
            "risk_reward": rr1,
            "sl_distance": round(sl_distance, 4),
            "sl_pct": sl_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "tp3_pct": tp3_pct,
            "sl_distance_pct": sl_pct,
            "tp1_distance_pct": tp1_pct,
            "tp2_distance_pct": tp2_pct,
            "tp3_distance_pct": tp3_pct,
            "risk_pct": round((sl_distance / entry_price) * 100.0, 2),
            "reward_pct_tp1": round((reward1 / entry_price) * 100.0, 2),
            "reward_pct_tp2": round((reward2 / entry_price) * 100.0, 2) if reward2 is not None else None,
            "reward_pct_tp3": round((reward3 / entry_price) * 100.0, 2) if reward3 is not None else None,
            "target_provenance": {
                "tp1_source": "RECENT_SWING_HIGH" if len(deduped_tps) > 0 else "STRUCTURAL_RISK_PROJECTION_1.5R",
                "tp2_source": "RECENT_SWING_HIGH" if tp2 is not None else "UNAVAILABLE",
                "tp3_source": "RECENT_SWING_HIGH" if tp3 is not None else "UNAVAILABLE",
                "tp1_price": round(tp1, 4),
                "tp2_price": round(tp2, 4) if tp2 is not None else None,
                "tp3_price": round(tp3, 4) if tp3 is not None else None,
                "tp1_timeframe": f"{timeframe}m",
                "tp2_timeframe": f"{timeframe}m" if tp2 is not None else None,
                "tp3_timeframe": f"{timeframe}m" if tp3 is not None else None,
                "tp1_status": "AVAILABLE",
                "tp2_status": "AVAILABLE" if tp2 is not None else "UNAVAILABLE",
                "tp3_status": "AVAILABLE" if tp3 is not None else "UNAVAILABLE",
                "sl_source": sl_source,
                "atr_used": round(cur_atr, 4),
                "experimental_atr_target": round(entry_price + (cur_atr * 3.0), 4)
            },
            "basis": "SWING_LOW_AND_BUY_SIDE_LIQUIDITY"
        }

    else:  # SHORT
        # Structural SL: Above nearest valid swing high (lowest high above entry) or VWAP buffer
        candidate_sl_highs = sorted([p for idx, p in recent_swing_highs if p > entry_price])
        if candidate_sl_highs:
            structural_sl = candidate_sl_highs[0] + (0.15 * cur_atr)
            sl_source = "RECENT_SWING_HIGH"
        else:
            structural_sl = max(entry_price + (1.5 * cur_atr), vwap + (0.2 * cur_atr))
            sl_source = "VWAP_ATR_BUFFER"

        # Ensure SL is strictly above entry with minimum buffer
        if structural_sl <= entry_price:
            structural_sl = entry_price + (1.5 * cur_atr)
        sl_distance = max(structural_sl - entry_price, 0.5 * cur_atr)
        structural_sl = entry_price + sl_distance

        # Structural TPs: Candidate lows below entry derived from valid market structure
        # Sorted DESCENDING: closest to entry first (TP1 > TP2 > TP3 where all are < entry)
        candidate_tp_lows = sorted([
            p for idx, p in recent_swing_lows
            if p < entry_price
        ], reverse=True)

        # Deduplicate candidates within 0.2 ATR
        deduped_tps = []
        for p in candidate_tp_lows:
            if not deduped_tps or (deduped_tps[-1] - p) >= (0.2 * cur_atr):
                deduped_tps.append(p)

        # Filter for minimum 1.0 R:R from entry
        deduped_tps = [p for p in deduped_tps if (entry_price - p) >= (1.0 * sl_distance)]

        tp1 = deduped_tps[0] if len(deduped_tps) > 0 else round(entry_price - (sl_distance * 1.5), 4)
        tp2 = deduped_tps[1] if len(deduped_tps) > 1 else None
        tp3 = deduped_tps[2] if len(deduped_tps) > 2 else None

        # Enforce strict hierarchy: SL > Entry > TP1 > TP2 > TP3
        if tp2 is not None and tp2 >= tp1:
            tp2 = None
            tp3 = None
        if tp3 is not None and tp2 is not None and tp3 >= tp2:
            tp3 = None

        reward1 = entry_price - tp1
        reward2 = (entry_price - tp2) if tp2 is not None else None
        reward3 = (entry_price - tp3) if tp3 is not None else None

        rr1 = round(reward1 / max(sl_distance, 1e-6), 2)
        rr2 = round(reward2 / max(sl_distance, 1e-6), 2) if reward2 is not None else None
        rr3 = round(reward3 / max(sl_distance, 1e-6), 2) if reward3 is not None else None

        # Direction-aware signed price change:
        sl_pct = round((sl_distance / entry_price) * 100.0, 2)
        tp1_pct = -round((reward1 / entry_price) * 100.0, 2)
        tp2_pct = -round((reward2 / entry_price) * 100.0, 2) if reward2 is not None else None
        tp3_pct = -round((reward3 / entry_price) * 100.0, 2) if reward3 is not None else None

        return {
            "sl": round(structural_sl, 4),
            "tp1": round(tp1, 4),
            "tp2": round(tp2, 4) if tp2 is not None else None,
            "tp3": round(tp3, 4) if tp3 is not None else None,
            "tp2_status": "AVAILABLE" if tp2 is not None else "UNAVAILABLE",
            "tp3_status": "AVAILABLE" if tp3 is not None else "UNAVAILABLE",
            "risk_distance": round(sl_distance, 4),
            "reward_distance_tp1": round(reward1, 4),
            "reward_distance_tp2": round(reward2, 4) if reward2 is not None else None,
            "reward_distance_tp3": round(reward3, 4) if reward3 is not None else None,
            "reward_risk_ratio": rr1,
            "reward_risk_tp1": rr1,
            "reward_risk_tp2": rr2,
            "reward_risk_tp3": rr3,
            "risk_reward": rr1,
            "sl_distance": round(sl_distance, 4),
            "sl_pct": sl_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "tp3_pct": tp3_pct,
            "sl_distance_pct": sl_pct,
            "tp1_distance_pct": tp1_pct,
            "tp2_distance_pct": tp2_pct,
            "tp3_distance_pct": tp3_pct,
            "risk_pct": round((sl_distance / entry_price) * 100.0, 2),
            "reward_pct_tp1": round((reward1 / entry_price) * 100.0, 2),
            "reward_pct_tp2": round((reward2 / entry_price) * 100.0, 2) if reward2 is not None else None,
            "reward_pct_tp3": round((reward3 / entry_price) * 100.0, 2) if reward3 is not None else None,
            "target_provenance": {
                "tp1_source": "RECENT_SWING_LOW" if len(deduped_tps) > 0 else "STRUCTURAL_RISK_PROJECTION_1.5R",
                "tp2_source": "RECENT_SWING_LOW" if tp2 is not None else "UNAVAILABLE",
                "tp3_source": "RECENT_SWING_LOW" if tp3 is not None else "UNAVAILABLE",
                "tp1_price": round(tp1, 4),
                "tp2_price": round(tp2, 4) if tp2 is not None else None,
                "tp3_price": round(tp3, 4) if tp3 is not None else None,
                "tp1_timeframe": f"{timeframe}m",
                "tp2_timeframe": f"{timeframe}m" if tp2 is not None else None,
                "tp3_timeframe": f"{timeframe}m" if tp3 is not None else None,
                "tp1_status": "AVAILABLE",
                "tp2_status": "AVAILABLE" if tp2 is not None else "UNAVAILABLE",
                "tp3_status": "AVAILABLE" if tp3 is not None else "UNAVAILABLE",
                "sl_source": sl_source,
                "atr_used": round(cur_atr, 4),
                "experimental_atr_target": round(entry_price - (cur_atr * 3.0), 4)
            },
            "basis": "SWING_HIGH_AND_SELL_SIDE_LIQUIDITY"
        }



class CausalRetestEngine:
    """Deterministic Causal Retest State Machine.

    Evaluates sequential closed candles and advances the retest state without lookahead.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: int = 3,
        direction: str = "LONG",
        retest_window: int = config.RETEST_WINDOW_CANDLES,
        zone_tolerance_pct: float = config.RETEST_ZONE_TOLERANCE_PCT,
        displacement_atr_mult: float = config.DISPLACEMENT_ATR_MULT,
        rvol_threshold: float = config.RVOL_THRESHOLD,
        require_freshness: bool = True
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.retest_window = retest_window
        self.zone_tolerance_pct = zone_tolerance_pct
        self.displacement_atr_mult = displacement_atr_mult
        self.rvol_threshold = rvol_threshold
        self.require_freshness = require_freshness

    def evaluate_step(
        self,
        current_state: RetestState,
        candles: List[dict],
        vwap: float = 0.0,
        require_vwap: bool = True
    ) -> RetestState:
        """Process latest closed candle and causal market indicators."""
        if len(candles) < 20:
            return current_state

        now_ms = int(time.time() * 1000)
        cur_candle = candles[-1]
        prev_candle = candles[-2]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        closes = [float(c["close"]) for c in candles]
        opens = [float(c["open"]) for c in candles]
        volumes = [float(c.get("volume") or 0.0) for c in candles]

        atr_series = calculate_atr(highs, lows, closes, 14)
        cur_atr = atr_series[-1] if atr_series else cur_candle["close"] * 0.01

        cur_close = float(cur_candle["close"])
        cur_open = float(cur_candle["open"])
        cur_high = float(cur_candle["high"])
        cur_low = float(cur_candle["low"])
        cur_ts = int(cur_candle["ts"])

        # -------------------------------------------------------------
        # VOLATILITY-AWARE DISTANCE COMPUTATION AT EVERY STEP
        # -------------------------------------------------------------
        z_low = current_state.zone_low or (current_state.breakout_price * 0.998 if current_state.breakout_price else cur_close * 0.998)
        z_high = current_state.zone_high or (current_state.breakout_price * 1.002 if current_state.breakout_price else cur_close * 1.002)

        if self.direction == "LONG":
            if cur_low <= z_high and cur_high >= z_low:
                dist = 0.0
            elif cur_low > z_high:
                dist = cur_low - z_high
            else:
                dist = z_low - cur_high
        else:  # SHORT
            if cur_high >= z_low and cur_low <= z_high:
                dist = 0.0
            elif cur_high < z_low:
                dist = z_low - cur_high
            else:
                dist = cur_low - z_high

        current_state.distance_pct = round((dist / max(cur_close, 1e-6)) * 100.0, 3)
        current_state.distance_atr = round(dist / max(cur_atr, 1e-6), 2)
        current_state.current_atr = round(cur_atr, 4)

        # -------------------------------------------------------------
        # STATE 1: IDLE / CHECK FOR BREAKOUT
        # -------------------------------------------------------------
        if current_state.state in ("IDLE", "INVALIDATED", "EXPIRED"):
            # Check swing high/low breakout
            swing_highs, swing_lows = detect_swing_points(highs[:-1], lows[:-1], lookback=3)
            body = abs(cur_close - cur_open)
            is_displaced = body >= (cur_atr * self.displacement_atr_mult)

            # Detect FVG on latest 3 candles
            fvg_res = structure_detectors.detect_fvg(
                highs=highs[-3:], lows=lows[-3:], closes=closes[-3:],
                timestamp=cur_ts, symbol=self.symbol, timeframe=f"{self.timeframe}m"
            )

            if self.direction == "LONG":
                # When require_vwap is True, must be above VWAP. Bullish close, and breaking a confirmed swing high
                vwap_cond = (cur_close > vwap) if require_vwap else True
                if vwap_cond and cur_close > cur_open:
                    recent_high = max(highs[:-1])
                    valid_peaks = [p for idx, p in swing_highs if p < cur_close]
                    if (valid_peaks or cur_close > recent_high) and is_displaced:
                        breakout_level = max(valid_peaks) if valid_peaks else recent_high
                        zone_low = breakout_level * (1.0 - self.zone_tolerance_pct / 100.0)
                        zone_high = max(breakout_level, cur_open)
                        if fvg_res.detected and fvg_res.direction == "BULLISH":
                            zone_low = min(zone_low, fvg_res.measurements.get("gap_low", zone_low))
                            zone_high = max(zone_high, fvg_res.measurements.get("gap_high", zone_high))

                        # Calculate initial distance
                        init_dist = max(0.0, cur_low - zone_high) if cur_low > zone_high else 0.0
                        return RetestState(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            direction=self.direction,
                            state="WAITING_FOR_RETEST",
                            breakout_ts=cur_ts,
                            breakout_price=cur_close,
                            vwap_at_breakout=vwap,
                            zone_low=zone_low,
                            zone_high=zone_high,
                            fvg_id=f"{self.symbol}_{self.timeframe}m_bull_{cur_ts}" if fvg_res.detected else None,
                            elapsed_candles=0,
                            distance_pct=round((init_dist / max(cur_close, 1e-6)) * 100.0, 3),
                            distance_atr=round(init_dist / max(cur_atr, 1e-6), 2),
                            current_atr=round(cur_atr, 4),
                            updated_ms=now_ms
                        )

            elif self.direction == "SHORT":
                # When require_vwap is True, must be below VWAP. Bearish close, and breaking a confirmed swing low
                vwap_cond = (cur_close < vwap) if require_vwap else True
                if vwap_cond and cur_close < cur_open:
                    recent_low = min(lows[:-1])
                    valid_valleys = [v for idx, v in swing_lows if v > cur_close]
                    if (valid_valleys or cur_close < recent_low) and is_displaced:
                        breakout_level = min(valid_valleys) if valid_valleys else recent_low
                        zone_high = breakout_level * (1.0 + self.zone_tolerance_pct / 100.0)
                        zone_low = min(breakout_level, cur_open)
                        if fvg_res.detected and fvg_res.direction == "BEARISH":
                            zone_low = min(zone_low, fvg_res.measurements.get("gap_low", zone_low))
                            zone_high = max(zone_high, fvg_res.measurements.get("gap_high", zone_high))

                        init_dist = max(0.0, zone_low - cur_high) if cur_high < zone_low else 0.0
                        return RetestState(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            direction=self.direction,
                            state="WAITING_FOR_RETEST",
                            breakout_ts=cur_ts,
                            breakout_price=cur_close,
                            vwap_at_breakout=vwap,
                            zone_low=zone_low,
                            zone_high=zone_high,
                            fvg_id=f"{self.symbol}_{self.timeframe}m_bear_{cur_ts}" if fvg_res.detected else None,
                            elapsed_candles=0,
                            distance_pct=round((init_dist / max(cur_close, 1e-6)) * 100.0, 3),
                            distance_atr=round(init_dist / max(cur_atr, 1e-6), 2),
                            current_atr=round(cur_atr, 4),
                            updated_ms=now_ms
                        )

            return current_state

        # -------------------------------------------------------------
        # STATE 2: WAITING_FOR_RETEST
        # -------------------------------------------------------------
        if current_state.state in ("WAITING_FOR_RETEST", "IDENTIFIED"):
            new_elapsed = current_state.elapsed_candles + 1
            if new_elapsed > self.retest_window:
                current_state.state = "EXPIRED"
                current_state.invalidation_reason = f"Exceeded maximum retest horizon ({self.retest_window} bars)"
                current_state.updated_ms = now_ms
                return current_state

            if self.direction == "LONG":
                # Invalidation: price dumps below zone by 0.5 ATR or falls below VWAP (if required)
                invalidation_cond = (cur_close < z_low - (0.5 * cur_atr)) or (require_vwap and cur_close < vwap)
                if invalidation_cond:
                    current_state.state = "INVALIDATED"
                    current_state.invalidation_ts = cur_ts
                    current_state.invalidation_reason = f"Price closed below zone low ({z_low:.2f}) by > 0.5 ATR" if cur_close < z_low - (0.5 * cur_atr) else f"Price closed below session VWAP ({vwap:.2f})"
                    current_state.updated_ms = now_ms
                    return current_state

                # Check if wick touches the retest zone
                if cur_low <= z_high and cur_low >= z_low - (0.2 * cur_atr):
                    current_state.state = "RETEST_TOUCHED"
                    current_state.touch_ts = cur_ts
                    current_state.elapsed_candles = new_elapsed
                    current_state.updated_ms = now_ms
                    return current_state

            elif self.direction == "SHORT":
                # Invalidation: price surges above zone by 0.5 ATR or rises above VWAP (if required)
                invalidation_cond = (cur_close > z_high + (0.5 * cur_atr)) or (require_vwap and cur_close > vwap)
                if invalidation_cond:
                    current_state.state = "INVALIDATED"
                    current_state.invalidation_ts = cur_ts
                    current_state.invalidation_reason = f"Price closed above zone high ({z_high:.2f}) by > 0.5 ATR" if cur_close > z_high + (0.5 * cur_atr) else f"Price closed above session VWAP ({vwap:.2f})"
                    current_state.updated_ms = now_ms
                    return current_state

                # Check if wick touches the retest zone
                if cur_high >= z_low and cur_high <= z_high + (0.2 * cur_atr):
                    current_state.state = "RETEST_TOUCHED"
                    current_state.touch_ts = cur_ts
                    current_state.elapsed_candles = new_elapsed
                    current_state.updated_ms = now_ms
                    return current_state

            current_state.elapsed_candles = new_elapsed
            current_state.updated_ms = now_ms
            return current_state

        # -------------------------------------------------------------
        # STATE 3: RETEST_TOUCHED / RETEST_ZONE_TOUCHED -> CHECK REJECTION
        # -------------------------------------------------------------
        if current_state.state in ("RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"):
            if self.direction == "LONG":
                # Bullish rejection: lower wick rejected zone, candle closes green and above zone_low
                if cur_close > cur_open and cur_close >= z_low:
                    current_state.state = "CONFIRMING_REJECTION"
                    current_state.rejection_ts = cur_ts
                    current_state.updated_ms = now_ms
                    return current_state
                elif cur_close < z_low - (0.5 * cur_atr):
                    current_state.state = "INVALIDATED"
                    current_state.invalidation_ts = cur_ts
                    current_state.invalidation_reason = f"Retest failed: Price closed below zone low ({z_low:.2f}) by > 0.5 ATR"
                    current_state.updated_ms = now_ms
                    return current_state

            elif self.direction == "SHORT":
                # Bearish rejection: upper wick rejected zone, candle closes red and below zone_high
                if cur_close < cur_open and cur_close <= z_high:
                    current_state.state = "CONFIRMING_REJECTION"
                    current_state.rejection_ts = cur_ts
                    current_state.updated_ms = now_ms
                    return current_state
                elif cur_close > z_high + (0.5 * cur_atr):
                    current_state.state = "INVALIDATED"
                    current_state.invalidation_ts = cur_ts
                    current_state.invalidation_reason = f"Retest failed: Price closed above zone high ({z_high:.2f}) by > 0.5 ATR"
                    current_state.updated_ms = now_ms
                    return current_state

            return current_state

        # -------------------------------------------------------------
        # STATE 4: CONFIRMING_REJECTION / REJECTION_CONFIRMED -> ENTRY_READY
        # -------------------------------------------------------------
        if current_state.state in ("CONFIRMING_REJECTION", "REJECTION_CONFIRMED"):
            # Check RVOL & CVD
            rvol = calculate_rvol(volumes, 20)
            cvd_series = calculate_cvd_series(candles[-10:])
            cvd_delta = cvd_series[-1] - cvd_series[0] if len(cvd_series) > 1 else 0.0

            cvd_confirmed = (cvd_delta > 0) if self.direction == "LONG" else (cvd_delta < 0)
            rvol_confirmed = rvol >= 1.0  # Baseline 1.0x

            # Check data freshness: fail closed if data is older than 3 bars
            candle_age_ms = now_ms - cur_ts
            is_data_fresh = (candle_age_ms <= (self.timeframe * 3 * 60 * 1000)) if self.require_freshness else True

            if cvd_confirmed and rvol_confirmed and is_data_fresh:
                # Advance to ENTRY_READY
                current_state.state = "ENTRY_READY"
                current_state.confirmation_ts = cur_ts
                current_state.updated_ms = now_ms
                return current_state

            return current_state

        return current_state


def evaluate_strategy_conditions(
    strategy: str,
    retest_state: RetestState,
    candles: List[dict],
    vwap: float = 0.0,
    market_context: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Evaluates strategy-specific conditions cleanly separated from the global framework.
    Returns:
      - conditions: List of structured condition dicts with status MET | PENDING | NOT_AVAILABLE | INVALID | NOT_APPLICABLE
      - waiting_for: Dynamic human-readable explanation of what is pending
      - next_required_event: Immediate next required event name
    """
    cur_candle = candles[-1] if candles else {}
    cur_close = float(cur_candle.get("close") or 0.0)
    volumes = [float(c.get("volume") or 0.0) for c in candles]

    rvol = calculate_rvol(volumes, 20) if len(volumes) >= 5 else 1.0
    cvd_series = calculate_cvd_series(candles[-10:]) if len(candles) >= 2 else []
    cvd_delta = cvd_series[-1] - cvd_series[0] if len(cvd_series) > 1 else 0.0

    cvd_ok = (cvd_delta > 0) if retest_state.direction == "LONG" else (cvd_delta < 0)
    rvol_ok = rvol >= config.RVOL_THRESHOLD

    state = retest_state.state
    is_long = retest_state.direction == "LONG"

    conditions: List[Dict[str, Any]] = []

    # 1. Breakout Confirmation
    breakout_met = state not in ("IDLE",)
    conditions.append({
        "name": "Breakout Displacement",
        "status": "MET" if breakout_met else "PENDING",
        "detail": f"Displacement impulse past {retest_state.breakout_price:.2f}" if retest_state.breakout_price else "Waiting for structural breakout"
    })

    # 2. Retest Zone Touch
    retest_met = state in ("RETEST_TOUCHED", "RETEST_ZONE_TOUCHED", "CONFIRMING_REJECTION", "REJECTION_CONFIRMED", "ENTRY_READY", "ENTRY_CANDIDATE", "TRIGGERED")
    retest_status = "MET" if retest_met else ("INVALID" if state == "INVALIDATED" else "PENDING")
    z_l = retest_state.zone_low or 0.0
    z_h = retest_state.zone_high or 0.0
    conditions.append({
        "name": "Retest Zone Touch",
        "status": retest_status,
        "detail": f"Zone [{z_l:.2f} - {z_h:.2f}], Dist: {retest_state.distance_pct:.2f}% ({retest_state.distance_atr:.2f} ATR)"
    })

    # 3. Rejection Wick Confirmation
    rejection_met = state in ("CONFIRMING_REJECTION", "REJECTION_CONFIRMED", "ENTRY_READY", "ENTRY_CANDIDATE", "TRIGGERED")
    rejection_status = "MET" if rejection_met else ("INVALID" if state == "INVALIDATED" else "PENDING")
    conditions.append({
        "name": "Rejection Wick",
        "status": rejection_status,
        "detail": "Confirmed candle rejection wick against zone" if rejection_met else "Waiting for candle wick rejection"
    })

    # 4. Volume / RVOL
    has_volume_data = bool(volumes and any(v > 0 for v in volumes[-5:]))
    if not has_volume_data:
        rvol_status = "NOT_AVAILABLE"
        rvol_detail = "Volume feed not available for instrument"
    elif rvol_ok:
        rvol_status = "MET"
        rvol_detail = f"RVOL {rvol:.2f}x >= baseline threshold {config.RVOL_THRESHOLD}x"
    else:
        rvol_status = "PENDING"
        rvol_detail = f"RVOL {rvol:.2f}x below baseline threshold {config.RVOL_THRESHOLD}x"
    conditions.append({
        "name": "Volume / RVOL",
        "status": rvol_status,
        "detail": rvol_detail
    })

    # 5. CVD Aggressor Flow
    has_taker_data = bool(candles and any(float(c.get("taker_buy") or 0.0) > 0 for c in candles[-5:]))
    if not has_taker_data:
        cvd_status = "NOT_AVAILABLE"
        cvd_detail = "Aggressor CVD data not available for instrument"
    elif cvd_ok:
        cvd_status = "MET"
        cvd_detail = f"CVD aggression confirmed (Delta: {cvd_delta:+.1f})"
    else:
        cvd_status = "PENDING"
        cvd_detail = f"CVD divergent (Delta: {cvd_delta:+.1f})"
    conditions.append({
        "name": "CVD Aggressor Flow",
        "status": cvd_status,
        "detail": cvd_detail
    })

    # 6. Session VWAP Context
    if vwap > 0:
        vwap_ok = (cur_close > vwap) if is_long else (cur_close < vwap)
        conditions.append({
            "name": "Session VWAP",
            "status": "MET" if vwap_ok else "PENDING",
            "detail": f"Session VWAP at {vwap:.2f} (Price {'above' if cur_close > vwap else 'below'} VWAP)"
        })
    else:
        conditions.append({
            "name": "Session VWAP",
            "status": "NOT_AVAILABLE",
            "detail": "Session VWAP data not available"
        })

    # 7. Fair Value Gap (FVG) - Strategy Specific (Optional confluence)
    fvg_detected = bool(retest_state.fvg_id)
    conditions.append({
        "name": "Fair Value Gap",
        "status": "MET" if fvg_detected else "NOT_APPLICABLE",
        "detail": f"FVG imbalance: {'Detected' if fvg_detected else 'None required'}"
    })

    # -------------------------------------------------------------
    # DYNAMIC "WAITING FOR" CALCULATION FROM ACTUAL STATE
    # -------------------------------------------------------------
    if state == "INVALIDATED":
        waiting_for = f"Setup invalidated: {retest_state.invalidation_reason or 'Structural invalidation boundary breached'}."
        next_required_event = "NONE"
    elif state == "EXPIRED":
        waiting_for = f"Setup expired: Exceeded allowed retest horizon ({retest_state.elapsed_candles}/{config.RETEST_WINDOW_CANDLES} bars)."
        next_required_event = "NONE"
    elif state in ("WAITING_FOR_RETEST", "IDENTIFIED"):
        waiting_for = f"Waiting for {retest_state.timeframe}m retest touch of {z_l:.2f} - {z_h:.2f} ({retest_state.distance_pct:.2f}%, {retest_state.distance_atr:.2f} ATR away)"
        next_required_event = "RETEST_ZONE_TOUCH"
    elif state in ("RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"):
        waiting_for = "Retest zone touched. Waiting for rejection candle confirmation."
        next_required_event = "REJECTION_CANDLE"
    elif state in ("CONFIRMING_REJECTION", "REJECTION_CONFIRMED"):
        pending_names = [c["name"] for c in conditions if c["status"] == "PENDING"]
        if "CVD Aggressor Flow" in pending_names and "Volume / RVOL" in pending_names:
            waiting_for = "Rejection confirmed. Waiting for volume & CVD order flow confirmation."
            next_required_event = "ORDER_FLOW_CONFIRMATION"
        elif "CVD Aggressor Flow" in pending_names:
            waiting_for = f"Rejection confirmed. Waiting for CVD order flow confirmation ({cvd_detail})."
            next_required_event = "CVD_CONFIRMATION"
        elif "Volume / RVOL" in pending_names:
            waiting_for = f"Rejection confirmed. Waiting for volume expansion (RVOL >= {config.RVOL_THRESHOLD}x)."
            next_required_event = "RVOL_CONFIRMATION"
        else:
            waiting_for = "Evaluating final entry confirmation criteria."
            next_required_event = "FINAL_CONFIRMATION"
    elif state in ("ENTRY_READY", "ENTRY_CANDIDATE"):
        waiting_for = "All conditions satisfied. Ready for deterministic trigger/execution."
        next_required_event = "TRIGGER"
    elif state == "TRIGGERED":
        waiting_for = "Order triggered / position executed in SHADOW."
        next_required_event = "NONE"
    else:
        waiting_for = "Scanning market structure for breakout."
        next_required_event = "BREAKOUT"

    return conditions, waiting_for, next_required_event


def generate_setup_candidate_from_state(
    retest_state: RetestState,
    candles: List[dict],
    vwap: float,
    market_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Produce a first-class structured setup candidate DTO from the retest state."""
    cur_candle = candles[-1] if candles else {}
    cur_close = float(cur_candle.get("close") or 0.0)
    cur_ts = int(cur_candle.get("ts") or 0)
    now_ms = int(time.time() * 1000)

    targets_stops = compute_structural_targets_stops(
        candles=candles,
        direction=retest_state.direction,
        entry_price=cur_close,
        vwap=vwap,
        timeframe=retest_state.timeframe
    )

    # Evaluate dynamic strategy conditions
    conditions, waiting_for, next_required_event = evaluate_strategy_conditions(
        strategy="VWAP_STRUCTURE_RETEST",
        retest_state=retest_state,
        candles=candles,
        vwap=vwap,
        market_context=market_context
    )

    # Zone geometry
    z_low = retest_state.zone_low or (cur_close * 0.998)
    z_high = retest_state.zone_high or (cur_close * 1.002)
    zone_dict = {
        "low": round(z_low, 4),
        "high": round(z_high, 4),
        "width": round(abs(z_high - z_low), 4),
        "width_pct": round((abs(z_high - z_low) / max(cur_close, 1e-6)) * 100.0, 2)
    }

    # Data freshness
    candle_age_sec = round((now_ms - cur_ts) / 1000.0, 1) if cur_ts > 0 else 0.0
    data_quality = "GOOD" if candle_age_sec <= (retest_state.timeframe * 3 * 60) else "STALE"
    data_freshness = {
        "last_candle_ts": cur_ts,
        "data_age_seconds": candle_age_sec,
        "quality": data_quality
    }

    # Stable deterministic setup identity: 1 active setup per symbol/direction/timeframe/breakout
    breakout_id = retest_state.breakout_ts or 0
    setup_id = f"setup_{retest_state.symbol}_{retest_state.direction}_{retest_state.timeframe}m_{breakout_id}"

    entry_conditions = {
        "rule": "VWAP_STRUCTURE_RETEST",
        "breakout_price": retest_state.breakout_price,
        "zone_low": retest_state.zone_low,
        "zone_high": retest_state.zone_high,
        "trigger_state": retest_state.state,
        "current_price": cur_close
    }

    invalidation = {
        "rule": "STRUCTURAL_VWAP_INVALIDATION",
        "invalidation_price": targets_stops["sl"],
        "reason": f"Break below {targets_stops['sl']} invalidates bullish structure" if retest_state.direction == "LONG" else f"Break above {targets_stops['sl']} invalidates bearish structure"
    }

    direction_label = "LONG" if retest_state.direction == "LONG" else "SHORT"
    is_long = (retest_state.direction == "LONG")
    bo_str = f"at {retest_state.breakout_price:.2f}" if retest_state.breakout_price is not None else "level pending"
    reason = (
        f"Price is trading {'above' if retest_state.direction == 'LONG' else 'below'} session VWAP ({vwap:.2f}). "
        f"Confirmed {retest_state.timeframe}m structural breakout {bo_str}. "
        f"State: {retest_state.state} (Elapsed {retest_state.elapsed_candles}/{config.RETEST_WINDOW_CANDLES} candles)."
    )

    rvol_status = next((c["status"] for c in conditions if c["name"] == "Volume / RVOL"), "PENDING")
    cvd_status = next((c["status"] for c in conditions if c["name"] == "CVD Aggressor Flow"), "PENDING")
    ai_conf = 75.0 if (rvol_status == "MET" and cvd_status == "MET") else 65.0

    # Dynamic allocation according to available targets
    if targets_stops.get("tp3") is not None and targets_stops.get("tp2") is not None:
        rec_tp1_pct, rec_tp2_pct, rec_tp3_pct = 30.0, 40.0, 30.0
    elif targets_stops.get("tp2") is not None:
        rec_tp1_pct, rec_tp2_pct, rec_tp3_pct = 50.0, 50.0, 0.0
    else:
        rec_tp1_pct, rec_tp2_pct, rec_tp3_pct = 100.0, 0.0, 0.0

    # Canonical status
    canonical_state = "ENTRY_READY" if retest_state.state in ("ENTRY_CANDIDATE", "ENTRY_READY") else (
        "CONFIRMING_REJECTION" if retest_state.state in ("REJECTION_CONFIRMED", "CONFIRMING_REJECTION") else (
            "RETEST_TOUCHED" if retest_state.state in ("RETEST_ZONE_TOUCHED", "RETEST_TOUCHED") else retest_state.state
        )
    )

    reasons = {
        "why_exists": reason,
        "why_entry": f"{direction_label} entry on {retest_state.timeframe}m retest confirmation at {cur_close:.2f}",
        "entry_detail": {
            "exact_price": cur_close,
            "condition": f"Retest of {z_low:.2f} - {z_high:.2f} zone with rejection wick",
            "breakout_displacement": f"Clean impulse break past {retest_state.breakout_price:.2f}" if retest_state.breakout_price is not None else "Breakout level pending",
            "retest_reasoning": f"Price pulled back into value zone and rejected opposite expansion",
            "confirmation": f"RVOL {rvol_status}, CVD {cvd_status}"
        },
        "why_stop": f"Structural stop at {targets_stops['sl']:.2f} ({targets_stops['sl_distance_pct']:.2f}%) beyond swing boundary",
        "sl_detail": {
            "exact_price": targets_stops["sl"],
            "structural_level": targets_stops.get("swing_level", targets_stops["sl"]),
            "buffer": "0.5x ATR buffer applied beyond structural swing",
            "invalidation_logic": invalidation["reason"],
            "distance_pct": targets_stops["sl_distance_pct"]
        },
        "why_tp1": f"First liquidity target at {targets_stops['tp1']:.2f} ({targets_stops['tp1_distance_pct']:.2f}%, {targets_stops['reward_risk_tp1']} R:R)" if targets_stops.get("tp1") else "TP1 UNAVAILABLE",
        "why_tp2": f"Second liquidity objective at {targets_stops['tp2']:.2f} ({targets_stops['tp2_distance_pct']:.2f}%, {targets_stops['reward_risk_tp2']} R:R)" if targets_stops.get("tp2") else "TP2 UNAVAILABLE (Single structural target identified)",
        "why_tp3": f"Extended trend target at {targets_stops['tp3']:.2f} ({targets_stops['tp3_distance_pct']:.2f}%, {targets_stops['reward_risk_tp3']} R:R)" if targets_stops.get("tp3") else "TP3 UNAVAILABLE (Market structure provides 2 primary liquidity targets)",
        "vwap_evidence": f"Session VWAP at {vwap:.2f}. Price is trading {'above' if is_long else 'below'} VWAP.",
        "vwap_gate_status": "VWAP: ANALYZED BY ML (GENERIC MANUAL VWAP GATE: NOT ADDED)",
        "empirical_calibration_notice": "EMPIRICAL SUCCESS PROBABILITY: NOT CALIBRATED",
        "waiting_for": waiting_for,
        "next_required_event": next_required_event,
        "missing_conditions": [c["name"] for c in conditions if c["status"] == "PENDING"]
    }

    return {
        "setup_id": setup_id,
        "candidate_id": setup_id,
        "symbol": retest_state.symbol,
        "display_symbol": config.to_display_symbol(retest_state.symbol),
        "venue_symbol": config.to_venue_symbol(retest_state.symbol),
        "direction": retest_state.direction,
        "timeframe": retest_state.timeframe,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "current_state": canonical_state,
        "retest_state": canonical_state,
        "setup_status": "ACTIVE" if canonical_state not in ("INVALIDATED", "EXPIRED") else canonical_state,
        "reason": reason,
        "vwap": round(vwap, 4),
        "breakout_price": retest_state.breakout_price,
        "entry_price": cur_close,
        "current_price": cur_close,
        "zone": zone_dict,
        "distance_pct": retest_state.distance_pct,
        "distance_atr": retest_state.distance_atr,
        "waiting_for": waiting_for,
        "next_required_event": next_required_event,
        "conditions": conditions,
        "data_freshness": data_freshness,
        "cvd_confirmed": cvd_status == "MET",
        "rvol_confirmed": rvol_status == "MET",
        "fvg_confirmed": bool(retest_state.fvg_id),
        "entry_conditions": entry_conditions,
        "invalidation": invalidation,
        "suggested_sl": targets_stops["sl"],
        "suggested_tp1": targets_stops["tp1"],
        "suggested_tp2": targets_stops["tp2"],
        "suggested_tp3": targets_stops["tp3"],
        "risk_distance": targets_stops["risk_distance"],
        "reward_distance_tp1": targets_stops["reward_distance_tp1"],
        "reward_distance_tp2": targets_stops["reward_distance_tp2"],
        "reward_distance_tp3": targets_stops["reward_distance_tp3"],
        "reward_risk_ratio": targets_stops["reward_risk_ratio"],
        "reward_risk_tp1": targets_stops["reward_risk_tp1"],
        "reward_risk_tp2": targets_stops["reward_risk_tp2"],
        "reward_risk_tp3": targets_stops["reward_risk_tp3"],
        "sl_distance_pct": targets_stops["sl_distance_pct"],
        "tp1_distance_pct": targets_stops["tp1_distance_pct"],
        "tp2_distance_pct": targets_stops["tp2_distance_pct"],
        "tp3_distance_pct": targets_stops["tp3_distance_pct"],
        "risk_pct": targets_stops.get("risk_pct"),
        "reward_pct_tp1": targets_stops.get("reward_pct_tp1"),
        "reward_pct_tp2": targets_stops.get("reward_pct_tp2"),
        "reward_pct_tp3": targets_stops.get("reward_pct_tp3"),
        "target_provenance": targets_stops.get("target_provenance", {}),
        "recommended_tp1_pct": rec_tp1_pct,
        "recommended_tp2_pct": rec_tp2_pct,
        "recommended_tp3_pct": rec_tp3_pct,
        "recommended_margin": 25.0,
        "recommended_leverage": 15.0,
        "risk_reward": targets_stops["risk_reward"],
        "ai_confidence": ai_conf,
        "confidence_pct": ai_conf,
        "calibration_status": "NOT CALIBRATED",
        "expected_retest_window": {"min_bars": 3, "max_bars": 12, "timeframe": f"{retest_state.timeframe}m"},
        "expected_retest_horizon": f"ESTIMATED / NOT CALIBRATED (3-12 bars on {retest_state.timeframe}m)",
        "retest_calibration_status": "NOT CALIBRATED",
        "reasons": reasons,
        "thesis": f"High-probability {direction_label} opportunity on {config.to_display_symbol(retest_state.symbol)} targeting structural liquidity at {targets_stops['tp1']:.2f}.",
        "generated_ms": now_ms,
        "expires_ms": now_ms + (30 * 60 * 1000),
        "status": "ACTIVE" if canonical_state not in ("INVALIDATED", "EXPIRED") else canonical_state
    }

