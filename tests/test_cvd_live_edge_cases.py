import pytest
import os
import numpy as np
from datetime import datetime
from institutional.data.models import TradeEvent
from institutional.cvd.live_engine import LiveCVDEngine

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_PATH = os.path.join(BASE_DIR, "PHASE5_3_MODEL_G_FROZEN.pkl")

@pytest.fixture(autouse=True)
def clean_cvd_state():
    state_file = os.path.join(BASE_DIR, "data", "cvd_state_BTCUSDT.json")
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
        except OSError:
            pass
    yield
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
        except OSError:
            pass

def get_base_trade(ts, tid, aggressor):
    return TradeEvent(
        symbol="BTCUSDT", trade_id=tid, timestamp=ts, 
        price=100.0, quantity=1.0, is_buyer_maker=(aggressor=="SELL"), source="bingx"
    )

def test_duplicate_trade_id_filtering():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    ts = 1640995200000
    
    t1 = get_base_trade(ts, "id_1", "BUY")
    t2 = get_base_trade(ts+1, "id_2", "BUY")
    t3 = get_base_trade(ts+2, "id_1", "SELL") # Duplicate ID!
    
    engine.add_trade(t1)
    engine.add_trade(t2)
    engine.add_trade(t3)
    
    # Only 2 trades should be accepted
    assert len(engine.trades) == 2
    assert "id_1" in engine.seen_trade_ids
    assert "id_2" in engine.seen_trade_ids
    
def test_out_of_order_events():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    ts = 1640995200000
    
    t1 = get_base_trade(ts+2000, "id_2", "BUY")
    t2 = get_base_trade(ts+1000, "id_1", "BUY")
    t3 = get_base_trade(ts+3000, "id_3", "BUY")
    
    engine.add_trade(t1)
    engine.add_trade(t2)
    engine.add_trade(t3)
    
    # Internal list is sorted during get_features
    # We will just call a mock get_features to trigger sorting
    # Since we need 300 periods to get actual features, we can just check the internal state after calling it on a dummy timestamp
    T_decision = ts + 300000
    engine.get_features(T_decision)
    
    # They should all be aggregated into the first block
    assert len(engine.history_blocks) == 1
    assert engine.history_blocks[0]['buy_volume'] == 300.0
    
def test_get_probability_missing_base_features():
    engine = LiveCVDEngine("BTCUSDT", MODEL_PATH)
    ts = 1640995200000
    # Add enough blocks to get valid CVD features
    periods = 300
    for p in range(periods):
        block_start = ts + p * 300000
        engine.add_trade(get_base_trade(block_start, f"id_{p}_1", "BUY"))
        engine.add_trade(get_base_trade(block_start+1000, f"id_{p}_2", "SELL"))
        
    T_decision = ts + periods * 300000
    
    # Pass empty base features dict
    prob_output = engine.get_probability({}, T_decision)
    # Should reject due to missing base features expected by Model G
    assert prob_output is None
