import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def get_baseline_features(df):
    features = []
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_15'] = df['close'].pct_change(15)
    df['vol_15'] = df['ret_1'].rolling(15).std()
    df['mom_5'] = df['close'] / df['close'].shift(5) - 1
    features = ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5']
    return df, features

def get_microstructure_features(df):
    df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
    df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
    return ['cvd_norm', 'snapshot_ofi_proxy_norm', 'mean_queue_imbalance', 'mean_relative_spread']

def run_cost_sensitivity():
    print("========================================")
    print("EXP 020/021: EVENT MODEL & COST SENSITIVITY")
    print("========================================")
    
    data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    if not os.path.exists(data_path):
        print("Data not found. Waiting for Exp 017.")
        return
        
    df = pd.read_parquet(data_path)
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
        
    df, base_features = get_baseline_features(df)
    micro_features = get_microstructure_features(df)
    
    df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
    df['target'] = (df['fwd_ret_5'] > 0).astype(int)
    
    used_cols = base_features + micro_features + ['fwd_ret_5', 'target']
    df = df.dropna(subset=used_cols)
    
    split_idx = int(len(df) * 0.66)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    models = {
        'Baseline': base_features,
        'Base + All Micro': base_features + micro_features
    }
    
    costs_bps = [6, 8, 10, 12, 15, 20]
    
    for name, feats in models.items():
        print(f"\n--- {name} ---")
        X_train = train_df[feats]
        y_train = train_df['target']
        X_test = test_df[feats]
        y_test = test_df['target']
        
        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(X_train, y_train)
        preds = clf.predict_proba(X_test)[:, 1]
        
        test_df_copy = test_df.copy()
        test_df_copy['prob'] = preds
        threshold = test_df_copy['prob'].quantile(0.9)
        signals = test_df_copy[test_df_copy['prob'] >= threshold]
        
        gross_return_bps = signals['fwd_ret_5'].mean() * 10000
        print(f"Gross EV: {gross_return_bps:.2f} bps")
        print("Cost Sensitivity (Net EV):")
        
        for cost in costs_bps:
            net_bps = gross_return_bps - cost
            print(f"  Cost: {cost:2d} bps -> Net: {net_bps:6.2f} bps")
            
        # Break-even cost
        print(f"Break-even Execution Cost: {gross_return_bps:.2f} bps")
        
if __name__ == '__main__':
    import os
    run_cost_sensitivity()
