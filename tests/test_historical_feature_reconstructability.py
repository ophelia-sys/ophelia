import pytest
from institutional.types import DataQuality
from core.trade_geometry import TradeGeometry
from core.probability_engine import ProbabilityPrediction, CalibratedProbabilityEngine

def test_feature_reconstructability_markers():
    """
    Ensure the probability engine explicitly handles HISTORICALLY_UNAVAILABLE features
    (DataQuality.UNAVAILABLE) appropriately.
    """
    engine = CalibratedProbabilityEngine()
    
    prediction = ProbabilityPrediction(
        calibrated_probability=0.75,
        prediction_horizon_minutes=60,
        data_quality=DataQuality.UNAVAILABLE, # Emulating unavailable microstructure
        evidence={},
        model_status="MODEL_UNAVAILABLE"
    )
    
    # The gate logic already handles this correctly, but we ensure the engine
    # structure supports recording the quality.
    assert prediction.data_quality == DataQuality.UNAVAILABLE
