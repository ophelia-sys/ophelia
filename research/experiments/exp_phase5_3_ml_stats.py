import os
import json
import numpy as np
import pandas as pd
import pickle
import statsmodels.api as sm
from sklearn.metrics import log_loss, brier_score_loss
from statsmodels.stats.multitest import multipletests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def dm_test(y, p1, p2, max_lag=59):
    # p1 = BASE, p2 = AUG
    loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p1)])
    loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p2)])
    d = loss1 - loss2  # positive means AUG is better
    
    if np.all(d == 0):
        return 0.0, 1.0
        
    model = sm.OLS(d, np.ones_like(d))
    res = model.fit(cov_type='HAC', cov_kwds={'maxlags': max_lag})
    return res.tvalues[0], res.pvalues[0]

def block_bootstrap(loss1, loss2, block_length=60, replications=1000):
    np.random.seed(42)
    n = len(loss1)
    if n < block_length:
        return 0.0, (0.0, 0.0)
    num_blocks = n // block_length
    d_actual = np.mean(loss1) - np.mean(loss2)
    
    boot_diffs = []
    blocks1 = [loss1[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    blocks2 = [loss2[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    
    for _ in range(replications):
        idx = np.random.randint(0, num_blocks, num_blocks)
        sample1 = np.concatenate([blocks1[i] for i in idx])
        sample2 = np.concatenate([blocks2[i] for i in idx])
        boot_diffs.append(np.mean(sample1) - np.mean(sample2))
        
    boot_diffs = np.array(boot_diffs)
    ci_lower = np.percentile(boot_diffs, 2.5)
    ci_upper = np.percentile(boot_diffs, 97.5)
    
    return np.mean(boot_diffs), (ci_lower, ci_upper)

def calculate_logloss(y, p):
    p = np.clip(p, 1e-15, 1 - 1e-15)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

def block_permutation(y, p_base, p_aug, block_length=60, iterations=1000):
    np.random.seed(42)
    n = len(y)
    if n < block_length:
        return 1.0
    num_blocks = n // block_length
    
    actual_diff = calculate_logloss(y, p_base) - calculate_logloss(y, p_aug)
    
    better_count = 0
    blocks_aug = [p_aug[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    tail_aug = p_aug[num_blocks*block_length:]
    
    for _ in range(iterations):
        idx = np.random.permutation(num_blocks)
        shuffled_aug = np.concatenate([blocks_aug[i] for i in idx])
        if len(tail_aug) > 0:
            shuffled_aug = np.concatenate([shuffled_aug, tail_aug])
            
        diff = calculate_logloss(y, p_base) - calculate_logloss(y, shuffled_aug)
        if diff >= actual_diff:
            better_count += 1
            
    return (better_count + 1) / (iterations + 1)

def main():
    print("--- Statistical Analysis Phase ---")
    
    with open(os.path.join(BASE_DIR, "PHASE5_3_OOS_PREDS.pkl"), "rb") as f:
        oos_store = pickle.load(f)
        
    df_raw = pd.read_json(os.path.join(BASE_DIR, "PHASE5_3_FINAL_RESULTS_RAW.json"))
    
    models = ["B", "C", "D", "E", "F", "G"]
    
    dm_pvals_family_A = []
    dm_pvals_family_B = []
    
    stats_results = []
    
    # Process each symbol & model
    for symbol in SYMBOLS:
        for mod in models:
            key = f"{symbol}_{mod}"
            if key not in oos_store:
                continue
                
            data = oos_store[key]
            y = data['y']
            p_aug = data['preds_aug']
            p_base = data['preds_base']
            
            # DM test
            t_stat, p_val = dm_test(y, p_base, p_aug, max_lag=59)
            
            if mod == "G":
                dm_pvals_family_A.append(p_val)
            else:
                dm_pvals_family_B.append(p_val)
                
            # Block Permutation
            perm_pval = block_permutation(y, p_base, p_aug)
            
            # Block Bootstrap for LogLoss difference (Base - Aug) -> Positive means Aug is better
            loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p_base)])
            loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p_aug)])
            
            boot_mean, (boot_ci_lo, boot_ci_hi) = block_bootstrap(loss1, loss2)
            
            stats_results.append({
                'symbol': symbol,
                'model': mod,
                'dm_tstat': t_stat,
                'dm_pval': p_val,
                'perm_pval': perm_pval,
                'boot_diff_mean': boot_mean,
                'boot_ci_lo': boot_ci_lo,
                'boot_ci_hi': boot_ci_hi
            })
            
    # Apply BH correction
    # Family A: MODEL G vs BASE across 6 symbols
    _, bh_pvals_A, _, _ = multipletests(dm_pvals_family_A, alpha=0.05, method='fdr_bh')
    
    # Family B: Ablations B-F vs BASE across 6 symbols (30 hypotheses)
    _, bh_pvals_B, _, _ = multipletests(dm_pvals_family_B, alpha=0.05, method='fdr_bh')
    
    # Assign BH P-Vals
    idx_A = 0
    idx_B = 0
    for r in stats_results:
        if r['model'] == "G":
            r['bh_pval'] = bh_pvals_A[idx_A]
            idx_A += 1
        else:
            r['bh_pval'] = bh_pvals_B[idx_B]
            idx_B += 1
            
    df_stats = pd.DataFrame(stats_results)
    
    # Merge with raw results
    df_merged = df_raw.copy()
    # It has 'model' column like "MODEL_G", "BASE_MATCHED_G". Let's extract base info.
    # We need to compute delta metrics
    
    final_report_md = ["# PHASE 5.3 CVD ML EXPERIMENT - FINAL RESULTS", ""]
    final_report_md.append("## 1. Primary Analysis: MODEL G vs BASE_MATCHED_G")
    
    # Filter for G
    df_g = df_merged[df_merged['model'] == 'MODEL_G'].set_index('symbol')
    df_base_g = df_merged[df_merged['model'] == 'BASE_MATCHED_G'].set_index('symbol')
    df_stat_g = df_stats[df_stats['model'] == 'G'].set_index('symbol')
    
    delta_logloss = df_base_g['log_loss'] - df_g['log_loss'] # positive means G is better
    delta_brier = df_base_g['brier'] - df_g['brier']
    
    pooled_oos = {
        'y': [], 'p_aug': [], 'p_base': [], 'R_val': []
    }
    for s in SYMBOLS:
        key = f"{s}_G"
        if key in oos_store:
            pooled_oos['y'].extend(oos_store[key]['y'])
            pooled_oos['p_aug'].extend(oos_store[key]['preds_aug'])
            pooled_oos['p_base'].extend(oos_store[key]['preds_base'])
            pooled_oos['R_val'].extend(oos_store[key]['R_val'])
            
    # Pooled Metrics
    pool_y = np.array(pooled_oos['y'])
    pool_p_aug = np.array(pooled_oos['p_aug'])
    pool_p_base = np.array(pooled_oos['p_base'])
    
    pool_ll_aug = calculate_logloss(pool_y, pool_p_aug)
    pool_ll_base = calculate_logloss(pool_y, pool_p_base)
    pool_brier_aug = brier_score_loss(pool_y, pool_p_aug)
    pool_brier_base = brier_score_loss(pool_y, pool_p_base)
    
    pool_dm_t, pool_dm_p = dm_test(pool_y, pool_p_base, pool_p_aug, max_lag=59)
    
    final_report_md.append("### Pooled Aggregate Metrics (All 6 Symbols)")
    final_report_md.append(f"- **Pooled LogLoss (Base):** {pool_ll_base:.5f}")
    final_report_md.append(f"- **Pooled LogLoss (CVD):** {pool_ll_aug:.5f}")
    final_report_md.append(f"- **Pooled Delta LogLoss:** {(pool_ll_base - pool_ll_aug):.5f}")
    final_report_md.append(f"- **Pooled Brier (Base):** {pool_brier_base:.5f}")
    final_report_md.append(f"- **Pooled Brier (CVD):** {pool_brier_aug:.5f}")
    final_report_md.append(f"- **Pooled Delta Brier:** {(pool_brier_base - pool_brier_aug):.5f}")
    final_report_md.append(f"- **Pooled DM Test (t-stat):** {pool_dm_t:.2f} (p={pool_dm_p:.4f})")
    
    final_report_md.append("\n### Per-Symbol Evidence (Including Regimes)")
    final_report_md.append("| Symbol | Base LL | CVD LL | Delta LL | Base Brier | CVD Brier | Delta Brier | DM p-val | BH q-val | Delta LL (2022) | Delta LL (2023) |")
    final_report_md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    
    improving_symbols = 0
    for s in SYMBOLS:
        b_ll = df_base_g.loc[s, 'log_loss'].values[0] if type(df_base_g.loc[s, 'log_loss']) is pd.Series else df_base_g.loc[s, 'log_loss']
        c_ll = df_g.loc[s, 'log_loss'].values[0] if type(df_g.loc[s, 'log_loss']) is pd.Series else df_g.loc[s, 'log_loss']
        d_ll = b_ll - c_ll
        
        b_br = df_base_g.loc[s, 'brier'].values[0] if type(df_base_g.loc[s, 'brier']) is pd.Series else df_base_g.loc[s, 'brier']
        c_br = df_g.loc[s, 'brier'].values[0] if type(df_g.loc[s, 'brier']) is pd.Series else df_g.loc[s, 'brier']
        d_br = b_br - c_br
        
        # 2022 / 2023 Regimes
        b_ll_2022 = df_base_g.loc[s, 'll_2022'].values[0] if type(df_base_g.loc[s, 'll_2022']) is pd.Series else df_base_g.loc[s, 'll_2022']
        c_ll_2022 = df_g.loc[s, 'll_2022'].values[0] if type(df_g.loc[s, 'll_2022']) is pd.Series else df_g.loc[s, 'll_2022']
        d_ll_2022 = b_ll_2022 - c_ll_2022
        
        b_ll_2023 = df_base_g.loc[s, 'll_2023'].values[0] if type(df_base_g.loc[s, 'll_2023']) is pd.Series else df_base_g.loc[s, 'll_2023']
        c_ll_2023 = df_g.loc[s, 'll_2023'].values[0] if type(df_g.loc[s, 'll_2023']) is pd.Series else df_g.loc[s, 'll_2023']
        d_ll_2023 = b_ll_2023 - c_ll_2023
        
        pval = df_stat_g.loc[s, 'dm_pval']
        qval = df_stat_g.loc[s, 'bh_pval']
        
        if d_ll > 0:
            improving_symbols += 1
            
        final_report_md.append(f"| {s} | {b_ll:.5f} | {c_ll:.5f} | {d_ll:.5f} | {b_br:.5f} | {c_br:.5f} | {d_br:.5f} | {pval:.4f} | {qval:.4f} | {d_ll_2022:.5f} | {d_ll_2023:.5f} |")
        
    final_report_md.append("\n### Pre-Execution Decision Rule Checklist (MODEL G)")
    
    # Rule 1: Brier Deterioration
    brier_diff = pool_brier_aug - pool_brier_base
    brier_pass = brier_diff <= 0.0005
    final_report_md.append(f"- **Brier Deterioration <= 0.0005:** {'PASS' if brier_pass else 'FAIL'} (Actual: {brier_diff:.5f})")
    
    # Rule 2: Multi-symbol Evidence
    sym_pass = improving_symbols >= 4
    final_report_md.append(f"- **Multi-Symbol Evidence (>=4/6):** {'PASS' if sym_pass else 'FAIL'} (Actual: {improving_symbols}/6)")
    
    # Rule 3: Cost Robustness (we do it pooled)
    pool_R = np.array(pooled_oos['R_val'])
    
    def get_enr(preds, r_val, cost):
        p90 = np.percentile(preds, 90)
        mask = preds >= p90
        gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
        return (gr - (cost / 10000.0)) * 10000.0
        
    enr_base = {c: get_enr(pool_p_base, pool_R, c) for c in [0, 5, 10, 15, 20, 25]}
    enr_aug = {c: get_enr(pool_p_aug, pool_R, c) for c in [0, 5, 10, 15, 20, 25]}
    
    delta_enr = {c: enr_aug[c] - enr_base[c] for c in enr_base}
    
    cost_pass = (delta_enr[0] > 0) and (delta_enr[5] > 0) and (delta_enr[10] > 0)
    final_report_md.append(f"- **Cost Robustness (>0 at 0, 5, 10 bps):** {'PASS' if cost_pass else 'FAIL'}")
    final_report_md.append(f"  - dENR(0): {delta_enr[0]:.2f} bps")
    final_report_md.append(f"  - dENR(5): {delta_enr[5]:.2f} bps")
    final_report_md.append(f"  - dENR(10): {delta_enr[10]:.2f} bps")
    
    # Rule 4: Stat Acceptance
    stat_pass = pool_dm_p <= 0.05 and pool_dm_t > 0
    # Note: pooled test does not undergo BH because it is a single primary hypothesis.
    final_report_md.append(f"- **Statistical Acceptance (Pooled p <= 0.05):** {'PASS' if stat_pass else 'FAIL'} (Actual: {pool_dm_p:.4f})")
    
    final_report_md.append("\n### FINAL DECISION CLASSIFICATION")
    if brier_pass and sym_pass and cost_pass and stat_pass:
        final_report_md.append("**CLASSIFICATION: RETAIN**")
        final_report_md.append("All frozen decision rules mathematically passed.")
    elif brier_pass and sym_pass and cost_pass:
        final_report_md.append("**CLASSIFICATION: INCONCLUSIVE**")
        final_report_md.append("Failed statistical significance but showed multi-symbol and cost robustness.")
    else:
        final_report_md.append("**CLASSIFICATION: REMOVE**")
        final_report_md.append("Failed baseline improvement rules.")
        
    final_report_md.append("\n## 2. Fold Boundaries")
    final_report_md.append("Extracted from MODEL G strict chronology:")
    try:
        # Just grab the first symbol's fold boundaries (they are identical across symbols)
        fb = df_g.loc['BTCUSDT', 'fold_boundaries']
        if type(fb) is pd.Series: fb = fb.values[0]
        final_report_md.append("| Fold | Train Start | Train End | Test Start | Test End | Train N | Test N |")
        final_report_md.append("|---|---|---|---|---|---|---|")
        for f in fb:
            final_report_md.append(f"| {f['fold']} | {f['train_start']} | {f['train_end']} | {f['test_start']} | {f['test_end']} | {f['train_samples']} | {f['test_samples']} |")
    except Exception as e:
        final_report_md.append(f"*(Fold boundaries not successfully parsed: {e})*")

    final_report_md.append("\n## 3. Ablation Analysis (Models B-F)")
    final_report_md.append("A full ablation breakdown is serialized in the accompanying JSON artifact.")
    
    # Dump to disk
    with open(os.path.join(BASE_DIR, "PHASE5_3_CVD_ML_FINAL_RESULTS.md"), "w") as f:
        f.write("\n".join(final_report_md))
        
    # Create final JSON
    final_json = {
        "pooled_G": {
            "logloss_base": pool_ll_base,
            "logloss_cvd": pool_ll_aug,
            "brier_base": pool_brier_base,
            "brier_cvd": pool_brier_aug,
            "dm_tstat": pool_dm_t,
            "dm_pval": pool_dm_p,
            "delta_enr": delta_enr
        },
        "per_symbol_G": df_stat_g.to_dict(orient="index"),
        "all_stats": stats_results
    }
    
    with open(os.path.join(BASE_DIR, "PHASE5_3_FINAL_RESULTS.json"), "w") as f:
        json.dump(final_json, f, indent=2)

if __name__ == "__main__":
    main()
