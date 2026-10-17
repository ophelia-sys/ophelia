import os
import sys
import pandas as pd
import numpy as np

# Ensure imports work without installing as package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import DataSplitter, PurgedWalkForwardValidation
from research.pipeline.models import get_model
from research.pipeline.metrics import MetricsEvaluator

def run_experiment():
    print("--- Stage A: Target & Horizon Discovery ---")
    
    loader = ResearchDataLoader()
    df = loader.load_symbol("BTCUSDT")
    
    # 1. Temporal Split (Discovery vs Locked OOS)
    # We restrict to 2022+ to ensure consistent dataset density
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['dt'].dt.year >= 2022].copy()
    
    discovery_df, _ = DataSplitter.split_discovery_oos(df, split_date_str="2023-09-01")
    print(f"Discovery Set Size: {len(discovery_df)}")
    
    # Horizons in 5m candles: 12 (1hr), 60 (5hr)
    horizons = [12, 60]
    thresholds_bps = [10, 15, 20]
    
    # Generate all labels
    discovery_df = LabelGenerator.generate_labels(discovery_df, horizons=horizons, thresholds_bps=thresholds_bps)
    
    # We will use the full feature set to evaluate the horizons
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    discovery_df = FeatureGenerator.generate_features(discovery_df, families)
    feature_cols = FeatureGenerator.get_feature_columns(families)
    
    results = []
    
    for h in horizons:
        fwd_return_col = f'R_{h}'
        
        for t_bps in thresholds_bps:
            target_col = f'target_{h}_up_{t_bps}'
            print(f"Evaluating: Horizon {h}, Target {target_col}", flush=True)
            
            valid_cols = feature_cols + [target_col, fwd_return_col]
            clean_df = discovery_df.dropna(subset=valid_cols).reset_index(drop=True)
            
            validator = PurgedWalkForwardValidation(n_folds=3, embargo=h)
            splits = validator.split(clean_df)
            
            y_true_oos = []
            y_pred_oos = []
            R_fwd_oos = []
            
            for train_idx, test_idx in splits:
                if len(train_idx) < 100 or len(test_idx) < 100: continue
                
                X_train = clean_df.loc[train_idx, feature_cols]
                y_train = clean_df.loc[train_idx, target_col]
                
                X_test = clean_df.loc[test_idx, feature_cols]
                y_test = clean_df.loc[test_idx, target_col]
                R_test = clean_df.loc[test_idx, fwd_return_col]
                
                # We expect targets to have some balance. If one class is too small, skip or note.
                if y_train.mean() < 0.01 or y_train.mean() > 0.99:
                    continue
                
                model = get_model('logistic')
                model.fit(X_train, y_train)
                preds = model.predict_proba(X_test)[:, 1]
                
                y_true_oos.extend(y_test.values)
                y_pred_oos.extend(preds)
                R_fwd_oos.extend(R_test.values)
                
            if len(y_true_oos) < 100:
                continue
                
            y_true_oos = np.array(y_true_oos)
            y_pred_oos = np.array(y_pred_oos)
            R_fwd_oos = np.array(R_fwd_oos)
            
            metrics = MetricsEvaluator.evaluate(y_true_oos, y_pred_oos, R_fwd_oos, costs_bps=12, fast=True)
            
            results.append({
                'horizon': h,
                'target': target_col,
                'class_balance': y_true_oos.mean(),
                'auc': metrics['auc'],
                'ci_lower': metrics['ci'][0],
                'ci_upper': metrics['ci'][1],
                'brier': metrics['brier'],
                'top_decile_gross_bps': metrics['deciles'][-1]['gross_ret_bps'] if metrics['deciles'] else None,
                'top_decile_net_bps': metrics['deciles'][-1]['net_ret_bps'] if metrics['deciles'] else None,
            })
            
    # Save Report
    output_path = os.path.join("research", "EXPERIMENT_002_REPORT.md")
    with open(output_path, "w") as f:
        f.write("# STAGE A: Target & Horizon Discovery (Exp 002)\n\n")
        f.write("## Hypothesis\n")
        f.write("Does altering the prediction horizon or using fixed threshold targets provide an economically viable edge?\n\n")
        f.write("| Horizon | Target | Balance | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for res in results:
            ci_str = f"[{res['ci_lower']:.4f}, {res['ci_upper']:.4f}]"
            gross = f"{res['top_decile_gross_bps']:.2f}" if res['top_decile_gross_bps'] is not None else "N/A"
            net = f"{res['top_decile_net_bps']:.2f}" if res['top_decile_net_bps'] is not None else "N/A"
            f.write(f"| {res['horizon']} | {res['target']} | {res['class_balance']:.4f} | {res['auc']:.4f} | {ci_str} | {res['brier']:.4f} | {gross} | {net} |\n")
            
    print(f"\nStage A completed. Report saved to {output_path}")

if __name__ == "__main__":
    run_experiment()
