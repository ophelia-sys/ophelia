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

def run_exp_011(fast=False):
    print("--- Exp 011: Target / Stop Structure ---")
    loader = ResearchDataLoader()
    df = loader.load_symbol('BTCUSDT')
    
    families = ['baseline', 'volatility', 'trend', 'momentum', 'volume']
    df = FeatureGenerator.generate_features(df, families)
    df['interact_volume_vol'] = df['vol_z'] * df['vol_60']
    
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
    top_indices = df_val[df_val['decile'] == 9]['idx'].values
    
    # We will test symmetric and asymmetric barriers
    # Stop is fixed at 10 bps, targets at 10, 20, 30 bps (T1, T2, T3)
    barriers = [
        {'t': 10, 's': 10, 'name': 'T1 (10bps) vs SL (10bps)'},
        {'t': 20, 's': 10, 'name': 'T2 (20bps) vs SL (10bps)'},
        {'t': 30, 's': 10, 'name': 'T3 (30bps) vs SL (10bps)'},
        {'t': 20, 's': 20, 'name': 'T2 (20bps) vs SL (20bps)'}
    ]
    
    results = []
    
    for b in barriers:
        print(f"Evaluating {b['name']}...")
        hits_t = 0
        hits_s = 0
        ambiguous = 0
        expired = 0
        holding_times = []
        
        target_pct = b['t'] / 10000.0
        stop_pct = b['s'] / 10000.0
        max_horizon = 60
        
        for idx in top_indices:
            res, hit_idx = EconomicEngine.evaluate_barriers(
                discovery, idx, target_pct, stop_pct, is_long=True, max_horizon=max_horizon
            )
            
            holding_times.append(hit_idx - idx)
            
            if res == 'TARGET':
                hits_t += 1
            elif res == 'STOP':
                hits_s += 1
            elif res == 'AMBIGUOUS':
                ambiguous += 1
            else:
                expired += 1
                
        total = len(top_indices)
        p_t = hits_t / total * 100
        p_s = hits_s / total * 100
        p_amb = ambiguous / total * 100
        p_exp = expired / total * 100
        
        # Expected return ignoring ambiguous and execution costs for simple expected value
        ev_bps = (p_t/100 * b['t']) - (p_s/100 * b['s'])
        
        results.append({
            'name': b['name'],
            'p_t': p_t,
            'p_s': p_s,
            'p_amb': p_amb,
            'p_exp': p_exp,
            'ev_bps': ev_bps,
            'avg_time': np.mean(holding_times)
        })

    with open('research/EXPERIMENT_011_REPORT.md', 'w') as f:
        f.write("# Exp 011: Target / Stop Structure\n\n")
        f.write("| Barrier | P(Target) % | P(Stop) % | P(Expired) % | P(Ambiguous) % | EV (bps) | Avg Hold (candles) |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['name']} | {r['p_t']:.1f}% | {r['p_s']:.1f}% | {r['p_exp']:.1f}% | {r['p_amb']:.1f}% | {r['ev_bps']:.2f} | {r['avg_time']:.1f} |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()
    run_exp_011(fast=args.fast)
