"""Script to execute the Ophelia Phase 12 Fresh-Period Incremental TimesFM Validation Protocol.

Outputs authoritative empirical metrics across 122 continuous days of fresh Binance Futures data.
Saves results to data/phase12_incremental_timesfm_results.json.
"""
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
sys.path.insert(0, os.path.abspath("."))

from control_plane.phase12_timesfm_engine import Phase12TimesFMValidationEngine


def main():
    parquet_path = "data/processed/phase12_fresh_universe_1m.parquet"
    if not os.path.exists(parquet_path):
        print(f"Error: Parquet file not found at {parquet_path}. Run prepare_phase12_dataset.py first.")
        sys.exit(1)

    engine = Phase12TimesFMValidationEngine(parquet_path=parquet_path)
    results = engine.run_validation()

    out_dir = os.path.abspath("data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "phase12_incremental_timesfm_results.json")

    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 95)
    print("OPHELIA — PHASE 12: FRESH-PERIOD INCREMENTAL TIMESFM VALIDATION SUMMARY")
    print("=" * 95)
    print(f"Dataset Window:        {results['dataset_period']}")
    print(f"Specification Hash:    {results['spec_hash']}")
    print(f"Candidate Counts:      Total={results['candidate_counts']['total']} | Train={results['candidate_counts']['train']} | Val={results['candidate_counts']['validation']} | Test={results['candidate_counts']['test']}")
    print(f"D4H on TEST Split:     N={results['candidate_counts']['d4h_test']} | TimesFM Reachable={results['candidate_counts']['tfm_reachable_test']}")
    print("-" * 95)

    print("PROGRESSION COHORTS (TEST SPLIT — UNTOUCHED OUT-OF-SAMPLE, 9.0 BPS FRICTION):")
    print(f"{'COHORT':28s} {'N':>5s} {'WIN %':>7s} {'GROSS R':>9s} {'NET R':>9s} {'MEAN R':>8s} {'MEDIAN':>8s} {'PF':>6s} {'MAX DD':>8s}")
    print("-" * 95)
    matrix = results["baseline_progression_matrix"]
    for c_key in ["A_BASELINE", "B_VARIANT_D", "C_D4H", "D_D4H_TFM_REACHABLE", "E_D4H_TFM_DOWNSIDE", "F_D4H_TFM_MANAGED"]:
        s = matrix[c_key]["test"]
        print(f"{c_key:28s} {s['count']:5d} {s['win_rate']:6.2f}% {s['gross_r']:+8.2f}R {s['net_r']:+8.2f}R {s['mean_r']:+7.3f}R {s['median_r']:+7.3f}R {s['pf']:6.2f} {s['max_drawdown']:7.2f}R")
    print("-" * 95)

    print("INCREMENTAL DELTAS ON UNTOUCHED TEST SET:")
    deltas = results["incremental_deltas_test"]
    for step_key, d in deltas.items():
        print(f"  {step_key:35s}: Delta N={d['delta_n']:+4d} | Delta WR={d['delta_win_rate_pct']:+5.2f}% | Delta Net R={d['delta_net_r']:+7.2f}R | Delta Mean={d['delta_mean_r']:+6.3f}R | Delta PF={d['delta_pf']:+5.2f}")
    print("-" * 95)

    print("TIMESFM HORIZON SENSITIVITY ON D4H (TEST SPLIT):")
    for hz_key, hz_s in results["horizon_sensitivity_test"].items():
        print(f"  {hz_key:15s}: N={hz_s['count']:4d} | WR={hz_s['win_rate']:5.2f}% | Net R={hz_s['net_r']:+7.2f}R | Mean R={hz_s['mean_r']:+6.3f}R | PF={hz_s['pf']:.2f}")
    print("-" * 95)

    print("TIMESFM VS SIMPLE BASELINES (60m POINT FORECAST RMSE ON TEST SPLIT):")
    for b_name, b_val in results["baseline_models_comparison"].items():
        print(f"  {b_name:30s}: RMSE=${b_val:.2f}")
    print("-" * 95)

    print("DOWNSIDE / STOP-MARGIN ANALYSIS (TEST SPLIT):")
    ds_s = results["downside_distribution_analysis"]
    print(f"  q10 Coverage of MAE:            {ds_s['q10_coverage_mae_pct']:.2f}%")
    print(f"  MAE Prediction RMSE:            ${ds_s['mae_prediction_rmse']:.2f} (Mean Bias: ${ds_s['mae_prediction_error_mean']:.2f})")
    print(f"  SL Touch Prediction Precision:  {ds_s['sl_touch_prediction_precision_pct']:.2f}%")
    print("-" * 95)

    print("ASSET BREAKDOWN ON UNTOUCHED TEST SET (D4H vs D4H + TimesFM):")
    for sym, as_res in results["asset_breakdown_test"].items():
        d4h_s = as_res["d4h"]
        tfm_s = as_res["d4h_timesfm"]
        print(f"  {sym:8s} | D4H: N={d4h_s['count']:3d}, Net R={d4h_s['net_r']:+6.2f}R, Mean={d4h_s['mean_r']:+5.3f}R | TFM: N={tfm_s['count']:3d}, Net R={tfm_s['net_r']:+6.2f}R, Mean={tfm_s['mean_r']:+5.3f}R | Delta Net={as_res['delta_net_r']:+6.2f}R")
    print("-" * 95)

    print("FRICTION SENSITIVITY (D4H vs D4H + TimesFM on TEST Split):")
    f_sens = results["friction_sensitivity_test"]
    for reg, label in [("zero_0bps", "0 bps (Gross)"), ("low_5bps", "5 bps (Low)"), ("base_9bps", "9 bps (Base)"), ("high_14bps", "14 bps (High)")]:
        d4h_r = f_sens["d4h"][reg]
        tfm_r = f_sens["d4h_timesfm"][reg]
        print(f"  {label:18s} | D4H: Net R={d4h_r['net_r']:+7.2f}R (Mean={d4h_r['mean_r']:+6.3f}R) | D4H+TFM: Net R={tfm_r['net_r']:+7.2f}R (Mean={tfm_r['mean_r']:+6.3f}R)")
    print("-" * 95)

    print("CLUSTER ANALYSIS (TEST Split):")
    cl = results["cluster_analysis_test"]
    print(f"  Total Candidates: {cl['total_test_candidates']} | Day Clusters: {cl['total_day_clusters']} | Mean Cluster Size: {cl['mean_cluster_size']} | Effective N_eff: {cl['effective_sample_size_n_eff']}")
    print("-" * 95)

    print("MULTIPLE-TESTING REGISTRY (BENJAMINI-HOCHBERG FDR alpha=0.05):")
    for h in results["multiple_testing_registry"]:
        print(f"  Rank {h['rank']}: {h['hypothesis_id']} - {h['name']:45s} | p={h['raw_p_value']:.5f} | BH crit={h['bh_critical_value']:.5f} | {h['fdr_status']}")
    print("=" * 95)

    print(f"\nFINAL SCIENTIFIC CONCLUSION: {results['scientific_conclusion']}")
    print(f"STOP CONDITION STATUS:      {results['stop_condition_status']}")
    print(f"Full results saved to:      {out_file}\n")


if __name__ == "__main__":
    main()
