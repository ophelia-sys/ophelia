"""
Kronos Institutional Advisory Engine for Ophelia.
Layer: control_plane/kronos
Contract: Strictly ADVISORY-ONLY. Zero execution authority.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List
from institutional.market_state import MarketState


@dataclass(frozen=True)
class KronosAdvisoryReport:
    """Read-only advisory assessment from Kronos."""
    symbol: str
    timestamp: int
    timeframe: str
    regime_assessment: str
    sentiment: str  # "BULLISH", "BEARISH", "NEUTRAL"
    volatility_assessment: str
    order_flow_assessment: str
    risk_warnings: List[str]
    confidence: float
    advisory_notice: str = "[KRONOS ADVISORY ONLY - NO EXECUTION AUTHORITY]"
    is_advisory: bool = True
    execution_authority: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KronosAdvisor:
    """
    Kronos Market Intelligence and Pre-Trade Advisory Service.
    Evaluates institutional MarketState snapshots to generate context commentary.
    CANNOT place orders, modify positions, or bypass RiskManager.
    """

    @classmethod
    def evaluate_market_state(cls, market_state: MarketState) -> KronosAdvisoryReport:
        """
        Analyze a MarketState snapshot and generate an advisory intelligence summary.
        """
        risk_warnings: List[str] = []

        # 1. Volatility warnings
        if market_state.volatility_state == "EXPANDED":
            risk_warnings.append("High volatility expansion (EXPANDED) detected: expect wider slippage and aggressive wicks.")
        elif market_state.volatility_state == "COMPRESSED":
            risk_warnings.append("Severe volatility compression / squeeze: breakout imminent, avoid mid-range entries.")

        # 2. VWAP and Chop warnings
        if market_state.vwap_state == "CHOP":
            risk_warnings.append("Price oscillating within VWAP noise corridor; high chop risk.")

        # 3. Order flow & CVD Divergence
        if market_state.cvd_state == "DIVERGENT":
            risk_warnings.append("CVD vs price divergence detected: momentum exhaustion warning.")

        # 4. Liquidity sweeps
        if market_state.liquidity_state.startswith("SWEEP"):
            risk_warnings.append(f"Recent liquidity sweep observed ({market_state.liquidity_state}): potential reversal area.")

        # 5. Data quality check
        if market_state.data_quality != "VALID":
            risk_warnings.append(f"Feed data quality is {market_state.data_quality}: reduce confidence.")

        # Sentiment synthesis
        sentiment = "NEUTRAL"
        if market_state.trend_state == "BULLISH" and market_state.vwap_state == "CLEAR_ABOVE":
            sentiment = "BULLISH"
        elif market_state.trend_state == "BEARISH" and market_state.vwap_state == "CLEAR_BELOW":
            sentiment = "BEARISH"

        regime = f"{market_state.session_state} Session | {market_state.trend_state} Trend | {market_state.vwap_state}"

        return KronosAdvisoryReport(
            symbol=market_state.symbol,
            timestamp=market_state.timestamp,
            timeframe=market_state.timeframe,
            regime_assessment=regime,
            sentiment=sentiment,
            volatility_assessment=f"Volatility is {market_state.volatility_state}",
            order_flow_assessment=f"Order flow is {market_state.order_flow_state} (CVD: {market_state.cvd_state})",
            risk_warnings=risk_warnings,
            confidence=market_state.confidence,
            is_advisory=True,
            execution_authority=False
        )

    @classmethod
    def execute_order(cls, *args, **kwargs):
        """Strict safety assertion: Kronos is forbidden from executing or proposing orders."""
        raise PermissionError(
            "CRITICAL SAFETY VIOLATION: Kronos is strictly advisory-only and cannot execute or propose orders."
        )

    @classmethod
    def authorize_trade(cls, *args, **kwargs):
        """Strict safety assertion: Kronos cannot authorize or bypass risk checks."""
        raise PermissionError(
            "CRITICAL SAFETY VIOLATION: Kronos cannot authorize trades or bypass risk checks."
        )
