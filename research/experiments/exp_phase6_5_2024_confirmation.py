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
from research.experiments.exp_phase5_3_ml_ablation import engineer_cvd_features
from research.experiments.exp_phase5_3_ml_stats import calculate_logloss
from sklearn.metrics import brier_score_loss
from research.phase6.statistics_frozen import dm_test, block_bootstrap, block_permutation
from statsmodels.stats.multitest import multipletests

from research.ml4t_benchmark.features.p7_volume_acceptance import engineer_p7_volume_acceptance_features

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
V2_DIR = os.path.join(BASE_DIR, 'data/normalized/v2')
CVD_DIR = os.path.join(BASE_DIR, 'research/data/normalized/cvd/5m')
P4_DIR = os.path.join(BASE_DIR, 'research/data/normalized/p4')

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h', 
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

P4_FEATS = ['large_trade_imbalance', 'large_trade_share', 'trade_size_zscore', 'trade_size_concentration']
P7_FEATS = ['price_to_vwap_8h', 'price_to_vwap_1d', 'volume_concentration_1d', 'value_area_proxy']

def load_cvd_symbol(symbol):
    dfs = []
    # Load 2022-2024
    for year in [2022, 2023, 2024]:
        for month in range(1, 13):
            path = os.path.join(CVD_DIR, f"{symbol}-{year}-{month:02d}.parquet")
            if os.path.exists(path):
                dfs.append(pd.read_parquet(path))
    if len(dfs) == 0:
        return pd.DataFrame(columns=['minute', 'delta_volume', 'buy_volume', 'sell_volume'])
    df = pd.concat(dfs, ignore_index=True)
    df.sort_values('minute', inplace=True)
    return df

def get_enr(preds, r_val, cost):
    if len(preds) == 0:
        return 0.0
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def run_confirmation_experiment(experiment_name, features_added, model_name):
    print(f"\n=======================================================")
    print(f"--- RUNNING PHASE 6.5 CONFIRMATION: {experiment_name} ---")
    print(f"=======================================================\n")
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    baseline_exp = Phase5BaselineExperiment()
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        
        # 1. Load Data (2022-2023 + 2024)
        v2_path_old = os.path.join(V2_DIR, f"binance_um_{symbol.lower()}_5m_v2.parquet")
        v2_path_2024 = os.path.join(V2_DIR, f"binance_um_{symbol.lower()}_5m_2024.parquet")
        
        df_old = pd.read_parquet(v2_path_old) if os.path.exists(v2_path_old) else pd.DataFrame()
        df_2024 = pd.read_parquet(v2_path_2024) if os.path.exists(v2_path_2024) else pd.DataFrame()
        
        df_sym = pd.concat([df_old, df_2024], ignore_index=True)
        df_sym = df_sym.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        
        if not pd.api.types.is_datetime64_any_dtype(df_sym['timestamp']):
            df_sym['timestamp'] = pd.to_datetime(df_sym['timestamp'], unit='ms')
            
        df_sym = baseline_exp.engineer_features(df_sym)
        
        # Target
        df_sym = baseline_exp.apply_labels(df_sym, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_sym['R_60'] = df_sym['gross_ret']
        df_sym = LabelGenerator.generate_labels(df_sym, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df_main = engineer_cvd_features(df_sym, df_cvd)
        
        # Experiment specific features
        if model_name == 'P4':
            p4_path = os.path.join(P4_DIR, f"{symbol}_p4_features.parquet")
            if not os.path.exists(p4_path):
                print(f"  [ERROR] P4 features not found for {symbol}")
                continue
            df_p4 = pd.read_parquet(p4_path)
            if not pd.api.types.is_datetime64_any_dtype(df_p4['timestamp']):
                df_p4['timestamp'] = pd.to_datetime(df_p4['timestamp'], unit='ms')
            
            df_p4 = df_p4[['timestamp'] + P4_FEATS]
            df_main = pd.merge(df_main, df_p4, on='timestamp', how='left')
            
        elif model_name == 'P7':
            df_main = engineer_p7_volume_acceptance_features(df_main)
            
        # Split into Train and Test
        # Train: 2022-01-01 to 2023-12-31 (exactly < 2024-01-01)
        # Test: 2024-01-01 to 2024-12-31 (strictly < 2025-01-01)
        # Any signal generated >= 2025-01-01 is explicitly discarded.
        
        train_df = df_main[(df_main['timestamp'] >= '2022-01-01') & (df_main['timestamp'] < '2024-01-01')].copy()
        test_df = df_main[(df_main['timestamp'] >= '2024-01-01') & (df_main['timestamp'] < '2025-01-01')].copy()
        
        # Dropna based on ALL features to ensure STRICT identical mask for Base and Test
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + features_added
        all_required = features_test + ['target_60_up_10', 'R_60']
        
        train_df = train_df.dropna(subset=all_required).reset_index(drop=True)
        test_df = test_df.dropna(subset=all_required).reset_index(drop=True)
        
        if len(train_df) == 0 or len(test_df) == 0:
            print(f"  Skipping {symbol}: 0 valid samples in Train or Test.")
            continue
            
        X_train_base = train_df[features_base].values
        X_train_test = train_df[features_test].values
        y_train = train_df['target_60_up_10'].values
        
        X_test_base = test_df[features_base].values
        X_test_test = test_df[features_test].values
        y_test = test_df['target_60_up_10'].values
        r_test = test_df['R_60'].values
        ts_test = test_df['timestamp'].values
        
        # Base Model (LightGBM)
        clf_base = LightGBMWrapper()
        clf_base.fit(X_train_base, y_train)
        p_base_test = clf_base.predict_proba(X_test_base)[:, 1]
        
        # Test Model (LightGBM + P4/P7)
        clf_test = LightGBMWrapper()
        clf_test.fit(X_train_test, y_train)
        p_test_test = clf_test.predict_proba(X_test_test)[:, 1]
        
        pooled_y.extend(y_test)
        pooled_p_base.extend(p_base_test)
        pooled_p_test.extend(p_test_test)
        pooled_r.extend(r_test)
        
        oos_store[symbol] = {
            'y': y_test,
            'p_base': p_base_test,
            'p_test': p_test_test,
            'r': r_test,
            'ts': ts_test
        }
        
        enrs_base = {str(c): get_enr(p_base_test, r_test, c) for c in [0, 5, 10, 15, 20, 25]}
        enrs_test = {str(c): get_enr(p_test_test, r_test, c) for c in [0, 5, 10, 15, 20, 25]}
        
        ll_base = calculate_logloss(y_test, p_base_test)
        ll_test = calculate_logloss(y_test, p_test_test)
        
        brier_base = brier_score_loss(y_test, p_base_test)
        brier_test = brier_score_loss(y_test, p_test_test)
        
        # Frozen Statistical Framework
        loss_base = -(y_test * np.log(np.clip(p_base_test, 1e-15, 1 - 1e-15)) + (1 - y_test) * np.log(np.clip(1 - p_base_test, 1e-15, 1 - 1e-15)))
        loss_test = -(y_test * np.log(np.clip(p_test_test, 1e-15, 1 - 1e-15)) + (1 - y_test) * np.log(np.clip(1 - p_test_test, 1e-15, 1 - 1e-15)))
        
        dm_t, dm_p = dm_test(y_test, p_base_test, p_test_test)
        boot_mean, boot_ci = block_bootstrap(loss_base, loss_test)
        boot_std = 0.0
        perm_p = block_permutation(y_test, p_base_test, p_test_test)
        
        print(f"  Base LL: {ll_base:.5f} | Test LL: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f}")
        print(f"  DM t-stat: {dm_t:.4f} (p={dm_p:.4e}) | Boot Mean Diff: {boot_mean:.6f} | Perm p-val: {perm_p:.4f}")
        
        all_results.append({
            'symbol': symbol,
            'samples_train': len(y_train),
            'samples_test': len(y_test),
            'll_base': ll_base,
            'll_test': ll_test,
            'll_diff': ll_base - ll_test,
            'brier_base': brier_base,
            'brier_test': brier_test,
            'brier_diff': brier_base - brier_test,
            'enrs_base': enrs_base,
            'enrs_test': enrs_test,
            'dm_t': dm_t,
            'dm_p': dm_p,
            'boot_mean': boot_mean,
            'boot_std': boot_std,
            'boot_ci_lower': boot_ci[0],
            'boot_ci_upper': boot_ci[1],
            'perm_p': perm_p
        })
        
    print(f"\n--- POOLED RESULTS ({model_name} 2024 CONFIRMATION) ---")
    
    # Calculate BH-FDR across all symbol DM p-values
    p_vals = [res['dm_p'] for res in all_results]
    if len(p_vals) > 0:
        _, bh_p_vals, _, _ = multipletests(p_vals, alpha=0.05, method='fdr_bh')
        for idx, res in enumerate(all_results):
            res['bh_fdr'] = bh_p_vals[idx]
    
    pooled_y = np.array(pooled_y)
    pooled_p_base = np.array(pooled_p_base)
    pooled_p_test = np.array(pooled_p_test)
    pooled_r = np.array(pooled_r)
    
    if len(pooled_y) > 0:
        ll_base = calculate_logloss(pooled_y, pooled_p_base)
        ll_test = calculate_logloss(pooled_y, pooled_p_test)
        brier_base = brier_score_loss(pooled_y, pooled_p_base)
        brier_test = brier_score_loss(pooled_y, pooled_p_test)
        
        enrs_base = {str(c): get_enr(pooled_p_base, pooled_r, c) for c in [0, 5, 10, 15, 20, 25]}
        enrs_test = {str(c): get_enr(pooled_p_test, pooled_r, c) for c in [0, 5, 10, 15, 20, 25]}
        
        loss_base_pooled = -(pooled_y * np.log(np.clip(pooled_p_base, 1e-15, 1 - 1e-15)) + (1 - pooled_y) * np.log(np.clip(1 - pooled_p_base, 1e-15, 1 - 1e-15)))
        loss_test_pooled = -(pooled_y * np.log(np.clip(pooled_p_test, 1e-15, 1 - 1e-15)) + (1 - pooled_y) * np.log(np.clip(1 - pooled_p_test, 1e-15, 1 - 1e-15)))
        
        dm_t_pooled, dm_p_pooled = dm_test(pooled_y, pooled_p_base, pooled_p_test)
        boot_mean_p, boot_ci_p = block_bootstrap(loss_base_pooled, loss_test_pooled)
        boot_std_p = 0.0
        perm_p_pooled = block_permutation(pooled_y, pooled_p_base, pooled_p_test)
        
        print(f"Pooled LL Base: {ll_base:.5f} | Test: {ll_test:.5f} | Diff: {ll_base - ll_test:.5f}")
        print(f"Pooled DM t-stat: {dm_t_pooled:.4f} (p={dm_p_pooled:.4e})")
    else:
        ll_base = ll_test = brier_base = brier_test = 0.0
        enrs_base = enrs_test = {}
        dm_t_pooled = dm_p_pooled = boot_mean_p = boot_std_p = perm_p_pooled = 0.0
        boot_ci_p = (0.0, 0.0)
        print("No valid samples across all symbols.")
        
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
            'enrs_base': enrs_base,
            'enrs_test': enrs_test,
            'dm_t': dm_t_pooled,
            'dm_p': dm_p_pooled,
            'boot_mean': boot_mean_p,
            'boot_std': boot_std_p,
            'boot_ci_lower': boot_ci_p[0],
            'boot_ci_upper': boot_ci_p[1],
            'perm_p': perm_p_pooled,
            'samples': len(pooled_y)
        }
    }
    
    filename_json = os.path.join(BASE_DIR, f'research/results/phase6_5_{model_name.lower()}_2024_results.json')
    filename_pkl = os.path.join(BASE_DIR, f'research/results/phase6_5_{model_name.lower()}_2024_oos_preds.pkl')
    
    with open(filename_json, 'w') as f:
        json.dump(output, f, indent=2)
        
    with open(filename_pkl, 'wb') as f:
        pickle.dump(oos_store, f)
        
    print(f"Done {model_name}. Results saved.")

def main():
    # Run P4
    run_confirmation_experiment('Experiment A (P4)', P4_FEATS, 'P4')
    
    # Run P7
    run_confirmation_experiment('Experiment B (P7)', P7_FEATS, 'P7')

if __name__ == "__main__":
    main()
