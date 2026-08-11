from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np

from indicators.anti_chop import (
    calculate_er, calculate_rvol, calculate_nes, calculate_nslope, calculate_bbs
)

@dataclass
class MathAnalysis:
    volatility_score: float | str
    momentum_score: float | str
    trend_persistence_score: float | str
    liquidity_score: float | str
    market_regime: str
    oi_state: str
    funding_state: str
    liquidation_state: str
    order_flow_state: str
    structural_break_state: str


class InstitutionalMathEngine:
    """
    Produces analytical outputs reflecting the structural state of the market.
    It does not place orders or make final trading decisions.
    """

    @classmethod
    def evaluate(cls, df_1m: pd.DataFrame, df_5m: Optional[pd.DataFrame] = None) -> MathAnalysis:
        if len(df_1m) < 200:
            return cls._empty_analysis()

        # We need the most recent row that is fully formed
        # Typically the scanner provides completed candles, so we look at -1 or -2 depending on implementation,
        # but to keep it self-contained we just take the last row of indicators.
        
        # Calculate base indicators
        er10 = calculate_er(df_1m, 10).iloc[-1]
        rvol20 = calculate_rvol(df_1m, 20).iloc[-1]
        nslope = calculate_nslope(df_1m).iloc[-1]
        nes = calculate_nes(df_1m).iloc[-1]
        bbs = calculate_bbs(df_1m).iloc[-1]

        # 1. Trend Persistence (0-10)
        # Based on Efficiency Ratio (0 to 1). 
        # er10 = 1.0 -> score 10.
        trend_persistence = min(10.0, max(0.0, er10 * 10.0))

        # 2. Momentum Score (0-10)
        # Based on Normalized EMA Slope and Spread
        # Typical nslope ranges -0.3 to 0.3
        momentum_magnitude = abs(nslope) * 10.0 + abs(nes) * 5.0
        momentum = min(10.0, max(0.0, momentum_magnitude))

        # 3. Volatility Score (0-10)
        # Based on Bollinger Band Squeeze (BBS) and RVOL
        # High BBS + High RVOL = High Volatility
        vol_magnitude = (bbs * 5.0) + (rvol20 * 2.0)
        volatility = min(10.0, max(0.0, vol_magnitude))

        # Market Regime
        if er10 > 0.6:
            regime = "TRENDING_STRONG"
        elif er10 > 0.4:
            regime = "TRENDING_NORMAL"
        else:
            regime = "CHOPPY"

        return MathAnalysis(
            volatility_score=round(volatility, 1),
            momentum_score=round(momentum, 1),
            trend_persistence_score=round(trend_persistence, 1),
            liquidity_score="UNAVAILABLE",
            market_regime=regime,
            oi_state="UNAVAILABLE",
            funding_state="UNAVAILABLE",
            liquidation_state="UNAVAILABLE",
            order_flow_state="UNAVAILABLE",
            structural_break_state="UNAVAILABLE"
        )

    @classmethod
    def _empty_analysis(cls) -> MathAnalysis:
        return MathAnalysis(
            volatility_score="UNAVAILABLE",
            momentum_score="UNAVAILABLE",
            trend_persistence_score="UNAVAILABLE",
            liquidity_score="UNAVAILABLE",
            market_regime="UNKNOWN",
            oi_state="UNAVAILABLE",
            funding_state="UNAVAILABLE",
            liquidation_state="UNAVAILABLE",
            order_flow_state="UNAVAILABLE",
            structural_break_state="UNAVAILABLE"
        )
