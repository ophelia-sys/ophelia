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

def run_exp_010(fast=False):
    print("--- Exp 010: Entry Timing ---")
    loader = ResearchDataLoader()
    df = loader.load_symbol('BTCUSDT')
    
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    df = FeatureGenerator.generate_features(df, families)
    df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
    
    # We evaluate entry timing for the locked horizon (60)
    df = LabelGenerator.generate_labels(df, horizons=[60], thresholds_bps=[10])
    features = FeatureGenerator.get_feature_columns(families) + ['interact_volume_vol']
    df.dropna(subset=features + ['target_60_up_10', 'R_60', 'close', 'high', 'low'], inplace=True)
    discovery, _ = DataSplitter.split_discovery_oos(df)
    X = discovery[features]
    y = discovery['target_60_up_10']
    
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(X)
    
    oof_preds = np.zeros(len(discovery))
    oof_mask = np.zeros(len(discovery), dtype=bool)
    
    model = get_model('logistic')
    for train_idx, test_idx in splits:
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        oof_preds[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]
        oof_mask[test_idx] = True
        
    test_indices = np.where(oof_mask)[0]
    df_val = pd.DataFrame({'pred': oof_preds[oof_mask], 'idx': test_indices})
    df_val['decile'] = pd.qcut(df_val['pred'], 10, labels=False, duplicates='drop')
    
    # Top decile long signals
    top_indices = df_val[df_val['decile'] == 9]['idx'].values
    
    results = []
    
    methods = [
        {'name': 'Immediate', 'type': 'market', 'delay': 0},
        {'name': 'Delay 1', 'type': 'market', 'delay': 1},
        {'name': 'Delay 2', 'type': 'market', 'delay': 2},
        {'name': 'Delay 3', 'type': 'market', 'delay': 3},
        {'name': 'Pullback 5bps (3c)', 'type': 'pullback', 'limit_bps': 5, 'wait': 3},
        {'name': 'Pullback 10bps (3c)', 'type': 'pullback', 'limit_bps': 10, 'wait': 3}
    ]
    
    horizon = 60
    
    for m in methods:
        print(f"Evaluating {m['name']}...")
        fills = 0
        missed = 0
        ambiguous = 0 # Currently handled by conservative logic in simulate_pullback_entry
        gross_rets = []
        maes, mfes = [], []
        
        for idx in top_indices:
            signal_price = discovery['close'].iloc[idx]
            
            if m['type'] == 'market':
                entry_idx, entry_price = EconomicEngine.simulate_entry(discovery, idx, delay_candles=m['delay'], is_long=True)
                if entry_idx is not None:
                    fills += 1
            elif m['type'] == 'pullback':
                limit_price = signal_price * (1 - m['limit_bps']/10000.0)
                entry_idx, entry_price, is_missed = EconomicEngine.simulate_pullback_entry(
                    discovery, idx, limit_price, max_wait=m['wait'], is_long=True
                )
                if is_missed:
                    missed += 1
                    continue
                else:
                    fills += 1
                    
            if entry_idx is not None:
                exit_idx = entry_idx + horizon
                if exit_idx < len(discovery):
                    exit_price = discovery['close'].iloc[exit_idx]
                    ret = (exit_price / entry_price) - 1.0
                    gross_rets.append(ret)
                    
                    mae, mfe = EconomicEngine.calculate_mae_mfe(discovery, entry_idx, exit_idx, is_long=True)
                    maes.append(mae)
                    mfes.append(mfe)
                    
        gross_bps = np.mean(gross_rets) * 10000.0 if len(gross_rets) > 0 else 0
        net_bps = gross_bps - 12.0 # Fixed 12 bps assumption
        
        results.append({
            'name': m['name'],
            'fill_rate': fills / len(top_indices) * 100,
            'missed': missed / len(top_indices) * 100,
            'gross': gross_bps,
            'net': net_bps,
            'mae': np.mean(maes) * 10000.0 if len(maes) > 0 else 0,
            'mfe': np.mean(mfes) * 10000.0 if len(mfes) > 0 else 0
        })

    with open('research/EXPERIMENT_010_REPORT.md', 'w') as f:
        f.write("# Exp 010: Entry Timing\n\n")
        f.write("| Method | Fill % | Missed % | Gross (bps) | Net (bps) | MAE (bps) | MFE (bps) |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['name']} | {r['fill_rate']:.1f}% | {r['missed']:.1f}% | {r['gross']:.2f} | {r['net']:.2f} | {r['mae']:.2f} | {r['mfe']:.2f} |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_010(fast=args.fast)
