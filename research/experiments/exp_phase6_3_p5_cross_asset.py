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
from research.ml4t_benchmark.features.cross_asset import generate_p5_features
from sklearn.metrics import log_loss, brier_score_loss

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h', 
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

P5_FEATS = ['primary_lead_return_5m', 'primary_lead_return_15m', 'primary_lead_return_30m', 
            'cross_asset_median_return_5m', 'cross_asset_median_return_15m',
            'cross_asset_dispersion_15m', 'target_relative_strength_to_primary_15m']

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def main():
    print("--- PHASE 6.3 P5 CROSS-ASSET ML EXPERIMENT ---")
    
    baseline_exp = Phase5BaselineExperiment()
    
    # Load all Futures OHLCV upfront for P5
    universe_dfs = {}
    print("Loading universe data...")
    for symbol in SYMBOLS:
        df_sym = baseline_exp.load_data(symbol)
        df_sym = baseline_exp.engineer_features(df_sym)
        # Ensure timestamp is datetime for proper alignment later
        if not pd.api.types.is_datetime64_any_dtype(df_sym['timestamp']):
            df_sym['timestamp'] = pd.to_datetime(df_sym['timestamp'], unit='ms')
        universe_dfs[symbol] = df_sym
        
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        df_ohlcv = universe_dfs[symbol].copy()
        
        # Frozen Target
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        # Engineer P5 Features
        p5_feats_df = generate_p5_features(symbol, universe_dfs)
        
        # Ensure timestamp alignment before merge
        # generate_p5_features returns a DataFrame with the exact same length/timestamps as universe_dfs[symbol]
        assert len(p5_feats_df) == len(df), "Length mismatch in P5 features"
        np.testing.assert_array_equal(p5_feats_df['timestamp'].values, df['timestamp'].values)
        
        df = pd.concat([df, p5_feats_df.drop(columns=['timestamp'])], axis=1)
        
        # Date filter strictly 2022-2023 for validation loop
        valid_df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')].copy()
        
        # Dropna based on all features to ensure STRICT matched sample
        valid_df = valid_df.dropna(subset=BASE_FEATS + CVD_FEATS_G + P5_FEATS + ['target_60_up_10', 'R_60'])
        valid_df = valid_df.reset_index(drop=True)
        
        if len(valid_df) == 0:
            print(f"  Skipping {symbol}: 0 valid samples after merging features.")
            continue
            
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + P5_FEATS
        
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
            
            # Test Model (LightGBM + P5)
            clf_test = LightGBMWrapper()
            clf_test.fit(X_test[train_idx], y[train_idx])
            oof_preds_test[test_idx] = clf_test.predict_proba(X_test[test_idx])[:, 1]
            
            oof_mask[test_idx] = True
            fold_assignment[test_idx] = f_idx
            
        y_oof = y[oof_mask]
        p_base_oof = oof_preds_base[oof_mask]
        p_test_oof = oof_preds_test[oof_mask]
        r_oof = R[oof_mask]
        ts_oof = timestamps[oof_mask]
        folds_oof = fold_assignment[oof_mask]
        
        pooled_y.extend(y_oof)
        pooled_p_base.extend(p_base_oof)
        pooled_p_test.extend(p_test_oof)
        pooled_r.extend(r_oof)
        
        oos_store[symbol] = {
            'y': y_oof,
            'p_base': p_base_oof,
            'p_test': p_test_oof,
            'r': r_oof,
            'ts': ts_oof,
            'fold': folds_oof
        }
        
        # Calculate ENR metrics
        base_enr_0 = get_enr(p_base_oof, r_oof, 0)
        base_enr_5 = get_enr(p_base_oof, r_oof, 5)
        test_enr_0 = get_enr(p_test_oof, r_oof, 0)
        test_enr_5 = get_enr(p_test_oof, r_oof, 5)
        
        ll_base = calculate_logloss(y_oof, p_base_oof)
        ll_test = calculate_logloss(y_oof, p_test_oof)
        
        brier_base = brier_score_loss(y_oof, p_base_oof)
        brier_test = brier_score_loss(y_oof, p_test_oof)
        
        dm_stat, dm_p = dm_test(y_oof, p_base_oof, p_test_oof, max_lag=59)
        
        loss_base = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_oof, p_base_oof)])
        loss_test = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_oof, p_test_oof)])
        
        bs_mean, bs_ci = block_bootstrap(loss_base, loss_test, block_length=60, replications=1000)
        perm_p = block_permutation(y_oof, p_base_oof, p_test_oof, block_length=60, iterations=1000)
        bs_p = np.nan
        
        print(f"  Valid OOS Samples: {len(y_oof)}")
        print(f"  Base LL: {ll_base:.5f} | Test LL: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f}")
        print(f"  Base ENR(0): {base_enr_0:.2f}bps | Test ENR(0): {test_enr_0:.2f}bps")
        print(f"  Base ENR(5): {base_enr_5:.2f}bps | Test ENR(5): {test_enr_5:.2f}bps")
        print(f"  DM p-val: {dm_p:.4f} | Bootstrap p-val: {bs_p:.4f} | Perm p-val: {perm_p:.4f}")
        
        all_results.append({
            'symbol': symbol,
            'samples': len(y_oof),
            'll_base': ll_base,
            'll_test': ll_test,
            'll_diff': ll_base - ll_test,
            'brier_base': brier_base,
            'brier_test': brier_test,
            'brier_diff': brier_base - brier_test,
            'base_enr_0': base_enr_0,
            'base_enr_5': base_enr_5,
            'test_enr_0': test_enr_0,
            'test_enr_5': test_enr_5,
            'dm_stat': dm_stat,
            'dm_pval': dm_p,
            'bs_mean_diff': bs_mean,
            'bs_ci_lower': bs_ci[0],
            'bs_ci_upper': bs_ci[1],
            'bs_pval': bs_p,
            'perm_pval': perm_p,
            'fold_boundaries': fold_boundaries
        })
        
    print("\n--- POOLED RESULTS ---")
    pooled_y = np.array(pooled_y)
    pooled_p_base = np.array(pooled_p_base)
    pooled_p_test = np.array(pooled_p_test)
    pooled_r = np.array(pooled_r)
    
    ll_base = calculate_logloss(pooled_y, pooled_p_base)
    ll_test = calculate_logloss(pooled_y, pooled_p_test)
    brier_base = brier_score_loss(pooled_y, pooled_p_base)
    brier_test = brier_score_loss(pooled_y, pooled_p_test)
    
    dm_stat, dm_p = dm_test(pooled_y, pooled_p_base, pooled_p_test, max_lag=59)
    
    print(f"Pooled LL Base: {ll_base:.5f} | Test: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f}")
    print(f"Pooled Brier Base: {brier_base:.5f} | Test: {brier_test:.5f} | Diff: {brier_base - brier_test:.5f}")
    print(f"Pooled DM p-val: {dm_p:.4f}")
    
    os.makedirs(os.path.join(BASE_DIR, 'research/results'), exist_ok=True)
    
    with open(os.path.join(BASE_DIR, 'research/results/phase6_3_p5_cross_asset_results.json'), 'w') as f:
        json.dump(all_results, f, indent=2)
        
    with open(os.path.join(BASE_DIR, 'research/results/phase6_3_p5_cross_asset_oos_preds.pkl'), 'wb') as f:
        pickle.dump(oos_store, f)
        
    print("Done. Results saved to research/results/phase6_3_p5_cross_asset_results.json and .pkl")

if __name__ == "__main__":
    main()
