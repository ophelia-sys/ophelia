import os
import sys
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.validation import PurgedWalkForwardValidation
from research.experiments.PHASE2_EDGE_DISCOVERY_V1.features import build_base_features, add_targets, BASELINE_FEATURES

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]
REGISTRY_PATH = r"c:\Users\dopa.mine\Desktop\ophelia\research\experiments\PHASE2_EDGE_DISCOVERY_V1\experiment_registry.csv"

def evaluate_predictions(y_true, y_prob, returns, mfe=None, mae=None, threshold=0.95):
    """Calculates all requested economic and classification metrics"""
    auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.5
    pr_auc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else y_true.mean()
    
    q_thresh = np.quantile(y_prob, threshold)
    mask = y_prob > q_thresh
    
    selected_returns = returns[mask]
    gross_exp = selected_returns.mean() * 10000 if len(selected_returns) > 0 else 0
    net_12 = gross_exp - 12 if len(selected_returns) > 0 else 0
    
    return {
        'auc': auc,
        'pr_auc': pr_auc,
        'gross_exp': gross_exp,
        'net_12': net_12,
        'signals': mask.sum()
    }

def run_experiment(experiment_id, feature_func, feature_list, model_params=None):
    if model_params is None:
        model_params = {'n_estimators': 100, 'learning_rate': 0.05, 'max_depth': 3, 'num_leaves': 7, 'random_state': 42}
    
    loader = ResearchDataLoader()
    
    all_long_preds, all_short_preds = [], []
    all_long_true, all_short_true = [], []
    all_long_ret, all_short_ret = [], []
    
    total_samples = 0
    
    for sym in SYMBOLS:
        print(f"[{experiment_id}] Processing {sym}...")
        df_1m = loader.load_symbol(sym)
        df_5m = feature_func(df_1m)
        df_5m = add_targets(df_5m, horizon=12)
        
        df_5m.dropna(subset=feature_list + ['target_long', 'target_short', 'R_12'], inplace=True)
        
        X = df_5m[feature_list]
        y_l = df_5m['target_long']
        y_s = df_5m['target_short']
        rets = df_5m['R_12']
        
        cv = PurgedWalkForwardValidation(n_folds=5, embargo=12)
        splits = cv.split(X)
        
        total_samples += len(X)
        
        for fold, (tr_idx, te_idx) in enumerate(splits):
            X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
            
            # LONG
            y_l_tr, y_l_te = y_l.iloc[tr_idx], y_l.iloc[te_idx]
            clf_l = lgb.LGBMClassifier(**model_params)
            clf_l.fit(X_tr, y_l_tr)
            preds_l = clf_l.predict_proba(X_te)[:, 1]
            
            all_long_preds.extend(preds_l)
            all_long_true.extend(y_l_te)
            all_long_ret.extend(rets.iloc[te_idx])
            
            # SHORT
            y_s_tr, y_s_te = y_s.iloc[tr_idx], y_s.iloc[te_idx]
            clf_s = lgb.LGBMClassifier(**model_params)
            clf_s.fit(X_tr, y_s_tr)
            preds_s = clf_s.predict_proba(X_te)[:, 1]
            
            all_short_preds.extend(preds_s)
            all_short_true.extend(y_s_te)
            all_short_ret.extend(-rets.iloc[te_idx])
            
    # Aggregate globally
    l_metrics = evaluate_predictions(np.array(all_long_true), np.array(all_long_preds), np.array(all_long_ret))
    s_metrics = evaluate_predictions(np.array(all_short_true), np.array(all_short_preds), np.array(all_short_ret))
    
    # Combined Expectancy (Top 5% of both)
    q_l = np.quantile(all_long_preds, 0.95)
    q_s = np.quantile(all_short_preds, 0.95)
    
    mask_l = np.array(all_long_preds) > q_l
    mask_s = np.array(all_short_preds) > q_s
    
    ret_l_selected = np.array(all_long_ret)[mask_l] * 10000
    ret_s_selected = np.array(all_short_ret)[mask_s] * 10000
    
    comb_ret = np.concatenate([ret_l_selected, ret_s_selected])
    comb_gross = comb_ret.mean() if len(comb_ret) > 0 else 0
    comb_net = comb_gross - 12
    
    # Log to registry
    import csv
    with open(REGISTRY_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            experiment_id,
            "baseline" if "BASE" in experiment_id else "unknown",
            "LightGBM",
            "R_12 +/- 10bps",
            5,
            total_samples,
            "TBD", "TBD",
            len(feature_list),
            str(model_params),
            l_metrics['auc'],
            s_metrics['auc'],
            comb_gross,
            comb_net,
            "TBD"
        ])
        
    print(f"--- Results {experiment_id} ---")
    print(f"LONG AUC: {l_metrics['auc']:.4f} | SHORT AUC: {s_metrics['auc']:.4f}")
    print(f"COMBINED GROSS: {comb_gross:.2f} bps | NET (12bps): {comb_net:.2f} bps")
    print(f"Total Signals (>0.95): {len(comb_ret)}")


