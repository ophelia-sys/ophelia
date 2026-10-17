import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def get_baseline_features(df):
    features = []
    # Simple baseline features mimicking Phase 5.3
    # Volatility
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_15'] = df['close'].pct_change(15)
    
    df['vol_15'] = df['ret_1'].rolling(15).std()
    
    # Momentum
    df['mom_5'] = df['close'] / df['close'].shift(5) - 1
    
    features = ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5']
    return df, features

def get_microstructure_features(df):
    # These are already in the parquet from EXP 017
    # Note: 'cvd' is raw sum, 'snapshot_ofi_proxy' is raw sum. 
    # Let's normalize them by volume to make them stationary across regimes.
    df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
    df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
    
    return ['cvd_norm', 'snapshot_ofi_proxy_norm', 'mean_queue_imbalance', 'mean_relative_spread']

def run_ablation():
    print("========================================")
    print("EXP 018/019: BASELINE & MICROSTRUCTURE ABLATION")
    print("========================================")
    
    data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    if not os.path.exists(data_path):
        print("Data not found. Waiting for Exp 017.")
        return
        
    df = pd.read_parquet(data_path)
    # Convert types
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
        
    df, base_features = get_baseline_features(df)
    micro_features = get_microstructure_features(df)
    
    # Labels (Predict if next 5m return > 0)
    # Using 1m candles, so target is close shifted -5 vs close
    df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
    df['target'] = (df['fwd_ret_5'] > 0).astype(int)
    
    # Only dropna on the features we actually use
    used_cols = base_features + micro_features + ['fwd_ret_5', 'target']
    df = df.dropna(subset=used_cols)
    
    # Time split (Train: first 10 days, Test: last 5 days)
    # 15 days total.
    split_idx = int(len(df) * 0.66)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    print(f"Train samples: {len(train_df)}, Test samples: {len(test_df)}")
    
    models = {
        'Baseline': base_features,
        'Base + CVD': base_features + ['cvd_norm'],
        'Base + OFI Proxy': base_features + ['snapshot_ofi_proxy_norm'],
        'Base + Queue Imbal': base_features + ['mean_queue_imbalance'],
        'Base + Spread': base_features + ['mean_relative_spread'],
        'Base + All Micro': base_features + micro_features
    }
    
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
        
        # Calculate naive gross EV (Top decile long-only)
        test_df_copy = test_df.copy()
        test_df_copy['prob'] = preds
        threshold = test_df_copy['prob'].quantile(0.9)
        signals = test_df_copy[test_df_copy['prob'] >= threshold]
        
        gross_return = signals['fwd_ret_5'].mean()
        
        # 12 bps execution cost assumed per trade (round trip)
        net_return = gross_return - 0.0012
        
        results[name] = {
            'AUC': auc,
            'Gross EV (bps)': gross_return * 10000,
            'Net EV (bps)': net_return * 10000
        }
        
    print("\n--- Ablation Results ---")
    for name, res in results.items():
        print(f"{name:20s} | AUC: {res['AUC']:.4f} | Gross EV: {res['Gross EV (bps)']:.2f} bps | Net EV: {res['Net EV (bps)']:.2f} bps")
        
if __name__ == '__main__':
    import os
    run_ablation()
