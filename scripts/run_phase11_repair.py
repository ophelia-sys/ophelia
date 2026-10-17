"""Ophelia Phase 11: Deterministic Strategy Repair & Regime Discovery Runner.

Executes Phase 11 repair engine over the 61-day Binance dataset.
Persists full results to data/phase11_repair_results.json.
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane.phase11_repair_engine import Phase11StrategyRepairRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_phase11_repair")

def main():
    logger.info("Initializing Phase 11 Deterministic Strategy Repair Runner...")
    parquet_path = "data/processed/binance_um_universe_1m_v2.parquet"
    if not os.path.exists(parquet_path):
        logger.error("Dataset not found at %s", parquet_path)
        sys.exit(1)
        
    runner = Phase11StrategyRepairRunner(parquet_path=parquet_path)
    results = runner.run_analysis()
    
    out_path = "data/phase11_repair_results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    logger.info("Results successfully persisted to %s", out_path)
    
    # Print summary of variants on TEST set
    print("\n" + "="*80)
    print("PHASE 11: DETERMINISTIC STRATEGY REPAIR - TEST SET AUDIT")
    print("="*80)
    test_base = results["baseline_performance"]["test"]
    print(f"BASELINE A (TEST): N={test_base['count']}, WR={test_base['win_rate']}%, Gross R={test_base['gross_r']}, Net R={test_base['net_r']}, Mean R={test_base['mean_r']}")
    print("-" * 80)
    print(f"{'Variant':<25} | {'N (Test)':<8} | {'Win Rate':<8} | {'Net R':<8} | {'Mean R':<8} | {'Delta R':<8} | {'Status'}")
    print("-" * 80)
    
    variants = results["strategy_variants"]
    mt_tests = {t["variant"]: t for t in results["multiple_testing_variants"]}
    
    for vname, vdata in variants.items():
        if vname == "A_BASELINE":
            continue
        tstats = vdata["test"]
        mt = mt_tests.get(vname, {})
        delta = mt.get("delta_mean_r", round(tstats["mean_r"] - test_base["mean_r"], 3))
        status = mt.get("status", "EVALUATED")
        print(f"{vname:<25} | {tstats['count']:<8} | {tstats['win_rate']:<7}% | {tstats['net_r']:<8} | {tstats['mean_r']:<8} | {delta:<+8} | {status}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
