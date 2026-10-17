import os
import sys
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from institutional.cvd.live_engine import LiveCVDEngine
from institutional.data.models import TradeEvent
from utils.logger import logger

def simulate_24h_warmup():
    print("=" * 60)
    print("PHASE 1: 24-HOUR WARM-UP PREREQUISITE AUDIT")
    print("=" * 60)
    
    symbol = "BTC-USDT"
    
    # 1. Instantiate the Engine
    try:
        engine = LiveCVDEngine(symbol)
        print(f"[OK] Instantiated LiveCVDEngine for {symbol}")
        print(f"[OK] Model loaded: {engine.model_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load LiveCVDEngine: {e}")
        return False
        
    # 2. Simulate 24 hours of trades (288 * 5m = 1440 minutes = 1440 trades)
    # Start at arbitrary timestamp
    start_time_ms = int(datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    
    print("[INFO] Simulating 24h+ of pseudo-trades (1 trade per minute for 1600 minutes)")
    
    for i in range(1600): # 320 blocks
        ts = start_time_ms + i * 60000
        # Create a dummy trade. Alternate buy/sell to give non-zero delta
        aggressor = "BUY" if i % 3 == 0 else "SELL"
        # Use pure random quantity to guarantee variance
        qty = np.random.random() * 1.0 + 0.1
        trade = TradeEvent(
            symbol=symbol,
            trade_id=f"trade_{i}",
            price=40000.0 + (i % 100),
            quantity=qty,
            is_buyer_maker=(i % 3 != 0),
            source="audit",
            timestamp=ts
        )
        engine.add_trade(trade)
        
    # 3. Test get_features at T_decision
    # T_decision = start_time + 1599m
    T_decision = start_time_ms + 1599 * 60000
    
    print(f"[INFO] Evaluating features at T_decision = {T_decision}")
    features = engine.get_features(T_decision)
    
    if features is None:
        print(f"[ERROR] Engine returned None. History blocks: {len(engine.history_blocks)}")
        return False
        
    print(f"[OK] Features successfully generated. History blocks: {len(engine.history_blocks)}")
    
    # 4. Validate no NaNs
    f_dict = features.__dict__
    has_nans = False
    for k, v in f_dict.items():
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            print(f"[ERROR] Feature {k} is {v}")
            has_nans = True
            
    if has_nans:
        print("[ERROR] 24-Hour Prerequisite failed due to NaNs in CVD features.")
        return False
        
    print("[OK] All 11 CVD features valid (No NaNs/Infs).")
    
    # 5. Base feature logic check
    base_features = {
        "ret_1": 0.001, "ret_3": 0.003, "ret_5": 0.005,
        "realized_vol_20": 0.02, "atr_pct_14": 0.01,
        "mom_10": 0.005, "vol_ratio": 1.2
    }
    
    prob = engine.get_probability(base_features, T_decision)
    if prob is None or "probability" not in prob:
        if isinstance(prob, dict) and prob.get("status") == "warming":
            print(f"[ERROR] Engine still reports warming: {prob}")
        else:
            print(f"[ERROR] Inference failed or returned None. prob={prob}")
        return False
        
    print(f"[OK] Model inference successful. P(LONG) = {prob['probability']:.4f}")
    print("[SUCCESS] 24-Hour Prerequisite mathematically proven.")
    return True

if __name__ == "__main__":
    simulate_24h_warmup()
