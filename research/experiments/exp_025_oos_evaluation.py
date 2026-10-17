import pandas as pd
import numpy as np
import json
import os
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

def run_oos_evaluation():
    print("========================================")
    print("EXP 025: OOS EVALUATION")
    print("========================================")
    
    with open(r"c:\Users\dopa.mine\Desktop\ophelia\research\configs\phase5_4_1_locked_config.json", 'r') as f:
        config = json.load(f)
        
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4_1"
    train_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    oos_path = os.path.join(out_dir, "BTCUSDT_microstructure_oos.parquet")
    
    train_df = pd.read_parquet(train_path)
    oos_df = pd.read_parquet(oos_path)
    
    for c in ['open', 'high', 'low', 'close', 'volume']:
        train_df[c] = train_df[c].astype(float)
        oos_df[c] = oos_df[c].astype(float)
        
    def add_features(df):
        df['ret_1'] = df['close'].pct_change(1)
        df['ret_5'] = df['close'].pct_change(5)
        df['ret_15'] = df['close'].pct_change(15)
        df['vol_15'] = df['ret_1'].rolling(15).std()
        df['mom_5'] = df['close'] / df['close'].shift(5) - 1
        df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
        df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
        
        # Target: 5m forward return
        df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
        df['target'] = (df['fwd_ret_5'] > 0).astype(int)
        
        # MAE and MFE
        df['min_fwd_5'] = df['low'].rolling(5).min().shift(-5) / df['close'] - 1
        df['max_fwd_5'] = df['high'].rolling(5).max().shift(-5) / df['close'] - 1
        return df
        
    train_df = add_features(train_df)
    oos_df = add_features(oos_df)
    
    # ---------------------------------------------------------
    # LABEL PURGE / EMBARGO CHECK
    # ---------------------------------------------------------
    # train_df['timestamp'] is candle OPEN.
    # candle close is timestamp + 60000 - 1
    # target evaluates return after 5 minutes, so outcome completes at timestamp + 6 * 60000 - 1
    # For safety, label end is timestamp + 6 * 60000
    
    # We must purge any training labels that overlap with OOS
    min_oos_ts = oos_df['timestamp'].min()
    train_df['target_end_time'] = train_df['timestamp'] + (6 * 60000)
    
    overlap_mask = train_df['target_end_time'] >= min_oos_ts
    purged_count = overlap_mask.sum()
    if purged_count > 0:
        print(f"LABEL PURGE: Purging {purged_count} training rows due to OOS overlap.")
        train_df = train_df[~overlap_mask].copy()
        
    if train_df['target_end_time'].max() >= min_oos_ts:
        print(f"Max train target end: {train_df['target_end_time'].max()}")
        print(f"Min OOS ts:           {min_oos_ts}")
        
    assert train_df['target_end_time'].max() < min_oos_ts, "OOS Purity Violation: Train labels extend into OOS period!"
    
    # ---------------------------------------------------------
    # COMMON SAMPLE RULE
    # ---------------------------------------------------------
    base_features = config['baseline_features']
    micro_features = config['microstructure_features']
    all_features = base_features + micro_features
    
    train_valid = train_df.dropna(subset=all_features + ['fwd_ret_5']).copy()
    
    oos_baseline_valid = oos_df.dropna(subset=base_features + ['fwd_ret_5']).copy()
    oos_micro_valid = oos_df.dropna(subset=micro_features + ['fwd_ret_5']).copy()
    oos_common = oos_df.dropna(subset=all_features + ['fwd_ret_5']).copy()
    
    print("\n--- OOS Sample Selection Bias Analysis ---")
    print(f"Total OOS Rows:               {len(oos_df)}")
    print(f"Baseline Eligible OOS Rows:   {len(oos_baseline_valid)}")
    print(f"Microstructure Eligible OOS:  {len(oos_micro_valid)}")
    print(f"Common Eligible OOS Rows:     {len(oos_common)}")
    print(f"Rows excluded from Baseline:  {len(oos_baseline_valid) - len(oos_common)}")
    
    # Use strictly the common sample for OOS
    oos_eval = oos_common
    
    # ---------------------------------------------------------
    # TRAINING AND EVALUATION
    # ---------------------------------------------------------
    
    models_to_test = {
        'Baseline': base_features,
        'Base + All Micro': all_features
    }
    
    results = {}
    oos_predictions = pd.DataFrame({'timestamp': oos_eval['timestamp'], 'target': oos_eval['target']})
    
    for name, feats in models_to_test.items():
        X_train = train_valid[feats]
        y_train = train_valid['target']
        X_test = oos_eval[feats]
        y_test = oos_eval['target']
        
        clf = LogisticRegression(max_iter=config['model_parameters']['max_iter'], 
                                 random_state=config['model_parameters']['random_state'])
        clf.fit(X_train, y_train)
        
        preds = clf.predict_proba(X_test)[:, 1]
        oos_predictions[f'prob_{name.replace(" ", "_")}'] = preds
        
        auc = roc_auc_score(y_test, preds)
        brier = brier_score_loss(y_test, preds)
        
        # 90th percentile threshold from TRAIN
        train_preds = clf.predict_proba(X_train)[:, 1]
        threshold = pd.Series(train_preds).quantile(0.9)
        
        # Predict on OOS
        test_df_copy = oos_eval.copy()
        test_df_copy['prob'] = preds
        signals = test_df_copy[test_df_copy['prob'] >= threshold]
        
        gross_ev = signals['fwd_ret_5'].mean() * 10000
        cost_bps = config['cost_assumptions_bps']
        net_ev = gross_ev - cost_bps
        
        mae = signals['min_fwd_5'].mean() * 10000
        mfe = signals['max_fwd_5'].mean() * 10000
        
        target_hit_rate = (signals['max_fwd_5'] >= 0.002).mean() # Approx 20 bps target
        stop_hit_rate = (signals['min_fwd_5'] <= -0.001).mean()  # Approx 10 bps stop
        
        results[name] = {
            'auc': auc,
            'brier': brier,
            'gross_ev': gross_ev,
            'net_ev': net_ev,
            'mae': mae,
            'mfe': mfe,
            'trade_count': len(signals),
            'target_rate': target_hit_rate,
            'stop_rate': stop_hit_rate
        }
        
    print("\n--- OOS Primary Comparison ---")
    print(f"{'Model':<20s} | {'AUC':<6s} | {'Brier':<6s} | {'Gross EV':<10s} | {'Net EV(12b)':<12s} | {'Trades':<8s}")
    for name, r in results.items():
        print(f"{name:<20s} | {r['auc']:.4f} | {r['brier']:.4f} | {r['gross_ev']:>6.2f} bps | {r['net_ev']:>7.2f} bps | {r['trade_count']:>8d}")
        
    base_gross = results['Baseline']['gross_ev']
    micro_gross = results['Base + All Micro']['gross_ev']
    inc_gross = micro_gross - base_gross
    print(f"\nIncremental Gross EV: {inc_gross:.2f} bps")
    print(f"Incremental Net EV:   {inc_gross:.2f} bps")
    
    # ---------------------------------------------------------
    # SAVE PREDICTIONS
    # ---------------------------------------------------------
    res_dir = r"c:\Users\dopa.mine\Desktop\ophelia\research\results\phase5_4_1"
    os.makedirs(res_dir, exist_ok=True)
    preds_path = os.path.join(res_dir, "oos_predictions.parquet")
    oos_predictions.to_parquet(preds_path)
    print(f"\nSaved OOS predictions to {preds_path}")

if __name__ == '__main__':
    run_oos_evaluation()
