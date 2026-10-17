import os
import json
import pickle
import numpy as np
import pandas as pd
import sys
from sklearn.metrics import brier_score_loss

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.experiments.exp_phase5_3_ml_stats import dm_test, calculate_logloss, block_bootstrap, block_permutation

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def expected_calibration_error(y_true, y_prob, n_bins=10):
    bins = np.linspace(0., 1., n_bins + 1)
    binids = np.digitize(y_prob, bins) - 1
    
    bin_sums = np.bincount(binids, weights=y_prob, minlength=len(bins))
    bin_true = np.bincount(binids, weights=y_true, minlength=len(bins))
    bin_total = np.bincount(binids, minlength=len(bins))
    
    nonzero = bin_total != 0
    prob_true = bin_true[nonzero] / bin_total[nonzero]
    prob_pred = bin_sums[nonzero] / bin_total[nonzero]
    
    ece = np.sum(np.abs(prob_true - prob_pred) * (bin_total[nonzero] / len(y_true)))
    return ece

def calibration_slope_intercept(y_true, y_prob):
    # Logit transform
    epsilon = 1e-15
    y_prob = np.clip(y_prob, epsilon, 1 - epsilon)
    logit_p = np.log(y_prob / (1 - y_prob))
    
    # OLS: y_true ~ logit_p
    import statsmodels.api as sm
    X = sm.add_constant(logit_p)
    model = sm.OLS(y_true, X)
    res = model.fit()
    
    if len(res.params) > 1:
        return res.params[1], res.params[0] # slope, intercept
    return 1.0, 0.0

def main():
    print("--- PHASE 6.3 P5 FINAL INTEGRITY AUDIT ---")
    
    preds_path = os.path.join(BASE_DIR, 'research/results/phase6_3_p5_cross_asset_oos_preds.pkl')
    with open(preds_path, 'rb') as f:
        oos_store = pickle.load(f)
        
    pvals = []
    audit_results = []
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    pooled_ts = []
    pooled_fold = []
    
    # Costs
    costs = [0, 5, 10, 15, 20, 25]
    
    # Arrays to store matched sample checks
    symbol_matched = True
    
    for symbol in SYMBOLS:
        data = oos_store[symbol]
        y = data['y']
        p_base = data['p_base']
        p_test = data['p_test']
        r = data['r']
        ts = data['ts']
        fold = data['fold']
        
        pooled_y.extend(y)
        pooled_p_base.extend(p_base)
        pooled_p_test.extend(p_test)
        pooled_r.extend(r)
        pooled_ts.extend(ts)
        pooled_fold.extend(fold)
        
        ll_base = calculate_logloss(y, p_base)
        ll_test = calculate_logloss(y, p_test)
        
        dm_stat, dm_p = dm_test(y, p_base, p_test, max_lag=59)
        pvals.append(dm_p)
        
        audit_results.append({
            'symbol': symbol,
            'll_base': ll_base,
            'll_test': ll_test,
        })
        
    pvals = np.array(pvals)
    n = len(pvals)
    sort_idx = np.argsort(pvals)
    sorted_pvals = pvals[sort_idx]
    
    q_vals = np.zeros(n)
    for i in range(n):
        rank = i + 1
        q = sorted_pvals[i] * n / rank
        q_vals[sort_idx[i]] = q
        
    for i in range(n-2, -1, -1):
        q_vals[sort_idx[i]] = min(q_vals[sort_idx[i]], q_vals[sort_idx[i+1]])
    q_vals = np.minimum(q_vals, 1.0)
    
    print("\n[SYMBOL LEVEL RESULTS & BH-FDR]")
    for i, res in enumerate(audit_results):
        sym = res['symbol']
        diff = res['ll_base'] - res['ll_test']
        p = pvals[i]
        q = q_vals[i]
        print(f"{sym:10s} | LL Diff: {diff:8.5f} | DM p: {p:8.4f} | BH q: {q:8.4f}")
        
    # Pooled Analysis
    pooled_y = np.array(pooled_y)
    pooled_p_base = np.array(pooled_p_base)
    pooled_p_test = np.array(pooled_p_test)
    pooled_r = np.array(pooled_r)
    pooled_ts = pd.to_datetime(pooled_ts)
    pooled_fold = np.array(pooled_fold)
    
    print("\n[POOLED OVERALL METRICS]")
    ll_base = calculate_logloss(pooled_y, pooled_p_base)
    ll_test = calculate_logloss(pooled_y, pooled_p_test)
    brier_base = brier_score_loss(pooled_y, pooled_p_base)
    brier_test = brier_score_loss(pooled_y, pooled_p_test)
    
    ece_base = expected_calibration_error(pooled_y, pooled_p_base)
    ece_test = expected_calibration_error(pooled_y, pooled_p_test)
    
    slope_b, int_b = calibration_slope_intercept(pooled_y, pooled_p_base)
    slope_t, int_t = calibration_slope_intercept(pooled_y, pooled_p_test)
    
    print(f"LogLoss Base: {ll_base:.5f} | Test: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f}")
    print(f"Brier   Base: {brier_base:.5f} | Test: {brier_test:.5f} | Diff: {brier_base - brier_test:.5f}")
    print(f"ECE     Base: {ece_base:.5f} | Test: {ece_test:.5f}")
    print(f"Calib Slope Base: {slope_b:.4f} | Test: {slope_t:.4f}")
    
    print("\n[POOLED ECONOMIC NET RETURN]")
    for cost in costs:
        enr_b = get_enr(pooled_p_base, pooled_r, cost)
        enr_t = get_enr(pooled_p_test, pooled_r, cost)
        print(f"Cost {cost:2d} bps | Base ENR: {enr_b:6.2f} bps | Test ENR: {enr_t:6.2f} bps | Diff: {enr_t - enr_b:6.2f} bps")
        
    print("\n[POOLED STATISTICAL TESTS]")
    dm_stat, dm_p = dm_test(pooled_y, pooled_p_base, pooled_p_test, max_lag=59)
    print(f"DM Test (HAC lag=59) | stat: {dm_stat:.4f} | pval: {dm_p:.4f}")
    
    loss_base = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(pooled_y, pooled_p_base)])
    loss_test = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(pooled_y, pooled_p_test)])
    
    bs_mean, bs_ci = block_bootstrap(loss_base, loss_test, block_length=60, replications=1000)
    print(f"Bootstrap (reps=1000) | mean_diff: {bs_mean:.6f} | CI: [{bs_ci[0]:.6f}, {bs_ci[1]:.6f}]")
    
    perm_p = block_permutation(pooled_y, pooled_p_base, pooled_p_test, block_length=60, iterations=1000)
    print(f"Permutation (iters=1000) | pval: {perm_p:.4f}")
    
    print("\n[BREAKDOWN BY FOLD]")
    for f in sorted(np.unique(pooled_fold)):
        mask = (pooled_fold == f)
        lb = calculate_logloss(pooled_y[mask], pooled_p_base[mask])
        lt = calculate_logloss(pooled_y[mask], pooled_p_test[mask])
        print(f"Fold {f} | Base LL: {lb:.5f} | Test LL: {lt:.5f} | Diff: {lb - lt:.5f}")
        
    print("\n[BREAKDOWN BY YEAR]")
    for y_year in [2022, 2023]:
        mask = (pooled_ts.year == y_year)
        lb = calculate_logloss(pooled_y[mask], pooled_p_base[mask])
        lt = calculate_logloss(pooled_y[mask], pooled_p_test[mask])
        print(f"Year {y_year} | Base LL: {lb:.5f} | Test LL: {lt:.5f} | Diff: {lb - lt:.5f}")

if __name__ == "__main__":
    main()
