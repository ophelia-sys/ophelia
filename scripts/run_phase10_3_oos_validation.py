"""Script to run the Ophelia Phase 10.3 Out-of-Sample Validation Protocol.

Outputs authoritative empirical metrics across 61 days of continuous Binance data.
"""
import json
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
sys.path.insert(0, os.path.abspath("."))

from control_plane.phase10_3_validation_engine import OutOfSampleValidationRunner

def main():
    parquet_path = "data/processed/binance_um_universe_1m_v2.parquet"
    if not os.path.exists(parquet_path):
        print(f"Error: Parquet file not found at {parquet_path}")
        sys.exit(1)
        
    runner = OutOfSampleValidationRunner(parquet_path=parquet_path)
    results = runner.run_validation()
    
    out_dir = os.path.abspath("data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "phase10_3_validation_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n" + "=" * 80)
    print("PHASE 10.3 OUT-OF-SAMPLE VALIDATION EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Dataset Period:       {results['dataset']['period']}")
    print(f"Total Candidates:     {results['dataset']['total_candidates']}")
    print(f"Day Clusters:         {results['dataset']['day_clusters']}")
    print(f"Effective N_eff:      {results['dataset']['effective_n']}")
    print(f"Train / Val / Test:   {results['dataset']['train_count']} / {results['dataset']['val_count']} / {results['dataset']['test_count']}")
    print("-" * 80)
    print("BASE STRATEGY (NET OF FEES & SLIPPAGE):")
    for sp in ["train", "val", "test"]:
        s = results["base_strategy"][sp]
        print(f"  {sp.upper():10s}: N={s['count']:4d}, Net R={s['net_r']:+7.2f}R, Mean={s['mean_r']:+6.3f}R, WR={s['win_rate']:5.2f}%, PF={s['pf']:.2f}")
    print("-" * 80)
    print("HYPOTHESIS A: TARGET REACHABILITY (q90 >= TP1) ON UNTOUCHED TEST SET:")
    reach_test = results["hypothesis_A_target_reachability"]["test"]
    r_c = reach_test["reachable_cohort"]
    u_c = reach_test["unreachable_cohort"]
    print(f"  Reachable Cohort:   N={r_c['count']:4d}, Net R={r_c['net_r']:+7.2f}R, Mean={r_c['mean_r']:+6.3f}R, WR={r_c['win_rate']:5.2f}%, PF={r_c['pf']:.2f}")
    print(f"  Unreachable Cohort: N={u_c['count']:4d}, Net R={u_c['net_r']:+7.2f}R, Mean={u_c['mean_r']:+6.3f}R, WR={u_c['win_rate']:5.2f}%, PF={u_c['pf']:.2f}")
    print(f"  Delta Mean R:       {reach_test['delta_mean_r']:+6.3f}R (p-value: {reach_test['p_value']:.4f})")
    print(f"  Precision:          {reach_test['precision_pct']:.2f}% | Recall: {reach_test['recall_pct']:.2f}% | Brier Score: {reach_test['brier_score']:.4f}")
    print("-" * 80)
    print("HYPOTHESIS B: POST-ENTRY MANAGEMENT (T+15m REFORECAST) ON UNTOUCHED TEST SET:")
    post_test = results["hypothesis_B_post_entry"]["test"]
    print(f"  Base Net R:         {post_test['base_net_r']:+7.2f}R")
    print(f"  Managed Net R:      {post_test['managed_net_r']:+7.2f}R (Delta: {post_test['delta_net_r']:+7.2f}R)")
    print(f"  Policy Counts:      {post_test['policy_distribution']}")
    print("-" * 80)
    print("HYPOTHESIS C: PULLBACK DEPTH (ALL CANDIDATES) ON UNTOUCHED TEST SET:")
    pull_test = results["hypothesis_C_pullback_depth"]["test"]
    print(f"  q10 Interval Coverage:  {pull_test['coverage_pct']:.2f}%")
    print(f"  MAE Prediction RMSE:    ${pull_test['mae_rmse']:.2f} (Bias: ${pull_test['mae_bias']:.2f})")
    print(f"  SL Touch Precision:     {pull_test['sl_touch_precision_pct']:.2f}%")
    print("-" * 80)
    print("HYPOTHESIS F: ENTRY DIRECTION GATING (q50 >= entry) ON TEST SET:")
    d_c = results["hypothesis_F_entry_direction"]["test_compatible"]
    d_i = results["hypothesis_F_entry_direction"]["test_incompatible"]
    print(f"  q50 >= Entry (Compat):   N={d_c['count']:4d}, Net R={d_c['net_r']:+7.2f}R, WR={d_c['win_rate']:5.2f}%, PF={d_c['pf']:.2f}")
    print(f"  q50 <  Entry (Incompat): N={d_i['count']:4d}, Net R={d_i['net_r']:+7.2f}R, WR={d_i['win_rate']:5.2f}%, PF={d_i['pf']:.2f}")
    print("-" * 80)
    print("MULTIPLE TESTING REGISTRY (BENJAMINI-HOCHBERG FDR alpha=0.05):")
    for h in results["multiple_testing_registry"]:
        print(f"  Rank {h['rank']}: {h['role']:25s} | p={h['p_value']:.4f} | BH crit={h['bh_critical']:.4f} | {h['status']}")
    print("=" * 80)
    print(f"Results saved to: {out_file}\n")

if __name__ == "__main__":
    main()
