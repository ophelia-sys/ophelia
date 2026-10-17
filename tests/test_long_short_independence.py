import pytest
import json
from unittest.mock import MagicMock, patch

from core.trading_engine import TradingEngine

class MockSettings:
    symbols = ["BTC-USDT"]
    timeframe = "5m"
    ema_fast = 9
    ema_slow = 21

def test_long_short_conflict_resolution(caplog):
    # Setup mock trading engine
    engine = TradingEngine()
    engine.settings = MockSettings()
    
    # Mock probability engine
    engine.probability_engine = MagicMock()
    
    # Mock threshold data
    engine.phase7_thresholds = {
        "BTC-USDT": {
            "threshold": 0.60,
            "short_threshold": 0.55,
            "version": "1.1.0"
        }
    }
    
    # Mock snapshot
    snapshot_mock = MagicMock()
    snapshot_mock.ohlcv = [MagicMock(close=50000.0)]
    engine.institutional_data = MagicMock()
    engine.institutional_data.get_snapshot.return_value = snapshot_mock
    
    # Mock legacy scanner to do nothing
    engine.scanner = MagicMock()
    engine.scanner.scan.return_value = []
    engine.scanner.last_failed_symbols = []
    
    engine.broker = MagicMock()
    engine.broker.get_protected_symbols.return_value = []

    # Case 1: Neither hits threshold
    engine.probability_engine.get_probability.return_value = {
        "probability_long": 0.50,
        "probability_short": 0.50,
        "status": "active"
    }
    
    with caplog.at_level("INFO"):
        engine.process_market()
        
    shadow_log = [rec.message for rec in caplog.records if "SHADOW_JSON" in rec.message][-1]
    log_data = json.loads(shadow_log.split("[SHADOW_JSON] ")[1])
    assert log_data["decision"] == "HOLD"
    
    # Case 2: Only Long hits threshold
    engine.probability_engine.get_probability.return_value = {
        "probability_long": 0.65,
        "probability_short": 0.50,
        "status": "active"
    }
    
    with caplog.at_level("INFO"):
        engine.process_market()
        
    shadow_log = [rec.message for rec in caplog.records if "SHADOW_JSON" in rec.message][-1]
    log_data = json.loads(shadow_log.split("[SHADOW_JSON] ")[1])
    assert log_data["decision"] == "LONG_CANDIDATE"
    
    # Case 3: Only Short hits threshold
    engine.probability_engine.get_probability.return_value = {
        "probability_long": 0.50,
        "probability_short": 0.58,
        "status": "active"
    }
    
    with caplog.at_level("INFO"):
        engine.process_market()
        
    shadow_log = [rec.message for rec in caplog.records if "SHADOW_JSON" in rec.message][-1]
    log_data = json.loads(shadow_log.split("[SHADOW_JSON] ")[1])
    assert log_data["decision"] == "SHORT_CANDIDATE"
    
    # Case 4: Both hit threshold, Long margin > Short margin
    # Long margin = 0.70 - 0.60 = 0.10
    # Short margin = 0.60 - 0.55 = 0.05
    engine.probability_engine.get_probability.return_value = {
        "probability_long": 0.70,
        "probability_short": 0.60,
        "status": "active"
    }
    
    with caplog.at_level("INFO"):
        engine.process_market()
        
    shadow_log = [rec.message for rec in caplog.records if "SHADOW_JSON" in rec.message][-1]
    log_data = json.loads(shadow_log.split("[SHADOW_JSON] ")[1])
    assert log_data["decision"] == "LONG_CANDIDATE"
    assert "CONFLICT RESOLVED" in log_data["reason"]
    
    # Case 5: Both hit threshold, Short margin > Long margin
    # Long margin = 0.65 - 0.60 = 0.05
    # Short margin = 0.65 - 0.55 = 0.10
    engine.probability_engine.get_probability.return_value = {
        "probability_long": 0.65,
        "probability_short": 0.65,
        "status": "active"
    }
    
    with caplog.at_level("INFO"):
        engine.process_market()
        
    shadow_log = [rec.message for rec in caplog.records if "SHADOW_JSON" in rec.message][-1]
    log_data = json.loads(shadow_log.split("[SHADOW_JSON] ")[1])
    assert log_data["decision"] == "SHORT_CANDIDATE"
    assert "CONFLICT RESOLVED" in log_data["reason"]

if __name__ == "__main__":
    pytest.main([__file__])
