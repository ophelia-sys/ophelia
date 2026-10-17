import pandas as pd
import numpy as np
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import DataSplitter, PurgedWalkForwardValidation
from research.pipeline.models import get_model
from research.pipeline.economic import EconomicEngine
from research.pipeline.metrics import MetricsEvaluator
import argparse

def run_exp_008(fast=False):
    print("--- Exp 008: Cost Sensitivity ---")
    loader = ResearchDataLoader()
    df = loader.load_symbol('BTCUSDT')
    
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    df = FeatureGenerator.generate_features(df, families)
    df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
    df = LabelGenerator.generate_labels(df, horizons=[60], thresholds_bps=[10])
    features = FeatureGenerator.get_feature_columns(families) + ['interact_volume_vol']
    df.dropna(subset=features + ['target_60_up_10', 'R_60'], inplace=True)
    discovery, _ = DataSplitter.split_discovery_oos(df)
    
    X = discovery[features]
    y = discovery['target_60_up_10']
    R = discovery['R_60']
    
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(X)
    
    oof_preds = np.zeros(len(discovery))
    oof_mask = np.zeros(len(discovery), dtype=bool)
    
    model = get_model('logistic')
    for train_idx, test_idx in splits:
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        oof_preds[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]
        oof_mask[test_idx] = True
        
    y_val = y.iloc[oof_mask]
    preds = oof_preds[oof_mask]
    R_val = R.iloc[oof_mask]
    
    # Calculate deciles for 0 cost to get gross returns
    deciles = MetricsEvaluator.economic_deciles(y_val, preds, R_val, costs_bps=0)
    
    # Extract gross returns by decile
    gross_rets_by_dec = {d['decile']: d['gross_ret_bps'] for d in deciles}
    top_dec_gross = gross_rets_by_dec[9]
    
    costs = [6, 8, 10, 12, 15, 20]
    # For the top decile, calculate net returns at each cost
    curve = {}
    for c in costs:
        curve[c] = top_dec_gross - c
        
    with open('research/EXPERIMENT_008_REPORT.md', 'w') as f:
        f.write("# Exp 008: Cost Sensitivity\n\n")
        f.write(f"**Top Decile Gross Return**: {top_dec_gross:.2f} bps\n\n")
        f.write("| Cost (bps) | Net Return (bps) | Viable |\n")
        f.write("|---|---|---|\n")
        for c in costs:
            net = curve[c]
            viable = "YES" if net > 0 else "NO"
            f.write(f"| {c} | {net:.2f} | {viable} |\n")
            
        f.write(f"\n**Break-Even Cost**: {top_dec_gross:.2f} bps\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_008(fast=args.fast)
