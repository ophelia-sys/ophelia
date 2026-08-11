import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd
from core.institutional_math import InstitutionalMathEngine, MathAnalysis
from institutional.institutional_math import InstitutionalMathEngine as InstitutionalMathEngineV3
from institutional.compatibility import V3Translator
from institutional.data.models import MarketDataSnapshot, OHLCVBar
from external.Kronos.provider import KronosProvider
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    math: MathAnalysis
    kronos_direction: str
    kronos_score: float
    overall_market_score: float
    confidence: float
    suggested_leverage: int
    suggested_tp_buffer: float
    approved: bool
    reason: str


class DecisionEngine:
    """
    The Decision Engine evaluates ENTRY OPPORTUNITIES identified by the Strategy Layer.
    It incorporates the Institutional Math Engine, Kronos, and strict rule enforcement
    (e.g., oversized candle exact thresholds) to determine if a trade is APPROVED or REJECTED.
    """

    def __init__(self):
        self.kronos = KronosProvider()

    def _calculate_overall_market_score(self, math_analysis: MathAnalysis, kronos_direction: str, kronos_score: float, signal_cross: str) -> float:
        base_score = 5.0 # Neutral
        if isinstance(math_analysis.volatility_score, (int, float)):
            base_score += (math_analysis.volatility_score - 5.0) * 0.1
        if isinstance(math_analysis.trend_persistence_score, (int, float)):
            base_score += (math_analysis.trend_persistence_score - 5.0) * 0.2
        if isinstance(math_analysis.momentum_score, (int, float)):
            base_score += (math_analysis.momentum_score - 5.0) * 0.2

        if kronos_direction == signal_cross:
            base_score += abs(kronos_score) * 2.0
        elif kronos_direction != "NEUTRAL":
            base_score -= abs(kronos_score) * 2.0

        return round(min(10.0, max(1.0, base_score)), 1)

    def evaluate(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        signal: Dict[str, Any], 
        snapshot: Optional[MarketDataSnapshot] = None
    ) -> MarketAnalysis:
        """
        Evaluate a given entry trigger.
        Returns a MarketAnalysis object containing the final decision and reasoning.
        """
        df_1m = df.copy()
        
        # Resample to 5m
        if not pd.api.types.is_datetime64_any_dtype(df_1m['timestamp']):
            df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
            
        df_temp = df_1m.copy()
        df_temp.set_index("timestamp", inplace=True)
        df_5m = df_temp.resample("5min").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        df_5m.reset_index(inplace=True)
        
        if df_1m["timestamp"].iloc[-1] < df_5m["timestamp"].iloc[-1] + pd.Timedelta(minutes=4):
            df_5m = df_5m.iloc[:-1]

        
        # 1. Fetch Math Analytics
        math_analysis = InstitutionalMathEngine.evaluate(df_1m, df_5m)

        # 2. Fetch Kronos Analysis
        kronos_resp = self.kronos.analyze(symbol)
        kronos_direction = kronos_resp.get("direction", "NEUTRAL")
        kronos_score = kronos_resp.get("score", 0.0)

        # 3. Calculate Overall Market Score (Advisory: 1-10)
        overall_market_score = self._calculate_overall_market_score(
            math_analysis, kronos_direction, kronos_score, signal.get("cross", "")
        )
        confidence = abs(kronos_score)

        # 4. Generate Advisory Suggestions (DO NOT modify active settings automatically)
        suggested_leverage = 20
        suggested_tp_buffer = 0.8
        if overall_market_score > 7.0:
            suggested_leverage = 20 # Can handle standard
        elif overall_market_score < 4.0:
            suggested_leverage = 10 # Suggest lower leverage in bad environment

        if isinstance(math_analysis.volatility_score, (int, float)) and math_analysis.volatility_score > 7.0:
            suggested_tp_buffer = 1.15 # Suggest wider buffer in high volatility

        analysis = MarketAnalysis(
            math=math_analysis,
            kronos_direction=kronos_direction,
            kronos_score=kronos_score,
            overall_market_score=overall_market_score,
            confidence=confidence,
            suggested_leverage=suggested_leverage,
            suggested_tp_buffer=suggested_tp_buffer,
            approved=True,
            reason="Approved by Decision Engine"
        )

        # 5. Evaluate strict candle-size rules
        # Exactly 0.20% and 0.35% must be considered <= threshold
        curr_1m = df_1m.iloc[-1]
        candle_pct_1m = abs(curr_1m["close"] - curr_1m["open"]) / curr_1m["open"] * 100.0
        
        curr_5m = df_5m.iloc[-1]
        candle_pct_5m = abs(curr_5m["close"] - curr_5m["open"]) / curr_5m["open"] * 100.0

        def is_le(val: float, threshold: float) -> bool:
            return val < threshold or math.isclose(val, threshold, rel_tol=1e-9, abs_tol=1e-9)

        # Evaluate 1m limits
        # <= 0.20% -> normal
        # > 0.20% and <= 0.40% -> requires Kronos
        # > 0.40% -> reject
        if not is_le(candle_pct_1m, 0.20):
            if is_le(candle_pct_1m, 0.40):
                # Requires stronger independent evidence (Kronos)
                if not self._check_kronos_override(kronos_direction, kronos_score, signal):
                    analysis.approved = False
                    analysis.reason = "1m oversized candle requires Kronos override > 0.77"
            else:
                analysis.approved = False
                analysis.reason = "1m candle > 0.40% (hard reject)"
                
        # Evaluate 5m limits
        # <= 0.35% -> normal
        # > 0.35% and <= 0.60% -> requires Kronos
        # > 0.60% -> reject
        if analysis.approved and not is_le(candle_pct_5m, 0.35):
            if is_le(candle_pct_5m, 0.60):
                if not self._check_kronos_override(kronos_direction, kronos_score, signal):
                    analysis.approved = False
                    analysis.reason = "5m oversized candle requires Kronos override > 0.77"
            else:
                analysis.approved = False
                analysis.reason = "5m candle > 0.60% (hard reject)"

        # 6. SHADOW MODE V3 EVALUATION
        import copy
        pre_shadow_state = copy.deepcopy(analysis)
        pre_shadow_signal = copy.deepcopy(signal)
        # Cannot deepcopy entire dict due to thread locks in institutional_engine
        engine_state = {k: v for k, v in self.__dict__.items() if k not in ("institutional_engine",)}
        pre_shadow_engine = copy.deepcopy(engine_state)

        try:
            if snapshot is not None:
                from institutional.types import DataQuality
                if getattr(snapshot, "data_quality", None) == DataQuality.VALID:
                    logger.info(f"[SHADOW] Using REAL_INSTITUTIONAL_DATA for {symbol}")
                else:
                    logger.info(f"[SHADOW] Using PARTIAL_INSTITUTIONAL_DATA for {symbol}")
                v3_snapshot = snapshot
            else:
                logger.info(f"[SHADOW] Using SYNTHETIC/LEGACY_INPUT for {symbol}")
                ohlcv = []
                for _, row in df_1m.iterrows():
                    ohlcv.append(OHLCVBar(
                        symbol=symbol,
                        timestamp=int(row['timestamp'].timestamp()),
                        open=row['open'],
                        high=row['high'],
                        low=row['low'],
                        close=row['close'],
                        volume=row['volume'],
                        source="SHADOW"
                    ))
                v3_snapshot = MarketDataSnapshot(
                    symbol=symbol,
                    timestamp=int(df_1m["timestamp"].iloc[-1].timestamp()),
                    timeframe="1m",
                    ohlcv=ohlcv
                )
            v3_engine = InstitutionalMathEngineV3()
            v3_state = v3_engine.analyze(v3_snapshot)
            v3_math_analysis = V3Translator.translate(v3_state)

            shadow_market_score = self._calculate_overall_market_score(
                v3_math_analysis, kronos_direction, kronos_score, signal.get("cross", "")
            )
            logger.info(f"[SHADOW] OMS: Live={overall_market_score} vs V3={shadow_market_score}")

            # Verify no side-effects on live analysis, signal, or engine state
            assert pre_shadow_state == analysis, "P0: V3 Shadow Mode mutated live MarketAnalysis state"
            assert pre_shadow_signal == signal, "P0: V3 Shadow Mode mutated live signal dict"
            assert pre_shadow_engine == self.__dict__, "P0: V3 Shadow Mode mutated DecisionEngine state"
        except Exception as e:
            logger.error(f"[SHADOW ERROR] V3 execution failed: {e}")

        return analysis

    def _check_kronos_override(self, kronos_direction: str, kronos_score: float, signal: Dict[str, Any]) -> bool:
        """
        Kronos High-Confidence Override for Oversized Candles.
        Requires score > +0.77 (LONG) or < -0.77 (SHORT).
        Exactly 0.77 must NOT qualify.
        """
        signal_dir = signal.get("cross", "")
        if signal_dir == "BULLISH" and kronos_direction == "BULLISH" and kronos_score > 0.77:
            return True
        if signal_dir == "BEARISH" and kronos_direction == "BEARISH" and kronos_score < -0.77:
            return True
        return False
