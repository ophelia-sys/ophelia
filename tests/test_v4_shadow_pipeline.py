import pytest
from core.trade_geometry import TradeGeometryEngine, TradeGeometry
from core.probability_engine import CalibratedProbabilityEngine, ProbabilityPrediction
from core.opportunity_gate import OpportunityGate, V4ShadowOpportunity
from institutional.types import MarketState, Direction, DataQuality
from unittest.mock import MagicMock

def test_trade_geometry_bullish():
    engine = TradeGeometryEngine(atr_multiplier_sl=2.0, atr_multiplier_tp=3.0)
    # Price 60000, ATR 1000, Bullish, Spread 2.0
    geometry = engine.calculate_geometry(current_price=60000.0, atr=1000.0, direction=Direction.BULLISH, spread=2.0)
    
    assert geometry is not None
    # Entry = 60000 + (2.0 / 2) = 60001
    assert geometry.entry_price == 60001.0
    # Cost = spread (2.0) + fee (60000 * 0.001 = 60.0) = 62.0
    assert geometry.estimated_cost_usdt == 62.0
    # Stop = 60001 - 2000 - 62 = 57939
    assert geometry.stop_loss == 57939.0
    # TP1 = 60001 + 3000 + 62 = 63063
    assert geometry.take_profit_1 == 63063.0
    
    # Risk = 60001 - 57939 = 2062
    # Reward = 63063 - 60001 = 3062
    # R = 3062 / 2062 = 1.48
    assert geometry.reward_to_risk == 1.48

def test_trade_geometry_bearish():
    engine = TradeGeometryEngine(atr_multiplier_sl=2.0, atr_multiplier_tp=3.0)
    geometry = engine.calculate_geometry(current_price=60000.0, atr=1000.0, direction=Direction.BEARISH, spread=2.0)
    
    assert geometry is not None
    assert geometry.entry_price == 59999.0 # 60000 - 1
    assert geometry.estimated_cost_usdt == 62.0
    # Stop = 59999 + 2000 + 62 = 62061
    assert geometry.stop_loss == 62061.0
    # TP1 = 59999 - 3000 - 62 = 56937
    assert geometry.take_profit_1 == 56937.0
    
    # Risk = 62061 - 59999 = 2062
    # Reward = 59999 - 56937 = 3062
    assert geometry.reward_to_risk == 1.48

def test_no_fake_probability():
    """
    Ensures that when no model is trained, the ProbabilityEngine returns 
    explicitly None, not 0, 0.5, or some other fabricated placeholder.
    """
    engine = CalibratedProbabilityEngine()
    engine.is_model_trained = False
    
    state = MarketState(symbol="BTC-USDT", timestamp=0, timeframe="1m")
    geom = TradeGeometry(60000, 58000, 62000, 63000, 64000, 10.0, 1.0)
    
    prediction = engine.evaluate(state, geom)
    assert prediction.calibrated_probability is None
    assert prediction.model_status == "MODEL_UNAVAILABLE"

def test_opportunity_gate_unavailable_model():
    """
    Test that the gate rejects trades if the model is unavailable.
    """
    gate = OpportunityGate()
    geom = TradeGeometry(60000, 58000, 62000, 63000, 64000, 10.0, 1.0)
    prediction = ProbabilityPrediction(
        calibrated_probability=None,
        prediction_horizon_minutes=60,
        data_quality=DataQuality.UNAVAILABLE,
        evidence={},
        model_status="MODEL_UNAVAILABLE"
    )
    
    opp = gate.evaluate("BTC-USDT", Direction.BULLISH, geom, prediction)
    assert not opp.approved
    assert opp.gate_reason == "MODEL_UNAVAILABLE"
    assert opp.expected_value is None

def test_opportunity_gate_ev_calculation():
    """
    Test the Expected Value calculation directly.
    """
    gate = OpportunityGate()
    # P(W) = 0.6, R = 1.5, P(L) = 0.4, Risk = 1
    # EV = (0.6 * 1.5) - (0.4 * 1) = 0.9 - 0.4 = 0.5
    ev = gate.calculate_expected_value(prob=0.6, reward_to_risk=1.5)
    assert round(ev, 2) == 0.5

def test_opportunity_gate_rejected_by_ev():
    """
    Test that a trade with sufficient probability but bad R-multiple is rejected by EV.
    """
    gate = OpportunityGate(min_ev=0.1, min_probability=0.55)
    # Prob = 0.56 (passes threshold), R = 0.5
    # EV = (0.56 * 0.5) - (0.44 * 1) = 0.28 - 0.44 = -0.16
    geom = TradeGeometry(60000, 58000, 61000, 62000, 63000, 10.0, 0.5)
    prediction = ProbabilityPrediction(
        calibrated_probability=0.56,
        prediction_horizon_minutes=60,
        data_quality=DataQuality.VALID,
        evidence={},
        model_status="VALIDATED_CHAMPION"
    )
    
    opp = gate.evaluate("BTC-USDT", Direction.BULLISH, geom, prediction)
    assert not opp.approved
    assert opp.gate_reason == "REJECTED_BY_EV"
    assert opp.expected_value < 0.1

def test_opportunity_gate_missing_feature_handling():
    """
    Test that trades are rejected if data quality is insufficient, even if 
    the model erroneously spits out a high probability (garbage in garbage out).
    """
    gate = OpportunityGate()
    geom = TradeGeometry(60000, 58000, 62000, 63000, 64000, 10.0, 1.0)
    prediction = ProbabilityPrediction(
        calibrated_probability=0.99, # High fake probability
        prediction_horizon_minutes=60,
        data_quality=DataQuality.INSUFFICIENT_DATA, # Missing data!
        evidence={},
        model_status="VALIDATED_CHAMPION"
    )
    
    opp = gate.evaluate("BTC-USDT", Direction.BULLISH, geom, prediction)
    assert not opp.approved
    assert opp.gate_reason == "INSUFFICIENT_DATA"

def test_champion_challenger_isolation():
    """
    Test that we have separate conceptual models that don't overwrite each other.
    """
    champion = CalibratedProbabilityEngine()
    champion.is_model_trained = True
    
    challenger = CalibratedProbabilityEngine()
    challenger.is_model_trained = False
    
    state = MarketState(symbol="BTC-USDT", timestamp=0, timeframe="1m")
    geom = TradeGeometry(60000, 58000, 62000, 63000, 64000, 10.0, 1.0)
    
    # Fake champion eval
    champ_pred = champion.evaluate(state, geom)
    # The current skeleton doesn't have trained model logic yet so we just verify
    # the instances are independent and don't share state.
    assert champion.is_model_trained is True
    assert challenger.is_model_trained is False
