import pandas as pd
import numpy as np
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import DataSplitter, PurgedWalkForwardValidation
from research.pipeline.models import get_model
from research.pipeline.metrics import MetricsEvaluator
import argparse
import os

def run_exp_013(fast=False):
    print("--- Exp 013: Cross-Asset Validation ---")
    
    assets = ['ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']
    
    # Data Quality Matrix
    quality = []
    
    loader = ResearchDataLoader()
    
    for a in assets:
        df = loader.load_symbol(a)
        n_rows = len(df)
        nulls = df.isnull().sum().sum()
        min_date = pd.to_datetime(df['timestamp'].min(), unit='ms')
        max_date = pd.to_datetime(df['timestamp'].max(), unit='ms')
        schema_ok = all(c in df.columns for c in ['open', 'high', 'low', 'close', 'volume'])
        quality.append({
            'asset': a,
            'rows': n_rows,
            'nulls': nulls,
            'start': min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else 'N/A',
            'end': max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else 'N/A',
            'schema': schema_ok
        })
        
    print("Data Quality Matrix Checked.")
    
    results = []
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    features = FeatureGenerator.get_feature_columns(families) + ['interact_volume_vol']
    
    for a in assets:
        print(f"Evaluating {a}...")
        df = loader.load_symbol(a)
        
        df = FeatureGenerator.generate_features(df, families)
        df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
        df = LabelGenerator.generate_labels(df, horizons=[60], thresholds_bps=[10])
        df.dropna(subset=features + ['target_60_up_10', 'R_60'], inplace=True)
        discovery, _ = DataSplitter.split_discovery_oos(df)
        
        X = discovery[features]
        y = discovery['target_60_up_10']
        R = discovery['R_60']
        
        cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
        splits = cv.split(X)
        
        model = get_model('logistic')
        aucs, gross_rets = [], []
        
        for train_idx, test_idx in splits:
            X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
            X_te, y_te, R_te = X.iloc[test_idx], y.iloc[test_idx], R.iloc[test_idx]
            
            model.fit(X_tr, y_tr)
            preds = model.predict_proba(X_te)[:, 1]
            
            metrics = MetricsEvaluator.evaluate(y_te, preds, R_te, fast=fast)
            aucs.append(metrics['auc'])
            gross_rets.append(metrics['deciles'][-1]['gross_ret_bps'])
            
        mean_auc = np.mean(aucs)
        mean_gross = np.mean(gross_rets)
        net_ret = mean_gross - 12.0
        
        classification = "UNIVERSAL" if mean_auc > 0.52 and net_ret > 0 else "NON_TRANSFERABLE" if mean_auc < 0.51 else "ASSET_SPECIFIC"
        
        results.append({
            'asset': a,
            'auc': mean_auc,
            'gross': mean_gross,
            'net': net_ret,
            'classification': classification
        })

    with open('research/EXPERIMENT_013_REPORT.md', 'w') as f:
        f.write("# Exp 013: Cross-Asset Validation\n\n")
        f.write("## Data Quality Matrix\n")
        f.write("| Asset | Rows | Nulls | Start | End | Schema OK |\n")
        f.write("|---|---|---|---|---|---|\n")
        for q in quality:
            f.write(f"| {q['asset']} | {q['rows']} | {q['nulls']} | {q['start']} | {q['end']} | {q['schema']} |\n")
            
        f.write("\n## Evaluation\n")
        f.write("| Asset | AUC | Gross (bps) | Net (bps) | Classification |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['asset']} | {r['auc']:.4f} | {r['gross']:.2f} | {r['net']:.2f} | {r['classification']} |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_013(fast=args.fast)
