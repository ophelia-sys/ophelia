import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def run_independent_reconciliation():
    print("========================================")
    print("EXP 023: INDEPENDENT RECONCILIATION")
    print("========================================")
    
    # 1. Load Data
    data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    df = pd.read_parquet(data_path)
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
        
    initial_rows = len(df)
    
    # 2. Features
    df['ret_1'] = df['close'].pct_change(1)
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_15'] = df['close'].pct_change(15)
    df['vol_15'] = df['ret_1'].rolling(15).std()
    df['mom_5'] = df['close'] / df['close'].shift(5) - 1
    df['cvd_norm'] = df['cvd'] / (df['volume'] + 1e-8)
    df['snapshot_ofi_proxy_norm'] = df['snapshot_ofi_proxy'] / (df['volume'] + 1e-8)
    
    features = ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5', 
                'cvd_norm', 'snapshot_ofi_proxy_norm', 'mean_queue_imbalance', 'mean_relative_spread']
                
    # 3. Target and Metrics
    df['fwd_ret_5'] = df['close'].shift(-5) / df['close'] - 1
    df['target'] = (df['fwd_ret_5'] > 0).astype(int)
    
    df['min_fwd_5'] = df['low'].rolling(5).min().shift(-5) / df['close'] - 1
    df['max_fwd_5'] = df['high'].rolling(5).max().shift(-5) / df['close'] - 1
    
    df = df.dropna(subset=features + ['fwd_ret_5'])
    eligible_rows = len(df)
    
    # 4. Train / Test Split
    split_idx = int(len(df) * 0.66)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    # 5. Model
    X_train = train_df[features]
    y_train = train_df['target']
    X_test = test_df[features]
    y_test = test_df['target']
    
    clf = LogisticRegression(max_iter=1000, random_state=42)
    clf.fit(X_train, y_train)
    preds = clf.predict_proba(X_test)[:, 1]
    
    # 6. Metrics
    auc = roc_auc_score(y_test, preds)
    test_df_copy = test_df.copy()
    test_df_copy['prob'] = preds
    threshold = test_df_copy['prob'].quantile(0.9)
    signals = test_df_copy[test_df_copy['prob'] >= threshold]
    
    gross_ev = signals['fwd_ret_5'].mean() * 10000
    cost_bps = 12.0
    net_ev = gross_ev - cost_bps
    break_even = gross_ev
    
    mae = signals['min_fwd_5'].mean() * 10000
    mfe = signals['max_fwd_5'].mean() * 10000
    
    print(f"Total Rows:            {initial_rows}")
    print(f"Eligible Rows:         {eligible_rows}")
    print(f"Test Samples:          {len(test_df)}")
    print(f"Signals Generated:     {len(signals)}")
    print(f"Target Rate (Test):    {y_test.mean():.4f}")
    print("-" * 30)
    print(f"AUC:                   {auc:.4f}")
    print(f"Gross EV:              {gross_ev:.2f} bps")
    print(f"Cost Assumption:       {cost_bps:.2f} bps")
    print(f"Net EV:                {net_ev:.2f} bps")
    print(f"Break-even Cost:       {break_even:.2f} bps")
    print(f"MAE:                   {mae:.2f} bps")
    print(f"MFE:                   {mfe:.2f} bps")
    
if __name__ == '__main__':
    run_independent_reconciliation()
