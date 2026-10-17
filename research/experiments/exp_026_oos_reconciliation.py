import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss

def run_independent_reconciliation():
    print("========================================")
    print("EXP 026: INDEPENDENT RECONCILIATION")
    print("========================================")
    
    oos_data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4_1\BTCUSDT_microstructure_oos.parquet"
    train_data_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_4\BTCUSDT_microstructure.parquet"
    preds_path = r"c:\Users\dopa.mine\Desktop\ophelia\research\results\phase5_4_1\oos_predictions.parquet"
    
    oos_df = pd.read_parquet(oos_data_path)
    train_df = pd.read_parquet(train_data_path)
    preds_df = pd.read_parquet(preds_path)
    
    # Independent recalculation of MAE, MFE, FWD_RET
    oos_df['fwd_ret_5'] = oos_df['close'].shift(-5) / oos_df['close'] - 1
    oos_df['min_fwd_5'] = oos_df['low'].rolling(5).min().shift(-5) / oos_df['close'] - 1
    oos_df['max_fwd_5'] = oos_df['high'].rolling(5).max().shift(-5) / oos_df['close'] - 1
    oos_df['target_calc'] = (oos_df['fwd_ret_5'] > 0).astype(int)
    
    # Merge predictions
    eval_df = pd.merge(oos_df, preds_df, on='timestamp', how='inner')
    
    print(f"Total OOS Rows:            {len(oos_df)}")
    print(f"Common Sample Count:       {len(eval_df)}")
    print(f"Target Rate:               {eval_df['target_calc'].mean():.4f}")
    
    models = {
        'Baseline': 'prob_Baseline',
        'Base + All Micro': 'prob_Base_+_All_Micro'
    }
    
    cost_bps = 12.0
    
    for name, prob_col in models.items():
        auc = roc_auc_score(eval_df['target_calc'], eval_df[prob_col])
        brier = brier_score_loss(eval_df['target_calc'], eval_df[prob_col])
        
        # We need the train threshold which was generated independently in 025.
        # But we can reconstruct it from train_df if we had the models.
        # To make it fully independent, we just take the top 10% of the scores if threshold isn't provided, 
        # but threshold was fixed based on TRAIN 90th percentile. We don't have the exact threshold stored.
        # Since we must independently reconcile, we'll infer the trade count directly from the actual signals logic.
        # Let's rebuild the model to get the exact train threshold.
        from sklearn.linear_model import LogisticRegression
        
        # Features
        feats_baseline = ['ret_1', 'ret_5', 'ret_15', 'vol_15', 'mom_5']
        feats_micro = ['cvd_norm', 'snapshot_ofi_proxy_norm', 'mean_queue_imbalance', 'mean_relative_spread']
        if name == 'Baseline':
            feats = feats_baseline
        else:
            feats = feats_baseline + feats_micro
            
        train_df['ret_1'] = train_df['close'].pct_change(1)
        train_df['ret_5'] = train_df['close'].pct_change(5)
        train_df['ret_15'] = train_df['close'].pct_change(15)
        train_df['vol_15'] = train_df['ret_1'].rolling(15).std()
        train_df['mom_5'] = train_df['close'] / train_df['close'].shift(5) - 1
        train_df['cvd_norm'] = train_df['cvd'] / (train_df['volume'] + 1e-8)
        train_df['snapshot_ofi_proxy_norm'] = train_df['snapshot_ofi_proxy'] / (train_df['volume'] + 1e-8)
        train_df['fwd_ret_5'] = train_df['close'].shift(-5) / train_df['close'] - 1
        train_df['target'] = (train_df['fwd_ret_5'] > 0).astype(int)
        
        # Filter overlapping train rows
        train_df['target_end_time'] = train_df['timestamp'] + 6 * 60000
        min_oos_ts = oos_df['timestamp'].min()
        train_valid = train_df[train_df['target_end_time'] < min_oos_ts].dropna(subset=feats_baseline + feats_micro + ['fwd_ret_5']).copy()
        
        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(train_valid[feats], train_valid['target'])
        
        train_preds = clf.predict_proba(train_valid[feats])[:, 1]
        threshold = pd.Series(train_preds).quantile(0.9)
        
        signals = eval_df[eval_df[prob_col] >= threshold]
        
        gross_ev = signals['fwd_ret_5'].mean() * 10000
        net_ev = gross_ev - cost_bps
        
        mae = signals['min_fwd_5'].mean() * 10000
        mfe = signals['max_fwd_5'].mean() * 10000
        
        target_hit_rate = (signals['max_fwd_5'] >= 0.002).mean() 
        stop_hit_rate = (signals['min_fwd_5'] <= -0.001).mean()  
        
        print(f"\n[{name}]")
        print(f"AUC:                 {auc:.4f}")
        print(f"Brier:               {brier:.4f}")
        print(f"Trade Count:         {len(signals)}")
        print(f"Gross EV:            {gross_ev:.2f} bps")
        print(f"Net EV:              {net_ev:.2f} bps")
        print(f"MAE:                 {mae:.2f} bps")
        print(f"MFE:                 {mfe:.2f} bps")
        print(f"Target Hit Rate:     {target_hit_rate:.4f}")
        print(f"Stop Hit Rate:       {stop_hit_rate:.4f}")

if __name__ == '__main__':
    run_independent_reconciliation()
