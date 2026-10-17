import os
import json
import pickle
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.experiments.exp_phase5_3_ml_stats import dm_test, calculate_logloss


SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

def main():
    print("--- PHASE 6.3 P5 STATISTICAL AUDIT ---")
    
    preds_path = os.path.join(BASE_DIR, 'research/results/phase6_3_p5_cross_asset_oos_preds.pkl')
    if not os.path.exists(preds_path):
        raise FileNotFoundError(f"Predictions not found at {preds_path}")
        
    with open(preds_path, 'rb') as f:
        oos_store = pickle.load(f)
        
    audit_results = []
    pvals = []
    
    for symbol in SYMBOLS:
        data = oos_store[symbol]
        y = data['y']
        p_base = data['p_base']
        p_test = data['p_test']
        
        ll_base = calculate_logloss(y, p_base)
        ll_test = calculate_logloss(y, p_test)
        ll_diff = ll_base - ll_test
        
        # DM Test
        dm_stat, dm_p = dm_test(y, p_base, p_test, max_lag=59)
        
        audit_results.append({
            'symbol': symbol,
            'll_diff': ll_diff,
            'dm_stat': dm_stat,
            'dm_pval': dm_p,
            'samples': len(y)
        })
        pvals.append(dm_p)
        
    # Benjamini-Hochberg FDR at alpha=0.05
    # Using scipy.stats.false_discovery_rate (which implements BH when method='bh')
    # Actually scipy.stats doesn't have false_discovery_rate until very recent scipy versions, 
    # let's use statsmodels if available, or just implement BH directly.
    # Manual BH:
    pvals = np.array(pvals)
    n = len(pvals)
    sort_idx = np.argsort(pvals)
    sorted_pvals = pvals[sort_idx]
    
    # BH critical values: (i/m) * Q
    q_vals = np.zeros(n)
    for i in range(n):
        rank = i + 1
        # q = p * (m / rank)
        # However, to maintain monotonicity (adjusted p-values), we take cumulative min from right to left
        q = sorted_pvals[i] * n / rank
        q_vals[sort_idx[i]] = q
        
    # Cumulative min from right to left to enforce monotonicity
    for i in range(n-2, -1, -1):
        q_vals[sort_idx[i]] = min(q_vals[sort_idx[i]], q_vals[sort_idx[i+1]])
        
    # Cap at 1.0
    q_vals = np.minimum(q_vals, 1.0)
    
    print("\n--- INDEPENDENT REPRODUCTION & BH-FDR (M=6) ---")
    for i, res in enumerate(audit_results):
        sym = res['symbol']
        diff = res['ll_diff']
        p = res['dm_pval']
        q = q_vals[i]
        
        direction = "IMPROVEMENT" if diff > 0 else "DEGRADATION"
        if diff > 0 and q < 0.05:
            sig = "SIGNIFICANT IMPROVEMENT"
        elif diff < 0 and q < 0.05:
            sig = "SIGNIFICANT DEGRADATION"
        else:
            sig = "NOT SIGNIFICANT"
            
        print(f"{sym:10s} | LL Diff: {diff:8.5f} | DM p: {p:8.4f} | BH q: {q:8.4f} | {direction:12s} | {sig}")

if __name__ == "__main__":
    main()
