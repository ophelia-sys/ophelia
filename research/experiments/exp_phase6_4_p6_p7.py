import os
import json
import numpy as np
import pandas as pd
import pickle
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.pipeline.models import LightGBMWrapper
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features
from research.experiments.exp_phase5_3_ml_stats import dm_test, block_bootstrap, block_permutation, calculate_logloss
from sklearn.metrics import brier_score_loss

from research.ml4t_benchmark.features.p6_funding import engineer_p6_funding_features
from research.ml4t_benchmark.features.p7_volume_acceptance import engineer_p7_volume_acceptance_features

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h', 
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

P6_FEATS = ['funding_rate', 'funding_rate_zscore_1d', 'funding_rate_change_8h', 'funding_price_interaction']
P7_FEATS = ['price_to_vwap_8h', 'price_to_vwap_1d', 'volume_concentration_1d', 'value_area_proxy']

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def run_feature_family(family_name, features_added, baseline_exp):
    print(f"\n=======================================================")
    print(f"--- RUNNING PHASE 6.4 ML EXPERIMENT: {family_name} ---")
    print(f"=======================================================\n")
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        # 1. Base Data
        df_sym = baseline_exp.load_data(symbol)
        df_sym = baseline_exp.engineer_features(df_sym)
        if not pd.api.types.is_datetime64_any_dtype(df_sym['timestamp']):
            df_sym['timestamp'] = pd.to_datetime(df_sym['timestamp'], unit='ms')
            
        # Target
        df_sym = baseline_exp.apply_labels(df_sym, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_sym['R_60'] = df_sym['gross_ret']
        df_sym = LabelGenerator.generate_labels(df_sym, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df_main = engineer_cvd_features(df_sym, df_cvd)
        
        # P6/P7 Features
        if family_name == 'P6':
            df_main = engineer_p6_funding_features(df_main, symbol)
        elif family_name == 'P7':
            df_main = engineer_p7_volume_acceptance_features(df_main)
            
        # Date filter strictly 2022-2023
        valid_df = df_main[(df_main['timestamp'] >= '2022-01-01') & (df_main['timestamp'] < '2024-01-01')].copy()
        
        # Dropna based on ALL features to ensure STRICT identical mask for Base and Test
        valid_df = valid_df.dropna(subset=BASE_FEATS + CVD_FEATS_G + features_added + ['target_60_up_10', 'R_60'])
        valid_df = valid_df.reset_index(drop=True)
        
        if len(valid_df) == 0:
            print(f"  Skipping {symbol}: 0 valid samples after merging features.")
            continue
            
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + features_added
        
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
        
        for f_idx, (train_idx, test_idx) in enumerate(splits):
            # Base Model (LightGBM)
            clf_base = LightGBMWrapper()
            clf_base.fit(X_base[train_idx], y[train_idx])
            oof_preds_base[test_idx] = clf_base.predict_proba(X_base[test_idx])[:, 1]
            
            # Test Model (LightGBM + P6/P7)
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
        
        enrs_base = {str(c): get_enr(p_base_oof, r_oof, c) for c in [0, 5, 10, 15, 20, 25]}
        enrs_test = {str(c): get_enr(p_test_oof, r_oof, c) for c in [0, 5, 10, 15, 20, 25]}
        
        ll_base = calculate_logloss(y_oof, p_base_oof)
        ll_test = calculate_logloss(y_oof, p_test_oof)
        
        brier_base = brier_score_loss(y_oof, p_base_oof)
        brier_test = brier_score_loss(y_oof, p_test_oof)
        
        dm_stat, dm_p = dm_test(y_oof, p_base_oof, p_test_oof, max_lag=59)
        
        loss_base = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_oof, p_base_oof)])
        loss_test = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_oof, p_test_oof)])
        
        bs_mean, bs_ci = block_bootstrap(loss_base, loss_test, block_length=60, replications=1000)
        perm_p = block_permutation(y_oof, p_base_oof, p_test_oof, block_length=60, iterations=1000)
        
        print(f"  Base LL: {ll_base:.5f} | Test LL: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f} | DM p: {dm_p:.4f} | Boot CI: [{bs_ci[0]:.5f}, {bs_ci[1]:.5f}]")
        
        all_results.append({
            'symbol': symbol,
            'samples': len(y_oof),
            'll_base': ll_base,
            'll_test': ll_test,
            'll_diff': ll_base - ll_test,
            'brier_base': brier_base,
            'brier_test': brier_test,
            'brier_diff': brier_base - brier_test,
            'enrs_base': enrs_base,
            'enrs_test': enrs_test,
            'dm_stat': dm_stat,
            'dm_pval': dm_p,
            'bs_mean_diff': bs_mean,
            'bs_ci_lower': bs_ci[0],
            'bs_ci_upper': bs_ci[1],
            'perm_pval': perm_p,
        })
        
    print(f"\n--- POOLED RESULTS ({family_name}) ---")
    pooled_y = np.array(pooled_y)
    pooled_p_base = np.array(pooled_p_base)
    pooled_p_test = np.array(pooled_p_test)
    pooled_r = np.array(pooled_r)
    
    ll_base = calculate_logloss(pooled_y, pooled_p_base)
    ll_test = calculate_logloss(pooled_y, pooled_p_test)
    brier_base = brier_score_loss(pooled_y, pooled_p_base)
    brier_test = brier_score_loss(pooled_y, pooled_p_test)
    
    dm_stat, dm_p = dm_test(pooled_y, pooled_p_base, pooled_p_test, max_lag=59)
    
    print(f"Pooled LL Base: {ll_base:.5f} | Test: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f} | DM p: {dm_p:.4f}")
    
    os.makedirs(os.path.join(BASE_DIR, 'research/results'), exist_ok=True)
    
    output = {
        'symbol_results': all_results,
        'pooled': {
            'll_base': ll_base,
            'll_test': ll_test,
            'll_diff': ll_base - ll_test,
            'brier_base': brier_base,
            'brier_test': brier_test,
            'brier_diff': brier_base - brier_test,
            'dm_stat': dm_stat,
            'dm_pval': dm_p,
            'samples': len(pooled_y)
        }
    }
    
    filename_json = os.path.join(BASE_DIR, f'research/results/phase6_4_{family_name.lower()}_results.json')
    filename_pkl = os.path.join(BASE_DIR, f'research/results/phase6_4_{family_name.lower()}_oos_preds.pkl')
    
    with open(filename_json, 'w') as f:
        json.dump(output, f, indent=2)
        
    with open(filename_pkl, 'wb') as f:
        pickle.dump(oos_store, f)
        
    print(f"Done {family_name}. Results saved to {filename_json} and .pkl")

def main():
    baseline_exp = Phase5BaselineExperiment()
    
    # 1. Run P6 (Funding/Positioning Pressure)
    run_feature_family('P6', P6_FEATS, baseline_exp)
    
    # 2. Run P7 (OHLCV Volume Acceptance Proxies)
    run_feature_family('P7', P7_FEATS, baseline_exp)

if __name__ == "__main__":
    main()
