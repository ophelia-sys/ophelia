import os
import sys

# Ensure imports work when run from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.phase6.registry import FeatureRegistry, FeatureRecord, PromotionState

def main():
    registry_path = "research/phase6/feature_registry.json"
    if os.path.exists(registry_path):
        os.remove(registry_path)
        
    registry = FeatureRegistry(registry_path)
    
    # 1. FVG Confirmation
    fvg = FeatureRecord(
        feature_id="fvg_confirmation_v1",
        name="FVG Confirmation",
        definition="Fair Value Gap completion confirmed by subsequent candle closure",
        raw_dependencies=["klines"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.PRODUCTION_CANDIDATE
    )
    registry.register_feature(fvg)
    
    # 2. Pool Confirmation
    pool = FeatureRecord(
        feature_id="pool_confirmation_v1",
        name="Liquidity Pool Confirmation",
        definition="Price entering a historical volume node and rejecting",
        raw_dependencies=["klines", "volume_profile"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.PRODUCTION_CANDIDATE
    )
    registry.register_feature(pool)
    
    # 3. Liquidity Sweep
    sweep = FeatureRecord(
        feature_id="liquidity_sweep_v1",
        name="Liquidity Sweep",
        definition="Price wicking through a structural extreme and immediately reversing",
        raw_dependencies=["klines"],
        exchange="Binance UM",
        timeframe="1m",
        status=PromotionState.PRODUCTION_CANDIDATE
    )
    registry.register_feature(sweep)
    
    # 4. Flow-Price Divergence (REJECTED)
    divergence = FeatureRecord(
        feature_id="flow_price_divergence_v1",
        name="Flow-Price Divergence",
        definition="max(0, Z_R - Z_DeltaOI) conditioned on Z_DeltaOI < -tau",
        raw_dependencies=["klines", "open_interest"],
        exchange="Binance UM",
        timeframe="1m",
        experiment_id="exp_037_039",
        dataset_hash="D2E839EDECFAE88B798993CFF9545FA626071EFCB722F266FBE15E0BEA3E20B5",
        status=PromotionState.REJECTED,
        rejection_reason="No demonstrated incremental OOS predictive value after economic costs; original inference additionally contained methodological defects, therefore no statistical promotion claim is permitted."
    )
    registry.register_feature(divergence)
    
    print("Feature registry initialized successfully.")
    print("Registered features:")
    for f_id, rec in registry.features.items():
        print(f" - {f_id} : {rec.status.value}")

if __name__ == "__main__":
    main()
