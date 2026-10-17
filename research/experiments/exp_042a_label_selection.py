import os
import sys
import pandas as pd
import numpy as np
from scipy.stats import spearmanr, skew, kurtosis

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from research.phase7.labeling import calculate_volatility_adjusted_forward_return, calculate_mfe_mae
from research.phase7.features import extract_queue_imbalance

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
OUTPUT_PATH = os.path.join(BASE_DIR, 'research', 'PHASE7_LABEL_SELECTION.md')

def main():
    print("Loading dataset for label selection...")
    df = pd.read_parquet(DATASET_PATH)
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Chronological Split for DEV data
    unique_times = np.sort(df['timestamp'].unique())
    split_idx = int(len(unique_times) * 0.6)
    split_time = unique_times[split_idx]
    
    df_dev = df[df['timestamp'] <= split_time].copy()
    
    # We will use mean_queue_imbalance as the baseline feature to test predictability
    print("Calculating candidate labels on DEV data...")
    df_dev['queue_imbalance'] = extract_queue_imbalance(df_dev)
    
    # Candidate 1: 15m raw forward return
    df_dev['label_raw_15'] = df_dev.groupby('symbol').apply(lambda x: x['close'].shift(-15) / x['close'] - 1).reset_index(level=0, drop=True)
    
    # Candidate 2: 15m vol-adjusted forward return
    df_dev['label_vol_adj_15'] = df_dev.groupby('symbol').apply(
        lambda x: calculate_volatility_adjusted_forward_return(x, horizon=15)
    ).reset_index(level=0, drop=True)
    
    df_dev = df_dev.dropna(subset=['queue_imbalance', 'label_raw_15', 'label_vol_adj_15']).copy()
    
    print(f"DEV rows for selection: {len(df_dev)}")
    
    candidates = ['label_raw_15', 'label_vol_adj_15']
    results = {}
    
    for c in candidates:
        y = df_dev[c].values
        x = df_dev['queue_imbalance'].values
        
        # Methodology:
        # 1. Distribution shape (skew, kurtosis) - prefer symmetry and lower fat-tails
        # 2. Predictability - Spearman Rank IC with a known strong base feature
        
        ic, p_val = spearmanr(x, y)
        sk = skew(y)
        kurt = kurtosis(y)
        
        results[c] = {
            "IC": float(ic),
            "IC_pval": float(p_val),
            "Skew": float(sk),
            "Kurtosis": float(kurt),
            "Mean": float(np.mean(y)),
            "Std": float(np.std(y))
        }
        
    # Selection logic: choose the one with highest absolute IC
    best_label = max(candidates, key=lambda c: abs(results[c]['IC']))
    
    report = ["# Phase 7 Label Selection\n"]
    report.append("## Candidate Labels Evaluated on DEV Data")
    for c in candidates:
        r = results[c]
        report.append(f"### {c}")
        report.append(f"- **Information Coefficient (IC) with Queue Imbalance**: {r['IC']:.4f} (p={r['IC_pval']:.4f})")
        report.append(f"- **Skewness**: {r['Skew']:.4f}")
        report.append(f"- **Kurtosis**: {r['Kurtosis']:.4f}")
        report.append(f"- **Mean**: {r['Mean']:.6f} | **Std**: {r['Std']:.6f}")
        report.append("")
        
    report.append(f"## Selected Label: `{best_label}`")
    report.append(f"**Selection Rationale**: The label with the highest absolute Information Coefficient on DEV data, indicating better inherent predictability by our base features.")
    
    with open(OUTPUT_PATH, 'w') as f:
        f.write("\n".join(report))
        
    print(f"Label selection complete. Best label: {best_label}")
    print(f"Report written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
