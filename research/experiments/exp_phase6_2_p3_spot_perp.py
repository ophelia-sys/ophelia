import os
import json
import numpy as np
import pandas as pd
import pickle
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.pipeline.models import LightGBMWrapper
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features
from research.experiments.exp_phase5_3_ml_stats import dm_test, block_bootstrap, block_permutation, calculate_logloss
from research.ml4t_benchmark.features.spot_perp import compute_p3_spot_perp_features
from sklearn.metrics import log_loss, brier_score_loss

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h', 
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

P3_FEATS = ['basis_bps', 'basis_zscore_1d', 'basis_change_1h', 
            'spot_perp_return_spread_5m', 'spot_perp_return_spread_15m']

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def main():
    print("--- PHASE 6.2 P3 SPOT/PERP ML EXPERIMENT ---")
    
    baseline_exp = Phase5BaselineExperiment()
    
    # Load canonical SPOT dataset once
    spot_path = os.path.join(BASE_DIR, 'data/processed/research_spot_5m.parquet')
    if not os.path.exists(spot_path):
        raise FileNotFoundError(f"Canonical SPOT data not found at {spot_path}")
    all_spot = pd.read_parquet(spot_path)
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        df_ohlcv = baseline_exp.load_data(symbol)
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        
        # Frozen Target
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        # Extract Spot for this symbol
        df_spot_sym = all_spot[all_spot['symbol'] == symbol].copy()
        
        # Spot features require setting index to T_decision (which corresponds to open_time here?)
        # The benchmark `df` uses `timestamp` as the candle open time. 
        # But wait, T_decision = t + 5m.
        # df_spot_sym['open_time'] is milliseconds epoch.
        # In ophelia, `df['timestamp']` is pandas datetime representing candle open time.
        # We need to make sure index aligns exactly.
        df_spot_sym['timestamp'] = pd.to_datetime(df_spot_sym['open_time'], unit='ms')
        
        # Align indexes
        df = df.set_index('timestamp')
        df_spot_sym = df_spot_sym.set_index('timestamp')
        
        # Engineer P3 Features
        p3_feats = compute_p3_spot_perp_features(df, df_spot_sym)
        df = pd.concat([df, p3_feats], axis=1).reset_index()
        
        df['orig_idx'] = np.arange(len(df))
        
        # Date filter strictly 2022-2023 for validation loop
        valid_df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')].copy()
        
        # Dropna based on all features to ensure STRICT matched sample
        valid_df = valid_df.dropna(subset=BASE_FEATS + CVD_FEATS_G + P3_FEATS + ['target_60_up_10', 'R_60'])
        valid_df = valid_df.reset_index(drop=True)
        
        if len(valid_df) == 0:
            print(f"  Skipping {symbol}: 0 valid samples after merging features.")
            continue
            
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + P3_FEATS
        
        X_base = valid_df[features_base].values
        X_test = valid_df[features_test].values
        
        y = valid_df['target_60_up_10'].values
        R = valid_df['R_60'].values
        timestamps = valid_df['timestamp'].values
        
        cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
        splits = list(cv.split(valid_df))
        
        oof_preds_base = np.zeros(len(valid_df))
        oof_preds_test = np.zeros(len(valid_df))
        oof_mask = np.zeros(len(valid_df), dtype=bool)
        fold_assignment = np.zeros(len(valid_df), dtype=int)
        
        fold_boundaries = []
        
        for f_idx, (train_idx, test_idx) in enumerate(splits):
            fold_boundaries.append({
                'fold': f_idx,
                'train_start': str(timestamps[train_idx[0]]),
                'train_end': str(timestamps[train_idx[-1]]),
                'test_start': str(timestamps[test_idx[0]]),
                'test_end': str(timestamps[test_idx[-1]]),
                'train_samples': len(train_idx),
                'test_samples': len(test_idx),
            })
            
            # Base Model (LightGBM)
            clf_base = LightGBMWrapper()
            clf_base.fit(X_base[train_idx], y[train_idx])
            oof_preds_base[test_idx] = clf_base.predict_proba(X_base[test_idx])[:, 1]
            
            # Test Model (LightGBM + P1)
            clf_test = LightGBMWrapper()
            clf_test.fit(X_test[train_idx], y[train_idx])
            oof_preds_test[test_idx] = clf_test.predict_proba(X_test[test_idx])[:, 1]
            
            oof_mask[test_idx] = True
            fold_assignment[test_idx] = f_idx
            
        y_oof = y[oof_mask]
        p_base_oof = oof_preds_base[oof_mask]
        p_test_oof = oof_preds_test[oof_mask]
        r_oof = R[oof_mask]
        
        # Diagnostics
        ll_base = log_loss(y_oof, p_base_oof)
        ll_test = log_loss(y_oof, p_test_oof)
        bs_base = brier_score_loss(y_oof, p_base_oof)
        bs_test = brier_score_loss(y_oof, p_test_oof)
        
        print(f"  LogLoss | Base: {ll_base:.4f} | Test: {ll_test:.4f} | Diff: {ll_test - ll_base:.4f}")
        print(f"  Brier   | Base: {bs_base:.4f} | Test: {bs_test:.4f} | Diff: {bs_test - bs_base:.4f}")
        
        all_results.append({
            'symbol': symbol,
            'logloss_base': ll_base,
            'logloss_test': ll_test,
            'logloss_diff': ll_test - ll_base,
            'brier_base': bs_base,
            'brier_test': bs_test,
            'brier_diff': bs_test - bs_base,
            'folds': fold_boundaries,
            'total_samples': len(y_oof)
        })
        
        oos_store[symbol] = {
            'y': y_oof,
            'p_base': p_base_oof,
            'p_test': p_test_oof,
            'r': r_oof,
            'timestamps': timestamps[oof_mask],
            'fold_indices': fold_assignment[oof_mask] if 'fold_assignment' in locals() else np.zeros(len(y_oof))
        }
        
        pooled_y.extend(y_oof)
        pooled_p_base.extend(p_base_oof)
        pooled_p_test.extend(p_test_oof)
        pooled_r.extend(r_oof)
        
    print("\n--- POOLED RESULTS ---")
    pooled_y = np.array(pooled_y)
    pooled_p_base = np.array(pooled_p_base)
    pooled_p_test = np.array(pooled_p_test)
    pooled_r = np.array(pooled_r)
    
    ll_base = log_loss(pooled_y, pooled_p_base)
    ll_test = log_loss(pooled_y, pooled_p_test)
    bs_base = brier_score_loss(pooled_y, pooled_p_base)
    bs_test = brier_score_loss(pooled_y, pooled_p_test)
    
    print(f"Pooled LogLoss | Base: {ll_base:.4f} | Test: {ll_test:.4f} | Diff: {ll_test - ll_base:.4f}")
    
    # DM Test
    dm_stat, dm_p = dm_test(pooled_y, pooled_p_base, pooled_p_test, max_lag=59)
    print(f"Diebold-Mariano Test (max_lag=59): Stat={dm_stat:.3f}, p-value={dm_p:.4e}")
    
    # Bootstrap
    loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(pooled_y, pooled_p_base)])
    loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(pooled_y, pooled_p_test)])
    bs_mean, (bs_ci_low, bs_ci_high) = block_bootstrap(loss1, loss2, block_length=60, replications=1000)
    print(f"Bootstrap 95% CI (Test - Base LogLoss): [{bs_ci_low:.4e}, {bs_ci_high:.4e}]")
    
    # Permutation
    perm_p = block_permutation(pooled_y, pooled_p_base, pooled_p_test, block_length=60, iterations=1000)
    print(f"Permutation p-value: {perm_p:.4e}")
    
    # ENR
    costs = [0, 5, 10, 15, 20, 25]
    print("\nEconomic Net Return (ENR) in bps @ 90th percentile")
    print(f"{'Cost (bps)':<15}{'Base ENR':<15}{'Test ENR':<15}{'Diff':<15}")
    for c in costs:
        enr_b = get_enr(pooled_p_base, pooled_r, c)
        enr_t = get_enr(pooled_p_test, pooled_r, c)
        print(f"{c:<15}{enr_b:<15.2f}{enr_t:<15.2f}{enr_t - enr_b:<15.2f}")
        
    out_dir = os.path.join(BASE_DIR, 'research/results')
    os.makedirs(out_dir, exist_ok=True)
    
    with open(os.path.join(out_dir, 'phase6_2_p3_results.json'), 'w') as f:
        json.dump(all_results, f, indent=4)
        
    with open(os.path.join(out_dir, 'phase6_2_p3_oos_preds.pkl'), 'wb') as f:
        pickle.dump(oos_store, f)
        
    print("\nExecution Complete. Results saved to research/results/")

if __name__ == "__main__":
    main()
