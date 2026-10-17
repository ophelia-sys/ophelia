import os
import sys

# Ensure imports work when run from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.phase6.registry import FeatureRegistry, PromotionState

def main():
    registry_path = "research/phase6/feature_registry.json"
    if not os.path.exists(registry_path):
        print(f"Registry not found at {registry_path}")
        return

    registry = FeatureRegistry(registry_path)
    
    # Correct FVG
    if "fvg_confirmation_v1" in registry.features:
        fvg = registry.features["fvg_confirmation_v1"]
        fvg.status = PromotionState.REJECTED
        fvg.rejection_reason = "Empirical evidence fails to support feature. Negative expectancy after costs."
        print("Updated FVG to REJECTED")

    # Correct POOL
    if "pool_confirmation_v1" in registry.features:
        pool = registry.features["pool_confirmation_v1"]
        pool.status = PromotionState.REJECTED
        pool.rejection_reason = "Empirical evidence fails to support feature. Negative expectancy after costs."
        print("Updated POOL to REJECTED")

    # Correct SWEEP
    if "liquidity_sweep_v1" in registry.features:
        sweep = registry.features["liquidity_sweep_v1"]
        sweep.status = PromotionState.INCONCLUSIVE
        sweep.rejection_reason = "INCONCLUSIVE / INSUFFICIENT_DATA"
        print("Updated SWEEP to INCONCLUSIVE")

    registry.save()
    print("Registry saved.")

if __name__ == "__main__":
    main()
