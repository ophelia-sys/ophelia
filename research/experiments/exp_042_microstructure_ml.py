import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from research.phase7.labeling import calculate_volatility_adjusted_forward_return
from research.phase7.features import extract_queue_imbalance, extract_book_slope, calculate_evidence_entropy_feature
from research.phase7.ml_pipeline import HistoricalMLEngine
from research.phase6.statistics import CalendarTimePortfolio

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
OUTPUT_PATH = os.path.join(BASE_DIR, 'research', 'PHASE7_INITIAL_ML_BASELINE_REPORT.md')

def main():
    print("Loading dataset...")
    df = pd.read_parquet(DATASET_PATH)
    
    # Sort and clean
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Basic Feature extraction
    print("Extracting features and labels...")
    df['queue_imbalance'] = extract_queue_imbalance(df)
    df['book_slope'] = extract_book_slope(df)
    
    # Fill Nans in some base features for entropy if available
    base_features = ['queue_imbalance']
    if 'snapshot_ofi_proxy' in df.columns:
        df['snapshot_ofi_proxy'] = df['snapshot_ofi_proxy'].fillna(0)
        base_features.append('snapshot_ofi_proxy')
    if 'cvd' in df.columns:
        df['cvd_norm'] = df.groupby('symbol')['cvd'].transform(lambda x: (x - x.rolling(100).mean())/x.rolling(100).std())
        base_features.append('cvd_norm')
        
    df['evidence_entropy'] = calculate_evidence_entropy_feature(df, base_features)
    
    # Label generation (Frozen from exp_042a: label_vol_adj_15)
    print("Calculating frozen label (15m vol-adjusted forward return)...")
    df['R_15_raw'] = df.groupby('symbol').apply(lambda x: x['close'].shift(-15) / x['close'] - 1).reset_index(level=0, drop=True)
    df['label_vol_adj_15'] = df.groupby('symbol').apply(
        lambda x: calculate_volatility_adjusted_forward_return(x, horizon=15)
    ).reset_index(level=0, drop=True)
    
    # Drop rows without labels
    df = df.dropna(subset=['label_vol_adj_15', 'queue_imbalance']).copy()
    
    # Chronological Split (first 60% dev, last 40% oos)
    unique_times = np.sort(df['timestamp'].unique())
    split_idx = int(len(unique_times) * 0.6)
    split_time = unique_times[split_idx]
    
    df_dev = df[df['timestamp'] <= split_time].copy()
    df_oos = df[df['timestamp'] > split_time].copy()
    
    print(f"DEV rows: {len(df_dev)}, OOS rows: {len(df_oos)}")
    
    experiments = {
        "EXP-A (Book Slope)": ['book_slope'],
        "EXP-B (Queue Imb)": ['queue_imbalance'],
        "EXP-C (Slope + Q-Imb)": ['book_slope', 'queue_imbalance'],
        "EXP-D (Entropy)": ['evidence_entropy'],
        "EXP-E (Base + Entropy)": base_features + ['evidence_entropy']
    }
    
    models = ['drift', 'ridge', 'tree', 'lightgbm']
    
    results_report = ["# Phase 7 Initial ML Baseline Report\n"]
    results_report.append("## Setup")
    results_report.append(f"- **Dataset:** {DATASET_PATH}")
    results_report.append(f"- **Label:** label_vol_adj_15 (Frozen Vol-adjusted 15m return)")
    results_report.append(f"- **DEV size:** {len(df_dev)} | **OOS size:** {len(df_oos)}")
    results_report.append("")
    
    # Unconditional baseline on OOS (using raw returns)
    baseline_returns = df_oos['R_15_raw'].dropna().values
    baseline_mean = np.mean(baseline_returns) * 10000
    results_report.append(f"### Unconditional Market Baseline (OOS)")
    results_report.append(f"Mean Return: {baseline_mean:.2f} bps")
    results_report.append("")
    
    for exp_name, feat_cols in experiments.items():
        print(f"\n--- {exp_name} ---")
        results_report.append(f"## {exp_name}")
        results_report.append(f"**Features:** {', '.join(feat_cols)}")
        
        for model_name in models:
            print(f"  Fitting {model_name}...")
            
            try:
                engine = HistoricalMLEngine(target_col='label_vol_adj_15', feature_cols=feat_cols, model_type=model_name, task_type='regression')
                engine.fit(df_dev)
                
                # Predict positive expectancy events
                events = engine.predict_events(df_oos, threshold=0.0, return_horizon=15)
                
                if len(events) < 10:
                    res_str = f"- **{model_name.upper()}**: INSUFFICIENT DATA (N={len(events)})"
                else:
                    ctp = CalendarTimePortfolio(events, horizon=15, bin_freq='1h', weighting='equal_symbol')
                    diag = ctp.get_three_layer_diagnostics()
                    
                    if not diag:
                        res_str = f"- **{model_name.upper()}**: NO PORTFOLIO GENERATED"
                    else:
                        cal_mean = diag['Layer_A_Calendar']['calendar_expectancy'] * 10000
                        cal_tstat = diag['Layer_A_Calendar']['calendar_t_stat']
                        ev_mean = diag['Layer_C_Event']['mean_event_return'] * 10000
                        n_events = diag['Layer_C_Event']['total_event_count']
                        excess = cal_mean - baseline_mean
                        
                        res_str = (f"- **{model_name.upper()}**: N={n_events} | "
                                   f"Cal Mean={cal_mean:.2f} bps (t={cal_tstat:.2f}) | "
                                   f"Excess={excess:.2f} bps")
                                   
                print(f"    {res_str}")
                results_report.append(res_str)
                
            except Exception as e:
                err_str = f"- **{model_name.upper()}**: ERROR ({str(e)})"
                print(f"    {err_str}")
                results_report.append(err_str)
        
        results_report.append("")
        
    results_report.append("## Conclusion & Verdict")
    results_report.append("Detailed review required to determine if complex models or entropy provide incremental value over naive/ridge baselines.")
        
    with open(OUTPUT_PATH, 'w') as f:
        f.write("\n".join(results_report))
        
    print(f"\nReport written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
