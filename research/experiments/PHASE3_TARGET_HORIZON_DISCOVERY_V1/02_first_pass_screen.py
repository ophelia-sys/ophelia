import os
import sys
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.validation import PurgedWalkForwardValidation
from research.experiments.PHASE2_EDGE_DISCOVERY_V1.features import build_base_features

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]
DEV_END_DATE = pd.to_datetime("2023-06-30 23:59:59")

# Selected diagonal grid based on feasibility (Thresholds >= 15bps)
GRID = [
    (30, 15), (30, 20), (30, 30),
    (60, 20), (60, 30), (60, 50),
    (120, 30), (120, 50), (120, 75),
    (240, 50), (240, 75), (240, 100)
]

def evaluate_predictions(y_true, y_prob, returns, threshold=0.95):
    auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.5
    pr_auc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else y_true.mean()
    brier = brier_score_loss(y_true, y_prob)
    
    q_thresh = np.quantile(y_prob, threshold)
    mask = y_prob > q_thresh
    
    selected_returns = returns[mask]
    gross_exp = selected_returns.mean() * 10000 if len(selected_returns) > 0 else 0
    net_12 = gross_exp - 12 if len(selected_returns) > 0 else 0
    
    return {
        'auc': auc,
        'pr_auc': pr_auc,
        'brier': brier,
        'gross_exp': gross_exp,
        'net_12': net_12,
        'signals': mask.sum()
    }

def run_grid():
    loader = ResearchDataLoader()
    
    # Load and prep data globally to save time
    data_cache = {}
    for sym in SYMBOLS:
        print(f"Pre-computing features for {sym}...")
        df_1m = loader.load_symbol(sym)
        df_5m = build_base_features(df_1m)
        df_dev = df_5m[df_5m.index <= DEV_END_DATE].copy()
        data_cache[sym] = df_dev
        
    model_params = {'n_estimators': 100, 'learning_rate': 0.05, 'max_depth': 3, 'num_leaves': 7, 'random_state': 42}
    feature_list = [c for c in data_cache[SYMBOLS[0]].columns if c not in ['open', 'high', 'low', 'close', 'volume', 'delta_v', 'timestamp']]
    
    results = []
    
    for h_min, t_bps in GRID:
        h_bars = h_min // 5
        t_dec = t_bps / 10000.0
        
        print(f"\n======================================")
        print(f"EVALUATING HORIZON: {h_min}m | THRESHOLD: {t_bps}bps")
        print(f"======================================")
        
        all_long_preds, all_short_preds = [], []
        all_long_true, all_short_true = [], []
        all_long_ret, all_short_ret = [], []
        
        for sym in SYMBOLS:
            df = data_cache[sym].copy()
            df[f'R_{h_min}'] = np.log(df['close'].shift(-h_bars) / df['close'])
            df['target_long'] = (df[f'R_{h_min}'] > t_dec).astype(int)
            df['target_short'] = (df[f'R_{h_min}'] < -t_dec).astype(int)
            
            df.loc[df.index[-h_bars:], ['target_long', 'target_short', f'R_{h_min}']] = np.nan
            df.dropna(subset=feature_list + ['target_long', 'target_short', f'R_{h_min}'], inplace=True)
            
            X = df[feature_list]
            y_l = df['target_long']
            y_s = df['target_short']
            rets = df[f'R_{h_min}']
            
            # Dynamic Embargo: max(12, horizon_bars) + standard 288 feature lookback allowance if needed, 
            # but PurgedWalkForward Validation only handles target overlap purging.
            # We embargo max(12, horizon_bars) to prevent target leakage.
            embargo_bars = max(12, h_bars)
            cv = PurgedWalkForwardValidation(n_folds=5, embargo=embargo_bars)
            splits = cv.split(X)
            
            for tr_idx, te_idx in splits:
                X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
                
                # LONG
                clf_l = lgb.LGBMClassifier(**model_params, verbose=-1)
                clf_l.fit(X_tr, y_l.iloc[tr_idx])
                all_long_preds.extend(clf_l.predict_proba(X_te)[:, 1])
                all_long_true.extend(y_l.iloc[te_idx])
                all_long_ret.extend(rets.iloc[te_idx])
                
                # SHORT
                clf_s = lgb.LGBMClassifier(**model_params, verbose=-1)
                clf_s.fit(X_tr, y_s.iloc[tr_idx])
                all_short_preds.extend(clf_s.predict_proba(X_te)[:, 1])
                all_short_true.extend(y_s.iloc[te_idx])
                all_short_ret.extend(-rets.iloc[te_idx])
                
        # Evaluate GLOBALLY
        l_mets = evaluate_predictions(np.array(all_long_true), np.array(all_long_preds), np.array(all_long_ret))
        s_mets = evaluate_predictions(np.array(all_short_true), np.array(all_short_preds), np.array(all_short_ret))
        
        # Combined Expectancy (Top 5%)
        q_l = np.quantile(all_long_preds, 0.95)
        q_s = np.quantile(all_short_preds, 0.95)
        mask_l = np.array(all_long_preds) > q_l
        mask_s = np.array(all_short_preds) > q_s
        
        ret_l = np.array(all_long_ret)[mask_l] * 10000
        ret_s = np.array(all_short_ret)[mask_s] * 10000
        comb_ret = np.concatenate([ret_l, ret_s])
        
        comb_gross = comb_ret.mean() if len(comb_ret) > 0 else 0
        comb_net = comb_gross - 12
        
        print(f"LONG AUC: {l_mets['auc']:.4f} | SHORT AUC: {s_mets['auc']:.4f}")
        print(f"COMBINED GROSS: {comb_gross:.2f} bps | NET (12bps): {comb_net:.2f} bps")
        
        results.append({
            'horizon_m': h_min,
            'threshold_bps': t_bps,
            'long_auc': l_mets['auc'],
            'short_auc': s_mets['auc'],
            'comb_gross_exp': comb_gross,
            'comb_net_exp': comb_net,
            'signals': len(comb_ret)
        })
        
    df_res = pd.DataFrame(results)
    out_path = os.path.join(os.path.dirname(__file__), "first_pass_screen_results.csv")
    df_res.to_csv(out_path, index=False)
    
    # Save a txt summary
    with open(os.path.join(os.path.dirname(__file__), "FIRST_PASS_SUMMARY.md"), "w") as f:
        f.write("# PHASE 3 - FIRST PASS SCREEN\n\n")
        f.write(df_res.to_string(index=False))

if __name__ == "__main__":
    run_grid()
