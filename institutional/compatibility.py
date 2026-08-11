import math
from typing import Optional
from institutional.types import MarketState, DataQuality
from core.institutional_math import MathAnalysis

class V3Translator:
    """
    Translates V3 MarketState into the legacy MathAnalysis contract.
    This provides mathematical compatibility for the DecisionEngine shadow mode.
    
    SHADOW TRANSFORMATION ONLY:
    The V3 momentum z-score -> 0-10 transformation is uncalibrated and observational.
    Canonical OFI remains UNAVAILABLE and no proxy is assigned.
    """

    @staticmethod
    def translate(state: MarketState) -> MathAnalysis:
        volatility = "UNAVAILABLE"
        momentum = "UNAVAILABLE"
        trend = "UNAVAILABLE"

        # Volatility: V3 Advisory Score (1-10 integer) -> 0-10 float
        if state.volatility_score is not None:
            volatility = float(state.volatility_score)

        # Momentum: V3 Robust Z-Score -> 0-10 float
        # Typical Z-score is -3 to +3. We map this to 0-10 by multiplying by 3.33.
        # Uncalibrated shadow transformation.
        if state.momentum_score is not None and not math.isnan(state.momentum_score):
            momentum_raw = abs(float(state.momentum_score)) * 3.33
            momentum = round(min(10.0, momentum_raw), 1)

        # Trend Persistence: V3 directional persistence (Efficiency Ratio 0-1) -> 0-10 float
        if state.trend_persistence is not None and not math.isnan(state.trend_persistence):
            trend_raw = float(state.trend_persistence) * 10.0
            trend = round(min(10.0, max(0.0, trend_raw)), 1)

        # Handle INSUFFICIENT_DATA properly
        if state.data_quality == DataQuality.INSUFFICIENT_DATA:
            volatility = "UNAVAILABLE"
            momentum = "UNAVAILABLE"
            trend = "UNAVAILABLE"

        return MathAnalysis(
            volatility_score=volatility,
            momentum_score=momentum,
            trend_persistence_score=trend,
            liquidity_score="UNAVAILABLE",
            market_regime=state.regime if state.regime else "UNKNOWN",
            oi_state=state.oi_state,
            funding_state=state.funding_state,
            liquidation_state=state.liquidation_state,
            order_flow_state=state.order_flow_state,
            structural_break_state=str(state.structural_break) if state.structural_break is not None else "UNAVAILABLE"
        )
