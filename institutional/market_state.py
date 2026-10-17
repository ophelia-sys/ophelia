"""
Authoritative Market-State Feature Engine for Ophelia.
Layer: institutional/market_state
Contract: Strictly isolated analytics/state object — NO execution proposal or authority.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone


@dataclass(frozen=True)
class MarketState:
    """
    Standardized market-state snapshot contract.
    Aggregates multi-dimensional microstructure and price-action state
    for research, telemetry, and advisory intelligence.
    """
    symbol: str
    timestamp: int  # UTC ms
    timeframe: str
    trend_state: str        # "BULLISH", "BEARISH", "SIDEWAYS"
    volatility_state: str   # "EXPANDED", "COMPRESSED", "NORMAL"
    volume_state: str       # "SURGE", "DRY", "NORMAL"
    vwap_state: str         # "CLEAR_ABOVE", "CLEAR_BELOW", "CHOP", "NEAR_VWAP"
    cvd_state: str          # "BULLISH_DELTA", "BEARISH_DELTA", "DIVERGENT", "ABSORPTION", "BALANCED"
    order_flow_state: str   # "BUY_DOMINANT", "SELL_DOMINANT", "BALANCED"
    liquidity_state: str    # "NORMAL", "THIN", "SWEEP_HIGH", "SWEEP_LOW"
    displacement_state: str # "IMPULSE_UP", "IMPULSE_DOWN", "NONE"
    session_state: str      # "LONDON", "NEW_YORK", "ASIAN", "OVERLAP", "CLOSED"
    data_quality: str       # "VALID", "DEGRADED", "STALE", "INVALID"
    confidence: float       # 0.0 to 1.0
    metrics: Dict[str, float] = field(default_factory=dict)
    news_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dictionary serialization for API and telemetry."""
        return asdict(self)


class MarketStateEngine:
    """
    Deterministic MarketState compiler.
    Transforms raw candle history, indicator values, and CVD engine telemetry
    into a structured MarketState representation.
    """

    @staticmethod
    def determine_session(utc_timestamp_ms: int) -> str:
        """Classify major crypto trading session based on UTC hour."""
        dt = datetime.fromtimestamp(utc_timestamp_ms / 1000.0, tz=timezone.utc)
        hour = dt.hour

        # London: 08:00 - 16:00 UTC
        # New York: 13:00 - 21:00 UTC
        # Overlap (London + NY): 13:00 - 16:00 UTC
        # Asian: 00:00 - 08:00 UTC
        if 13 <= hour < 16:
            return "OVERLAP"
        elif 8 <= hour < 13:
            return "LONDON"
        elif 16 <= hour < 21:
            return "NEW_YORK"
        elif 0 <= hour < 8:
            return "ASIAN"
        else:
            return "LATE_NY_CLOSE"

    @classmethod
    def compile(
        cls,
        symbol: str,
        timestamp: int,
        timeframe: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        current_price: float,
        vwap: float,
        supertrend_direction: Optional[str] = None,
        cvd_state_dict: Optional[Dict[str, Any]] = None,
        structure_detections: Optional[List[Any]] = None
    ) -> MarketState:
        """
        Synthesize a clean MarketState object from raw series and detections.
        """
        metrics: Dict[str, float] = {}

        # 1. VWAP State & Distance
        vwap_diff_pct = ((current_price - vwap) / vwap) * 100 if vwap > 0 else 0.0
        metrics["vwap_diff_pct"] = round(vwap_diff_pct, 4)
        metrics["vwap"] = round(vwap, 4)

        if abs(vwap_diff_pct) < 0.15:
            vwap_state = "NEAR_VWAP"
        elif vwap_diff_pct >= 0.35:
            vwap_state = "CLEAR_ABOVE"
        elif vwap_diff_pct <= -0.35:
            vwap_state = "CLEAR_BELOW"
        else:
            vwap_state = "CHOP"

        # 2. Trend State
        if supertrend_direction:
            trend_state = supertrend_direction.upper()
        else:
            # Fallback simple moving average comparison if available
            if len(closes) >= 20:
                sma20 = sum(closes[-20:]) / 20.0
                metrics["sma20"] = round(sma20, 4)
                if current_price > sma20 and vwap_diff_pct > 0.1:
                    trend_state = "BULLISH"
                elif current_price < sma20 and vwap_diff_pct < -0.1:
                    trend_state = "BEARISH"
                else:
                    trend_state = "SIDEWAYS"
            else:
                trend_state = "SIDEWAYS"

        # 3. Volatility State (Normalized ATR)
        if len(closes) >= 15:
            tr_list = [
                max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
                for i in range(-14, 0)
            ]
            atr = sum(tr_list) / len(tr_list)
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0.0
            metrics["atr_pct"] = round(atr_pct, 4)

            if atr_pct > 0.8:
                volatility_state = "EXPANDED"
            elif atr_pct < 0.2:
                volatility_state = "COMPRESSED"
            else:
                volatility_state = "NORMAL"
        else:
            volatility_state = "NORMAL"

        # 4. Volume State
        if len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20.0
            cur_vol = volumes[-1]
            vol_ratio = cur_vol / max(avg_vol, 1e-9)
            metrics["vol_ratio"] = round(vol_ratio, 2)
            if vol_ratio > 2.0:
                volume_state = "SURGE"
            elif vol_ratio < 0.5:
                volume_state = "DRY"
            else:
                volume_state = "NORMAL"
        else:
            volume_state = "NORMAL"

        # 5. CVD State & Order Flow State
        cvd_state = "BALANCED"
        order_flow_state = "BALANCED"
        cvd_dq = "VALID"

        if cvd_state_dict:
            imbalance = cvd_state_dict.get("imbalance_ratio", 0.0)
            tvi_5 = cvd_state_dict.get("taker_volume_imbalance_5m", 0.0)
            cvd_dq = cvd_state_dict.get("data_quality", "VALID")
            metrics["cvd_cumulative"] = float(cvd_state_dict.get("cumulative_delta", 0.0))
            metrics["cvd_imbalance"] = float(imbalance)

            if tvi_5 > 0.25:
                order_flow_state = "BUY_DOMINANT"
                cvd_state = "BULLISH_DELTA"
            elif tvi_5 < -0.25:
                order_flow_state = "SELL_DOMINANT"
                cvd_state = "BEARISH_DELTA"

        # 6. Structure & Liquidity States from Detections
        liquidity_state = "NORMAL"
        displacement_state = "NONE"

        if structure_detections:
            for det in structure_detections:
                if det.detector_name == "LIQUIDITY_SWEEP" and det.detected:
                    liquidity_state = "SWEEP_HIGH" if det.direction == "BEARISH" else "SWEEP_LOW"
                elif det.detector_name == "DISPLACEMENT" and det.detected:
                    displacement_state = "IMPULSE_UP" if det.direction == "BULLISH" else "IMPULSE_DOWN"
                elif det.detector_name == "CVD_DIVERGENCE" and det.detected:
                    cvd_state = "DIVERGENT"

        # 7. Session Classification
        session_state = cls.determine_session(timestamp)

        # 8. Overall Confidence Score (0.0 to 1.0)
        confidence_base = 0.8
        if cvd_dq != "VALID":
            confidence_base -= 0.3
        if volatility_state == "COMPRESSED":
            confidence_base -= 0.1
        confidence = round(max(0.2, min(1.0, confidence_base)), 2)

        return MarketState(
            symbol=symbol,
            timestamp=timestamp,
            timeframe=timeframe,
            trend_state=trend_state,
            volatility_state=volatility_state,
            volume_state=volume_state,
            vwap_state=vwap_state,
            cvd_state=cvd_state,
            order_flow_state=order_flow_state,
            liquidity_state=liquidity_state,
            displacement_state=displacement_state,
            session_state=session_state,
            data_quality=cvd_dq,
            confidence=confidence,
            metrics=metrics
        )
