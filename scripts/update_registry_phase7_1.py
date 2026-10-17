import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.phase6.registry import FeatureRegistry, FeatureRecord, PromotionState

def update_registry():
    registry = FeatureRegistry()
    
    # 1. BOOK_SLOPE
    registry.register_feature(FeatureRecord(
        feature_id="book_slope",
        name="Book Slope",
        definition="Bid Slope - Ask Slope / Bid Slope + Ask Slope (Requires L2 Depth)",
        raw_dependencies=["depth_snapshots"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.UNTESTED,
        rejection_reason="DATA_UNAVAILABLE_FOR_HISTORICAL_EVALUATION"
    ))
    
    # 2. TRUE_QUEUE_IMBALANCE
    registry.register_feature(FeatureRecord(
        feature_id="true_queue_imbalance",
        name="True Queue Imbalance",
        definition="Imbalance of sizes at the best bid and ask (Requires BBA/L2 Depth)",
        raw_dependencies=["book_ticker", "depth_snapshots"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.UNTESTED,
        rejection_reason="DATA_UNAVAILABLE_FOR_HISTORICAL_EVALUATION"
    ))
    
    # 3. TRADE_AGGRESSIVENESS_PROXY
    registry.register_feature(FeatureRecord(
        feature_id="trade_aggressiveness_proxy_v1",
        name="Trade Aggressiveness Proxy",
        definition="Delta V / Volume (Aggressive Buy Vol - Aggressive Sell Vol / Total Vol)",
        raw_dependencies=["trades"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.REJECTED,
        rejection_reason="Tested in Phase 7. Showed statistical association but failed to overcome standard taker costs. Not true queue imbalance."
    ))
    
    # 4. EVIDENCE_ENTROPY
    registry.register_feature(FeatureRecord(
        feature_id="evidence_entropy_v1",
        name="Evidence Entropy",
        definition="Shannon entropy of cross-sectional feature probabilities",
        raw_dependencies=["klines"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.REJECTED,
        rejection_reason="Failed incrementality over constituent features."
    ))

    # 5. MICROPRICE
    registry.register_feature(FeatureRecord(
        feature_id="microprice",
        name="Microprice",
        definition="Volume-weighted mid price",
        raw_dependencies=["book_ticker"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.UNTESTED,
        rejection_reason="DATA_UNAVAILABLE_FOR_HISTORICAL_EVALUATION"
    ))

    # 6. DEPTH_IMBALANCE
    registry.register_feature(FeatureRecord(
        feature_id="depth_imbalance",
        name="Depth Imbalance",
        definition="Imbalance of sizes up to N levels deep",
        raw_dependencies=["depth_snapshots"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.UNTESTED,
        rejection_reason="DATA_UNAVAILABLE_FOR_HISTORICAL_EVALUATION"
    ))
    
    print("Registry updated successfully.")

if __name__ == "__main__":
    update_registry()
