import sys
import os
import pandas as pd
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.backtest.engine import OpheliaBacktest
from research.phase6.pipeline import ResearchPipeline

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    return true_range.rolling(period).mean()

def run_real_validation():
    print("Loading Backtest Engine...")
    dataset_id = "binance_um_btcusdt_1m_v1"
    
    try:
        engine = OpheliaBacktest(dataset_id)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
        
    print("Fetching historical data via DuckDB...")
    iterator = engine.loader.get_chronological_iterator(dataset_id)
    df = iterator.fetchdf()
    
    print(f"Loaded {len(df)} rows. Calculating ATR...")
    atr_series = calculate_atr(df)
    
    print("Executing Phase 6 Validation Pipeline (Statistical OOS)...")
    pipeline = ResearchPipeline(n_folds=5)
    results = pipeline.run_pipeline(df, atr_series)
    
    audit = results['audit']
    power = results['power']
    event_stats = results['event_stats']
    stats = results['statistical_results']
    costs = results['cost_results']
    folds = results['folds']
    
    report_lines = []
    report_lines.append("# Phase 6 Historical Empirical Validation Results")
    report_lines.append("\n## 1. Dataset Identity")
    report_lines.append(f"- **Dataset ID:** `{dataset_id}`")
    report_lines.append("- **Source:** Binance Vision USDⓈ-M perpetual futures")
    report_lines.append("- **Symbol:** BTCUSDT")
    report_lines.append("- **Interval:** 1m")
    report_lines.append("- **Date Range:** 2023-01-01 to 2023-03-31")
    report_lines.append(f"- **Observation Count:** {len(df)}")
    
    report_lines.append("\n## 2. Data Quality")
    report_lines.append(f"- **Audit Status:** {audit['status']}")
    report_lines.append(f"- **Completeness:** {engine.manifest.get('completeness_percentage', 100.0)}%")
    report_lines.append(f"- **Missing Intervals (Gaps):** {engine.manifest.get('missing_intervals', 0)}")
    
    report_lines.append("\n## 3. Event Accounting")
    report_lines.append(f"- **Raw Event Count:** {event_stats['raw_events']}")
    report_lines.append(f"- **Cluster Count:** {event_stats['cluster_count']}")
    report_lines.append(f"- **Primary Events:** {event_stats['primary_events']}")
    report_lines.append(f"- **Non-Primary Events:** {event_stats['non_primary_events']}")
    
    report_lines.append("\n**Primary Events by Type:**")
    for k, v in event_stats['primary_type_counts'].items():
        report_lines.append(f"- {k}: {v}")
        
    report_lines.append("\n## 4. OOS Walk-Forward Fold Structure")
    report_lines.append("Chronological Train -> Purge (60m) -> Embargo (24h) -> Test")
    for i, fold in enumerate(folds):
        report_lines.append(f"### Fold {i+1}")
        report_lines.append(f"- Train Start: {fold['train_start']}")
        report_lines.append(f"- Train End: {fold['train_end']}")
        report_lines.append(f"- Purge End: {fold['purge_end']}")
        report_lines.append(f"- Embargo End: {fold['embargo_end']}")
        report_lines.append(f"- Test Start: {fold['test_start']}")
        report_lines.append(f"- Test End: {fold['test_end']}")
        report_lines.append(f"- Train Event Count: {fold['train_event_count']}")
        report_lines.append(f"- Test Event Count: {fold['test_event_count']}")
        
    report_lines.append("\n## 5. Baseline Statistics (TEST)")
    report_lines.append("| Horizon | N | Mean Return | Std Dev |")
    report_lines.append("|---|---|---|---|")
    for h, b_stats in results['baselines'].items():
        report_lines.append(f"| {h}m | {b_stats['N']} | {b_stats['mean']:.6f} | {b_stats['std']:.6f} |")
        
    report_lines.append("\n## 6. OOS Statistical Inference")
    report_lines.append("| Feature | Horizon | N | Mean | Excess | Effect Size | HAC SE | Raw p-val | FDR p-val | 95% CI Lower | 95% CI Upper | Classification |")
    report_lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for res in stats:
        if res.get("classification") == "INCONCLUSIVE / INSUFFICIENT DATA":
            report_lines.append(f"| {res['feature']} | {res['horizon']}m | {res['N']} | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | {res['classification']} |")
        else:
            report_lines.append(f"| {res['feature']} | {res['horizon']}m | {res['N']} | {res['mean_return']:.6f} | {res['excess_return']:.6f} | {res['effect_size']:.6f} | {res['hac_se']:.6f} | {res['raw_p']:.4f} | {res['fdr_p']:.4f} | {res['ci_lower']:.6f} | {res['ci_upper']:.6f} | {res['classification']} |")
            
    report_lines.append("\n## 7. Power Analysis (Simulation)")
    report_lines.append(f"- **Status:** {power['status']}")
    report_lines.append(f"- **Effective N:** {power['estimated_n_eff']}")
    if power.get('mde'):
        report_lines.append(f"- **Minimum Detectable Effect (MDE):** {power['mde']:.6f}")
        for eff, pwr in power['power_by_effect'].items():
            report_lines.append(f"  - Power at {eff:.2f} effect: {pwr:.2%}")
            
    report_lines.append("\n## 8. Cost Analysis (Horizon=60m)")
    for scenario, cres in costs.items():
        report_lines.append(f"### {scenario}")
        report_lines.append(f"- Events N: {cres['N']}")
        report_lines.append(f"- Mean Net Return: {cres['mean_net_return']:.6f}")
        report_lines.append(f"- Total Net Return: {cres['net_expectancy']:.6f}")
        report_lines.append(f"- Total Fees: {cres['total_fees']:.6f}")
        report_lines.append(f"- Total Slippage: {cres['total_slippage']:.6f}")

    report_lines.append("\n## 9. Limitations & Next Steps")
    report_lines.append("- Parameter Optimization: NOT PERFORMED — EXPLORATORY FIXED PARAMETERS")
    report_lines.append("- OI/OFI/Microprice: NOT AVAILABLE (Requires orderbook history)")
    report_lines.append("\n**Recommended Next Action:**")
    report_lines.append("Extend dataset or integrate Open Interest features to achieve full empirical capability before engaging LIVE risk logic.")
    
    out_path = "PHASE6_HISTORICAL_VALIDATION_RESULTS.md"
    with open(out_path, "w", encoding='utf-8') as f:
        f.write("\n".join(report_lines))
        
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    run_real_validation()
