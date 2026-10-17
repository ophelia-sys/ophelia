import pytest
import os
import time
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from institutional.cvd.paper_signal_engine import PaperSignalEngine, PaperSignal
from institutional.data.engine import InstitutionalDataEngine
from institutional.types import Direction
from institutional.data.models import OHLCVBar, TradeEvent
from research.experiments.exp_phase5_3_ml_ablation import engineer_cvd_features

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_PATH = os.path.join(BASE_DIR, "PHASE5_3_MODEL_G_FROZEN.pkl")

class MockSnapshot:
    def __init__(self, ohlcv):
        self.ohlcv_history = ohlcv

@pytest.fixture
def mock_inst_data():
    inst = MagicMock(spec=InstitutionalDataEngine)
    inst._trades = {}
    inst._lock = MagicMock()
    import threading
    inst._lock = threading.Lock()
    return inst

@pytest.fixture
def mock_telegram():
    return MagicMock()

def generate_ohlcv_history(T_decision, count=60):
    bars = []
    start = T_decision - (count * 300000)
    for i in range(count):
        bars.append(OHLCVBar(
            symbol="BTCUSDT",
            timestamp=start + (i * 300000),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000.0,
            source="mock"
        ))
    return bars

def test_paper_signal_valid_inference(mock_inst_data, mock_telegram):
    T_decision = 1640995200000 
    
    mock_inst_data.get_snapshot.return_value = MockSnapshot(generate_ohlcv_history(T_decision, count=60))
    mock_inst_data._trades["BTCUSDT"] = [
        TradeEvent("BTCUSDT", "1", T_decision - 1000, 100.5, 10.0, False, "mock"),
        TradeEvent("BTCUSDT", "2", T_decision - 500, 100.5, 5.0, True, "mock")
    ]
    
    engine = PaperSignalEngine(mock_inst_data, mock_telegram, model_path=MODEL_PATH)
    engine._write_log = MagicMock() 
    
    with patch("institutional.cvd.live_engine.LiveCVDEngine.get_probability") as mock_prob:
        mock_prob.return_value = {
            'probability': 0.75, 'cvd_feature_values': {'cvd_delta_5m': 1.0}, 'data_quality': 'VALID', 
            'model_version': '1.0', 'feature_registry_version': 'test'
        }
        engine.evaluate("BTCUSDT", T_decision + 100) 
    
    engine._write_log.assert_called_once()
    record = engine._write_log.call_args[0][0]
    
    assert record["suppressed"] is False
    assert record["decision_timestamp"] == T_decision
    assert record["symbol"] == "BTCUSDT"
    assert "predicted_probability" in record
    assert record["model_class"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert record["data_quality"] == "VALID"
    assert "geometry_status" in record
    
    mock_telegram.notify.assert_called_once()
    msg = mock_telegram.notify.call_args[0][0]
    assert "OPHELIA PAPER SIGNAL" in msg
    assert "predicted_probability" not in msg.lower() 
    assert "Predicted probability" in msg
    assert "PAPER / OBSERVATION ONLY" in msg

def test_missing_feature_rejection(mock_inst_data):
    T_decision = 1640995200000
    mock_inst_data.get_snapshot.return_value = MockSnapshot([])
    engine = PaperSignalEngine(mock_inst_data, None, model_path=MODEL_PATH)
    engine._write_log = MagicMock()
    
    engine.evaluate("BTCUSDT", T_decision)
    record = engine._write_log.call_args[0][0]
    assert record["suppressed"] is True
    assert record["reason"] == "INSUFFICIENT_HISTORY"

def test_stale_data_rejection(mock_inst_data):
    T_decision = 1640995200000
    history = generate_ohlcv_history(T_decision - 300000, count=60)
    mock_inst_data.get_snapshot.return_value = MockSnapshot(history)
    engine = PaperSignalEngine(mock_inst_data, None, model_path=MODEL_PATH)
    engine._write_log = MagicMock()
    
    engine.evaluate("BTCUSDT", T_decision)
    record = engine._write_log.call_args[0][0]
    assert record["suppressed"] is True
    assert record["reason"] == "STALE_DATA"

def test_duplicate_decision_suppression(mock_inst_data):
    T_decision = 1640995200000
    mock_inst_data.get_snapshot.return_value = MockSnapshot(generate_ohlcv_history(T_decision, count=60))
    engine = PaperSignalEngine(mock_inst_data, None, model_path=MODEL_PATH)
    engine._write_log = MagicMock()
    
    with patch("institutional.cvd.live_engine.LiveCVDEngine.get_probability") as mock_prob:
        mock_prob.return_value = {
            'probability': 0.75, 'cvd_feature_values': {}, 'data_quality': 'VALID', 
            'model_version': '1.0', 'feature_registry_version': 'test'
        }
        engine.evaluate("BTCUSDT", T_decision)
        assert engine._write_log.call_count == 1
        assert engine._write_log.call_args[0][0]["suppressed"] is False
        
        engine.evaluate("BTCUSDT", T_decision + 1000)
        assert engine._write_log.call_count == 1

def test_probability_classification(mock_inst_data):
    T_decision = 1640995200000
    mock_inst_data.get_snapshot.return_value = MockSnapshot(generate_ohlcv_history(T_decision, count=60))
    engine = PaperSignalEngine(mock_inst_data, None, model_path=MODEL_PATH)
    engine._write_log = MagicMock()
    
    with patch("institutional.cvd.live_engine.LiveCVDEngine.get_probability") as mock_prob:
        mock_prob.return_value = {
            'probability': 0.51, 'cvd_feature_values': {}, 'data_quality': 'VALID', 
            'model_version': '1.0', 'feature_registry_version': 'test'
        }
        engine.evaluate("BTCUSDT", T_decision)
        assert engine._write_log.call_args[0][0]["model_class"] == "BULLISH"
        
        engine.evaluated_decisions.clear()
        mock_prob.return_value['probability'] = 0.50
        engine.evaluate("BTCUSDT", T_decision)
        assert engine._write_log.call_args[0][0]["model_class"] == "NEUTRAL"
        
        engine.evaluated_decisions.clear()
        mock_prob.return_value['probability'] = 0.49
        engine.evaluate("BTCUSDT", T_decision)
        assert engine._write_log.call_args[0][0]["model_class"] == "BEARISH"

def test_nan_rejection(mock_inst_data):
    T_decision = 1640995200000
    mock_inst_data.get_snapshot.return_value = MockSnapshot(generate_ohlcv_history(T_decision, count=60))
    engine = PaperSignalEngine(mock_inst_data, None, model_path=MODEL_PATH)
    engine._write_log = MagicMock()
    
    with patch("research.experiments.exp_phase5_1_baseline.Phase5BaselineExperiment.engineer_features") as mock_feat:
        df = pd.DataFrame([{'timestamp': pd.to_datetime(T_decision - 300000, unit='ms'), 'atr_14': np.nan}])
        mock_feat.return_value = df
        
        engine.evaluate("BTCUSDT", T_decision)
        record = engine._write_log.call_args[0][0]
        assert record["suppressed"] is True
        assert record["reason"] == "MISSING_FEATURE_OR_NAN"

def test_zero_execution_side_effects():
    import ast
    with open(os.path.join(BASE_DIR, "institutional", "cvd", "paper_signal_engine.py"), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
        
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
                assert name not in ["place_order", "cancel_order", "process_signal"], f"Found execution method {name}"
            elif isinstance(node.func, ast.Name):
                name = node.func.id
                assert name not in ["place_order", "cancel_order"], f"Found execution method {name}"
