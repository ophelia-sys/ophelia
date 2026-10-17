"""Ophelia Phase 11.5: HTF Regime & Trade Management Research Runner.

Executes Phase 11.5 HTF engine over the 61-day Binance dataset.
Persists full results to data/phase11_5_htf_results.json.
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane.phase11_5_htf_engine import Phase11_5HTFEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_phase11_5_htf_research")

def main():
    logger.info("Initializing Phase 11.5 HTF Regime & Trade Management Research...")
    parquet_path = "data/processed/binance_um_universe_1m_v2.parquet"
    if not os.path.exists(parquet_path):
        logger.error("Dataset not found at %s", parquet_path)
        sys.exit(1)
        
    engine = Phase11_5HTFEngine(parquet_path=parquet_path)
    results = engine.run_research()
    
    out_path = "data/phase11_5_htf_results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    logger.info("Results successfully persisted to %s", out_path)
    
    # Print formatted comparative matrix
    print("\n" + "="*95)
    print("PHASE 11.5: HTF REGIME & TRADE MANAGEMENT COMPARATIVE MATRIX (TEST SET OOS)")
    print("="*95)
    print(f"{'Strategy Configuration':<30} | {'N':<6} | {'Win Rate':<9} | {'Gross R':<9} | {'Net R (9bps)':<13} | {'Mean R':<8} | {'PF':<6}")
    print("-" * 95)
    
    comp = results["comparative_matrix"]
    for cfg_name, split_data in comp.items():
        tdata = split_data["TEST"]
        print(f"{cfg_name:<30} | {tdata['count']:<6} | {tdata['win_rate']:<8}% | {tdata['gross_r']:<9} | {tdata['net_r']:<13} | {tdata['mean_r']:<8} | {tdata['pf']:<6}")
        
    print("="*95)
    print(f"\nBest Trade Management Policy (Validation Selected): {results['trade_management_audit']['best_policy']}")
    print("-" * 95)
    print("Trade Management Policies on TEST Split (Variant D):")
    print(f"{'Policy':<25} | {'N':<6} | {'Win Rate':<9} | {'Gross R':<9} | {'Net R (9bps)':<13} | {'Mean R':<8} | {'PF':<6}")
    print("-" * 95)
    for pol_name, pdata in results["trade_management_audit"]["policies_evaluated"].items():
        ptest = pdata["test"]
        print(f"{pol_name:<25} | {ptest['count']:<6} | {ptest['win_rate']:<8}% | {ptest['gross_r']:<9} | {ptest['net_r']:<13} | {ptest['mean_r']:<8} | {ptest['pf']:<6}")
    print("="*95 + "\n")

if __name__ == "__main__":
    main()
