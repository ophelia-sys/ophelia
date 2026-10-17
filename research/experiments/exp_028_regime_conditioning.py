import pandas as pd
import numpy as np
import json
import os
from sklearn.linear_model import LogisticRegression

def run_exp_028():
    print("========================================")
    print("EXP 028: REGIME CONDITIONING (DEV/VAL)")
    print("========================================")
    
    in_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_5"
    dev_path = os.path.join(in_dir, "BTCUSDT_context_dev.parquet")
    val_path = os.path.join(in_dir, "BTCUSDT_context_val.parquet")
    
    dev_df = pd.read_parquet(dev_path)
    val_df = pd.read_parquet(val_path)
    
    # Base configuration
    base_features = ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5']
    micro_features = ['cvd_norm', 'snapshot_ofi_proxy_norm']
    all_features = base_features + micro_features
    
    # Ensure targets
    for df in [dev_df, val_df]:
        df['target'] = (df['fwd_ret_5'] > 0).astype(int)
    
    # Train Logistic Regression models on Dev
    dev_valid = dev_df.dropna(subset=all_features + ['fwd_ret_5', 'regime_vol', 'regime_trend', 'regime_mom']).copy()
    val_valid = val_df.dropna(subset=all_features + ['fwd_ret_5', 'regime_vol', 'regime_trend', 'regime_mom']).copy()
    
    # ---------------------------------------------------------
    # LABEL PURGE (Dev -> Val overlap)
    # ---------------------------------------------------------
    min_val_ts = val_valid['timestamp'].min()
    dev_valid['target_end_time'] = dev_valid['timestamp'] + (6 * 60000)
    overlap_mask = dev_valid['target_end_time'] >= min_val_ts
    purged_count = overlap_mask.sum()
    if purged_count > 0:
        dev_valid = dev_valid[~overlap_mask].copy()
    
    # ---------------------------------------------------------
    # TRAINING
    # ---------------------------------------------------------
    models = {
        'Baseline': base_features,
        'Base_Micro': all_features
    }
    
    # To store signal thresholds based on Dev
    thresholds = {}
    
    for name, feats in models.items():
        X_train = dev_valid[feats]
        y_train = dev_valid['target']
        
        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(X_train, y_train)
        
        dev_valid[f'prob_{name}'] = clf.predict_proba(X_train)[:, 1]
        val_valid[f'prob_{name}'] = clf.predict_proba(val_valid[feats])[:, 1]
        
        # Determine 90th percentile threshold on Dev
        thresholds[name] = dev_valid[f'prob_{name}'].quantile(0.90)
    
    cost_bps = 12.0
    
    def analyze_regimes(df, name, threshold, dataset_name):
        signals = df[df[f'prob_{name}'] >= threshold]
        
        grouped = signals.groupby(['regime_vol', 'regime_trend', 'regime_mom']).agg(
            trade_count=('fwd_ret_5', 'count'),
            gross_ev=('fwd_ret_5', lambda x: x.mean() * 10000)
        ).reset_index()
        
        grouped['net_ev'] = grouped['gross_ev'] - cost_bps
        grouped['dataset'] = dataset_name
        return grouped
    
    results = []
    for name in models.keys():
        dev_regimes = analyze_regimes(dev_valid, name, thresholds[name], 'Dev')
        val_regimes = analyze_regimes(val_valid, name, thresholds[name], 'Val')
        
        merged = pd.merge(dev_regimes, val_regimes, on=['regime_vol', 'regime_trend', 'regime_mom'], suffixes=('_dev', '_val'))
        merged['model'] = name
        
        # Classification
        merged['classification'] = 'DEAD_ZONE'
        for i, row in merged.iterrows():
            if row['net_ev_dev'] > 0 and row['net_ev_val'] > 0 and row['trade_count_dev'] >= 30 and row['trade_count_val'] >= 30:
                merged.at[i, 'classification'] = 'ROBUST_ECONOMIC_CANDIDATE'
            elif row['net_ev_dev'] > 0 and row['net_ev_val'] <= 0:
                merged.at[i, 'classification'] = 'CONDITIONAL_EDGE'
            elif row['gross_ev_dev'] < -10 and row['gross_ev_val'] < -10:
                merged.at[i, 'classification'] = 'NOISE_FILTER'
        
        results.append(merged)
    
    final_results = pd.concat(results, ignore_index=True)
    
    print("\n--- Regime Evaluation Summary (Dev / Val) ---")
    cols_to_print = ['model', 'regime_vol', 'regime_trend', 'regime_mom', 'trade_count_dev', 'net_ev_dev', 'trade_count_val', 'net_ev_val', 'classification']
    print(final_results[cols_to_print].to_string(index=False))
    
    # Save the Dev/Val results, and the thresholds for OOS
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\research\results\phase5_5"
    os.makedirs(out_dir, exist_ok=True)
    
    final_results.to_csv(os.path.join(out_dir, "regime_analysis_dev_val.csv"), index=False)
    
    config = {
        'thresholds': thresholds,
        'features': models,
        'cost_bps': cost_bps
    }
    with open(os.path.join(out_dir, "phase5_5_dev_frozen_config.json"), "w") as f:
        json.dump(config, f, indent=4)
    print("\nSaved regime analysis and thresholds.")

if __name__ == '__main__':
    run_exp_028()
