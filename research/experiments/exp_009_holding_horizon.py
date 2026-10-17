import pandas as pd
import numpy as np
from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import DataSplitter, PurgedWalkForwardValidation
from research.pipeline.models import get_model
from research.pipeline.metrics import MetricsEvaluator
from research.pipeline.economic import EconomicEngine
import argparse

def run_exp_009(fast=False):
    print("--- Exp 009: Holding Horizon ---")
    loader = ResearchDataLoader()
    df = loader.load_symbol('BTCUSDT')
    
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    df = FeatureGenerator.generate_features(df, families)
    df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
    
    horizons = [1, 3, 6, 12, 24, 48, 60]
    names = ['5m', '15m', '30m', '1h', '2h', '4h', '5h']
    
    # We use up_10 for all to be consistent or just basic directional?
    # User said evaluate horizon, keeping other things constant. We will predict `target_H_up_10`.
    # But wait, 10 bps might be too large for 1 candle (5m). Let's just predict directional R_H > 0 for this experiment,
    # or the standard threshold. Let's use target_H_up_10 to match the locked target structure, though it may be sparse for 5m.
    df = LabelGenerator.generate_labels(df, horizons=horizons, thresholds_bps=[10])
    features = FeatureGenerator.get_feature_columns(families) + ['interact_volume_vol']
    targets = [f'target_{h}_up_10' for h in horizons]
    returns = [f'R_{h}' for h in horizons]
    df.dropna(subset=features + targets + returns, inplace=True)
    discovery, _ = DataSplitter.split_discovery_oos(df)
    X = discovery[features]
    
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(X)
    
    results = []
    
    for h, name in zip(horizons, names):
        print(f"Evaluating {name} (Horizon {h})...")
        target_col = f'target_{h}_up_10'
        y = discovery[target_col]
        R = discovery[f'R_{h}']
        
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
        
        metrics = MetricsEvaluator.evaluate(y_val, preds, R_val, costs_bps=12, fast=fast)
        top_dec = metrics['deciles'][-1]
        
        # Calculate MAE/MFE for top decile
        # We need the indices of the top decile in discovery
        test_indices = np.where(oof_mask)[0]
        # Deciles were calculated on y_val. We need to match.
        df_val = pd.DataFrame({'pred': preds, 'idx': test_indices})
        df_val['decile'] = pd.qcut(df_val['pred'], 10, labels=False, duplicates='drop')
        top_indices = df_val[df_val['decile'] == 9]['idx'].values
        
        mfes = []
        maes = []
        for idx in top_indices:
            mae, mfe = EconomicEngine.calculate_mae_mfe(discovery, idx, idx + h, is_long=True)
            mfes.append(mfe)
            maes.append(mae)
            
        mean_mfe = np.mean(mfes) * 10000.0
        mean_mae = np.mean(maes) * 10000.0
        
        results.append({
            'horizon': name,
            'auc': metrics['auc'],
            'fwd_ret': top_dec['mean_ret_bps'],
            'gross': top_dec['gross_ret_bps'],
            'net': top_dec['net_ret_bps'],
            'mfe': mean_mfe,
            'mae': mean_mae
        })

    with open('research/EXPERIMENT_009_REPORT.md', 'w') as f:
        f.write("# Exp 009: Holding Horizon\n\n")
        f.write("| Horizon | AUC | Fwd Ret (bps) | Gross (bps) | Net (bps) | MFE (bps) | MAE (bps) |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['horizon']} | {r['auc']:.4f} | {r['fwd_ret']:.2f} | {r['gross']:.2f} | {r['net']:.2f} | {r['mfe']:.2f} | {r['mae']:.2f} |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_009(fast=args.fast)
