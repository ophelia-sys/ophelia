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

def run_experiment(horizon: int, target: str):
    print(f"--- Stage B: Feature Discovery ---")
    print(f"Using Locked Target: {target} | Horizon: {horizon}")
    
    loader = ResearchDataLoader()
    df = loader.load_symbol("BTCUSDT")
    
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['dt'].dt.year >= 2022].copy()
    
    discovery_df, _ = DataSplitter.split_discovery_oos(df, split_date_str="2023-09-01")
    
    # We need the threshold bps if it's a threshold target
    thresholds_bps = [10, 15, 20]
    discovery_df = LabelGenerator.generate_labels(discovery_df, horizons=[horizon], thresholds_bps=thresholds_bps)
    
    # Define combinations
    sequences = [
        ['baseline'],
        ['baseline', 'volatility'],
        ['baseline', 'trend'],
        ['baseline', 'momentum'],
        ['baseline', 'volume'],
        ['baseline', 'volatility', 'trend'],
        ['baseline', 'volatility', 'momentum'],
        ['baseline', 'trend', 'momentum'],
        ['baseline', 'trend', 'volume'],
        ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    ]
    
    results = []
    fwd_return_col = f'R_{horizon}'
    
    # Pre-generate all features
    all_fams = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    discovery_df = FeatureGenerator.generate_features(discovery_df, all_fams)
    
    validator = PurgedWalkForwardValidation(n_folds=3, embargo=horizon)
    
    for seq in sequences:
        print(f"Evaluating Features: {seq}")
        feature_cols = FeatureGenerator.get_feature_columns(seq)
        
        valid_cols = feature_cols + [target, fwd_return_col]
        clean_df = discovery_df.dropna(subset=valid_cols).reset_index(drop=True)
        
        splits = validator.split(clean_df)
        
        y_true_oos = []
        y_pred_oos = []
        R_fwd_oos = []
        
        for train_idx, test_idx in splits:
            if len(train_idx) < 100 or len(test_idx) < 100: continue
            
            X_train = clean_df.loc[train_idx, feature_cols]
            y_train = clean_df.loc[train_idx, target]
            X_test = clean_df.loc[test_idx, feature_cols]
            y_test = clean_df.loc[test_idx, target]
            R_test = clean_df.loc[test_idx, fwd_return_col]
            
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
            'features': "+".join(seq),
            'auc': metrics['auc'],
            'ci_lower': metrics['ci'][0],
            'ci_upper': metrics['ci'][1],
            'brier': metrics['brier'],
            'top_decile_gross_bps': metrics['deciles'][-1]['gross_ret_bps'] if metrics['deciles'] else None,
            'top_decile_net_bps': metrics['deciles'][-1]['net_ret_bps'] if metrics['deciles'] else None,
        })
        
    output_path = os.path.join("research", "EXPERIMENT_003_REPORT.md")
    with open(output_path, "w") as f:
        f.write("# STAGE B: Feature Family Discovery (Exp 003)\n\n")
        f.write(f"**Locked Target**: {target} | **Locked Horizon**: {horizon}\n\n")
        f.write("| Features | AUC | 95% CI | Brier | Top Dec Gross (bps) | Top Dec Net (bps) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for res in results:
            ci_str = f"[{res['ci_lower']:.4f}, {res['ci_upper']:.4f}]"
            gross = f"{res['top_decile_gross_bps']:.2f}" if res['top_decile_gross_bps'] is not None else "N/A"
            net = f"{res['top_decile_net_bps']:.2f}" if res['top_decile_net_bps'] is not None else "N/A"
            f.write(f"| {res['features']} | {res['auc']:.4f} | {ci_str} | {res['brier']:.4f} | {gross} | {net} |\n")
            
    print(f"\nStage B completed. Report saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python exp_003_feature_discovery.py <horizon> <target>")
        sys.exit(1)
    run_experiment(int(sys.argv[1]), sys.argv[2])
