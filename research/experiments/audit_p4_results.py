import os
import json
import pickle
import numpy as np
import pandas as pd
from scipy import stats
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.experiments.exp_phase5_3_ml_stats import dm_test, block_bootstrap, block_permutation, calculate_logloss
from sklearn.metrics import log_loss, brier_score_loss
from statsmodels.stats.multitest import multipletests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
PREDS_PKL = os.path.join(BASE_DIR, 'research/results/phase6_3_p4_large_trade_oos_preds.pkl')
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def calculate_calibration(y_true, y_prob):
    bins = np.linspace(0, 1, 11)
    bin_indices = np.digitize(y_prob, bins) - 1
    ece = 0
    for i in range(10):
        mask = bin_indices == i
        if np.sum(mask) > 0:
            prob_pred = np.mean(y_prob[mask])
            prob_true = np.mean(y_true[mask])
            ece += np.abs(prob_pred - prob_true) * (np.sum(mask) / len(y_prob))
            
    eps = 1e-7
    p = np.clip(y_prob, eps, 1-eps)
    logit_p = np.log(p / (1 - p))
    try:
        slope, intercept, _, _, _ = stats.linregress(logit_p, y_true)
    except:
        slope, intercept = 1.0, 0.0
        
    return ece, slope, intercept

def compute_slice_metrics(y, p_base, p_test, r):
    ll_base = calculate_logloss(y, p_base)
    ll_test = calculate_logloss(y, p_test)
    brier_base = brier_score_loss(y, p_base)
    brier_test = brier_score_loss(y, p_test)
    ece_base, slope_base, int_base = calculate_calibration(y, p_base)
    ece_test, slope_test, int_test = calculate_calibration(y, p_test)
    
    enrs_base = {c: get_enr(p_base, r, c) for c in [0, 5, 10, 15, 20, 25]}
    enrs_test = {c: get_enr(p_test, r, c) for c in [0, 5, 10, 15, 20, 25]}
    
    dm_stat, dm_p = dm_test(y, p_base, p_test, max_lag=59)
    
    loss_base = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p_base)])
    loss_test = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p_test)])
    
    bs_mean, _ = block_bootstrap(loss_base, loss_test, block_length=60, replications=1000)
    perm_p = block_permutation(y, p_base, p_test, block_length=60, iterations=1000)
    
    return {
        'samples': len(y),
        'll_base': ll_base,
        'll_test': ll_test,
        'brier_base': brier_base,
        'brier_test': brier_test,
        'ece_base': ece_base,
        'ece_test': ece_test,
        'slope_base': slope_base,
        'slope_test': slope_test,
        'int_base': int_base,
        'int_test': int_test,
        'enrs_base': enrs_base,
        'enrs_test': enrs_test,
        'dm_p': dm_p,
        'bs_mean': bs_mean,
        'perm_p': perm_p
    }

def run_audit():
    with open(PREDS_PKL, 'rb') as f:
        preds = pickle.load(f)
        
    audit = []
    audit.append("# PHASE 6.3 P4 - RESULT INTEGRITY AUDIT (FINAL EXHAUSTIVE)\n")
    
    all_y = []
    all_p_base = []
    all_p_test = []
    all_r = []
    all_ts = []
    all_folds = []
    
    p_vals = []
    symbol_metrics = {}
    
    for symbol in SYMBOLS:
        d = preds[symbol]
        y = np.array(d['y'])
        p_base = np.array(d['p_base'])
        p_test = np.array(d['p_test'])
        r = np.array(d['r'])
        ts = np.array(d['ts'])
        fold = np.array(d['fold'])
        
        all_y.extend(y)
        all_p_base.extend(p_base)
        all_p_test.extend(p_test)
        all_r.extend(r)
        all_ts.extend(ts)
        all_folds.extend(fold)
        
        # Verify arrays are identical shape
        assert len(y) == len(p_base) == len(p_test) == len(r) == len(ts) == len(fold)
        
        metrics = compute_slice_metrics(y, p_base, p_test, r)
        symbol_metrics[symbol] = metrics
        p_vals.append(metrics['dm_p'])
        
    _, bh_q, _, _ = multipletests(p_vals, alpha=0.05, method='fdr_bh')
    
    # Per-Symbol Output
    audit.append("## 1. Symbol Level Independent Reproduction\n")
    for i, symbol in enumerate(SYMBOLS):
        m = symbol_metrics[symbol]
        audit.append(f"### {symbol}")
        audit.append(f"- Samples: {m['samples']}")
        audit.append(f"- LogLoss: Base {m['ll_base']:.5f} | Test {m['ll_test']:.5f} | Diff {(m['ll_base'] - m['ll_test'])*10000:.2f} bps")
        audit.append(f"- Brier: Base {m['brier_base']:.5f} | Test {m['brier_test']:.5f}")
        audit.append(f"- ECE: Base {m['ece_base']:.4f} | Test {m['ece_test']:.4f}")
        audit.append(f"- Calib Slope/Int: Base ({m['slope_base']:.4f}, {m['int_base']:.4f}) | Test ({m['slope_test']:.4f}, {m['int_test']:.4f})")
        for cost in [0, 5, 10, 15, 20, 25]:
            audit.append(f"- ENR({cost}): Base {m['enrs_base'][cost]:.2f}bps | Test {m['enrs_test'][cost]:.2f}bps")
        audit.append(f"- DM p-val (Lag 59): {m['dm_p']:.4f}")
        audit.append(f"- Bootstrap 1000-Block Diff: {m['bs_mean']:.5f}")
        audit.append(f"- Permutation 1000-Block p-val: {m['perm_p']:.4f}")
        audit.append(f"- BH-FDR q-val: {bh_q[i]:.4f}\n")
    
    # Slices
    all_y = np.array(all_y)
    all_p_base = np.array(all_p_base)
    all_p_test = np.array(all_p_test)
    all_r = np.array(all_r)
    all_ts = np.array(all_ts)
    all_folds = np.array(all_folds)
    
    audit.append("## 2. Temporal Slices (Pooled)\n")
    
    # Years
    year_2022_mask = (pd.to_datetime(all_ts, unit='ms').year == 2022)
    year_2023_mask = (pd.to_datetime(all_ts, unit='ms').year == 2023)
    
    m_2022 = compute_slice_metrics(all_y[year_2022_mask], all_p_base[year_2022_mask], all_p_test[year_2022_mask], all_r[year_2022_mask])
    audit.append("### 2022")
    audit.append(f"- Samples: {m_2022['samples']} | LL Diff: {(m_2022['ll_base'] - m_2022['ll_test'])*10000:.2f} bps | DM p-val: {m_2022['dm_p']:.4f}")
    audit.append(f"- ENR(0): Base {m_2022['enrs_base'][0]:.2f}bps | Test {m_2022['enrs_test'][0]:.2f}bps")
    
    m_2023 = compute_slice_metrics(all_y[year_2023_mask], all_p_base[year_2023_mask], all_p_test[year_2023_mask], all_r[year_2023_mask])
    audit.append("\n### 2023")
    audit.append(f"- Samples: {m_2023['samples']} | LL Diff: {(m_2023['ll_base'] - m_2023['ll_test'])*10000:.2f} bps | DM p-val: {m_2023['dm_p']:.4f}")
    audit.append(f"- ENR(0): Base {m_2023['enrs_base'][0]:.2f}bps | Test {m_2023['enrs_test'][0]:.2f}bps\n")
    
    audit.append("## 3. Fold Slices (Pooled)\n")
    for f_idx in [0, 1, 2]:
        mask = (all_folds == f_idx)
        if np.sum(mask) > 0:
            m_f = compute_slice_metrics(all_y[mask], all_p_base[mask], all_p_test[mask], all_r[mask])
            audit.append(f"### Fold {f_idx}")
            audit.append(f"- Samples: {m_f['samples']} | LL Diff: {(m_f['ll_base'] - m_f['ll_test'])*10000:.2f} bps | DM p-val: {m_f['dm_p']:.4f}")
            audit.append(f"- ENR(0): Base {m_f['enrs_base'][0]:.2f}bps | Test {m_f['enrs_test'][0]:.2f}bps")
            
    audit.append("\n## 4. Aggregate Performance\n")
    
    m_pooled = compute_slice_metrics(all_y, all_p_base, all_p_test, all_r)
    audit.append("### Pooled Aggregate")
    audit.append(f"- Samples: {m_pooled['samples']} | LL Diff: {(m_pooled['ll_base'] - m_pooled['ll_test'])*10000:.2f} bps | DM p-val: {m_pooled['dm_p']:.4f}")
    for cost in [0, 5, 10, 15, 20, 25]:
        audit.append(f"- ENR({cost}): Base {m_pooled['enrs_base'][cost]:.2f}bps | Test {m_pooled['enrs_test'][cost]:.2f}bps")
        
    audit.append("\n### Equal-Weighted Aggregate")
    ew_ll_diff = np.mean([(symbol_metrics[s]['ll_base'] - symbol_metrics[s]['ll_test'])*10000 for s in SYMBOLS])
    audit.append(f"- Equal-Weighted LL Diff: {ew_ll_diff:.2f} bps")
    for cost in [0, 5, 10, 15, 20, 25]:
        ew_enr_base = np.mean([symbol_metrics[s]['enrs_base'][cost] for s in SYMBOLS])
        ew_enr_test = np.mean([symbol_metrics[s]['enrs_test'][cost] for s in SYMBOLS])
        audit.append(f"- EW ENR({cost}): Base {ew_enr_base:.2f}bps | Test {ew_enr_test:.2f}bps")

    with open(os.path.join(BASE_DIR, 'PHASE6_3_P4_LARGE_TRADE_RESULT_INTEGRITY_AUDIT.md'), 'w') as f:
        f.write("\n".join(audit))
        
if __name__ == "__main__":
    run_audit()
