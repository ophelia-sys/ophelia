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
from research.experiments.exp_004_interactions import generate_interaction_features

def run_experiment(horizon: int, target: str, features: list, interactions: list, model_name: str):
    print(f"--- Stage G: Locked OOS Evaluation ---")
    
    loader = ResearchDataLoader()
    df = loader.load_symbol("BTCUSDT")
    
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['dt'].dt.year >= 2022].copy()
    
    # WE ARE NOW EVALUATING ON THE LOCKED OOS SPLIT
    discovery_df, oos_df = DataSplitter.split_discovery_oos(df, split_date_str="2023-09-01")
    
    thresholds_bps = [10, 15, 20]
    
    # 1. Train on the entire Discovery set
    print("Training on full Discovery Set...")
    discovery_df = LabelGenerator.generate_labels(discovery_df, horizons=[horizon], thresholds_bps=thresholds_bps)
    discovery_df = FeatureGenerator.generate_features(discovery_df, ['baseline', 'volatility', 'trend', 'momentum', 'volume'])
    discovery_df = generate_interaction_features(discovery_df)
    
    base_cols = FeatureGenerator.get_feature_columns(features)
    current_cols = base_cols + interactions
    current_cols = [c for c in current_cols if c in discovery_df.columns]
    
    fwd_return_col = f'R_{horizon}'
    valid_cols = current_cols + [target, fwd_return_col]
    clean_discovery_df = discovery_df.dropna(subset=valid_cols).reset_index(drop=True)
    
    X_train = clean_discovery_df[current_cols]
    y_train = clean_discovery_df[target]
    
    model = get_model(model_name)
    model.fit(X_train, y_train)
    
    # 2. Evaluate on the Locked OOS set
    print("Evaluating on Locked OOS Set...")
    oos_df = LabelGenerator.generate_labels(oos_df, horizons=[horizon], thresholds_bps=thresholds_bps)
    oos_df = FeatureGenerator.generate_features(oos_df, ['baseline', 'volatility', 'trend', 'momentum', 'volume'])
    oos_df = generate_interaction_features(oos_df)
    
    clean_oos_df = oos_df.dropna(subset=valid_cols).reset_index(drop=True)
    
    X_test = clean_oos_df[current_cols]
    y_test = clean_oos_df[target]
    R_test = clean_oos_df[fwd_return_col]
    
    preds = model.predict_proba(X_test)[:, 1]
    
    metrics = MetricsEvaluator.evaluate(y_test.values, preds, R_test.values, costs_bps=12)
    
    output_path = os.path.join("research", "EXPERIMENT_006_LOCKED_OOS_REPORT.md")
    with open(output_path, "w") as f:
        f.write("# STAGE G: Locked OOS Evaluation (Exp 006)\n\n")
        f.write(f"**Locked Config**: Target={target} | Horizon={horizon} | Features={features} | Interactions={interactions} | Model={model_name}\n\n")
        f.write("## Strict Final OOS Results\n\n")
        
        ci_str = f"[{metrics['ci'][0]:.4f}, {metrics['ci'][1]:.4f}]"
        gross = f"{metrics['deciles'][-1]['gross_ret_bps']:.2f}" if metrics['deciles'] else "N/A"
        net = f"{metrics['deciles'][-1]['net_ret_bps']:.2f}" if metrics['deciles'] else "N/A"
        
        f.write(f"- **AUC**: {metrics['auc']:.4f}\n")
        f.write(f"- **95% CI**: {ci_str}\n")
        f.write(f"- **Brier Score**: {metrics['brier']:.4f}\n")
        f.write(f"- **Top Decile Gross (bps)**: {gross}\n")
        f.write(f"- **Top Decile Net (bps)**: {net}\n")
        
    print(f"\nStage G completed. Report saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python exp_006_locked_oos.py <horizon> <target> <features_csv> <interactions_csv> <model_name>")
        sys.exit(1)
    
    h = int(sys.argv[1])
    t = sys.argv[2]
    f_list = sys.argv[3].split(',')
    i_list = sys.argv[4].split(',') if sys.argv[4] else []
    m_name = sys.argv[5]
    run_experiment(h, t, f_list, i_list, m_name)
