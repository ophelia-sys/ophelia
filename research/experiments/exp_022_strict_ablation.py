import pandas as pd
import numpy as np
import os
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def get_baseline_features(df):
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_15'] = df['close'].pct_change(15)
    df['vol_15'] = df['ret_1'].rolling(15).std()
    df['mom_5'] = df['close'] / df['close'].shift(5) - 1
    return ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5']

def get_microstructure_features(df):
    df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
    df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
    return ['cvd_norm', 'snapshot_ofi_proxy_norm', 'mean_queue_imbalance', 'mean_relative_spread']

def run_strict_ablation():
    print("========================================")
    print("EXP 022: STRICT COMMON-SAMPLE ABLATION")
    print("========================================")
    
    data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    if not os.path.exists(data_path):
        print("Data not found.")
        return
        
    df = pd.read_parquet(data_path)
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
        
    base_features = get_baseline_features(df)
    micro_features = get_microstructure_features(df)
    
    # Target: 5m forward return
    df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
    df['target'] = (df['fwd_ret_5'] > 0).astype(int)
    
    # MAE and MFE (Max Adverse/Favorable Excursion)
    df['min_fwd_5'] = df['low'].rolling(5).min().shift(-5) / df['close'] - 1
    df['max_fwd_5'] = df['high'].rolling(5).max().shift(-5) / df['close'] - 1
    
    # Coverage Analysis
    baseline_valid = df.dropna(subset=base_features + ['fwd_ret_5']).copy()
    micro_valid = df.dropna(subset=micro_features + ['fwd_ret_5']).copy()
    common_sample = df.dropna(subset=base_features + micro_features + ['fwd_ret_5']).copy()
    
    print("\n--- Sample Selection Bias Analysis ---")
    print(f"Baseline Eligible Rows:       {len(baseline_valid)}")
    print(f"Microstructure Eligible Rows: {len(micro_valid)}")
    print(f"Common Eligible Rows:         {len(common_sample)}")
    
    rows_lost = len(baseline_valid) - len(common_sample)
    print(f"Rows Lost from Baseline:      {rows_lost}")
    if rows_lost > 0:
        lost_df = baseline_valid[~baseline_valid.index.isin(common_sample.index)]
        print("Reason for loss: Missing Microstructure Data (likely API gaps or zero volume)")
        print(f"Mean Volatility (Lost):   {lost_df['vol_15'].mean():.6f}")
        print(f"Mean Volatility (Common): {common_sample['vol_15'].mean():.6f}")
    
    # Use STRICTLY the common sample
    df = common_sample
    
    split_idx = int(len(df) * 0.66)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    print(f"\nCommon Train Samples: {len(train_df)}, Common Test Samples: {len(test_df)}")
    
    models = {
        'Baseline': base_features,
        'Base + CVD': base_features + ['cvd_norm'],
        'Base + OFI Proxy': base_features + ['snapshot_ofi_proxy_norm'],
        'Base + Queue Imbal': base_features + ['mean_queue_imbalance'],
        'Base + Spread': base_features + ['mean_relative_spread'],
        'Base + All Micro': base_features + micro_features
    }
    
    print("\n--- Ablation Results (Common Sample) ---")
    print(f"{'Model':<20s} | {'AUC':<6s} | {'Gross EV':<10s} | {'Net EV(12b)':<12s} | {'MAE':<8s} | {'MFE':<8s}")
    
    results = {}
    for name, feats in models.items():
        X_train = train_df[feats]
        y_train = train_df['target']
        X_test = test_df[feats]
        y_test = test_df['target']
        
        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(X_train, y_train)
        preds = clf.predict_proba(X_test)[:, 1]
        
        auc = roc_auc_score(y_test, preds)
        
        test_df_copy = test_df.copy()
        test_df_copy['prob'] = preds
        threshold = test_df_copy['prob'].quantile(0.9)
        signals = test_df_copy[test_df_copy['prob'] >= threshold]
        
        gross_ev = signals['fwd_ret_5'].mean()
        net_ev = gross_ev - 0.0012 # 12 bps cost explicitly
        
        mae = signals['min_fwd_5'].mean()
        mfe = signals['max_fwd_5'].mean()
        
        results[name] = {
            'auc': auc,
            'gross': gross_ev * 10000,
            'net': net_ev * 10000,
            'mae': mae * 10000,
            'mfe': mfe * 10000
        }
        
        print(f"{name:<20s} | {auc:.4f} | {gross_ev*10000:>6.2f} bps | {net_ev*10000:>7.2f} bps | {mae*10000:>6.2f} | {mfe*10000:>6.2f}")
        
if __name__ == '__main__':
    run_strict_ablation()
