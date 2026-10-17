import pandas as pd
import numpy as np
import json
import os
from sklearn.linear_model import LogisticRegression

def run_exp_029():
    print("========================================")
    print("EXP 029: ONE-TIME OOS EVALUATION")
    print("========================================")
    
    in_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_5"
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\research\results\phase5_5"
    
    dev_path = os.path.join(in_dir, "BTCUSDT_context_dev.parquet")
    oos_path = os.path.join(in_dir, "BTCUSDT_context_oos.parquet")
    
    dev_df = pd.read_parquet(dev_path)
    oos_df = pd.read_parquet(oos_path)
    
    for df in [dev_df, oos_df]:
        df['target'] = (df['fwd_ret_5'] > 0).astype(int)
        
    with open(os.path.join(out_dir, "phase5_5_dev_frozen_config.json"), "r") as f:
        config = json.load(f)
        
    thresholds = config['thresholds']
    features = config['features']
    cost_bps = config['cost_bps']
    
    regime_map = pd.read_csv(os.path.join(out_dir, "regime_analysis_dev_val.csv"))
    
    # Select regimes that had some edge in dev or val just to track them
    # "Target regimes" are ROBUST_ECONOMIC_CANDIDATE. We will also track CONDITIONAL_EDGE.
    robust_regimes = regime_map[regime_map['classification'] == 'ROBUST_ECONOMIC_CANDIDATE']
    conditional_regimes = regime_map[regime_map['classification'] == 'CONDITIONAL_EDGE']
    
    print(f"Found {len(robust_regimes)} ROBUST regimes.")
    print(f"Found {len(conditional_regimes)} CONDITIONAL regimes.")
    
    oos_valid = oos_df.dropna(subset=['regime_vol', 'regime_trend', 'regime_mom', 'fwd_ret_5']).copy()
    
    # Drop rows missing features for Baseline or Base_Micro
    all_features = features['Base_Micro']
    oos_valid = oos_valid.dropna(subset=all_features).copy()
    dev_valid = dev_df.dropna(subset=all_features + ['fwd_ret_5']).copy()
    
    oos_predictions = pd.DataFrame({'timestamp': oos_valid['timestamp'], 'target': oos_valid['target']})
    
    results = []
    
    for name, feats in features.items():
        # Train on DEV (frozen)
        X_train = dev_valid[feats]
        y_train = dev_valid['target']
        
        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(X_train, y_train)
        
        # Predict on OOS
        X_test = oos_valid[feats]
        preds = clf.predict_proba(X_test)[:, 1]
        
        oos_valid[f'prob_{name}'] = preds
        oos_predictions[f'prob_{name}'] = preds
        
        threshold = thresholds[name]
        
        # Evaluate on ROBUST regimes
        if len(robust_regimes) > 0:
            robust_for_model = robust_regimes[robust_regimes['model'] == name]
            
            # Merge to filter OOS signals
            signals = oos_valid[oos_valid[f'prob_{name}'] >= threshold].copy()
            signals = pd.merge(signals, robust_for_model[['regime_vol', 'regime_trend', 'regime_mom']], 
                               on=['regime_vol', 'regime_trend', 'regime_mom'], how='inner')
            
            trade_count = len(signals)
            if trade_count > 0:
                gross_ev = signals['fwd_ret_5'].mean() * 10000
                net_ev = gross_ev - cost_bps
                win_rate = (signals['fwd_ret_5'] > 0).mean()
            else:
                gross_ev = 0.0
                net_ev = 0.0
                win_rate = 0.0
                
            results.append({
                'model': name,
                'classification': 'ROBUST_ECONOMIC_CANDIDATE',
                'trades': trade_count,
                'gross_ev': gross_ev,
                'net_ev': net_ev,
                'win_rate': win_rate
            })
            
        # Evaluate on CONDITIONAL regimes (for tracking)
        if len(conditional_regimes) > 0:
            cond_for_model = conditional_regimes[conditional_regimes['model'] == name]
            
            signals = oos_valid[oos_valid[f'prob_{name}'] >= threshold].copy()
            signals = pd.merge(signals, cond_for_model[['regime_vol', 'regime_trend', 'regime_mom']], 
                               on=['regime_vol', 'regime_trend', 'regime_mom'], how='inner')
            
            trade_count = len(signals)
            if trade_count > 0:
                gross_ev = signals['fwd_ret_5'].mean() * 10000
                net_ev = gross_ev - cost_bps
                win_rate = (signals['fwd_ret_5'] > 0).mean()
            else:
                gross_ev = 0.0
                net_ev = 0.0
                win_rate = 0.0
                
            results.append({
                'model': name,
                'classification': 'CONDITIONAL_EDGE',
                'trades': trade_count,
                'gross_ev': gross_ev,
                'net_ev': net_ev,
                'win_rate': win_rate
            })
            
    print("\n--- OOS EVALUATION RESULTS ---")
    if len(results) > 0:
        res_df = pd.DataFrame(results)
        print(res_df.to_string(index=False))
    else:
        print("No eligible regimes found to trade in OOS.")
        
    oos_predictions.to_parquet(os.path.join(out_dir, "oos_predictions.parquet"))
    print("\nSaved OOS predictions.")

if __name__ == '__main__':
    run_exp_029()
