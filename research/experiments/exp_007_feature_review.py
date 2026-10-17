import pandas as pd
import numpy as np
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import DataSplitter, PurgedWalkForwardValidation
from research.pipeline.models import get_model
from research.pipeline.metrics import MetricsEvaluator
import argparse

def run_exp_007(fast=False):
    print("--- Exp 007: Feature Quality Review ---")
    loader = ResearchDataLoader()
    df = loader.load_symbol('BTCUSDT')
    
    # 1. Feature Gen
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    df = FeatureGenerator.generate_features(df, families)
    df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
    
    # 2. Label Gen
    df = LabelGenerator.generate_labels(df, horizons=[60], thresholds_bps=[10])
    
    target_col = 'target_60_up_10'
    base_features = FeatureGenerator.get_feature_columns(families) + ['interact_volume_vol']
    
    df.dropna(subset=base_features + [target_col, 'R_60'], inplace=True)
    discovery, _ = DataSplitter.split_discovery_oos(df)
    
    X = discovery[base_features]
    y = discovery[target_col]
    R = discovery['R_60']
    
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(X)
    
    # Base Evaluation
    def eval_features(feat_list):
        aucs, gross_rets = [], []
        model = get_model('logistic')
        for train_idx, test_idx in splits:
            X_tr, y_tr = X.iloc[train_idx][feat_list], y.iloc[train_idx]
            X_te, y_te, R_te = X.iloc[test_idx][feat_list], y.iloc[test_idx], R.iloc[test_idx]
            
            model.fit(X_tr, y_tr)
            preds = model.predict_proba(X_te)[:, 1]
            
            metrics = MetricsEvaluator.evaluate(y_te, preds, R_te, fast=fast)
            aucs.append(metrics['auc'])
            # Top decile gross is the last decile (9)
            top_dec = metrics['deciles'][-1]
            gross_rets.append(top_dec['gross_ret_bps'])
            
        return np.mean(aucs), np.mean(gross_rets)

    base_auc, base_gross = eval_features(base_features)
    print(f"Base Model -> AUC: {base_auc:.4f}, Gross bps: {base_gross:.2f}")
    
    print("\nMarginal Contribution (Dropping Feature):")
    results = []
    for f in base_features:
        ablated = [col for col in base_features if col != f]
        auc, gross = eval_features(ablated)
        auc_drop = base_auc - auc
        gross_drop = base_gross - gross
        print(f"Drop {f:<15} | AUC Drop: {auc_drop:+.4f} | Gross Drop: {gross_drop:+.2f} bps")
        results.append((f, auc_drop, gross_drop))
        
    with open('research/EXPERIMENT_007_REPORT.md', 'w') as f:
        f.write("# Exp 007: Feature Quality Review\n\n")
        f.write(f"**Base AUC**: {base_auc:.4f} | **Base Gross**: {base_gross:.2f} bps\n\n")
        f.write("| Feature Dropped | AUC Impact | Gross Impact (bps) | Action |\n")
        f.write("|---|---|---|---|\n")
        for f_name, auc_d, gross_d in results:
            action = "KEEP" if auc_d > 0.001 or gross_d > 0.1 else "REVIEW"
            f.write(f"| {f_name} | {auc_d:+.4f} | {gross_d:+.2f} | {action} |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_007(fast=args.fast)
