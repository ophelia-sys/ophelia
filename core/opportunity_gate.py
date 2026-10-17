from dataclasses import dataclass
from typing import Optional
from core.trade_geometry import TradeGeometry
from core.probability_engine import ProbabilityPrediction
from institutional.types import Direction, DataQuality

@dataclass
class V4ShadowOpportunity:
    symbol: str
    direction: Direction
    geometry: TradeGeometry
    prediction: ProbabilityPrediction
    expected_value: Optional[float]
    approved: bool
    gate_reason: str

class OpportunityGate:
    def __init__(self, min_ev: float = 0.1, min_probability: float = 0.55):
        self.min_ev = min_ev
        self.min_probability = min_probability
        
    def calculate_expected_value(self, prob: float, reward_to_risk: float) -> float:
        """
        EV = (P(W) * R) - (P(L) * 1)
        Note: The spread/fee costs are already accounted for inside the R-multiple
        calculated by TradeGeometryEngine.
        """
        p_loss = 1.0 - prob
        return (prob * reward_to_risk) - (p_loss * 1.0)
        
    def evaluate(self, symbol: str, direction: Direction, geometry: TradeGeometry, prediction: ProbabilityPrediction) -> V4ShadowOpportunity:
        
        # 1. Check Model Availability
        if prediction.calibrated_probability is None or prediction.model_status == "MODEL_UNAVAILABLE":
            return V4ShadowOpportunity(
                symbol=symbol,
                direction=direction,
                geometry=geometry,
                prediction=prediction,
                expected_value=None,
                approved=False,
                gate_reason="MODEL_UNAVAILABLE"
            )
            
        ev = self.calculate_expected_value(prediction.calibrated_probability, geometry.reward_to_risk)
        
        # 2. Check Data Quality
        if prediction.data_quality in (DataQuality.UNAVAILABLE, DataQuality.INSUFFICIENT_DATA, DataQuality.INVALID):
            return V4ShadowOpportunity(
                symbol=symbol,
                direction=direction,
                geometry=geometry,
                prediction=prediction,
                expected_value=ev,
                approved=False,
                gate_reason="INSUFFICIENT_DATA"
            )
            
        # 3. Check Base Probability
        if prediction.calibrated_probability < self.min_probability:
            return V4ShadowOpportunity(
                symbol=symbol,
                direction=direction,
                geometry=geometry,
                prediction=prediction,
                expected_value=ev,
                approved=False,
                gate_reason="LOW_PROBABILITY"
            )
            
        # 4. Check Expected Value
        if ev < self.min_ev:
            return V4ShadowOpportunity(
                symbol=symbol,
                direction=direction,
                geometry=geometry,
                prediction=prediction,
                expected_value=ev,
                approved=False,
                gate_reason="REJECTED_BY_EV"
            )
            
        return V4ShadowOpportunity(
            symbol=symbol,
            direction=direction,
            geometry=geometry,
            prediction=prediction,
            expected_value=ev,
            approved=True,
            gate_reason="APPROVED"
        )
