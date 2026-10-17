import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, brier_score_loss

# Add ophelia root to path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from research.experiments.exp_phase5_3_ml_stats import dm_test, block_permutation

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def report_stats(y, p_base, p_test, r, prefix=""):
    ll_base = log_loss(y, p_base)
    ll_test = log_loss(y, p_test)
    bs_base = brier_score_loss(y, p_base)
    bs_test = brier_score_loss(y, p_test)
    
    print(f"\n[{prefix}] (N={len(y)})")
    print(f"LogLoss | Base: {ll_base:.4f} | Test: {ll_test:.4f} | Delta: {ll_test - ll_base:.4f}")
    print(f"Brier   | Base: {bs_base:.4f} | Test: {bs_test:.4f} | Delta: {bs_test - bs_base:.4f}")
    
    # DM and Permutation only if N > 100 to avoid excessive output or rank errors
    if len(y) > 100:
        dm_stat, dm_p = dm_test(y, p_base, p_test, max_lag=59)
        perm_p = block_permutation(y, p_base, p_test, block_length=60, iterations=1000)
        print(f"DM Stat: {dm_stat:.3f}, p-val: {dm_p:.4e} | Perm p-val: {perm_p:.4e}")
    else:
        dm_stat, dm_p, perm_p = np.nan, np.nan, np.nan
        
    print("ENR (bps):")
    for cost in [0, 5, 10, 15, 20, 25]:
        e_b = get_enr(p_base, r, cost)
        e_t = get_enr(p_test, r, cost)
        print(f"  Cost {cost} bps -> Base: {e_b:6.2f} | Test: {e_t:6.2f} | Delta: {e_t - e_b:6.2f}")
        
    return {
        'N': len(y),
        'll_base': ll_base, 'll_test': ll_test, 'll_delta': ll_test - ll_base,
        'bs_base': bs_base, 'bs_test': bs_test, 'bs_delta': bs_test - bs_base,
        'dm_stat': dm_stat, 'dm_p': dm_p, 'perm_p': perm_p
    }

def main():
    pkl_path = os.path.join(BASE_DIR, 'research/results/PHASE6_2_P1_OOS_PREDS.pkl')
    with open(pkl_path, 'rb') as f:
        oos_store = pickle.load(f)
        
    print("============================================================")
    print("P1 FULL INTEGRITY REPRODUCTION REPORT")
    print("============================================================")
    
    # Track per-symbol perm p-values for FDR
    symbol_p_values = {}
    
    # 1. Per-Symbol, Per-Fold
    for symbol, data in oos_store.items():
        print(f"\n============== {symbol} ==============")
        y = data['y']
        p_base = data['p_base']
        p_test = data['p_test']
        r = data['r']
        folds = data['fold_indices']
        
        # Symbol Pooled
        stats = report_stats(y, p_base, p_test, r, prefix=f"{symbol} ALL FOLDS")
        if not np.isnan(stats['perm_p']):
            symbol_p_values[symbol] = stats['perm_p']
        
        # Per Fold
        for f in np.unique(folds):
            mask = (folds == f)
            report_stats(y[mask], p_base[mask], p_test[mask], r[mask], prefix=f"{symbol} FOLD {int(f)}")
            
    # 1.5 Calculate BH-FDR
    print("\n============== BENJAMINI-HOCHBERG FDR ==============")
    if symbol_p_values:
        pvals = np.array(list(symbol_p_values.values()))
        symbols = list(symbol_p_values.keys())
        # Sort p-values
        sort_idx = np.argsort(pvals)
        sorted_pvals = pvals[sort_idx]
        sorted_symbols = [symbols[i] for i in sort_idx]
        
        m = len(sorted_pvals)
        q_values = np.zeros(m)
        
        # BH procedure: q_i = min( p_i * m / i, q_{i+1} )  # going backwards
        # Start from the largest p-value
        for i in range(m - 1, -1, -1):
            rank = i + 1
            q = sorted_pvals[i] * m / rank
            if i == m - 1:
                q_values[i] = q
            else:
                q_values[i] = min(q, q_values[i+1])
                
        for i in range(m):
            sym = sorted_symbols[i]
            p_val = sorted_pvals[i]
            q_val = q_values[i]
            sig = "SIGNIFICANT" if q_val < 0.05 else "NOT SIG"
            print(f"{sym:10} | Raw p-val: {p_val:.4e} | BH q-val: {q_val:.4e} | {sig}")
    
    # 2. Time-Based Aggregation
    print("\n============== TIME-BASED ==============")
    all_y = []
    all_p_base = []
    all_p_test = []
    all_r = []
    all_ts = []
    
    for symbol, data in oos_store.items():
        all_y.extend(data['y'])
        all_p_base.extend(data['p_base'])
        all_p_test.extend(data['p_test'])
        all_r.extend(data['r'])
        all_ts.extend(data['timestamps'])
        
    all_y = np.array(all_y)
    all_p_base = np.array(all_p_base)
    all_p_test = np.array(all_p_test)
    all_r = np.array(all_r)
    all_ts = pd.to_datetime(all_ts)
    
    # 2022
    mask_2022 = all_ts.year == 2022
    report_stats(all_y[mask_2022], all_p_base[mask_2022], all_p_test[mask_2022], all_r[mask_2022], prefix="YEAR 2022")
    
    # 2023
    mask_2023 = all_ts.year == 2023
    report_stats(all_y[mask_2023], all_p_base[mask_2023], all_p_test[mask_2023], all_r[mask_2023], prefix="YEAR 2023")
    
    # POOLED
    print("\n============== POOLED ==============")
    report_stats(all_y, all_p_base, all_p_test, all_r, prefix="GLOBAL POOLED")
    
if __name__ == "__main__":
    main()
