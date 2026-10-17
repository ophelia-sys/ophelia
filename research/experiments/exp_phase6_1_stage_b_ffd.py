import os
import json
import numpy as np
import pandas as pd
import pickle
from numba import njit
from joblib import Parallel, delayed

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.pipeline.models import LightGBMWrapper
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features
from research.experiments.ml4t.fractional_differencing import get_ffd_weights, apply_ffd
from research.experiments.exp_phase5_3_ml_stats import dm_test, block_bootstrap, block_permutation, calculate_logloss
from sklearn.metrics import log_loss, brier_score_loss

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']

CVD_FEATS_B = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h']
CVD_FEATS_C = ['cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h']
CVD_FEATS_D = ['cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h']
CVD_FEATS_E = ['cvd_acceleration_15m', 'cvd_acceleration_1h']
CVD_FEATS_G = CVD_FEATS_B + CVD_FEATS_C + CVD_FEATS_D + CVD_FEATS_E

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def main():
    print("--- PHASE 6.1 STAGE B FFD ML EXPERIMENT ---")
    
    loader = ResearchDataLoader()
    baseline_exp = Phase5BaselineExperiment()
    
    d_val = 0.55
    threshold = 1e-4
    ffd_weights = get_ffd_weights(d_val, threshold)
    w_len = len(ffd_weights)
    warmup_bars = w_len - 1
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    for symbol in SYMBOLS:
        print(f"Processing {symbol}...")
        df_ohlcv = loader.load_symbol(symbol)
        
        # Base features & Labels
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        # FFD Feature (log close)
        # Handle 0 or negative close safely just in case, though close is > 0
        df['log_close'] = np.log(df['close'].astype(float))
        df['ffd_log_close_d055'] = apply_ffd(df['log_close'].values, ffd_weights)
        
        # Date filter strictly 2022-2023
        df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')]
        
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + ['ffd_log_close_d055']
        
        # Drop NaNs based on TEST features (which includes FFD) so both use identical rows
        valid_df = df.dropna(subset=features_test + ['target_60_up_10', 'R_60'])
        
        X_base = valid_df[features_base].values
        X_test = valid_df[features_test].values
        y = valid_df['target_60_up_10'].values
        R = valid_df['R_60'].values
        timestamps = valid_df['timestamp'].values
        
        # Preflight Check 1: Did we lose any rows inside 2022-2023 due to FFD warmup?
        # df[2022-2023] without FFD
        valid_df_base_only = df.dropna(subset=features_base + ['target_60_up_10', 'R_60'])
        
        if len(valid_df) != len(valid_df_base_only):
            print(f"WARNING: Symbol {symbol} FFD warmup caused OOS sample loss! "
                  f"Base rows: {len(valid_df_base_only)}, FFD rows: {len(valid_df)}")
        else:
            print(f"SUCCESS: {symbol} 167-bar warmup was fully absorbed by pre-2022 padding. Rows: {len(valid_df)}")
            
        cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
        splits = cv.split(valid_df)
        
        oof_preds_base = np.zeros(len(valid_df))
        oof_preds_test = np.zeros(len(valid_df))
        oof_mask = np.zeros(len(valid_df), dtype=bool)
        
        fold_boundaries = []
        
        for f_idx, (train_idx, test_idx) in enumerate(splits):
            fold_boundaries.append({
                'fold': f_idx,
                'train_start': str(timestamps[train_idx[0]]),
                'train_end': str(timestamps[train_idx[-1]]),
                'test_start': str(timestamps[test_idx[0]]),
                'test_end': str(timestamps[test_idx[-1]]),
                'train_samples': len(train_idx),
                'test_samples': len(test_idx)
            })
            
            # Base Model (LightGBM)
            clf_base = LightGBMWrapper()
            clf_base.fit(X_base[train_idx], y[train_idx])
            oof_preds_base[test_idx] = clf_base.predict_proba(X_base[test_idx])[:, 1]
            
            # Test Model (LightGBM + FFD)
            clf_test = LightGBMWrapper()
            clf_test.fit(X_test[train_idx], y[train_idx])
            oof_preds_test[test_idx] = clf_test.predict_proba(X_test[test_idx])[:, 1]
            
            oof_mask[test_idx] = True
            
        y_val = y[oof_mask]
        p_base = oof_preds_base[oof_mask]
        p_test = oof_preds_test[oof_mask]
        R_val = R[oof_mask]
        ts_val = timestamps[oof_mask]
        
        # Preflight Check 2: Match verification
        assert len(y_val) == len(p_base) == len(p_test)
        print(f"SUCCESS: {symbol} Test arrays matched exactly: N = {len(y_val)}")
        
        pooled_y.extend(y_val)
        pooled_p_base.extend(p_base)
        pooled_p_test.extend(p_test)
        pooled_r.extend(R_val)
        
        ll_base = log_loss(y_val, p_base)
        ll_test = log_loss(y_val, p_test)
        
        br_base = brier_score_loss(y_val, p_base)
        br_test = brier_score_loss(y_val, p_test)
        
        dm_t, dm_p = dm_test(y_val, p_base, p_test, max_lag=59)
        perm_pval = block_permutation(y_val, p_base, p_test)
        
        loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_val, p_base)])
        loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_val, p_test)])
        boot_mean, (boot_lo, boot_hi) = block_bootstrap(loss1, loss2)
        
        # 2022/2023 metrics
        mask_2022 = (ts_val >= np.datetime64('2022-01-01')) & (ts_val < np.datetime64('2023-01-01'))
        mask_2023 = (ts_val >= np.datetime64('2023-01-01')) & (ts_val < np.datetime64('2024-01-01'))
        
        ll_base_22 = log_loss(y_val[mask_2022], p_base[mask_2022]) if sum(mask_2022) > 0 else np.nan
        ll_test_22 = log_loss(y_val[mask_2022], p_test[mask_2022]) if sum(mask_2022) > 0 else np.nan
        ll_base_23 = log_loss(y_val[mask_2023], p_base[mask_2023]) if sum(mask_2023) > 0 else np.nan
        ll_test_23 = log_loss(y_val[mask_2023], p_test[mask_2023]) if sum(mask_2023) > 0 else np.nan
        
        enr_base = {c: get_enr(p_base, R_val, c) for c in [0, 5, 10, 15, 20, 25]}
        enr_test = {c: get_enr(p_test, R_val, c) for c in [0, 5, 10, 15, 20, 25]}
        
        all_results.append({
            'symbol': symbol,
            'logloss_base': ll_base,
            'logloss_test': ll_test,
            'brier_base': br_base,
            'brier_test': br_test,
            'dm_tstat': dm_t,
            'dm_pval': dm_p,
            'perm_pval': perm_pval,
            'boot_mean': boot_mean,
            'boot_lo': boot_lo,
            'boot_hi': boot_hi,
            'enr_base': enr_base,
            'enr_test': enr_test,
            'll_base_2022': ll_base_22,
            'll_test_2022': ll_test_22,
            'll_base_2023': ll_base_23,
            'll_test_2023': ll_test_23,
            'samples': len(y_val)
        })
        
        oos_store[symbol] = {
            'ts': ts_val,
            'y': y_val,
            'p_base': p_base,
            'p_test': p_test,
            'R_val': R_val
        }

    df_res = pd.DataFrame(all_results)
    
    # BH correction on DM p-vals
    from statsmodels.stats.multitest import multipletests
    _, bh_pvals, _, _ = multipletests(df_res['dm_pval'], alpha=0.05, method='fdr_bh')
    df_res['bh_qval'] = bh_pvals
    
    # Pooled Metrics
    pool_y = np.array(pooled_y)
    pool_pb = np.array(pooled_p_base)
    pool_pt = np.array(pooled_p_test)
    pool_r = np.array(pooled_r)
    
    pool_ll_base = calculate_logloss(pool_y, pool_pb)
    pool_ll_test = calculate_logloss(pool_y, pool_pt)
    pool_br_base = brier_score_loss(pool_y, pool_pb)
    pool_br_test = brier_score_loss(pool_y, pool_pt)
    pool_dm_t, pool_dm_p = dm_test(pool_y, pool_pb, pool_pt, max_lag=59)
    
    pool_enr_base = {c: get_enr(pool_pb, pool_r, c) for c in [0, 5, 10, 15, 20, 25]}
    pool_enr_test = {c: get_enr(pool_pt, pool_r, c) for c in [0, 5, 10, 15, 20, 25]}
    
    final_json = {
        'pooled': {
            'logloss_base': pool_ll_base,
            'logloss_test': pool_ll_test,
            'brier_base': pool_br_base,
            'brier_test': pool_br_test,
            'dm_tstat': pool_dm_t,
            'dm_pval': pool_dm_p,
            'enr_base': pool_enr_base,
            'enr_test': pool_enr_test,
            'samples': len(pool_y)
        },
        'per_symbol': df_res.to_dict(orient="records")
    }
    
    res_dir = os.path.join(BASE_DIR, 'research/results')
    os.makedirs(res_dir, exist_ok=True)
    with open(os.path.join(res_dir, 'phase6_1_stage_b_ffd_results.json'), 'w') as f:
        json.dump(final_json, f, indent=2)
        
    with open(os.path.join(res_dir, 'phase6_1_stage_b_ffd_oos_preds.pkl'), 'wb') as f:
        pickle.dump(oos_store, f)
        
    print("\nBenchmark Execution Complete. Metrics and OOS predictions saved.")
    
if __name__ == "__main__":
    main()
